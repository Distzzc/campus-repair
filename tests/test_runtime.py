"""R01/R04/R05: real process lifecycle, data restore and failure blocking."""
from contextlib import closing
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from conftest import ROOT


def test_R01_R04_real_server_health_fault_recovery_and_graceful_shutdown(settings, tmp_path):
    env_file = tmp_path / '.env'
    # No shell expansion is used. Dotenv is loaded explicitly in a child process.
    env_file.write_text('\n'.join(f'{key}={value}' for key, value in settings.items()))
    python_bin = Path(sys.executable).parent
    initialized = subprocess.run([str(python_bin / 'dotenv'), '-f', str(env_file), 'run', '--',
                                  sys.executable, '-m', 'flask', '--app', 'campus_repair.cli:create_cli_app', 'init-db'],
                                 cwd=ROOT, capture_output=True, text=True)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    address = f'http://127.0.0.1:{port}/health'
    logfile = tmp_path / 'server-output.txt'
    with logfile.open('w') as stream:
        process = subprocess.Popen([str(python_bin / 'dotenv'), '-f', str(env_file), 'run', '--',
                                    sys.executable, '-m', 'gunicorn', '--bind', f'127.0.0.1:{port}', 'wsgi:app'],
                                   cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 10
            while True:
                try:
                    with urlopen(address, timeout=1) as response:
                        assert response.status == 200
                        body = json.load(response)
                        assert body['request_id'] == response.headers['X-Request-ID']
                    break
                except (URLError, ConnectionError):
                    assert time.monotonic() < deadline and process.poll() is None
                    time.sleep(0.05)
            path = Path(settings['DATABASE_PATH'])
            moved = path.with_suffix('.moved')
            path.rename(moved)
            try:
                urlopen(address, timeout=2)
                raise AssertionError('Expected dependency failure')
            except HTTPError as response:
                assert response.code == 503
                assert json.load(response)['error']['code'] == 'DEPENDENCY_UNAVAILABLE'
            moved.rename(path)
            with urlopen(address, timeout=2) as response:
                assert response.status == 200
        finally:
            started = time.monotonic()
            process.terminate()
            try:
                exit_code = process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise
    assert exit_code == 0 and time.monotonic() - started < 15
    records = [json.loads(line) for line in logfile.read_text().splitlines()]
    assert any(record['event'] == 'shutdown' for record in records)
    requests = [record for record in records if record['event'] == 'request_completed']
    assert [record['status_code'] for record in requests] == [200, 503, 200]


def test_R04_backup_restore_preserves_data_and_refuses_overwrite(settings, tmp_path):
    source = Path(settings['DATABASE_PATH'])
    with sqlite3.connect(source) as connection:
        connection.execute('CREATE TABLE sentinel(value TEXT)')
        connection.execute("INSERT INTO sentinel VALUES ('preserved')")
    backup, restored = tmp_path / 'backup.sqlite3', tmp_path / 'restored.sqlite3'
    for action, src, dst in [('backup', source, backup), ('restore', backup, restored)]:
        result = subprocess.run([sys.executable, 'scripts/database_backup.py', action, str(src), str(dst)],
                                cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        with closing(sqlite3.connect(dst)) as connection:
            assert connection.execute('SELECT value FROM sentinel').fetchone() == ('preserved',)
            assert connection.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    content = restored.read_bytes()
    result = subprocess.run([sys.executable, 'scripts/database_backup.py', 'restore', str(backup), str(restored)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 1 and restored.read_bytes() == content
    assert str(restored) not in result.stdout


def test_R05_controlled_failure_is_nonzero_without_touching_host_database(tmp_path, settings):
    sentinel = Path(settings['DATABASE_PATH'])
    before = sentinel.read_bytes()
    testfile = tmp_path / 'test_controlled.py'
    testfile.write_text('def test_controlled():\n    assert False\n')
    environment = {**os.environ, 'APP_ENV': 'production', 'DATABASE_PATH': str(sentinel)}
    command = [sys.executable, '-m', 'pytest', '-q', '-c', '/dev/null', str(testfile)]
    failed = subprocess.run(command, env=environment, cwd=tmp_path, capture_output=True, text=True)
    assert failed.returncode == 1
    testfile.write_text('def test_controlled():\n    assert True\n')
    passed = subprocess.run(command, env=environment, cwd=tmp_path, capture_output=True, text=True)
    assert passed.returncode == 0
    assert sentinel.read_bytes() == before
