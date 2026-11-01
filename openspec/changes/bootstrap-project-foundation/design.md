## Context

动机见 proposal.md。检查时仓库只有 `.agents/skills/`、`openspec/config.yaml`、`openspec/specs/.gitkeep` 和 `openspec/changes/archive/.gitkeep`，没有 AGENTS.md、业务代码、测试、依赖、README 或 Git 元数据。config.yaml 为合法映射，仅配置 `schema: spec-driven`，无有效 context 字段或定制 rules；CLI 为 1.13.0，context 解析根为本仓库。所有初始化文件保留，不重新 init 或修改技能文件。

规划顺序为 proposal → design/specs → tasks；本次仅写这些规划产物及 docs/verification/ 的规划验证记录。以下结构、命令和行为均是待实现契约，不代表已存在或已验证。

## Goals / Non-Goals

**Goals:** 用最小实际依赖形成可启动、可诊断、可复现的单体基础；提前固定配置、健康、错误和验证契约，让新会话可独立实施。

**Non-Goals:** 不为未来业务建立空类、仓储接口或路由；本次无业务页面和业务表，无数据库迁移框架或 AI SDK。业务方向仅作为后续规范，适用阶段明确区分。

## Decisions

### D1. 工程结构与依赖方向

拟在 apply 创建：

```text
campus_repair/
  __init__.py             # create_app：加载/校验配置，注册基础设施和健康路由
  config.py               # 环境解析及无敏感值的启动错误
  db.py                   # sqlite3 连接、显式初始化、请求结束关闭
  cli.py                  # 专用初始化工厂，仅注册 init-db
  errors.py               # JSON 错误、HTTPException/未捕获异常处理
  logging_config.py       # 请求标识、耗时、JSON 输出
  routes/health.py        # 只有 /health
wsgi.py                   # app = create_app()，供 Gunicorn 使用
pyproject.toml            # Python ==3.12.*；依赖声明、pytest 配置
requirements.lock         # 运行依赖及完整传递依赖精确锁定
requirements-dev.lock     # 包含运行锁文件，追加 pytest 完整精确版本
scripts/init-container.sh # 专属卷权限准备、降权、显式初始化
tests/                    # conftest.py 与配置/健康/错误/日志/数据库测试
Dockerfile
compose.yaml
.env.example
.gitignore
.dockerignore
README.md
AGENTS.md
docs/standards/            # product.md backend.md security.md testing.md operations.md ai.md
docs/verification/         # 规划与后续实现证据
```

路由解析 HTTP、调用基础设施/未来服务并组织响应；服务承载业务规则、逐资源权限和事务；数据访问只负责读写。方向为路由 → 服务 → 数据访问 → SQLite；配置、日志和错误为公共基础设施，数据访问不得导入路由。本次健康无业务规则，直接使用 db.py 执行探测；不创建空 services/、repositories/、models/、templates/ 或 static/。未来有首个实际用途时再新增服务/数据访问模块、Jinja2 模板与静态文件。服务端模板与适量 JS 能减少部署组件；不采用独立前端、Redis、队列和微服务。

应用工厂每次创建独立配置和日志状态，不在 import 阶段读取配置或打开连接；wsgi 导入执行工厂是唯一入口副作用。测试可通过工厂注入配置映射，仍必须经过同一验证，不绕过合法性检查。使用 Python 标准库 sqlite3；不引入 ORM，避免零业务阶段增加模型和迁移负担。

### D2. 配置契约和启动顺序

应用配置只来自进程环境；测试显式映射覆盖环境，映射同样校验。应用本身不自动发现或加载 `.env`，也不依赖 Flask 的隐式 dotenv 行为；本地用 `python-dotenv` CLI 显式加载，Compose 用 `--env-file .env` 插值后按白名单传入容器。README 明确这三者的区别。

