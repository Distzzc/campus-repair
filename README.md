# 校园报修与 AI 工单辅助系统

面向学生、后勤管理员和维修人员，统一报修提交、任务分配、维修处理、进度查询和结果确认，解决描述不完整、进度不透明、分配不清晰和历史记录分散的问题。后续 AI 辅助整理描述、建议分类并提示补充信息。

## 当前范围

已提供 Flask 应用工厂、环境配置校验、SQLite 显式初始化和连接管理、免认证 `/health`、统一 JSON 错误、请求标识、JSON 日志、pytest、Docker Compose、常驻规范与验证工具。实际检查结果和未验证事项见 [实施记录](docs/verification/implementation.md)及[课程交付索引](docs/lesson-07/README.md)。规划严格校验通过不能代替运行验收。

当前不实现登录注册、工单业务接口、上传、分配、评价、统计、AI 模型调用、向量检索或 MCP；不创建占位业务端点。技术栈为 Python 3.12、Flask、SQLite、Jinja2、HTML/CSS/JavaScript、pytest、Docker Compose，生产使用 Gunicorn。前端后续按实际用途加入服务端模板及适量 JS，无独立前端框架、Redis、队列或微服务。

## 获取代码

```sh
git clone https://github.com/Distzzc/campus-repair.git
cd campus-repair
```

也可使用维护者提供的完整源码副本。仓库地址已配置；教师访问权限、远程发布状态和另一人异机复现需要独立确认，本地实现记录不代表这些检查已通过。

本地需要 Python **3.12**（实现环境3.12.14）、venv、pip、curl，以下命令面向 macOS/Linux shell。容器需要运行中的 Docker Engine/Desktop 与 Compose插件v2及以上；使用 `docker compose version` 检查。具体已验证版本/平台及镜像digest见实施记录。

## 配置

```sh
cp .env.example .env
mkdir -p instance
pwd
```

编辑 `.env`，将 DATABASE_PATH 的 `/absolute/path/to/campus-repair` 替换为刚输出的实际绝对目录。路径含空格时将整个值用双引号包住；不要提交 `.env`。本地必填值示意：

```dotenv
APP_ENV=development
DATABASE_PATH=/your/actual/campus-repair/instance/campus-repair.sqlite3
```

| 变量 | 必填/省略默认 | 合法规则 |
| --- | --- | --- |
| APP_ENV | 必填，无默认 | 精确 `development`、`testing`、`production` |
| DATABASE_PATH | 必填，无默认 | `.sqlite3`后缀绝对文件路径；父目录已存在且可写；已有文件必须为可读写普通文件；拒绝相对路径、目录、URI和`:memory:` |
| LOG_LEVEL | 可选，INFO | DEBUG/INFO/WARNING/ERROR；不抑制请求完成日志 |
| DB_TIMEOUT_SECONDS | 可选，2 | 十进制整数1–10；拒绝浮点、空白、非数字 |
| HOST_PORT | Compose可选，8000 | 十进制整数1024–65535；主机仅绑定127.0.0.1，本地Gunicorn使用显式--bind |

必填缺失/空值为 CONFIG_MISSING；非法配置为 CONFIG_INVALID；显式可选空值亦非法。数据库未初始化/不可连接为 DATABASE_INIT_FAILED。普通应用在监听前失败，只输出字段名、代码和静态规则，不回显值、路径或堆栈。当前没有登录功能，不要求无用途的SECRET_KEY。

应用只读进程环境，不自动加载 `.env`。本地用 dotenv CLI 显式加载，默认覆盖同名继承变量；使用前确认选定的文件，测试则清理环境并注入隔离配置。`FLASK_SKIP_DOTENV=1` 防止 Flask CLI 再加载隐含文件。

Compose 的 `--env-file .env` 只负责插值，随后显式传入白名单；容器固定 APP_ENV=production、DATABASE_PATH=/data/campus-repair.sqlite3，主机绝对路径不透传。LOG_LEVEL/DB_TIMEOUT_SECONDS可配置，HOST_PORT控制映射并在应用启动前校验；非法字符串也可能被Compose自身提前拒绝。

## 本地启动

