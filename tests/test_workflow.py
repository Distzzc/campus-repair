"""A01–A04, W01–W06 and U01–U04: real registration and complete role flow."""
import io
import secrets
import sqlite3
from uuid import uuid4

from PIL import Image
import pytest
from campus_repair import create_app
from campus_repair.migration import migrate
from campus_repair.services.demo import seed


@pytest.fixture
def portal(settings):
    migrate({**settings, 'DB_TIMEOUT_SECONDS': 1})
    migrate({**settings, 'DB_TIMEOUT_SECONDS': 1})
    config = {**settings, 'ADMIN_INVITE_CODE': secrets.token_urlsafe(24),
              'WORKER_INVITE_CODE': secrets.token_urlsafe(24), 'DEMO_PASSWORD': secrets.token_urlsafe(16)}
    return create_app(config)


def csrf(client):
    return client.get('/api/v1/session').json['data']['csrf']


def post(client, path, data, key=None, token=None):
    return client.post('/api/v1' + path, json=data, headers={
        'X-CSRF-Token': token or csrf(client), 'Idempotency-Key': key or str(uuid4())})


def register(app, username, role='student'):
    client = app.test_client()
    password = secrets.token_urlsafe(16)
    response = post(client, '/register', {'username': username, 'name': '测试用户', 'password': password,
                                         'role': role, 'invite_code': app.config.get(role.upper() + '_INVITE_CODE', '')})
    assert response.status_code == 200, response.json
    return client, password


@pytest.fixture
def actors(portal):
    return {role: register(portal, 'user_' + role, role)[0] for role in ('student', 'worker', 'admin')}


def ticket_data():
    return {'title': '宿舍水龙头持续漏水', 'location': '宿舍3栋402室', 'description': '今天早上发现水龙头关闭后仍持续滴水，请协助处理。', 'category': '水电', 'priority': 'normal'}


def ticket_id(client):
    response = post(client, '/tickets', ticket_data())
    assert response.status_code == 200, response.json
    return response.json['data']['id']


def act(client, identifier, name, **extra):
    ticket = client.get('/api/v1/tickets/' + str(identifier)).json['data']
    return post(client, f'/tickets/{identifier}/actions', {'action': name, 'version': ticket['version'], **extra})


def test_A01_A02_register_roles_and_hashes(portal):
    for role in ['student', 'worker', 'admin']:
        client, password = register(portal, 'test_' + role, role)
        assert client.get('/api/v1/session').json['data']['user']['role'] == role
        with sqlite3.connect(portal.config['DATABASE_PATH']) as db:
            hashed = db.execute('SELECT password_hash FROM users WHERE username=?', ('test_' + role,)).fetchone()[0]
            assert hashed.startswith('$argon2id$') and password not in hashed
        assert client.get('/').status_code == 200
    client = portal.test_client()
    info = {'username': 'invalid', 'name': '测试账户', 'password': secrets.token_urlsafe(16), 'role': 'admin', 'invite_code': 'incorrect'}
    assert post(client, '/register', info).status_code == 400
    info['role'] = 'student'; info['password'] = 'short'
    assert post(client, '/register', info).status_code == 400
    assert client.post('/api/v1/register', json=info).status_code == 403


def test_A03_A04_login_logout_expiry_csrf_limit(portal):
    client, password = register(portal, 'login_user')
    old_cookie = client.get_cookie('campus_session').value
    assert post(client, '/logout', {}).status_code == 200
    assert client.get('/api/v1/tickets').status_code == 401
    client.set_cookie('campus_session', old_cookie)
    assert client.get('/api/v1/tickets').status_code == 401
    csrf(client)
    assert post(client, '/login', {'username': 'login_user', 'password': password}).status_code == 200
    assert client.get_cookie('campus_session').http_only
    assert client.get_cookie('campus_session').same_site == 'Lax'
    assert client.post('/api/v1/tickets', json=ticket_data()).status_code == 403
    post(client, '/logout', {})
    for _ in range(5):
        assert post(client, '/login', {'username': 'login_user', 'password': 'incorrect'}).status_code == 401
    assert post(client, '/login', {'username': 'login_user', 'password': password}).status_code == 429
    fresh, _ = register(portal, 'expiry_user')
    with sqlite3.connect(portal.config['DATABASE_PATH']) as db:
        db.execute('UPDATE sessions SET expires=0')
    assert fresh.get('/api/v1/tickets').status_code == 401