| 变量 | 必填/默认 | 合法规则与用途 |
| --- | --- | --- |
| APP_ENV | 必填，无默认 | 精确 `development`、`testing`、`production`，区分运行环境；生产禁用调试器和重载 |
| DATABASE_PATH | 必填，无默认 | 非空绝对文件路径，文件名后缀 `.sqlite3`；拒绝 `:memory:`、URI、目录及相对路径；父目录须已存在且可写，文件若存在须为普通文件；读写权限在数据库启动探测时校验 |
| LOG_LEVEL | 可选 `INFO` | 精确 `DEBUG`、`INFO`、`WARNING`、`ERROR`；设置事件最低级别，所有请求完成日志至少 INFO 且不被此变量抑制 |
| DB_TIMEOUT_SECONDS | 可选 `2` | 十进制整数 1–10，拒绝浮点、空白和非数字；用于 SQLite busy timeout，连接及探测均遵守 |
| HOST_PORT | Compose 可选 `8000` | 十进制整数 1024–65535；主机只绑定 127.0.0.1，非 Flask 应用配置 |

必填缺失/空值报 `CONFIG_MISSING`，非法枚举/格式/范围/路径报 `CONFIG_INVALID`；错误只含代码、变量名和静态规则说明，不回显值、路径或异常。可选变量显式空字符串亦非法，不退回默认。无鉴权功能时不要求无用途的 SECRET_KEY；未来会话变更再引入并定义轮换。未知环境变量不装入应用配置。所有字段先解析再校验，不使用字符串真假值转换。

启动流程：解析 → 校验所有字段 → 配置 JSON 日志 → 检查目录与文件权限 → 检查已有文件读写权限、用读写连接打开数据库并执行 `SELECT 1` → 注册应用入口。启动不创建数据库和父目录；数据库缺失/文件不可读写/打不开/锁超时导致 `DATABASE_INIT_FAILED`，进程非零退出且不监听端口。配置错误只输出独立 JSON 启动事件（`request_id` 等请求字段为 null），不产生堆栈/原始值。数据库初始化由显式 `flask --app campus_repair.cli:create_cli_app init-db` 命令负责：该子命令复用配置校验但跳过「数据库必须已存在」的启动探测，创建空文件并执行 `SELECT 1`，无业务表，重复执行不清空已有数据。CLI 注册方式必须允许缺库时执行 init-db，普通工厂及 wsgi 不允许绕过探测；实现使用专门 CLI 工厂入口 `campus_repair.cli:create_cli_app` 分离初始化模式，README 的 init-db 命令据此使用该入口。最终命令统一见 D6，避免隐藏开关。

选择显式初始化而非启动时自动建库，使挂载错误不会被无声替换为空库。目录由操作者/容器启动脚本负责创建；应用不递归创建任意路径。

### D3. SQLite 生命周期与持久化

初始化使用可创建模式；正常运行使用 SQLite URI `mode=rw`（对路径正确 URI 编码），防止运行时文件删除后自动创建空库。每次健康探测新开连接，放入请求上下文，结束无论成功失败均关闭；不得跨线程/进程共享连接。每个连接设置 `foreign_keys=ON` 和指定 busy timeout；本次无写事务，不启用 WAL 或共享内存模式。短连接每次重新打开并读取查询返回的数字 1，避免旧连接掩盖挂载消失；不得用文件存在性代替查询。

本地数据库位于项目 `instance/campus-repair.sqlite3`，容器位于 `/data/campus-repair.sqlite3`，通过 Compose 逻辑 named volume `campus_repair_data:/data` 持久化（保留项目名前缀，不设全局固定 name，支持隔离验证）。配置必须使用各自绝对路径；容器路径不得从本机绝对路径直接透传。不挂载源码覆盖镜像。故障注入用隔离临时库重命名/移除，下一次 `/health` 必须失败，恢复文件后下一次可成功，无需重启。单进程、单 worker 起步，SQLite 适用于单机低并发；以后需要并发写扩展时另提数据库变更。

### D4. HTTP 契约

所有此处 JSON 均使用 `application/json`，UTF-8；字段名精确如下，示例 request_id 为动态 UUID v4 字符串。所有响应包括 `X-Request-ID`，值与正文中的 request_id（如有）及日志一致。使用服务端生成的 UUID v4，每请求一个，忽略任何外部 X-Request-ID，不信任用户提供标识。

