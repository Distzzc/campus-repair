## Why

当前只有工程骨架，浏览器不能完成报修。用户明确授权本次完成主要业务与UI并在Docker运行，选择手动报修/基础提示而非真实模型，要求三类演示账号及真实分类注册。

## What Changes

- 学生直接注册；维修/管理员凭角色邀请码注册；Argon2id密码散列、可撤销会话、CSRF与逐工单授权。
- 报修、本人/全部/获派列表、筛选分页、分配接单、记录、结果确认/退回、取消、评价、图片附件、统计。
- 响应式中文工作台、注册登录、详情时间线、表单四态和非模型基础提示。
- 版本化迁移、显式演示seed/reset、环境邀请码/演示密码、Docker构建启动及验证。

## Capabilities

### New Capabilities
- `identity-access`: 三角色注册登录、邀请码与授权。
- `repair-workflow`: 六态工单、事务审计、幂等、附件与统计。
- `repair-workspace`: 可实际操作的中文UI、基础提示、演示部署。

### Modified Capabilities
- `application-foundation`: 工厂注册真实业务路由，替代骨架阶段仅health的限制。
- `engineering-governance`: 当前产品阶段由仅基础更新为业务闭环，AI保持后续。
- `reproducible-runtime`: 容器增加显式迁移与可选seed，保留既有持久化/健康契约。

## Impact

新增实际用途的services/repositories/templates/static及迁移SQL；新增Argon2与Pillow运行依赖。无真实AI调用、检索、MCP或外部服务。用户已授权本次实现和本机Docker部署，不自动Git提交/推送/归档。
