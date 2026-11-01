"""HTTP adapters for the authenticated workspace and versioned business API."""
from functools import wraps
import io

from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, send_file
from campus_repair.repositories import store
from campus_repair.services import accounts, workorders

blueprint = Blueprint('portal', __name__)


def success(data):
    return jsonify(data=data, request_id=g.request_id)


def current_session():
    if not hasattr(g, 'portal_session'):
        g.portal_session = accounts.session_for(request.cookies.get('campus_session'))
    return g.portal_session


def set_cookie(response, token):
    response.set_cookie('campus_session', token, max_age=28800, httponly=True,
                        secure=current_app.config['COOKIE_SECURE'], samesite='Lax')
    response.headers['Cache-Control'] = 'no-store'
    return response


def ensure_session():
    session = current_session()
    if session:
        return session, None
    token, session = accounts.create_session()
    g.portal_session = session
    return session, token


def authenticated(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        g.user = accounts.user_for(current_session())
        if not g.user:
            accounts.fail(401, 'UNAUTHENTICATED', '请先登录')
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            accounts.validate_csrf(current_session(), request.headers.get('X-CSRF-Token'))
        return function(*args, **kwargs)
    return wrapped


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        accounts.fail(400, 'VALIDATION_ERROR', '请求需为JSON对象')
    return data


@blueprint.get('/api/v1/session')
def session_info():
    session, token = ensure_session()
    response = success({'user': accounts.user_for(session), 'csrf': session['csrf']})
    response.headers['Cache-Control'] = 'no-store'
    return set_cookie(response, token) if token else response


@blueprint.post('/api/v1/login')
@blueprint.post('/api/v1/register')
@blueprint.post('/api/v1/logout')
def account_operation():
    operation = request.path.rsplit('/', 1)[1]
    if operation not in ('login', 'register', 'logout'):
        accounts.fail(404, 'NOT_FOUND', '接口不存在')
    session = current_session()
    accounts.validate_csrf(session, request.headers.get('X-CSRF-Token'))
    if operation == 'logout':
        accounts.revoke(session)
        response = success({'redirect': '/login'})
        response.delete_cookie('campus_session', secure=current_app.config['COOKIE_SECURE'], httponly=True, samesite='Lax')
        return response
    data = body()
    user_id = accounts.login(data, session) if operation == 'login' else accounts.register(data, session, current_app.config)
    accounts.revoke(session)
    token, _session = accounts.create_session(user_id)
    return set_cookie(success({'redirect': '/'}), token)


@blueprint.get('/api/v1/tickets')
@authenticated
def ticket_list():
    return success(workorders.list_tickets(g.user, request.args))


@blueprint.post('/api/v1/tickets')
@authenticated
def ticket_create():
    return success(workorders.create_ticket(g.user, body(), request.headers.get('Idempotency-Key')))


@blueprint.get('/api/v1/tickets/<int:ticket_id>')
@authenticated
def ticket_detail(ticket_id):
    return success(workorders.detail(g.user, ticket_id))


@blueprint.post('/api/v1/tickets/<int:ticket_id>/actions')
@authenticated
def ticket_action(ticket_id):
    return success(workorders.action(g.user, ticket_id, body(), request.headers.get('Idempotency-Key')))


@blueprint.post('/api/v1/tickets/<int:ticket_id>/review')
@authenticated
def ticket_review(ticket_id):
    return success(workorders.review(g.user, ticket_id, body(), request.headers.get('Idempotency-Key')))


@blueprint.post('/api/v1/tickets/<int:ticket_id>/attachments')
@authenticated
def attachment_upload(ticket_id):
    file = request.files.get('file')
    if not file:
        accounts.fail(400, 'VALIDATION_ERROR', '请选择图片')
    return success(workorders.add_attachment(g.user, ticket_id, file.read(5 * 1024 * 1024 + 1), request.headers.get('Idempotency-Key')))


@blueprint.get('/api/v1/attachments/<int:attachment_id>')
@authenticated
def attachment_download(attachment_id):
    attachment = store.one('SELECT * FROM attachments WHERE id=?', (attachment_id,))
    if not attachment:
        accounts.fail(404, 'NOT_FOUND', '附件不存在')
    workorders.authorized(g.user, attachment['ticket_id'])
    response = send_file(io.BytesIO(attachment['content']), mimetype=attachment['mime'], download_name=attachment['filename'])
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@blueprint.get('/api/v1/workers')
@authenticated
def workers():
    if g.user['role'] != 'admin':
        accounts.fail(403, 'FORBIDDEN', '仅管理员可查看维修人员')
    return success(store.many("SELECT id,name FROM users WHERE role='worker' ORDER BY id"))


@blueprint.get('/api/v1/stats')
@authenticated
def stats():
    return success(workorders.statistics(g.user))


@blueprint.get('/login')
@blueprint.get('/register')
def identity_page():
    session, token = ensure_session()
    if accounts.user_for(session):
        return redirect('/')
    response = current_app.make_response(render_template('identity.html', registering=request.path == '/register'))
    return set_cookie(response, token) if token else response


@blueprint.get('/')
@blueprint.get('/tickets')
@blueprint.get('/tickets/new')
@blueprint.get('/tickets/<int:ticket_id>')
@blueprint.get('/statistics')
@blueprint.get('/profile')
@blueprint.get('/help')
def workspace(ticket_id=None):
    session = current_session()
    user = accounts.user_for(session)
    if not user:
        return redirect('/login')
    if ticket_id:
        workorders.authorized(user, ticket_id)
    return render_template('workspace.html', user=user, page=request.path, ticket_id=ticket_id,
                           statuses=workorders.STATUSES, categories=workorders.CATEGORIES,
                           priorities=workorders.PRIORITIES)