| 场景 | 状态码 | 正文（键集合固定） |
| --- | --- | --- |
| `GET /health`，真实查询成功 | 200 | `{"status":"ok","checks":{"database":"ok"},"request_id":"<uuid>"}` |
| `GET /health`，运行期间连接/查询失败或超时 | 503 | `{"error":{"code":"DEPENDENCY_UNAVAILABLE","message":"Service temporarily unavailable","details":{}},"request_id":"<uuid>"}` |
| 未知 `/api`、`/api/…` 路由 | 404 | `{"error":{"code":"NOT_FOUND","message":"Resource not found","details":{}},"request_id":"<uuid>"}` |
| 其他未知路径（本次全站统一） | 404 | 同上 |
| 不支持的方法，例如 `POST /health` | 405 | `{"error":{"code":"METHOD_NOT_ALLOWED","message":"Method not allowed","details":{}},"request_id":"<uuid>"}`，保留正确 Allow 头 |
| 未捕获异常 | 500 | `{"error":{"code":"INTERNAL_ERROR","message":"Internal server error","details":{}},"request_id":"<uuid>"}` |

本次只提供 /health；Flask 自动 HEAD/OPTIONS 语义可保留，HEAD 不返回正文，非业务接口。未知业务 API 不得用占位 200 或 501。统一错误禁止使用异常原文、SQL、数据库路径、堆栈或配置值。其他标准 HTTP 异常保留 HTTP 状态和必要协议头，固定通用 code `HTTP_ERROR`、message `Request failed`、details `{}`。未来验证失败约定 400 `VALIDATION_ERROR`，仅允许字段名/稳定错误标识进入 details；身份不足 401 `UNAUTHENTICATED`、无权限 403 `FORBIDDEN`、状态冲突 409 `STATE_CONFLICT`，后续变更再定义具体端点与 Scenario，本次不生成处理业务的代码。

### D5. 日志、隐私和请求结束

stdout 一行一个 JSON，无前缀和多行堆栈。请求完成事件精确包含 `timestamp`（UTC RFC3339 毫秒）、`level`（INFO/WARNING/ERROR）、`event`（`request_completed`）、`request_id`（UUID v4）、`method`、`path`、`status_code`（整数）、`duration_ms`（非负数）；503/4xx 为 WARNING，5xx（503 除外）为 ERROR，其余 INFO。计时用单调时钟，覆盖异常请求；每次请求恰好一个完成事件，关闭 Gunicorn 默认文本 access log，框架/服务器事件也统一 JSON 格式。

path 使用匹配到的路由模板（本次 `/health`），未知路由固定 `<unmatched>`；不记录原始路径、查询串或 URL，以防输入中夹带隐私。允许附加字段仅为 `error_code`；不记录原始异常、headers/cookies、密码、令牌、密钥、完整正文、故障描述、地点、附件或 AI 提示词。启动/停机事件允许 method/path/status_code/duration_ms/request_id 为 null，并使用 `startup_failed`、`startup_completed`、`shutdown` 等 event。LOG_LEVEL 不得关闭请求完成审计；此变量控制其他事件。默认不启用 traceback，调试环境同样遵守脱敏。

### D6. 可复现运行和测试入口

实现时锁定 Python 3.12 的运行依赖（Flask、Gunicorn、python-dotenv CLI）与 pytest 及完整传递版本。pyproject 声明范围，requirements.lock 精确固定运行依赖，requirements-dev.lock 包含运行锁及测试依赖，并与声明一致；安装使用对应锁文件，不依赖全局包。Docker 基础镜像使用 Python 3.12 的明确补丁标签及 digest，构建记录 digest，不使用 latest；只在 apply 时解析实际可用版本并记录，提案不虚构版本解析结果。不需要联网搜索来完成本次设计。

.env.example 只含 APP_ENV=development、`DATABASE_PATH=/absolute/path/to/campus-repair/instance/campus-repair.sqlite3`、LOG_LEVEL=INFO、DB_TIMEOUT_SECONDS=2、HOST_PORT=8000，注明占位路径必须替换，不含密钥。本地配置与容器示例共用同一文件，但 Compose 明确覆盖 APP_ENV=production、DATABASE_PATH=/data/campus-repair.sqlite3，仅传入 LOG_LEVEL 和 DB_TIMEOUT_SECONDS，HOST_PORT 只参与端口映射。解释 Compose env_file 与应用读取无关，避免使用 `env_file` 全量注入主机路径。

