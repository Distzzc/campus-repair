# 校园报修与 AI 工单辅助系统

面向学生、后勤管理员和维修人员，统一报修提交、任务分配、维修处理、进度查询和结果确认，解决描述不完整、进度不透明、分配不清晰和历史记录分散的问题。后续 AI 辅助整理描述、建议分类并提示补充信息。

## 当前进度

当前已有 OpenSpec 规划、`.env.example`、`.gitignore`、`.dockerignore` 和本 README。应用代码、依赖声明与锁文件、测试、Dockerfile、Compose、AGENTS.md 及领域规范尚未实现。

**下文运行命令是已确定的目标流程；须在对应文件实现后执行。目前不能据此启动应用。** 本地启动、容器运行、健康接口和 pytest 均待验证。实际结果见 [验证记录](docs/verification/)。

首条变更为 `bootstrap-project-foundation`：

- [提案](openspec/changes/bootstrap-project-foundation/proposal.md)：项目定位、四项能力和范围。
- [设计](openspec/changes/bootstrap-project-foundation/design.md)：目录职责、配置与接口契约、规范草案、Scenario 映射。
- [任务清单](openspec/changes/bootstrap-project-foundation/tasks.md)：实施顺序及验收依据。
- [应用基础规约](openspec/changes/bootstrap-project-foundation/specs/application-foundation/spec.md)、[健康与可观测性规约](openspec/changes/bootstrap-project-foundation/specs/health-observability/spec.md)、[可复现运行规约](openspec/changes/bootstrap-project-foundation/specs/reproducible-runtime/spec.md)、[工程治理规约](openspec/changes/bootstrap-project-foundation/specs/engineering-governance/spec.md)。

## 本次骨架范围

技术栈确定为 Python 3.12、Flask、SQLite、Jinja2、HTML/CSS/JavaScript、pytest 和 Docker Compose；生产容器使用 Gunicorn。前端采用服务端模板和适量 JavaScript，不引入独立前端框架、Redis、消息队列或微服务。

本次变更将交付应用工厂、配置校验、数据库连接、免认证 `/health`、统一错误、请求标识、JSON 日志、隔离测试、可复现启动及工程文档。业务页面、业务表和业务接口均不在本次实现范围内。

后续角色职责：学生报修、查看本人工单、补充信息、按阶段取消、确认结果并评价；管理员查看全部工单、调整分类/优先级、分配维修人员和查看基础统计；维修人员查看获派工单、接单、记录处理和提交结果。这些能力当前均未实现。

未来工单主流程：待分配 → 待接单 → 处理中 → 待确认 → 已完成。学生在待确认反馈未解决时返回处理中并保留负责人；学生只可在待分配/待接单取消为已取消。已完成和已取消是终态，其他转换默认拒绝。工单保留原始描述及完整操作历史。

## 目录与分层

当前代码尚未创建；目标目录及用途如下：

| 路径 | 职责 |
| --- | --- |
| `campus_repair/__init__.py`、`wsgi.py` | 应用工厂、最小运行入口 |
| `campus_repair/config.py`、`db.py`、`cli.py` | 配置校验、SQLite 生命周期、显式初始化 |
| `campus_repair/routes/health.py` | 唯一实际 HTTP 路由 `/health` |
| `campus_repair/errors.py`、`logging_config.py` | 错误、请求标识和结构化日志 |
| `tests/` | 使用独立临时数据库的 pytest 用例 |
| `scripts/init-container.sh` | 专属数据卷权限准备与初始化 |
| `docs/standards/`、`AGENTS.md` | 待创建的常驻规范及读取说明；草案见设计 D7 |
| `docs/verification/` | 实际执行的验证证据与待验证项 |
| `openspec/` | 初始化配置、能力规约与变更规划 |

未来依赖方向为路由 → 服务 → 数据访问 → SQLite：路由处理 HTTP，服务负责业务规则、权限和事务，数据访问负责读写且不依赖路由。当前健康检查直接调用数据库基础设施，不创建无实际用途的空服务层、仓储类、模板或业务端点。

## 获取代码与前置条件

仓库当前没有配置远程地址。请从项目维护者取得真实仓库 URL，再替换以下占位值；也可使用已取得的完整源码副本，直接进入项目根目录。

```sh
git clone '替换为维护者提供的真实仓库URL' campus-repair
cd campus-repair
```

