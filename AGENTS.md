# Campus Repair 常驻工程约束

项目：校园报修与 AI 工单辅助系统。Python 3.12 / Flask / SQLite / Jinja2 / pytest / Docker Compose 单体；不引入独立前端、Redis、消息队列或微服务。

开始任务先读取当前变更的 proposal.md、design.md、specs/ 和 tasks.md，确认授权范围；按下表读取全部涉及领域的规范。不得覆盖 `.agents/skills/` 和 OpenSpec 初始化文件。没有业务逻辑时不创建空服务、仓储、模型或业务端点。后续业务规则仅在对应变更中实现。

| 修改领域 / 读取时机 | 必须读取 |
| --- | --- |
| 需求、页面、表单、状态前 | [产品规范](docs/standards/product.md) |
| 路由、配置、服务、数据库前 | [后端规范](docs/standards/backend.md) |
| 配置、权限、输入输出、附件、出站请求前 | [安全规范](docs/standards/security.md) |
| 实现、测试、验证记录前 | [测试规范](docs/standards/testing.md) |
| 构建、依赖、容器、数据、发布前 | [运维规范](docs/standards/operations.md) |
| AI 设计、提示词、调用、评测前 | [AI 规范](docs/standards/ai.md) |

强制要求：路由→服务→数据访问，禁止反向依赖；snake_case 模块/函数/变量，PascalCase 类型，UPPER_SNAKE_CASE 配置/常量。默认拒绝、逐资源授权；配置和密钥外置；禁止记录敏感输入和原始异常。测试从 Scenario 推导，隔离数据库，不使用真实数据。事务内不得调用外部服务。详细规则、适用阶段和检查方法以上述文档为准。

验证使用 `python -m pytest -q`、Compose test 和 OpenSpec严格校验；必需检查失败/未执行阻断完成。只有实现、规约、测试、文档一致且真实证据齐备才勾选任务；验证记录写入 `docs/verification/`，课程交付索引写入 `docs/lesson-07/`。不得虚构通过、跨会话实验或另一人异机评审；未执行写“待验证”。不自动提交、推送或归档。