在项目根目录执行：

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
FLASK_SKIP_DOTENV=1 dotenv -f .env run -- python -m flask --app campus_repair.cli:create_cli_app init-db
dotenv -f .env run -- gunicorn -c gunicorn.conf.py --bind 127.0.0.1:8000 wsgi:app
```

初始化只创建空数据库并验证查询，不创建业务表，重复运行不清空数据；普通工厂不自动建库或父目录。`gunicorn.conf.py` 启用 preload，在监听前完成校验，禁调试/重载、1 worker、30秒超时、10秒优雅停机及服务器JSON日志。修改本地端口请改 `--bind`，HOST_PORT不控制该命令。

另开终端检查 `/health`；前台服务按 `Ctrl+C` 停止，数据保留。不要使用 Flask 开发服务器运行生产服务。

## 容器一条命令启动

填写 `.env` 后：

```sh
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
```

一次性init服务准备专属卷权限，降至UID/GID10001显式初始化；成功后app以非root启动。容器内部8000，主机默认127.0.0.1:8000。专属named volume逻辑名为campus_repair_data，实际带Compose项目名前缀，挂载/data；数据库为/data/campus-repair.sqlite3。重建及重复初始化均不得清空数据，不挂载本机源码。

```sh
docker compose --env-file .env logs --tail 100 app
docker compose --env-file .env down
```

日常down保留卷；不要将删除卷的down -v作为日常停止命令。SIGTERM停机宽限15秒。健康探针10秒间隔、3秒超时、3次重试、10秒启动宽限。生产target不装pytest，test服务在test profile，默认up不启动测试。

## 健康与错误契约

```sh
curl -i http://127.0.0.1:8000/health
```

HOST_PORT修改后同步替换访问端口。GET /health无需登录，每次重新连接数据库，读取真实数据库元信息并执行SELECT 1；请求结束关闭连接。

成功 HTTP 200，request_id为动态UUID v4：

```json
{"status":"ok","checks":{"database":"ok"},"request_id":"<uuid>"}
```

运行期间依赖失效 HTTP 503：

```json
{"error":{"code":"DEPENDENCY_UNAVAILABLE","message":"Service temporarily unavailable","details":{}},"request_id":"<uuid>"}
```

未知API/其他路径404 NOT_FOUND，错误方法405 METHOD_NOT_ALLOWED（保留Allow头），未捕获异常500 INTERNAL_ERROR，其他HTTP异常保留状态/协议头并使用HTTP_ERROR。错误JSON均有error(code/message/details)和request_id，无内部路径/SQL/异常文本。

每个请求服务端生成UUID v4，忽略传入X-Request-ID；响应头/JSON/日志一致。每次请求恰好一条request_completed JSON日志，含UTC毫秒时间、级别、request_id、方法、路由模板或`<unmatched>`、状态码、耗时；405未匹配成功的方法同样记录`<unmatched>`。不记录原始URL、查询串、正文、头、密码、令牌、密钥、报修信息或原始异常。

## 测试与规范检查

```sh
python -m pytest -q
python scripts/check_standards.py
docker compose --env-file .env run --rm --no-deps test
openspec validate bootstrap-project-foundation --type change --strict --no-interactive
```

本地先激活虚拟环境。pytest从Scenario推导，正常/失败/边界均覆盖；每例独立临时库，不读真实.env，不用主机/项目卷。测试包括实际Gunicorn生命周期、健康故障恢复、连接关闭、脱敏、真实锁超时、备份恢复、受控失败阻断与规范代码变异检查。必需测试失败或必需运行验证未执行时不能标记完成。

规范入口为 [AGENTS.md](AGENTS.md)，其引用产品、后端、安全、测试、运维、AI六份文件，明确读取时机、适用阶段、检查方法和缺陷判据。`check_standards.py` 检查Python模块/函数/类命名及基础设施反向依赖；测试在临时副本引入违规代码，必须失败、恢复后通过。真正另起会话和另一人异机评审需要另外留证，不能用重复跑pytest代替。

## 数据与验证记录

`.gitignore`和`.dockerignore`排除真实.env、SQLite及journal/WAL/SHM、上传、日志、虚拟环境、缓存和构建产物；保留.env.example及锁文件。忽略规则不删除已有跟踪文件，提交前仍须检查历史和暂存内容。

备份/恢复通过 `python scripts/database_backup.py backup SOURCE DEST`、`restore BACKUP NEW_DATABASE` 使用SQLite backup API，拒绝覆盖目标。详细说明见[运维规范](docs/standards/operations.md)。只能在隔离副本演练，先完整性检查并查询已知记录，再安排运行库切换；不得热拷单个活动数据库文件。

[实施记录](docs/verification/implementation.md)保存命令/环境/退出结果/证据/限制；[Scenario映射](docs/verification/scenario-matrix.md)关联4项能力、26个场景、测试和任务；[课程索引](docs/lesson-07/README.md)集中列出交付证据。未来表结构变更须版本化迁移、备份、回滚演练，发布保留前一镜像digest。

## 产品方向与后续独立变更

学生查本人、补充信息、按阶段取消并确认评价；管理员查全部、改分类/优先级、分配和统计；维修人员查获派、接单、记录和提交结果。这些业务当前尚未实现。

未来状态流：待分配→待接单→处理中→待确认→已完成；学生待确认反馈未解决返回处理中并保留负责人，待分配/待接单可取消为已取消。终态不自动重开，其他转换默认拒绝。详细角色/术语/页面四态/表单与状态规范见[产品规范](docs/standards/product.md)。

后续依次独立创建：①登录与角色权限；②学生报修和本人查询；③分配与维修处理；④确认、评价和附件；⑤AI描述整理与分类建议；⑥基础统计及可选相似历史检索。

AI仅产出可编辑草稿、分类和补充提示，保留原文，不编造原因/地点/处理结果，不自动提交/分配/改状态，失败仍能手动报修；提示词版本、输出校验、超时降级和评测在后续变更落实。

当前变更的[提案](openspec/changes/bootstrap-project-foundation/proposal.md)、[设计](openspec/changes/bootstrap-project-foundation/design.md)、[规约目录](openspec/changes/bootstrap-project-foundation/specs/)、[任务清单](openspec/changes/bootstrap-project-foundation/tasks.md)是实施与验收依据。路由→服务→数据访问，无反向依赖；当前没有业务规则，健康直接使用数据库基础设施，不为空壳层创建代码。
