## Context

现有Flask/SQLite工厂、健康、错误和JSON日志已经运行，首条变更已归档；当前无业务数据/界面。已读取根AGENTS及六领域规范。

## Goals / Non-Goals

完成学生、管理员、维修人员闭环与可演示UI；真实注册三类型、提供演示凭据。不接真实模型、不实现短信邮件、找回密码、历史向量检索。

## Decisions

- 单体Jinja2+CSS+原生JS；路由→业务服务→仓储→SQLite。布局为深蓝侧栏、浅灰工作区、绿色操作色、表格/状态标签/详情时间线，移动端可折叠菜单。
- users表角色CHECK(student/admin/worker)，Argon2id散列；sessions表存随机256bit令牌的SHA256摘要、用户、CSRF nonce与8h过期时间。匿名会话用于登录/注册防CSRF；登录轮换令牌，退出删除服务器会话。HttpOnly、SameSite=Lax；COOKIE_SECURE在本机HTTP为false，HTTPS环境必须true。没有签名Cookie，不引入无用途的Flask SECRET_KEY。
- 学生公开注册；admin/worker必须匹配环境ADMIN_INVITE_CODE/WORKER_INVITE_CODE，长度>=16，无配置时禁该角色注册；DEMO_PASSWORD可选长度>=12，仅seed使用。注册用户名ASCII3–32，姓名2–40，密码12–128，登录失败统一错误；数据库持久限速：同会话登录/注册失败5次后15min拒绝。
- tickets存title(3–100)、location(3–160)、original_description/description(10–3000)、category(水电/网络/家具/空调/其他)、priority(normal/high/urgent)、owner、assignee、status、version、UTC时间；events不可覆盖；attachments存校验后图片BLOB，最多5MB/张、10张/单，PNG/JPEG/WebP；reviews每单最多一条1–5分和0–1000字评价。
- API /api/v1：GET session；POST register/login/logout；GET/POST tickets；GET ticket；POST tickets/id/actions；POST/GET附件；GET workers（管理员）、GET stats。返回data/request_id或error/code/message/details/request_id。权限不足403，未登录401，未知404，非法400，冲突409，限流429。学生只本人、worker只获派、admin全部；附件继承工单读权限，上传允许非终态的授权主体。
- 过滤status/category/priority/q、page>=1/page_size1–100默认20；拒绝未知字段、非法枚举/排序；默认created_at DESC,id DESC。写请求必须Idempotency-Key(UUID)，主体+操作+键唯一，24h同体重放、异体409；写事务BEGIN IMMEDIATE，version乐观锁及审计同事务，无外部调用。注册/登录通过独立事务与会话保护；附件内容摘要入幂等指纹。
- 状态：new→waiting；admin assign waiting→assigned；获派worker accept→working；worker finish需结果说明→confirm；owner confirm→completed；owner reopen需说明→working；owner cancel仅waiting/assigned→cancelled。note不改状态；admin classify调整非终态分类/优先级；终态不可修改。评价仅完成后本人且唯一。
- 迁移SQL001创建业务表，独立migrate-db命令，Docker init在init-db后migrate，再按DEMO_MODE选择seed。seed不覆盖已有用户/工单；reset-demo显式确认只重置带demo标记的数据，不触碰真实注册数据。所有演示凭据只存本机.env（不提交），最终直接向用户提供；示例无密码明文值。
- 基础整理仅按关键字建议分类、检查地点/现象/时间线索并回显原文，UI标“基础提示，未调用AI”；不自动提交/改事实或状态。

## Risks / Trade-offs

SQLite单机写入串行→短事务/超时/并发版本校验。图片BLOB增加备份体积→5MB/10张上限。邀请码泄露→外置并可轮换，默认拒绝。演示不等于生产→端口仅loopback；HTTPS设置Secure。

## Migration Plan

先一致备份，再运行001迁移；user_version记录，重复执行幂等。当前旧骨架不使用新表，可恢复旧镜像，数据回滚需先恢复备份。保留既有归档/证据。本次Docker部署持久卷不清空。
