# application-foundation Specification

## Purpose

建立校园报修与 AI 工单辅助系统的最小应用基础，使操作者能够通过明确环境配置启动独立应用、初始化并访问持久化数据库，在错误配置或依赖缺失时得到可定位且不泄露敏感内容的启动失败结果。

## Requirements

### Requirement: Independent application startup
系统 MUST 提供可独立创建、配置隔离的应用入口，先校验配置并验证已初始化数据库，再开始接收请求；本次不得暴露业务占位接口。

#### Scenario: F01 正常启动
- **GIVEN** 合法 APP_ENV 和 DATABASE_PATH，父目录可写，数据库已初始化且可查询
- **WHEN** 操作者使用文档中的最小应用入口启动服务
- **THEN** 服务成功启动，GET /health 返回 200，且无需登录
- **AND** 不注册登录、工单、分配、评价、统计或 AI 业务端点

#### Scenario: F02 多实例隔离
- **GIVEN** 两套合法配置分别指向两个独立临时数据库
- **WHEN** 同一进程先后创建两个应用并请求健康检查
- **THEN** 各应用查询各自数据库，更改一个应用配置或关闭其连接不影响另一个

### Requirement: Deterministic environment validation
系统 SHALL 仅从显式环境输入（测试允许显式映射）加载应用配置，不隐式发现 .env。APP_ENV 必填且仅接受 development/testing/production；DATABASE_PATH 必填且为 .sqlite3 后缀的绝对文件路径，拒绝内存库、URI、目录和相对路径。LOG_LEVEL 默认 INFO，仅接受 DEBUG/INFO/WARNING/ERROR；DB_TIMEOUT_SECONDS 默认2，只接受1–10的十进制整数。显式空值非法。配置错误 MUST 在监听前非零退出，只返回变量名、稳定代码和静态规则说明，不回显值。

#### Scenario: F03 必填配置缺失
- **GIVEN** 分别缺失 APP_ENV、DATABASE_PATH 或将其设为空字符串，其他配置合法
- **WHEN** 操作者启动应用
- **THEN** 每种输入均非零退出且不监听 HTTP，错误事件代码为 CONFIG_MISSING 并指出对应变量名，不包含该变量内容

#### Scenario: F04 非法配置拒绝
- **GIVEN** 其他字段合法，分别输入 APP_ENV=prod、LOG_LEVEL=TRACE、LOG_LEVEL 空值、DB_TIMEOUT_SECONDS 为0/11/1.5/空值/带空白值，或 DATABASE_PATH 为相对路径/URI/:memory:/目录/非 .sqlite3 文件/父目录不存在或不可写
- **WHEN** 操作者逐项启动应用
- **THEN** 每项均在监听前非零退出，返回 CONFIG_INVALID、字段名及静态合法范围，不回显路径、原值或堆栈

#### Scenario: F05 可选默认与边界
- **GIVEN** 必填项合法，分别省略可选项或设置 DB_TIMEOUT_SECONDS=1 和10，LOG_LEVEL 取各个合法枚举
- **WHEN** 加载配置并启动应用
- **THEN** 省略时分别采用 INFO 和2；所有合法边界均接受，且不读取未显式加载的主机 .env

### Requirement: Explicit database initialization and lifecycle
系统 MUST 提供显式、幂等的数据库初始化命令。正常启动及每个探测只能读写打开已存在数据库，不自动建库；每个请求独立连接并在请求结束时关闭，异常亦关闭，不共享跨请求连接。初始化不得创建业务表或清空既有数据。

#### Scenario: F06 初始化幂等
- **GIVEN** 合法配置和已存在可写父目录，但数据库文件尚不存在
- **WHEN** 执行文档中的 init-db，再向隔离库写入测试哨兵数据并再次执行 init-db
- **THEN** 首次创建数据库且查询成功，二次成功退出，哨兵数据仍可查询，无业务表被初始化

#### Scenario: F07 启动数据库不可达
- **GIVEN** 配置格式合法，但数据库缺失、文件不可读写、连接打开失败或探测查询超时
- **WHEN** 通过普通入口启动服务
- **THEN** 非零退出且不监听，错误代码为 DATABASE_INIT_FAILED，未创建替代空库；输出无数据库路径、SQL、异常原文或敏感值

#### Scenario: F08 请求连接释放
- **GIVEN** 已启动的应用及能观察连接关闭的隔离测试
- **WHEN** 分别执行成功健康请求与模拟查询异常的请求
- **THEN** 两种请求结束时连接均关闭，下一请求使用新连接，失败请求不会遗留未关闭连接
