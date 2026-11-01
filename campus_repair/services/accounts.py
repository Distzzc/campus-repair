"""Argon2id identity, revocable server sessions and role-gated registration."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from campus_repair.repositories import store

HASHER = PasswordHasher()


class BusinessError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(code)


def fail(status, code, message):
    raise BusinessError(status, code, message)


def text(value, field, minimum, maximum):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        fail(400, 'VALIDATION_ERROR', f'{field}需为{minimum}–{maximum}个字符')
    return value.strip()


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def session_for(token):
    if not token or len(token) > 200:
        return None
    return store.one('SELECT * FROM sessions WHERE token_hash=? AND expires>?', (digest(token), time.time()))


def create_session(user_id=None):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with store.transaction():
        store.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
        store.execute('INSERT INTO sessions(token_hash,user_id,csrf,expires) VALUES (?,?,?,?)',
                      (digest(token), user_id, csrf, time.time() + 28800))
    return token, session_for(token)


def user_for(session):
    return store.one('SELECT id,username,name,role FROM users WHERE id=?', (session['user_id'],)) if session else None


def validate_csrf(session, token):
    if not session or not isinstance(token, str) or not hmac.compare_digest(session['csrf'].encode(), token.encode()):
        fail(403, 'CSRF_INVALID', '页面已过期，请刷新后重试')


def check_rate(session):
    if session['blocked_until'] > time.time():
        fail(429, 'RATE_LIMITED', '尝试过于频繁，请15分钟后重试')


def failed_attempt(session):
    with store.transaction():
        store.execute('UPDATE sessions SET failures=failures+1,blocked_until=CASE WHEN failures>=4 THEN ? ELSE 0 END WHERE token_hash=?',
                      (time.time() + 900, session['token_hash']))


def register(data, session, config):
    check_rate(session)
    username = text(data.get('username'), '用户名', 3, 32)
    if not re.fullmatch(r'[A-Za-z0-9_]{3,32}', username):
        fail(400, 'VALIDATION_ERROR', '用户名仅支持英文字母、数字和下划线')
    name = text(data.get('name'), '姓名', 2, 40)
    password = data.get('password')
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        fail(400, 'VALIDATION_ERROR', '密码需为12–128个字符')
    role = data.get('role')
    if role not in ('student', 'admin', 'worker'):
        fail(400, 'VALIDATION_ERROR', '请选择有效账户类型')
    if role != 'student':
        expected = config.get(f'{role.upper()}_INVITE_CODE', '')
        provided = data.get('invite_code', '')
        if not expected or not isinstance(provided, str) or not hmac.compare_digest(expected.encode(), provided.encode()):
            failed_attempt(session)
            fail(400, 'INVITE_INVALID', '角色邀请码无效，请联系管理员')
    password_hash = HASHER.hash(password)
    try:
        with store.transaction():
            cursor = store.execute('INSERT INTO users(username,name,password_hash,role) VALUES (?,?,?,?)',
                                   (username, name, password_hash, role))
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        fail(409, 'USERNAME_EXISTS', '该用户名已被注册')
    return user_id


def login(data, session):
    check_rate(session)
    username = text(data.get('username'), '用户名', 3, 32)
    password = data.get('password', '')
    if not isinstance(password, str) or len(password) > 128:
        fail(400, 'VALIDATION_ERROR', '登录信息格式无效')
    user = store.one('SELECT * FROM users WHERE username=?', (username,))
    try:
        # Also perform a password derivation for unknown users.
        if not user:
            HASHER.hash(password)
            raise VerificationError('Invalid credentials')
        HASHER.verify(user['password_hash'], password)
    except (VerificationError, InvalidHashError):
        failed_attempt(session)
        fail(401, 'INVALID_CREDENTIALS', '用户名或密码错误')
    return user['id']


def revoke(session):
    with store.transaction():
        store.execute('DELETE FROM sessions WHERE token_hash=?', (session['token_hash'],))