def test_W01_W02_W03_full_lifecycle_and_authorization(portal, actors):
    student, admin, worker = (actors[role] for role in ('student','admin','worker'))
    identifier = ticket_id(student)
    stranger, _ = register(portal, 'stranger')
    assert stranger.get(f'/api/v1/tickets/{identifier}').status_code == 403
    assert worker.get(f'/api/v1/tickets/{identifier}').status_code == 403
    assert post(student, f'/tickets/{identifier}/actions', {'action': 'assign', 'version': 1, 'assignee_id': 2}).status_code == 403
    worker_id = admin.get('/api/v1/workers').json['data'][0]['id']
    assert act(admin, identifier, 'assign', assignee_id=worker_id).status_code == 200
    assert act(worker, identifier, 'accept').json['data']['status'] == 'working'
    assert act(student, identifier, 'cancel').status_code == 409
    assert act(worker, identifier, 'finish', note='已更换密封件，现场测试未再滴水').status_code == 200
    assert act(student, identifier, 'reopen', note='下午发现仍然滴水，请继续检查').json['data']['status'] == 'working'
    assert act(worker, identifier, 'finish', note='重新检查并更换水龙头，测试正常').status_code == 200
    assert act(student, identifier, 'confirm').status_code == 200
    assert post(student, f'/tickets/{identifier}/review', {'rating': 5, 'comment': '非常满意'}).status_code == 200
    assert post(student, f'/tickets/{identifier}/review', {'rating': 5}).status_code == 409
    detail = student.get(f'/api/v1/tickets/{identifier}').json['data']
    assert detail['status'] == 'completed' and len(detail['events']) == 7
    assert detail['review']['rating'] == 5
    other = ticket_id(student)
    assert act(student, other, 'cancel').status_code == 200


def test_W04_idempotency_version_and_rollback(actors, portal):
    client = actors['student']; key = str(uuid4()); payload = ticket_data()
    first = post(client, '/tickets', payload, key).json['data']
    assert post(client, '/tickets', payload, key).json['data'] == first
    assert post(client, '/tickets', {**payload, 'title':'不同的报修内容'}, key).status_code == 409
    identifier = first['id']
    assert post(client, f'/tickets/{identifier}/actions', {'action':'note','version':99,'note':'测试说明'}).status_code == 409
    assert post(client, f'/tickets/{identifier}/actions', {'action':'note','version':1,'note':'测试说明'}).status_code == 200
    assert post(client, f'/tickets/{identifier}/actions', {'action':'note','version':1,'note':'再次说明'}).status_code == 409
    assert len(client.get(f'/api/v1/tickets/{identifier}').json['data']['events']) == 2


def test_W05_image_validation_and_inherited_permissions(portal, actors):
    client=actors['student']; identifier=ticket_id(client)
    image=io.BytesIO();Image.new('RGB',(20,20),'green').save(image,format='PNG'); content=image.getvalue()
    def upload(blob):
        return client.post(f'/api/v1/tickets/{identifier}/attachments',data={'file':(io.BytesIO(blob),'a.png')},
                           headers={'X-CSRF-Token':csrf(client),'Idempotency-Key':str(uuid4())})
    result=upload(content); assert result.status_code==200,result.json
    aid=result.json['data']['id']
    assert client.get(f'/api/v1/attachments/{aid}').data==content
    stranger,_=register(portal,'image_stranger')
    assert stranger.get(f'/api/v1/attachments/{aid}').status_code==403
    assert upload(b'<script>not an image</script>').status_code==400
    assert upload(b'x'*(5*1024*1024+1)).status_code==400
    for _ in range(9):assert upload(content).status_code==200
    assert upload(content).status_code==400


def test_W06_filters_statistics(actors):
    client=actors['student'];ticket_id(client)
    for query in ['status=bad','page=0','page_size=101','sort=title','unknown=x']:
        assert client.get('/api/v1/tickets?'+query).status_code==400
    assert client.get('/api/v1/tickets?page=1&page_size=1').json['data']['total']==1
    assert client.get('/api/v1/stats').json['data']['total']==1
    assert actors['worker'].get('/api/v1/stats').json['data']['total']==0


def test_U01_U03_U04_pages_demo_and_reset_preserve_real_data(portal):
    with portal.app_context():
        seed(portal.config['DEMO_PASSWORD'])
        seed(portal.config['DEMO_PASSWORD'])
    client,password=register(portal,'real_student')
    identifier=ticket_id(client)
    for page in ['/','/tickets','/tickets/new','/statistics','/profile','/help',f'/tickets/{identifier}']:
        response=client.get(page)
        assert response.status_code==200 and 'text/html' in response.content_type
    with portal.app_context():
        seed(portal.config['DEMO_PASSWORD'],reset=True)
    assert client.get(f'/api/v1/tickets/{identifier}').status_code==200
    assert portal.test_client().get('/register').status_code==200
    script=portal.test_client().get('/static/app.js').text
    assert '未调用 AI' in script and 'original_description' in script


def test_W04_explicit_transaction_rollback(portal):
    from campus_repair.repositories import store
    with portal.app_context():
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.execute("INSERT INTO users(username,name,password_hash,role) VALUES ('rollback','回滚用户','test-hash','student')")
                raise RuntimeError('controlled failure')
        assert store.one("SELECT id FROM users WHERE username='rollback'") is None


def test_A02_duplicate_registration_and_unicode_invite(portal):
    register(portal, 'duplicate')
    client = portal.test_client()
    data = {'username':'duplicate','name':'注册用户','password':secrets.token_urlsafe(16),'role':'student'}
    assert post(client,'/register',data).status_code == 409
    data.update(username='unicode_invite',role='admin',invite_code='无效的邀请码包含非英文')
    assert post(client,'/register',data).status_code == 400
    assert post(client,'/register',data,token='非法验证字符串').status_code == 403
