"""C2: health, errors, identity and privacy scenarios H01–H08."""
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from uuid import UUID

import pytest
from werkzeug.exceptions import TooManyRequests
from campus_repair import create_app


def test_H01_real_query_and_public_contract(app, monkeypatch):
    from campus_repair.routes import health
    original = health.probe
    calls = []
    def observed(connection):
        calls.append(connection)
        original(connection)
    monkeypatch.setattr(health, 'probe', observed)
    response = app.test_client().get('/health')
    assert response.status_code == 200
    assert response.mimetype == 'application/json'
    assert response.json == {'status': 'ok', 'checks': {'database': 'ok'},
                             'request_id': response.headers['X-Request-ID']}
    assert len(calls) == 1


def test_H02_dependency_removed_and_restored(app, settings):
    client = app.test_client()
    assert client.get('/health').status_code == 200
    path = Path(settings['DATABASE_PATH'])
    backup = path.with_suffix('.backup')
    path.rename(backup)
    response = client.get('/health')
    assert response.status_code == 503
    assert response.json['error'] == {'code': 'DEPENDENCY_UNAVAILABLE',
                                     'message': 'Service temporarily unavailable', 'details': {}}
    assert not path.exists()
    backup.rename(path)
    assert client.get('/health').status_code == 200


@pytest.mark.parametrize('target', ['campus_repair.db.open_connection', 'campus_repair.routes.health.probe'])
def test_H02_connection_or_query_error_recovers(app, monkeypatch, target):
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            raise sqlite3.OperationalError('SENSITIVE SELECT /private/path')
        patch.setattr(target, fail)
        assert app.test_client().get('/health').status_code == 503
    assert app.test_client().get('/health').status_code == 200


def test_H02_real_database_lock_timeout(app, settings):
    with sqlite3.connect(settings['DATABASE_PATH']) as connection:
        connection.execute('BEGIN EXCLUSIVE')
        assert app.test_client().get('/health').status_code == 503
        connection.rollback()
    assert app.test_client().get('/health').status_code == 200


@pytest.mark.parametrize('path', ['/api', '/api/v1/tickets', '/missing'])
def test_H03_unknown_route(app, path):
    response = app.test_client().get(path)
    assert response.status_code == 404
    assert response.mimetype == 'application/json'
    assert response.json['error'] == {'code': 'NOT_FOUND', 'message': 'Resource not found', 'details': {}}
    assert set(response.json) == {'error', 'request_id'}


def test_H04_method_not_allowed_preserves_protocol(app):
    response = app.test_client().post('/health')
    assert response.status_code == 405
    assert response.json['error']['code'] == 'METHOD_NOT_ALLOWED'
    allowed = {v.strip() for v in response.headers['Allow'].split(',')}
    assert 'GET' in allowed and 'POST' not in allowed


def add_failure_routes(app):
    @app.get('/test-boom')
    def boom():
        raise RuntimeError('PRIVATE-FAILURE SELECT password /database/private.sqlite3')
    @app.get('/test-http-error')
    def standard_error():
        raise TooManyRequests('PRIVATE-FAILURE', retry_after=7)


def test_H05_safe_unexpected_and_standard_errors(app, capsys):
    add_failure_routes(app)
    for path, status, code in [('/test-boom', 500, 'INTERNAL_ERROR'),
                               ('/test-http-error', 429, 'HTTP_ERROR')]:
        response = app.test_client().get(path)
        assert response.status_code == status
        assert response.json['error']['code'] == code
        assert response.json['error']['details'] == {}
        assert 'PRIVATE' not in response.text and 'SELECT' not in response.text
        if status == 429:
            assert response.headers['Retry-After'] == '7'
    assert 'PRIVATE' not in capsys.readouterr().out


@pytest.mark.parametrize('level', ['INFO', 'ERROR'])
def test_H06_H07_identity_and_complete_json_logs(settings, capsys, level):
    app = create_app({**settings, 'LOG_LEVEL': level})
    add_failure_routes(app)
    client = app.test_client()
    capsys.readouterr()
    seen = set()
    for method, path, status, severity in [
        ('GET', '/health', 200, 'INFO'), ('GET', '/missing', 404, 'WARNING'),
        ('POST', '/health', 405, 'WARNING'), ('GET', '/test-boom', 500, 'ERROR'),
        ('HEAD', '/health', 200, 'INFO')]:
        response = client.open(path, method=method, headers={'X-Request-ID': 'same-untrusted-value'})
        assert response.status_code == status
        rid = response.headers['X-Request-ID']
        assert UUID(rid).version == 4 and rid not in seen
        seen.add(rid)
        if method != 'HEAD':
            assert response.json['request_id'] == rid
        else:
            assert response.data == b''
        lines = capsys.readouterr().out.splitlines()
        assert len(lines) == 1
        log = json.loads(lines[0])
        assert log['event'] == 'request_completed' and log['request_id'] == rid
        assert log['level'] == severity and log['status_code'] == status
        assert log['method'] == method and log['duration_ms'] >= 0
        assert log['path'] == ('<unmatched>' if status in (404, 405) else path)
        assert log['timestamp'].endswith('Z')
        assert len(log['timestamp'].split('.')[1]) == 4
        datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00'))
    Path(settings['DATABASE_PATH']).unlink()
    response = client.get('/health')
    record = json.loads(capsys.readouterr().out)
    assert record['status_code'] == 503 and record['level'] == 'WARNING'
    assert record['request_id'] == response.headers['X-Request-ID'] == response.json['request_id']


def test_H08_sensitive_inputs_are_not_logged(app, capsys):
    add_failure_routes(app)
    client = app.test_client()
    client.set_cookie('session', 'PRIVATE-COOKIE')
    capsys.readouterr()
    for path in ['/health', '/PRIVATE-PATH', '/test-boom']:
        response = client.get(path + '?q=PRIVATE-QUERY', data='PRIVATE-BODY',
                              headers={'Authorization': 'Bearer PRIVATE-TOKEN',
                                       'X-Request-ID': 'PRIVATE-IDENTITY'})
        text = capsys.readouterr().out + response.text
        assert 'PRIVATE-' not in text and 'SELECT password' not in text
        for line in text.splitlines():
            if line.startswith('{'):
                json.loads(line)


def test_F05_log_level_filters_lifecycle_but_keeps_requests(settings, capsys):
    app = create_app({**settings, 'LOG_LEVEL': 'ERROR'})
    assert capsys.readouterr().out == ''
    app.test_client().get('/health')
    record = json.loads(capsys.readouterr().out)
    assert record['event'] == 'request_completed' and record['level'] == 'INFO'