本地流程面向 macOS/Linux 的 shell，需要 Python 3.12、venv、pip 和 curl；容器流程需要 Docker Engine 或 Docker Desktop，以及支持 `docker compose` 的 Compose v2。具体已验证的补丁版本、平台及镜像 digest 在实现运行验证后记录，不使用隐含全局 Python 包。

## 配置填写

先复制已提供的示例：

```sh
cp .env.example .env
```

本地运行时，创建 `instance/`，将 `.env` 中的 `DATABASE_PATH` 替换为本机项目的**绝对路径**，例如 `/your/project/campus-repair/instance/campus-repair.sqlite3`；这只是填写格式，须替换为实际路径。可在项目根目录运行 `pwd` 确认目录。路径含空格时在 `.env` 中用引号包住整个值。不得提交真实 `.env`。

| 变量 | 必填/省略时默认 | 合法范围与用途 |
| --- | --- | --- |
| `APP_ENV` | 必填，无默认 | 精确为 `development`、`testing`、`production` |
| `DATABASE_PATH` | 必填，无默认 | `.sqlite3` 后缀的绝对文件路径；拒绝 URI、`:memory:`、相对路径和目录；父目录已存在且可写，已有文件须为可读写普通文件 |
| `LOG_LEVEL` | 可选，`INFO` | `DEBUG`、`INFO`、`WARNING`、`ERROR`；不抑制请求完成日志 |
| `DB_TIMEOUT_SECONDS` | 可选，`2` | 十进制整数 1–10；数据库等待超时秒数，拒绝浮点、空白等非法输入 |
| `HOST_PORT` | Compose 可选，`8000` | 十进制整数 1024–65535；主机绑定 `127.0.0.1`，本地 Gunicorn 使用显式 `--bind` 参数 |

必填项缺失或为空时以 `CONFIG_MISSING` 启动失败；非法枚举、路径或范围以 `CONFIG_INVALID` 失败；可选项显式空值同样非法。未初始化、不可读写或不可连接的数据库以 `DATABASE_INIT_FAILED` 失败。失败应在监听前发生，只输出变量名、稳定代码和静态说明，不回显配置值、路径或堆栈。本阶段无鉴权功能，不要求无用途的 `SECRET_KEY`。

配置加载方式按设计实现：

- 应用只读取进程环境，不自动发现 `.env`；本地用 `dotenv -f .env run -- …` 显式加载，避免外部 shell 已设置同名变量造成混淆。
- 初始化命令使用 `FLASK_SKIP_DOTENV=1` 禁止 Flask 再隐式加载文件。
- Compose 的 `--env-file .env` 用于插值，不意味着应用会读取主机文件。Compose 将明确传入 `APP_ENV=production`、`DATABASE_PATH=/data/campus-repair.sqlite3` 及日志/超时白名单项；主机 `DATABASE_PATH` 不透传，`HOST_PORT` 仅控制映射并须先校验。

## 本地启动（待骨架实现后验证）