README 的待实现独立复现流程（仓库尚无远程 URL，不编造地址；最终填入真实 URL，或明确让读者提供代码来源）：

```sh
git clone <实际仓库URL> campus-repair
cd campus-repair
cp .env.example .env
# 按说明填写本地绝对路径；必须先完成这一步
# 一条命令构建、初始化并启动；容器使用 /data 路径
docker compose --env-file .env up --build -d
curl -i http://127.0.0.1:8000/health
docker compose --env-file .env run --rm --no-deps test
docker compose --env-file .env down
```

HOST_PORT 修改后相应替换 curl 端口；Compose 初始化服务在 app 启动及端口发布前对该变量执行显式范围校验，非法输出 CONFIG_INVALID 和 HOST_PORT，不回显输入。缺省采用8000，显式空值必须保留并拒绝，不用会将空值替换默认的插值写法。app 服务 healthcheck 使用 Python urllib 请求 `http://127.0.0.1:8000/health`，10 秒间隔、3 秒超时、3 次重试、10 秒 start_period。Gunicorn 监听 `0.0.0.0:8000`，1 worker，超时 30 秒，graceful-timeout 10 秒；Compose stop_grace_period 15 秒，脚本通过 exec 转发 SIGTERM。镜像以固定非 root UID/GID 10001 运行。初始化专用一次性服务以 root 仅创建/修正 /data 所有权，再降权调用 init-db；app 依赖该服务成功完成，不在 app 启动时清空或创建库。初始化失败时应用不得启动。明确不对已有任意目录递归 chown；只管理专属卷根及本项目数据库文件。test 服务属于 test profile（默认 up 不启动，显式 run 可执行），使用测试构建 target、隔离临时目录、不挂载数据卷、不暴露端口；生产 target 不装 pytest。

本地流程：`python3.12 -m venv .venv`，激活，`python -m pip install -r requirements-dev.lock`，`python -m pip install --no-deps -e .`，创建 instance/，填写 .env；初始化命令为 `FLASK_SKIP_DOTENV=1 dotenv -f .env run -- python -m flask --app campus_repair.cli:create_cli_app init-db`；启动 `dotenv -f .env run -- gunicorn --bind 127.0.0.1:8000 --workers 1 wsgi:app`；测试 `python -m pytest -q`。cli.py 仅承载有实际用途的初始化入口。FLASK_SKIP_DOTENV=1 是固定 CLI 控制前缀，禁用 Flask 自动 dotenv，命令执行由显式 CLI 注入。生产不使用 Flask 开发服务器。

.gitignore 至少覆盖 `.env`、`.env.*`（反向保留 `.env.example`）、`instance/`、`*.sqlite*`、`*.db`、数据库 journal/WAL/SHM、`uploads/`、`logs/`、`*.log`、`.venv/`、`venv/`、`__pycache__/`、`.pytest_cache/`、`.coverage`、`htmlcov/`、构建缓存；Docker build context 同样通过 .dockerignore 排除这些内容、Git 和本机虚拟环境。

### D7. 常驻规范的落地内容和读取时机

本次在此给出完整规范基线；apply 创建根 AGENTS.md，引用下表文档，不改写 OpenSpec 生成的工作流文件。AGENTS.md 常驻约束：项目名称与栈；只实施当前变更；开始任务先读 proposal/design/specs/tasks，再按触及领域读取下表文档；保持分层、默认拒绝、脱敏、Scenario 驱动测试；验证失败阻断完成；不得声称未执行检查通过；不得提交密钥或运行数据。未涉及领域无需无差别读取，但跨领域必须全部读相关规范。未来新会话先读 AGENTS.md，再读领域文件和变更，不能依赖聊天历史。

