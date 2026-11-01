# health-observability Specification

## Purpose

向操作者提供不依赖登录的真实依赖健康信号，向调用方提供一致的 JSON 错误和请求标识，并通过可关联的结构化日志诊断成功、失败和异常请求，同时保护数据库位置、密钥及潜在报修隐私不被公开或记录。

## Requirements

### Requirement: Public dependency health
GET /health SHALL 无需身份认证，每次新开数据库连接并真实执行 SELECT 1 检查返回值。成功 MUST 返回200及精确结构 `{"status":"ok","checks":{"database":"ok"},"request_id":"<uuid>"}`；运行期连接/查询错误或超时 MUST 返回503及统一错误，code 为 DEPENDENCY_UNAVAILABLE、message 为 Service temporarily unavailable、details 为 {}。不得返回数据库路径、SQL、堆栈或配置。

#### Scenario: H01 健康检查成功
- **GIVEN** 服务已正常启动，数据库可连接且查询返回1，客户端无登录凭证
- **WHEN** 客户端 GET /health
- **THEN** 返回200和规定 JSON，Content-Type 为 application/json，观测到本次请求实际执行查询

#### Scenario: H02 运行期依赖失效与恢复
- **GIVEN** 服务已启动并完成一次成功查询
- **WHEN** 隔离测试移走数据库文件，或注入连接失败/查询失败/超时，再请求 /health
- **THEN** 每种失败返回503和规定的 DEPENDENCY_UNAVAILABLE 错误，无替代空库产生
- **AND** 恢复原库或解除故障后下一次请求返回200，无需重启应用

### Requirement: Consistent JSON errors
系统 SHALL 对所有 HTTP 错误返回精确顶层 `error` 与 `request_id`；error 精确包含 code、message、details。details 本次恒为 {}。未知路径为404 NOT_FOUND/Resource not found；方法错误为405 METHOD_NOT_ALLOWED/Method not allowed；未捕获异常为500 INTERNAL_ERROR/Internal server error；其他 HTTP 错误保留状态及必要协议头，使用 HTTP_ERROR/Request failed。所有错误为 application/json，不泄露内部实现信息。

#### Scenario: H03 未知 API 路由
- **GIVEN** 服务已启动，本次未提供业务 API
- **WHEN** 分别 GET /api、/api/v1/tickets 和随机未知非 API 路径
- **THEN** 均返回404、NOT_FOUND 和规定 JSON 结构，不返回 HTML、占位成功或内部路由清单

#### Scenario: H04 方法不允许
- **GIVEN** 服务已启动
- **WHEN** 客户端 POST /health
- **THEN** 返回405、METHOD_NOT_ALLOWED、规定 JSON 和正确 Allow 头，包含 GET，不包含 POST

#### Scenario: H05 错误信息脱敏
- **GIVEN** 仅在测试应用注入分别产生500与其他标准 HTTP 错误的路由，异常中包含数据库路径、SQL 和敏感哨兵字符串
- **WHEN** 请求测试路由及触发503的健康检查
- **THEN** 对应返回500 INTERNAL_ERROR、原HTTP状态 HTTP_ERROR、503 DEPENDENCY_UNAVAILABLE；正文符合统一结构，保留必要协议头，不含哨兵、路径、SQL、异常原文或堆栈
- **AND** 测试路由不进入生产路由表

### Requirement: Server generated request identity
系统 MUST 为每个请求生成不同的 UUID v4，忽略传入 X-Request-ID；所有响应（含错误）X-Request-ID、JSON request_id 及对应日志标识一致。HEAD 无正文时仍须有响应头及日志。

#### Scenario: H06 请求标识一致与隔离
- **GIVEN** 客户端连续请求200、404、405、503及测试500，部分请求传入相同或非法 X-Request-ID
- **WHEN** 收集各响应头、正文及日志，并另发 HEAD /health
- **THEN** 每次标识均为不同的有效 UUID v4，不采用传入值，头/正文/日志一致；HEAD 无正文但头和日志标识一致

### Requirement: Single line structured request logging
系统 MUST 对每个请求输出恰好一条 JSON request_completed 日志，包含 timestamp（UTC RFC3339毫秒）、level、event、request_id、method、path、status_code（整数）和 duration_ms（非负数）。path 为路由模板或固定 `<unmatched>`。2xx/3xx 为 INFO，4xx/503 为 WARNING，其余5xx为 ERROR；LOG_LEVEL 不得抑制完成日志。不得记录原始 URL、查询串、请求正文、headers/cookies、密码、令牌、密钥、敏感报修信息、SQL或原始异常。

#### Scenario: H07 JSON日志完整且覆盖失败
- **GIVEN** 正常与故障注入请求，LOG_LEVEL 分别为默认和 ERROR
- **WHEN** 执行200/404/405/503/500请求并逐行解析 stdout
- **THEN** 每个请求恰有一条可解析 JSON 完成事件，字段类型/级别符合规定，耗时>=0，时间格式有效，标识可关联；无文本 access log 或多行堆栈

#### Scenario: H08 日志敏感信息不落盘
- **GIVEN** 请求正文、查询串、未知路径、Cookie、Authorization、X-Request-ID 和故障异常中分别放入独特敏感哨兵
- **WHEN** 请求 /health、未知路径以及产生500的测试路由
- **THEN** 所有输出行均不含任何哨兵，已知路径记录模板，未知路径只记录 <unmatched>，响应同样无敏感值
