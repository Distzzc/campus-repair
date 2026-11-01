"""Authorized work order operations; every write and audit is one transaction."""
import hashlib
import io
import json
import time
import warnings
from uuid import UUID

from PIL import Image, UnidentifiedImageError
from campus_repair.repositories import store
from campus_repair.services.accounts import fail, text

STATUSES = {'waiting': '待分配', 'assigned': '待接单', 'working': '处理中', 'confirm': '待确认', 'completed': '已完成', 'cancelled': '已取消'}
CATEGORIES = ('水电', '网络', '家具', '空调', '其他')
PRIORITIES = {'normal': '普通', 'high': '优先', 'urgent': '紧急'}


def scope(user):
    if user['role'] == 'admin':
        return '1=1', []
    field = 'owner_id' if user['role'] == 'student' else 'assignee_id'
    return f't.{field}=?', [user['id']]


def authorized(user, ticket_id):
    ticket = store.one('SELECT t.*,u.name owner_name,w.name assignee_name FROM tickets t JOIN users u ON u.id=t.owner_id LEFT JOIN users w ON w.id=t.assignee_id WHERE t.id=?', (ticket_id,))
    if not ticket:
        fail(404, 'NOT_FOUND', '工单不存在')
    if user['role'] != 'admin' and ticket['owner_id' if user['role'] == 'student' else 'assignee_id'] != user['id']:
        fail(403, 'FORBIDDEN', '无权访问该工单')
    return ticket


def audit(ticket_id, actor, action, before, after, note):
    store.execute('INSERT INTO events(ticket_id,actor_id,action,before_status,after_status,note) VALUES (?,?,?,?,?,?)',
                  (ticket_id, actor, action, before, after, note))


def write_once(user, operation, key, payload, perform):
    try:
        UUID(key)
    except (ValueError, TypeError, AttributeError):
        fail(400, 'VALIDATION_ERROR', '缺少有效的幂等请求标识')
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    with store.transaction():
        store.execute('DELETE FROM idempotency WHERE expires<?', (time.time(),))
        previous = store.one('SELECT * FROM idempotency WHERE actor_id=? AND operation=? AND key=?', (user['id'], operation, key))
        if previous:
            if previous['fingerprint'] != fingerprint:
                fail(409, 'IDEMPOTENCY_CONFLICT', '重复请求内容不一致')
            return json.loads(previous['response'])
        result = perform()
        store.execute('INSERT INTO idempotency VALUES (?,?,?,?,?,?)',
                      (user['id'], operation, key, fingerprint, json.dumps(result, ensure_ascii=False), time.time() + 86400))
        return result


def validate_fields(data):
    title = text(data.get('title'), '标题', 3, 100)
    location = text(data.get('location'), '地点', 3, 160)
    description = text(data.get('description'), '故障描述', 10, 3000)
    original = text(data.get('original_description', description), '原始描述', 10, 3000)
    category, priority = data.get('category'), data.get('priority', 'normal')
    if category not in CATEGORIES or priority not in PRIORITIES:
        fail(400, 'VALIDATION_ERROR', '分类或优先级无效')
    return title, location, original, description, category, priority


def create_ticket(user, data, key):
    if user['role'] != 'student':
        fail(403, 'FORBIDDEN', '仅学生可提交报修')
    fields = validate_fields(data)
    def perform():
        cursor = store.execute('INSERT INTO tickets(owner_id,title,location,original_description,description,category,priority) VALUES (?,?,?,?,?,?,?)', (user['id'], *fields))
        audit(cursor.lastrowid, user['id'], 'create', None, 'waiting', '提交报修')
        return {'id': cursor.lastrowid}
    return write_once(user, 'create_ticket', key, data, perform)


def detail(user, ticket_id):
    ticket = authorized(user, ticket_id)
    ticket['events'] = store.many('SELECT e.*,u.name actor_name FROM events e JOIN users u ON u.id=e.actor_id WHERE ticket_id=? ORDER BY e.id', (ticket_id,))
    ticket['attachments'] = store.many('SELECT id,filename,mime,created_at FROM attachments WHERE ticket_id=? ORDER BY id', (ticket_id,))
    ticket['review'] = store.one('SELECT rating,comment,created_at FROM reviews WHERE ticket_id=?', (ticket_id,))
    return ticket