| 文档/读取时机 | 规范内容及适用阶段 | 明确检查方法 |
| --- | --- | --- |
| product.md；涉及需求、页面、状态或表单前 | 本次固定定位、术语和未来页面清单；未来业务页统一加载/正常/错误/空状态、字段必填/类型/长度校验，错误可恢复且保留已填输入，前后端校验一致 | 本次审阅文档涵盖角色/页面/状态表；未来逐页检查四态、表单边界与越权用例，并保存页面证据 |
| backend.md；改路由/服务/数据库前 | 本次遵守 D1–D5；未来业务 API `/api/v1`，成功 `{"data":...,"request_id":...}`，失败统一 error；非法筛选/排序/分页为 400 VALIDATION_ERROR，不得默默忽略；分页 page>=1、1<=page_size<=100，默认20；排序白名单，默认 created_at DESC,id DESC；事务在服务层，外部调用在事务外；状态写入需并发条件更新；创建/关键动作幂等键以主体+操作+键唯一，同键同体重放原结果，异体409，保存24小时（具体接口后续细化） | 本次工厂/错误/健康测试及依赖方向审查；未来非法参数、同时间稳定排序、回滚、并发冲突、重复提交测试；审查事务代码无网络调用 |
| security.md；改配置、权限、表单、附件或外部请求前 | 本次密钥外置、输入校验和脱敏；未来默认拒绝、每资源校验主体与动作、附件继承工单权限、密码仅使用受维护库的 Argon2id 安全散列；会话令牌放 HttpOnly/Secure/SameSite Cookie，登录轮换、退出撤销、状态修改防 CSRF；Jinja2 默认转义，禁用用户内容 safe；外部地址使用固定配置白名单，仅 HTTPS，拒绝回环/内网/链路本地/元数据及重定向绕过，密钥不进入日志 | 本次恶意敏感哨兵检查、.gitignore/.dockerignore 审查；未来授权矩阵/CSRF/XSS/密码散列参数/撤销/附件越权及 SSRF 测试，不将未来项标通过 |
| testing.md；写实现、测试、验证记录前 | Scenario 为用例来源，正常/失败/边界分组；每个测试 tmp_path 建独立库、无主机 .env、无真实用户数据；规范变更同步用例和映射 | 执行 `python -m pytest -q` 和 Compose test；测试名映射到 Scenario ID，失败/跳过须说明，必需项未通过阻断完成 |
| operations.md；改依赖/启动/部署/数据前 | 本次锁版本、持久卷、真实健康探测、SIGTERM 优雅退出、JSON 日志；未来业务表变更必须有版本化迁移、前向及失败回滚方案；发布保留旧镜像 digest，迁移不兼容时恢复备份再回滚；备份用 sqlite3 backup API 或停服一致性复制，禁止热拷单个活动文件 | 本次洁净构建、重启持久化、停机日志/退出码、备份至临时卷并恢复后查询；未来升级/降级演练及恢复校验结果必须留证 |
| ai.md；设计或修改 AI 前 | 本次仅文档。后续保留学生原文、生成可编辑草稿/分类/补充提示；不编造原因、地点或处理结果；不自动提交、分配或改状态；提示词纳入版本管理；输入最小化、超时、结构/字段校验失败回退人工，外部调用不得置于数据库事务；返回内容仅作不可信建议 | 本次审阅边界文档；引入 AI 时定义版本化脱敏评测集，覆盖幻觉、缺失信息、注入、超时/失败、分类准确率和人工回退，制定指标阈值后方可合入 |

产品规范中的未来业务基线必须包含：

- 学生提交报修、查看本人记录、补充信息、在待分配/待接单阶段取消、待确认阶段确认结果并评价；取消仅限未开始处理，由后续权限变更实现并测试。
- 管理员查看全部工单、调整分类/优先级、分配人员和看基础统计；维修人员仅访问分配给自己的工单、接单、写记录和提交结果。
- 术语：工单为一次报修及其完整历史；负责人为当前获分配的维修人员；处理记录是维修补充内容，状态记录是不可覆盖的变更审计。
- 未来页面：学生报修表、个人列表、详情/补充/结果确认；管理员工作台、工单详情/分配、统计；维修人员任务列表、处理详情；登录页面与无权限页。每个页面需求必须定义加载/正常/错误/空状态、可操作阶段、校验和恢复路径。本次不生成页面。
- 状态流与操作者：提交→待分配；管理员分配→待接单；获派维修人员接单→处理中；该人员提交结果→待确认；学生确认→已完成；学生反馈未解决→处理中（保留负责人）；学生在待分配/待接单取消→已取消。已完成/已取消终态，不自动关闭、不隐式重开；其他转换拒绝。补充信息不改变状态；管理员重新分配等扩展另提规则，不提前假定允许。
- 后续工单记录保留提交人、地点、原始描述、整理后描述、分类、附件、负责人、状态、创建/更新时间；每次状态变化原子追加操作人、时间、前后状态及说明。用户只得访问授权记录，评价与确认仅限本人。所有以上业务规则当前为「后续阶段，待实现/待验证」。

