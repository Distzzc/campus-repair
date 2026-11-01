## MODIFIED Requirements

### Requirement: Independent application startup
系统 MUST 提供可独立创建、配置隔离的应用入口，先校验配置并验证已初始化数据库，再开始接收请求；提供已实现的认证、工单和页面路由，不得暴露无实际用途的业务占位接口。

#### Scenario: F01 正常启动
- **GIVEN** 合法 APP_ENV 和 DATABASE_PATH，父目录可写，数据库已初始化且可查询
- **WHEN** 操作者使用文档中的最小应用入口启动服务
- **THEN** 服务成功启动，GET /health 返回 200，且无需登录
- **AND** 注册实际登录、工单、分配、评价和统计端点；真实AI调用仍未引入

#### Scenario: F02 多实例隔离
- **GIVEN** 两套合法配置分别指向两个独立临时数据库
- **WHEN** 同一进程先后创建两个应用并请求健康检查
- **THEN** 各应用查询各自数据库，更改一个应用配置或关闭其连接不影响另一个