def list_tickets(user, args):
    if set(args) - {'status', 'category', 'priority', 'q', 'page', 'page_size', 'sort'}:
        fail(400, 'VALIDATION_ERROR', '存在未知筛选参数')
    if args.get('sort', 'newest') != 'newest':
        fail(400, 'VALIDATION_ERROR', '排序参数无效')
    condition, values = scope(user)
    for field, allowed in [('status', STATUSES), ('category', CATEGORIES), ('priority', PRIORITIES)]:
        value = args.get(field, '')
        if value:
            if value not in allowed:
                fail(400, 'VALIDATION_ERROR', '筛选条件无效')
            condition += f' AND t.{field}=?'
            values.append(value)
    query = args.get('q', '')
    if len(query) > 100:
        fail(400, 'VALIDATION_ERROR', '搜索内容最多100字')
    if query:
        condition += ' AND (t.title LIKE ? OR t.location LIKE ? OR CAST(t.id AS TEXT)=?)'
        values += ['%' + query + '%', '%' + query + '%', query]
    try:
        page, size = int(args.get('page', 1)), int(args.get('page_size', 20))
        if page < 1 or not 1 <= size <= 100:
            raise ValueError()
    except (ValueError, TypeError):
        fail(400, 'VALIDATION_ERROR', '分页参数无效')
    total = store.one(f'SELECT COUNT(*) n FROM tickets t WHERE {condition}', values)['n']
    items = store.many(f'SELECT t.*,u.name owner_name,w.name assignee_name FROM tickets t JOIN users u ON u.id=t.owner_id LEFT JOIN users w ON w.id=t.assignee_id WHERE {condition} ORDER BY t.created_at DESC,t.id DESC LIMIT ? OFFSET ?', (*values, size, (page - 1) * size))
    return {'items': items, 'total': total, 'page': page, 'page_size': size}


def action(user, ticket_id, data, key):
    def perform():
        ticket = authorized(user, ticket_id)
        if data.get('version') != ticket['version']:
            fail(409, 'STATE_CONFLICT', '工单已更新，请刷新后操作')
        status, name, role = ticket['status'], data.get('action'), user['role']
        target, note = status, data.get('note', '')
        if not isinstance(note, str) or len(note) > 3000:
            fail(400, 'VALIDATION_ERROR', '说明最多3000字')
        if status in ('completed', 'cancelled'):
            fail(409, 'STATE_CONFLICT', '工单已结束，不能修改')
        if name == 'assign':
            if role != 'admin':
                fail(403, 'FORBIDDEN', '仅管理员可分配')
            if status != 'waiting':
                fail(409, 'STATE_CONFLICT', '当前阶段不能分配')
            worker = store.one("SELECT id FROM users WHERE id=? AND role='worker'", (data.get('assignee_id'),))
            if not worker:
                fail(400, 'VALIDATION_ERROR', '请选择有效维修人员')
            store.execute('UPDATE tickets SET assignee_id=? WHERE id=?', (worker['id'], ticket_id))
            target, note = 'assigned', '已分配维修人员'
        elif name == 'classify':
            if role != 'admin':
                fail(403, 'FORBIDDEN', '仅管理员可调整')
            if data.get('category') not in CATEGORIES or data.get('priority') not in PRIORITIES:
                fail(400, 'VALIDATION_ERROR', '分类或优先级无效')
            store.execute('UPDATE tickets SET category=?,priority=? WHERE id=?', (data['category'], data['priority'], ticket_id))
            note = '调整故障分类与优先级'
        elif name == 'note':
            note = text(note, '补充说明', 2, 3000)
        elif name == 'cancel':
            if role != 'student':
                fail(403, 'FORBIDDEN', '仅报修学生可取消')
            if status not in ('waiting', 'assigned'):
                fail(409, 'STATE_CONFLICT', '维修开始后不能取消')
            target, note = 'cancelled', note or '学生取消报修'
        else:
            transitions = {'accept': ('worker', 'assigned', 'working'), 'finish': ('worker', 'working', 'confirm'),
                           'confirm': ('student', 'confirm', 'completed'), 'reopen': ('student', 'confirm', 'working')}
            if name not in transitions:
                fail(400, 'VALIDATION_ERROR', '操作类型无效')
            expected_role, expected_status, target = transitions[name]
            if role != expected_role:
                fail(403, 'FORBIDDEN', '当前角色不能执行该操作')
            if status != expected_status:
                fail(409, 'STATE_CONFLICT', '当前状态不能执行该操作')
            note = text(note, '处理或反馈说明', 2, 3000) if name in ('finish', 'reopen') else (note or {'accept': '维修人员接单', 'confirm': '学生确认维修完成'}[name])
        store.execute("UPDATE tickets SET status=?,version=version+1,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND version=?", (target, ticket_id, ticket['version']))
        audit(ticket_id, user['id'], name, status, target, note)
        return {'id': ticket_id, 'status': target, 'version': ticket['version'] + 1}
    return write_once(user, f'action:{ticket_id}', key, data, perform)


