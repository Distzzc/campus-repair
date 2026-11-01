## Why

校园报修与 AI 工单辅助系统面向学生、后勤管理员和维修人员，统一报修、分配、处理、查询和结果确认，解决描述不完整、进度不透明、分配不清晰和历史分散的问题。仓库目前仅有 OpenSpec 初始化文件，需要先建立可运行、可验证的工程基础，再逐步引入业务和 AI。

## What Changes

- 明确产品定位、角色、术语、状态流和后续路线图，建立常驻工程规范及检查方法。
- 规划 Python 3.12 / Flask 应用工厂、最小入口、环境配置校验和 SQLite 连接管理。
- 提供免认证 `GET /health`，通过真实数据库查询返回 200 或 503；提供统一 API 错误、请求标识和 JSON 日志。
- 规划 pytest 隔离测试、Docker Compose 持久化运行、README 和真实验证记录。
- 本次 propose 仅创建规划文件与规划校验记录。根目录 AGENTS.md、docs/standards/、代码、依赖、Dockerfile、Compose、.env.example、.gitignore 和 README 均由后续 apply 按本提案创建；规范草案完整保存在 design.md，避免提前改变仓库运行行为。

## Capabilities

### New Capabilities

1. `application-foundation`（C1）：目录职责、应用工厂、启动配置、SQLite 生命周期。
2. `health-observability`（C2）：健康检查、错误契约、请求标识、结构化日志与脱敏。
3. `reproducible-runtime`（C3）：隔离测试、本地及容器启动、数据持久化与运维验证。
4. `engineering-governance`（C4）：产品边界、常驻工程规范、Scenario 映射、完成定义和证据记录。

### Modified Capabilities

无。`openspec list --specs` 确认没有已有能力；保留 config.yaml、.gitkeep 和已生成的技能文件。

## Impact

新增规划根为 `openspec/changes/bootstrap-project-foundation/`；实现阶段拟新增 `campus_repair/`、`tests/`、项目运行文件和工程文档。本次仅新增 API 契约 `/health`；未来业务 API 采用 `/api/v1`，但本次不创建业务端点或占位业务代码。技术栈为 Python 3.12、Flask、SQLite、Jinja2、HTML/CSS/JavaScript、pytest、Docker Compose；生产容器使用 Gunicorn。

### Scope and Non-goals

交付最小启动、配置、数据库、健康检查、错误/日志、测试、可复现运行和规范。无登录注册、工单接口、图片上传、分配、评价、统计、AI 调用、向量检索或 MCP；无独立前端框架、Redis、队列或微服务。本次不提交、推送或归档，不执行 apply。

### Roadmap

按独立变更依次推进：①登录与角色权限；②学生报修与本人工单查询；③管理员分配与维修处理；④结果确认、评价和附件；⑤AI 描述整理与分类建议；⑥基础统计及可选相似历史工单检索。详细业务约束与适用阶段见 design.md；上述内容不进入本次实现待办。