完成定义：当前变更所有需求/Scenario 有实现或适用的文档检查证据，tasks 全完成、pytest 与运行必需验证通过、README/规范/规约相符、无真实敏感数据；规划校验通过不等于实现完成。未来业务和 AI 的验收只能在对应变更执行，不以本次文档审阅代替。

### D8. 能力、Scenario 与实施验收映射

Scenario ID 固定为标题前缀，tasks 引用此 ID；详细前置/操作/结果见 specs。以下为完整索引，待实现记录须逐项填写命令/证据/结果。

| 能力 | Scenario ID | 验收载体/任务组 |
| --- | --- | --- |
| C1 application-foundation | F01 正常启动、F02 多实例隔离 | 工厂与入口测试 / 1、2 |
| C1 | F03 必填缺失、F04 非法配置、F05 可选默认与边界 | 参数化配置测试 / 1、2 |
| C1 | F06 初始化幂等、F07 启动数据库不可达、F08 连接释放 | CLI/数据库测试 / 1、2 |
| C2 health-observability | H01 正常健康、H02 依赖失效恢复 | 隔离库健康测试 / 1、2 |
| C2 | H03 未知 API、H04 方法错误、H05 异常脱敏 | 测试 client 故障注入 / 2 |
| C2 | H06 请求标识、H07 JSON 日志、H08 日志脱敏 | 日志捕获/哨兵检查 / 2 |
| C3 reproducible-runtime | R01 本地复现、R02 Compose 复现 | 洁净环境命令证据 / 3、5 |
| C3 | R03 卷持久化、R04 停机与恢复演练 | 隔离卷/备份验证 / 3、5 |
| C3 | R05 测试隔离与失败阻断、R06 仓库卫生 | 测试及文件审查 / 2、3、5 |
| C4 engineering-governance | G01 定位与路线图、G02 规范可执行 | 文档检查 / 4 |
| C4 | G03 映射和真实记录、G04 AI边界 | 文档/证据检查 / 4、5 |

## Risks / Trade-offs

- [SQLite 单机和写入并发限制] → 本次无业务写入，单 worker；后续按负载单独提案评估迁移。
- [SELECT 1 只能证明可连接可查询，不能证明表结构/写入能力] → 明确其为最小依赖就绪检查；未来迁移与业务可用性另加检查。
- [显式初始化增加一个入口] → CLI 工厂仅供初始化、独立验证；Compose 一次性服务封装，用户仍一条命令启动。
- [持久卷权限及 macOS/容器路径混淆] → 固定 UID、专属卷初始化、本地与容器配置分离并用洁净演练验证。
- [标准覆盖未来需求可能被误读为已完成] → 每个文档标阶段、未来用例只列计划，验证记录禁止虚构通过。
- [锁文件/镜像平台差异] → 在实现时记录 Python 补丁版、镜像 digest、Docker/Compose 版本和架构，在目标平台洁净构建。
- [请求日志只记录路由模板降低故障细节] → 用 request_id 关联固定错误码，不通过敏感输入提高可观测性。

## Migration Plan

当前无业务数据，不需要业务 schema 迁移。apply 顺序按 tasks：先可启动骨架，再测试、运行、规范与验证。首次部署显式初始化空库；现存数据库必须原样保留。发布前备份卷中的 SQLite（backup API 或停服复制）；保存镜像 digest。失败时停止新容器、恢复旧镜像及原卷；若未来迁移不兼容，先恢复备份再启旧版本。日常 `docker compose down` 保留卷；`down -v` 会删数据，仅在明确的隔离验证卷中使用，README 不作为日常停止命令推荐。恢复演练在临时库/卷完成，记录查询结果与文件校验，绝不操作真实数据。