def review(user, ticket_id, data, key):
    def perform():
        ticket = authorized(user, ticket_id)
        if user['role'] != 'student':
            fail(403, 'FORBIDDEN', '仅报修学生本人可评价')
        if ticket['status'] != 'completed':
            fail(409, 'STATE_CONFLICT', '仅已完成工单可评价')
        rating = data.get('rating')
        comment = data.get('comment', '')
        if type(rating) is not int or not 1 <= rating <= 5 or not isinstance(comment, str) or len(comment) > 1000:
            fail(400, 'VALIDATION_ERROR', '评分需为1–5，评价最多1000字')
        if store.one('SELECT ticket_id FROM reviews WHERE ticket_id=?', (ticket_id,)):
            fail(409, 'STATE_CONFLICT', '该工单已评价')
        store.execute('INSERT INTO reviews(ticket_id,rating,comment) VALUES (?,?,?)', (ticket_id, rating, comment))
        return {'id': ticket_id, 'rating': rating}
    return write_once(user, f'review:{ticket_id}', key, data, perform)


def add_attachment(user, ticket_id, content, key):
    if not content or len(content) > 5 * 1024 * 1024:
        fail(400, 'VALIDATION_ERROR', '图片不得超过5MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in ('PNG', 'JPEG', 'WEBP') or image.width * image.height > 20000000:
                    raise ValueError()
                mime = Image.MIME[image.format]
                suffix = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}[image.format]
                image.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        fail(400, 'VALIDATION_ERROR', '请选择有效PNG、JPEG或WebP图片')
    def perform():
        ticket = authorized(user, ticket_id)
        if ticket['status'] in ('completed', 'cancelled'):
            fail(409, 'STATE_CONFLICT', '工单已结束')
        if store.one('SELECT COUNT(*) n FROM attachments WHERE ticket_id=?', (ticket_id,))['n'] >= 10:
            fail(400, 'VALIDATION_ERROR', '每单最多10张图片')
        cursor = store.execute('INSERT INTO attachments(ticket_id,actor_id,filename,mime,content) VALUES (?,?,?,?,?)',
                               (ticket_id, user['id'], f'现场图片.{suffix}', mime, content))
        audit(ticket_id, user['id'], 'attachment', ticket['status'], ticket['status'], '添加现场图片')
        return {'id': cursor.lastrowid}
    return write_once(user, f'attachment:{ticket_id}', key, {'sha256': hashlib.sha256(content).hexdigest()}, perform)


def statistics(user):
    condition, values = scope(user)
    rows = store.many(f'SELECT t.status,COUNT(*) count FROM tickets t WHERE {condition} GROUP BY t.status', values)
    by_status = {key: 0 for key in STATUSES}
    by_status.update({row['status']: row['count'] for row in rows})
    categories = store.many(f'SELECT t.category,COUNT(*) count FROM tickets t WHERE {condition} GROUP BY t.category ORDER BY count DESC,t.category', values)
    average = store.one(f'SELECT ROUND(AVG(r.rating),1) average FROM reviews r JOIN tickets t ON t.id=r.ticket_id WHERE {condition}', values)['average']
    return {'total': sum(by_status.values()), 'by_status': by_status, 'categories': categories, 'average_rating': average}
