"""C1: normal, failure, and boundary scenarios F01–F08."""
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

import pytest
from campus_repair import create_app
from campus_repair.config import ConfigurationError, load_config
from campus_repair.db import initialize_database
from conftest import ROOT


def test_F01_F02_startup_and_instance_isolation(settings, tmp_path):
    first = create_app(settings)
    second_path = tmp_path / "other.sqlite3"
    sqlite3.connect(second_path).close()
    second = create_app({**settings, "DATABASE_PATH": str(second_path)})
    assert first.test_client().get('/health').status_code == 200
    Path(settings['DATABASE_PATH']).unlink()
    assert first.test_client().get('/health').status_code == 503
    assert second.test_client().get('/health').status_code == 200
    assert first.config['DATABASE_PATH'] != second.config['DATABASE_PATH']
    assert '/health' in {rule.rule for rule in first.url_map.iter_rules()}
    assert not first.debug


def test_F01_import_has_no_configuration_or_connection_side_effects():
    program = 'import sqlite3; sqlite3.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError()); import campus_repair'
    result = subprocess.run([sys.executable, '-c', program], cwd=ROOT,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert result.stdout == ''


@pytest.mark.parametrize('field', ['APP_ENV', 'DATABASE_PATH'])
@pytest.mark.parametrize('missing', [True, False])
def test_F03_missing_required(settings, field, missing):
    settings.pop(field) if missing else settings.update({field: ''})
    with pytest.raises(ConfigurationError) as error:
        load_config(settings)
    assert error.value.code == 'CONFIG_MISSING'
    assert error.value.field == field


@pytest.mark.parametrize(('field', 'value'), [
    ('APP_ENV', 'prod'), ('APP_ENV', ' production'),
    ('LOG_LEVEL', 'TRACE'), ('LOG_LEVEL', ''),
    ('DB_TIMEOUT_SECONDS', '0'), ('DB_TIMEOUT_SECONDS', '11'),
    ('DB_TIMEOUT_SECONDS', '1.5'), ('DB_TIMEOUT_SECONDS', ''),
    ('DB_TIMEOUT_SECONDS', ' 1'), ('DB_TIMEOUT_SECONDS', '1 '),
    ('DB_TIMEOUT_SECONDS', '1\n'), ('DB_TIMEOUT_SECONDS', '１'),
    ('DB_TIMEOUT_SECONDS', '9' * 5000),
    ('DATABASE_PATH', 'relative.sqlite3'), ('DATABASE_PATH', ':memory:'),
    ('DATABASE_PATH', 'file:/tmp/demo.sqlite3'), ('DATABASE_PATH', '/tmp/demo.db'),
    ('DATABASE_PATH', '/tmp/a\x00.sqlite3'),
])
def test_F04_invalid_values(settings, field, value):
    with pytest.raises(ConfigurationError) as error:
        load_config({**settings, field: value})
    assert error.value.code == 'CONFIG_INVALID'
    assert error.value.field == field


def test_F04_parent_and_directory_validation(settings, tmp_path):
    directory = tmp_path / 'directory.sqlite3'
    directory.mkdir()
    for path in (directory, tmp_path / 'missing' / 'a.sqlite3'):
        with pytest.raises(ConfigurationError):
            load_config({**settings, 'DATABASE_PATH': str(path)})
    directory.chmod(0o555)
    try:
        with pytest.raises(ConfigurationError):
            load_config({**settings, 'DATABASE_PATH': str(directory / 'a.sqlite3')})
    finally:
        directory.chmod(0o755)


@pytest.mark.parametrize('level', ['DEBUG', 'INFO', 'WARNING', 'ERROR'])
@pytest.mark.parametrize('timeout', ['1', '10'])
def test_F05_valid_boundaries(settings, level, timeout):
    config = load_config({**settings, 'LOG_LEVEL': level, 'DB_TIMEOUT_SECONDS': timeout})
    assert config['LOG_LEVEL'] == level
    assert config['DB_TIMEOUT_SECONDS'] == int(timeout)


def test_F05_defaults_no_implicit_dotenv(settings, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.env').write_text('APP_ENV=production\nLOG_LEVEL=ERROR\nDB_TIMEOUT_SECONDS=10\n')
    settings.pop('DB_TIMEOUT_SECONDS')
    config = load_config(settings)
    assert config['APP_ENV'] == 'testing'
    assert config['LOG_LEVEL'] == 'INFO'
    assert config['DB_TIMEOUT_SECONDS'] == 2
    with pytest.raises(ConfigurationError):
        load_config()


def test_F06_explicit_cli_initialization_is_idempotent(settings, tmp_path, monkeypatch):
    path = tmp_path / 'new.sqlite3'
    for key, value in {**settings, 'DATABASE_PATH': str(path)}.items():
        monkeypatch.setenv(key, value)
    from campus_repair.cli import create_cli_app
    cli = create_cli_app().test_cli_runner()
    assert not path.exists()
    assert cli.invoke(args=['init-db']).exit_code == 0
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT name FROM sqlite_master').fetchall() == []
        connection.execute('CREATE TABLE sentinel (value TEXT)')
        connection.execute("INSERT INTO sentinel VALUES ('preserved')")
    assert cli.invoke(args=['init-db']).exit_code == 0
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT value FROM sentinel').fetchone() == ('preserved',)


@pytest.mark.parametrize('fault', ['missing', 'permission', 'corrupt', 'timeout'])
def test_F07_database_startup_failure_is_safe(settings, fault, capsys, monkeypatch):
    path = Path(settings['DATABASE_PATH'])
    if fault == 'missing':
        path.unlink()
    elif fault == 'permission':
        path.chmod(0o000)
    elif fault == 'corrupt':
        path.write_bytes(b'SENSITIVE-DATABASE-INPUT' * 100)
    else:
        def fail(_config, **kwargs):
            raise sqlite3.OperationalError('SENSITIVE-DATABASE-INPUT SELECT password')
        monkeypatch.setattr('campus_repair.db.open_connection', fail)
    try:
        with pytest.raises(SystemExit) as error:
            create_app(settings)
        assert error.value.code == 1
        record = json.loads(capsys.readouterr().out)
        assert record['error_code'] == 'DATABASE_INIT_FAILED'
        text = json.dumps(record)
        assert str(path) not in text and 'SENSITIVE' not in text and 'SELECT' not in text
        if fault == 'missing':
            assert not path.exists()
    finally:
        if path.exists():
            path.chmod(0o600)


def test_F03_F04_F07_failure_precedes_network_listener(settings):
    for changes, code in [({'APP_ENV': ''}, 'CONFIG_MISSING'),
                          ({'APP_ENV': 'invalid-private-value'}, 'CONFIG_INVALID'),
                          ({'DATABASE_PATH': str(Path(settings['DATABASE_PATH']).with_name('absent.sqlite3'))}, 'DATABASE_INIT_FAILED')]:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = {**os.environ, **settings, **changes}
        result = subprocess.run([sys.executable, '-m', 'gunicorn', '--bind', f'127.0.0.1:{port}', 'wsgi:app'],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
        assert result.returncode != 0
        assert code in result.stdout
        assert 'invalid-private-value' not in result.stdout + result.stderr
        assert 'Traceback' not in result.stdout + result.stderr
        with socket.socket() as sock:
            assert sock.connect_ex(('127.0.0.1', port)) != 0


@pytest.mark.parametrize('failure', [False, True])
def test_F08_request_connections_close(settings, monkeypatch, failure):
    from campus_repair import db
    app = create_app(settings)
    original = db.open_connection
    used = []
    def track(config, **kwargs):
        connection = original(config, **kwargs)
        used.append(connection)
        return connection
    monkeypatch.setattr(db, 'open_connection', track)
    if failure:
        def fail(connection):
            raise sqlite3.OperationalError('private details')
        monkeypatch.setattr('campus_repair.routes.health.probe', fail)
    for _ in range(2):
        assert app.test_client().get('/health').status_code == (503 if failure else 200)
    assert len(used) == 2 and used[0] is not used[1]
    for connection in used:
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute('SELECT 1')
