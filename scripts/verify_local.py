"""Reproduce the README in a clean temporary checkout and Python 3.12 venv."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen
import venv

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/verification'


def main():
    transcript = []
    results = []
    def ignore(directory, names):
        return [name for name in names if name in {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 'instance', 'uploads', 'logs', 'build', 'dist'}
                or (name.startswith('.env') and name != '.env.example') or name.endswith('.egg-info')]
    try:
        with tempfile.TemporaryDirectory(prefix='campus-local-') as temporary:
            source = Path(temporary) / 'campus-repair'
            shutil.copytree(ROOT, source, ignore=ignore)
            venv.EnvBuilder(with_pip=True).create(source / '.venv')
            python = source / '.venv/bin/python'
            env = {key: value for key, value in os.environ.items()
                   if key not in {'APP_ENV', 'DATABASE_PATH', 'LOG_LEVEL', 'DB_TIMEOUT_SECONDS', 'PYTHONPATH'}}
            env['FLASK_SKIP_DOTENV'] = '1'
            def run(arguments):
                print('Running:', ' '.join(str(arg) for arg in arguments[:5]), flush=True)
                result = subprocess.run([str(arg) for arg in arguments], cwd=source, env=env,
                                        capture_output=True, text=True)
                transcript.append('$ ' + ' '.join(str(arg) for arg in arguments) + '\n' + result.stdout + result.stderr + f'\nexit={result.returncode}\n')
                if result.returncode:
                    raise RuntimeError('Clean local command failed: ' + str(arguments[0]))
                return result
            run([python, '-m', 'pip', 'install', '--no-cache-dir', '-r', 'requirements-dev.lock'])
            run([python, '-m', 'pip', 'install', '--no-deps', '--no-build-isolation', '-e', '.'])
            run([python, '-m', 'pip', 'check'])
            (source / 'instance').mkdir()
            path = source / 'instance/campus-repair.sqlite3'
            (source / '.env').write_text((source / '.env.example').read_text().replace('/absolute/path/to/campus-repair/instance/campus-repair.sqlite3', str(path)))
            dotenv = source / '.venv/bin/dotenv'
            run([dotenv, '-f', '.env', 'run', '--', python, '-m', 'flask', '--app', 'campus_repair.cli:create_cli_app', 'init-db'])
            run([dotenv, '-f', '.env', 'run', '--', python, '-m', 'flask', '--app', 'campus_repair.cli:create_cli_app', 'migrate-db'])
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            server_output = Path(temporary) / 'server.txt'
            with server_output.open('w') as output:
                process = subprocess.Popen([str(dotenv), '-f', '.env', 'run', '--', str(python), '-m', 'gunicorn', '-c', 'gunicorn.conf.py', '--bind', f'127.0.0.1:{port}', 'wsgi:app'],
                                           cwd=source, env=env, stdout=output, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 10
                    while True:
                        try:
                            with urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as response:
                                assert response.status == 200
                                body = json.load(response)
                                assert body['request_id'] == response.headers['X-Request-ID']
                            break
                        except (URLError, ConnectionError):
                            assert time.monotonic() < deadline and process.poll() is None
                            time.sleep(0.1)
                    run([python, '-m', 'pytest', '-q'])
                finally:
                    started = time.monotonic()
                    process.terminate()
                    status = process.wait(timeout=15)
            assert status == 0
            records = [json.loads(line) for line in server_output.read_text().splitlines()]
            assert any(record['event'] == 'shutdown' for record in records)
            transcript.append('Real Gunicorn stdout:\n' + server_output.read_text())
            results.append({'scenario': 'R01', 'result': 'passed', 'python': sys.version.split()[0],
                            'details': 'Clean copy, fresh venv, locked install, explicit dotenv/init, HTTP200, full pytest, SIGTERM exit0',
                            'shutdown_seconds': round(time.monotonic() - started, 3)})
    except Exception as error:
        results.append({'scenario': 'R01', 'result': 'failed', 'details': str(error)})
        raise
    finally:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / 'clean-local-transcript.txt').write_text('\n'.join(transcript))
        (OUTPUT / 'clean-local-results.json').write_text(json.dumps({'date': datetime.now(timezone.utc).isoformat(), 'results': results}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
