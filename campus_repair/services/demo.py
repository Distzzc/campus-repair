"""Explicit opt-in demonstration data. Never overwrite registered accounts."""
from campus_repair.repositories import store
from campus_repair.services.accounts import HASHER, fail
from campus_repair.services.workorders import audit


def seed(password, reset=False):
    if not password or len(password) < 12:
        fail(400, 'CONFIG_MISSING', 'DEMO_PASSWORD需至少12字符')
    account_hash = HASHER.hash(password)
    with store.transaction():
        if reset:
            store.execute('DELETE FROM tickets WHERE demo=1')
            store.execute('DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE demo=1)')
            store.execute('DELETE FROM idempotency WHERE actor_id IN (SELECT id FROM users WHERE demo=1)')
        users = {}
        for username, name, role in [('student', '林同学', 'student'), ('admin', '陈老师', 'admin'), ('worker', '李师傅', 'worker')]:
            user = store.one('SELECT * FROM users WHERE username=?', (username,))
            if user and not user['demo']:
                fail(409, 'STATE_CONFLICT', '演示用户名已被真实账户使用')
            if not user:
                cursor = store.execute('INSERT INTO users(username,name,password_hash,role,demo) VALUES (?,?,?,?,1)',
                                       (username, name, account_hash, role))
                users[role] = cursor.lastrowid
            else:
                users[role] = user['id']
                if reset:
                    store.execute('UPDATE users SET password_hash=? WHERE id=?', (account_hash, user['id']))
        if store.one('SELECT id FROM tickets WHERE demo=1 LIMIT 1'):
            return
        examples = [
            ('宿舍洗手池水龙头持续漏水', '紫荆公寓 · 3栋 402室', '洗手池水龙头关闭后仍有水滴，今天早上发现，希望协助检查。', '水电', 'high', 'waiting'),
            ('自习室空调无法正常制冷', '图书馆 · 二楼 自习区', '空调可以启动，但运行半小时后室内仍然很热，昨天下午开始出现。', '空调', 'normal', 'assigned'),
            ('教学楼走廊照明灯不亮', '明德楼 · 三楼 东侧走廊', '走廊靠近楼梯口的两盏灯不亮，晚上通行较暗，昨晚发现。', '水电', 'urgent', 'working'),
            ('宿舍网络连接不稳定', '紫荆公寓 · 2栋 305室', '网线已连接，电脑网络每隔几分钟断开，重启后仍会出现。', '网络', 'normal', 'confirm'),
            ('教室座椅靠背松动', '博学楼 · 101教室', '第三排靠窗座椅靠背松动，坐下有明显晃动，今天发现。', '家具', 'normal', 'completed'),
            ('公共洗衣房排水异常', '紫荆公寓 · 一楼 洗衣房', '洗衣机排水时地面出现积水，现场已暂停使用并提醒同学。', '水电', 'high', 'waiting')]
        for title, location, description, category, priority, status in examples:
            ticket_id = store.execute('INSERT INTO tickets(owner_id,title,location,original_description,description,category,priority,demo) VALUES (?,?,?,?,?,?,?,1)',
                                      (users['student'], title, location, description, description, category, priority)).lastrowid
            audit(ticket_id, users['student'], 'create', None, 'waiting', '提交报修（演示数据）')
            before = 'waiting'
            transitions = [('assigned', 'assign', 'admin', '管理员已分配李师傅'), ('working', 'accept', 'worker', '已接单，开始现场检查'),
                           ('confirm', 'finish', 'worker', '已完成处理，请报修同学检查确认'), ('completed', 'confirm', 'student', '已确认恢复正常')]
            if status != 'waiting':
                for after, action, actor_role, note in transitions:
                    audit(ticket_id, users[actor_role], action, before, after, note)
                    before = after
                    if after == status:
                        break
                store.execute('UPDATE tickets SET status=?,assignee_id=?,version=(SELECT COUNT(*) FROM events WHERE ticket_id=?) WHERE id=?',
                              (status, users['worker'], ticket_id, ticket_id))
            if status == 'completed':
                store.execute('INSERT INTO reviews(ticket_id,rating,comment) VALUES (?,5,?)', (ticket_id, '处理及时，谢谢师傅！'))