前置文件：`pyproject.toml`、两份依赖锁、应用代码和 `wsgi.py`。以下命令须在项目根目录执行；当前这些前置文件尚未提供。

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
mkdir -p instance
```

按上一节填写 `.env` 后，显式初始化数据库：

```sh
FLASK_SKIP_DOTENV=1 dotenv -f .env run -- python -m flask --app campus_repair.cli:create_cli_app init-db
```

初始化只创建数据库并检查查询，无业务表；重复运行不得清空既有数据。普通启动只连接已有库，不创建数据库或父目录。随后启动：

```sh
dotenv -f .env run -- gunicorn --bind 127.0.0.1:8000 --workers 1 wsgi:app
```

在另一个终端检查健康状态。需要其他本地端口时修改 `--bind` 和访问地址；`HOST_PORT` 不影响上述本地命令。前台进程用 `Ctrl+C` 停止，数据库仍保留；生产运行禁用 Flask 开发服务器、调试器和自动重载。

## 容器启动（待容器文件实现后验证）

前置文件：Dockerfile、compose.yaml、容器初始化脚本及应用/依赖。当前均尚未提供。准备好 `.env` 后，一条命令构建、显式初始化并启动：

```sh
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
```

目标 Compose 行为：一次性初始化服务只管理专属卷根及数据库文件的权限，然后降权执行 `init-db`；初始化失败阻断 app。应用以 UID/GID 10001 运行，Gunicorn 单 worker，容器内部监听8000。镜像固定 Python 3.12 补丁标签与 digest，不依赖本机源码挂载。

数据库使用 Compose 项目隔离的 named volume `campus_repair_data`，挂载 `/data`，文件为 `/data/campus-repair.sqlite3`。本机 `.env` 的绝对路径仅供本地运行，与容器路径不同。容器重建和重复初始化须保留既有数据。

查看日志和停止服务：

```sh
docker compose --env-file .env logs --tail 100 app
docker compose --env-file .env down
```

日常 `down` 保留数据卷；不要将删除卷的 `down -v` 作为日常停止命令。服务须处理 SIGTERM，在15秒宽限内退出。健康探针每10秒检查一次，超时3秒、重试3次、启动宽限10秒；这些行为仍待实际验证。

## 健康检查与 API 契约（待实现）

```sh
curl -i http://127.0.0.1:8000/health
```

容器 `HOST_PORT` 改动后相应替换访问端口。`GET /health` 无需登录，每次新开连接执行 `SELECT 1`，不以文件存在检查代替查询。

正常返回 HTTP 200；`request_id` 实际为服务端生成的 UUID v4：

```json
{"status":"ok","checks":{"database":"ok"},"request_id":"<uuid>"}
```

运行期数据库不可用或查询失败时返回 HTTP 503：

```json
{"error":{"code":"DEPENDENCY_UNAVAILABLE","message":"Service temporarily unavailable","details":{}},"request_id":"<uuid>"}
```

未知 API 返回404 `NOT_FOUND`，不支持方法返回405 `METHOD_NOT_ALLOWED`，未捕获异常返回500 `INTERNAL_ERROR`；统一 JSON 错误结构见设计 D4。响应头 `X-Request-ID`、正文和日志保持一致，忽略外部传入的标识。

日志每行一个 JSON，包含时间、级别、请求标识、方法、路由模板或 `<unmatched>`、状态码和耗时。不输出原始 URL、查询串、完整正文、密码、令牌、密钥、敏感报修信息、数据库路径、SQL 或原始异常。

## 运行测试与验收（待实现）

本地激活虚拟环境并安装测试锁后：

```sh
python -m pytest -q
```

容器测试使用独立 target/profile，不挂载运行数据卷，不暴露端口；显式运行：

```sh
docker compose --env-file .env run --rm --no-deps test
```

用例按正常、失败、边界组织，每个测试使用隔离临时库，不读取主机 `.env` 或真实数据。设计 D8 映射了26个 Scenario：F01–F08、H01–H08、R01–R06、G01–G04。必需测试失败或必需验证未执行时，不能标记实现完成。

规划文件可独立校验（需要已安装 OpenSpec 1.13.0）：

```sh
openspec validate bootstrap-project-foundation --type change --strict --no-interactive
```

严格校验仅说明规划结构有效，不能替代启动、pytest、持久化或备份恢复验收。验证记录放在 `docs/verification/`，包含环境版本、命令、退出结果、证据和限制，未执行项标记“待验证”。

## 数据与工程约束

`.gitignore` 排除本地环境、SQLite及其 journal/WAL/SHM、上传、日志、虚拟环境、缓存和构建产物；`.dockerignore` 同时阻止这些文件和 Git 元数据进入构建上下文。`.env.example` 和依赖锁保留。忽略规则不会移除已被 Git 跟踪的文件，提交前仍应检查实际内容。

后续迁移必须版本化，发布保留旧镜像 digest；不兼容迁移回滚时先恢复备份。备份用 SQLite backup API 或停服后一致性复制，不能热拷单个活动文件。备份恢复、卷持久化和停机演练仅在隔离临时数据上验证；具体运维操作文档待对应任务交付。

未来业务默认拒绝、逐资源授权；附件继承工单权限；非法筛选必须报错；服务层划定事务，事务内不得调用外部服务。完整强制规则、检查方法与适用阶段见设计 D7；根 AGENTS.md 和六份领域规范待任务4.2创建。

## 后续独立变更

1. 用户登录与角色权限。
2. 学生报修和本人工单查询。
3. 管理员分配与维修处理流程。
4. 结果确认、评价和附件。
5. AI 描述整理与分类建议。
6. 基础统计及可选相似历史工单检索。

AI 仅提供可编辑草稿、分类建议及缺失信息提示，必须保留学生原文；不得编造故障原因、地点或处理结果，不得自动提交、分配或修改状态。不可用时仍须能手动报修。提示词版本、输出校验、超时降级及评测阈值由后续 AI 变更实现；当前没有模型调用、向量检索或 MCP。
