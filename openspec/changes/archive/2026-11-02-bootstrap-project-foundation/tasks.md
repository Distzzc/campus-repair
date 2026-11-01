本清单跟踪已获授权的 apply 实施；历史 propose 阶段不勾选实现任务。先读 proposal.md、design.md、四份 specs；能力/Scenario 总索引见 design.md D8。无待决的范围问题；业务与 AI 仅写规范，不实现。组间默认顺序：1→2→3→4→5，各任务须记录实际验收结果。首组完成即能本地初始化、启动并访问真实健康检查。

2026-11-02 用户明确要求先完成3.1并创建README，故先交付这些独立文件。当时3.1已完成，检查证据见 `docs/verification/bootstrap-project-foundation-config-docs.md`。随后用户授权完整实施；当前结果以本清单复选框和 `docs/verification/implementation.md` 为准。

## 1. 最小可启动骨架（C1、C2）

- [x] 1.1 建立 design D1 的有用途目录、Python 3.12 依赖声明、运行锁 requirements.lock 和测试锁 requirements-dev.lock（含传递版本），创建应用工厂与 wsgi.py；验收：洁净3.12虚拟环境可按锁安装，导入包不读取配置/打开数据库，两个工厂实例配置独立（F01/F02），无空业务层或占位端点。
- [x] 1.2 实现 design D2 环境解析、默认/边界校验及脱敏启动错误；验收：分别缺失必填项、输入非法枚举/路径/超界值时监听前非零退出且代码/字段正确，合法边界接受，未显式加载 .env 不读取它（F03–F05）。
- [x] 1.3 实现 db.py、cli.py 专用 init-db、普通启动探测及请求连接关闭；验收：临时父目录中 init-db 可首次建库且重复运行保留哨兵，普通入口缺库失败，启动不自动建库，连接成功/失败均关闭（F06–F08）。
- [x] 1.4 注册唯一 GET /health 与统一 HTTP/异常错误处理，设置 UUID v4 请求标识、JSON请求完成日志和协议头保留；验收：显式初始化后本地启动，curl /health 返回200及固定契约，移走临时库返回503，未知 /api/v1/tickets 为404，响应头/正文/日志关联（H01–H08 的初步烟测，完整测试见组2）。

## 2. 最小自动化测试与失败/边界覆盖（C1、C2、C3）

- [x] 2.1 建立 pytest fixture、临时数据库和环境清理；将用例按正常/失败/边界分组并在测试名或注释标 Scenario ID；验收：`python -m pytest -q` 可运行，每个测试仅访问自己的 tmp_path，不读取主机 .env（R05）。
- [x] 2.2 覆盖 F01–F08：实例隔离、必填缺失/空值、非法配置、默认与合法边界、初始化幂等、启动失败/超时、连接释放；验收：参数化测试全通过，启动失败含进程退出/不监听判据，权限故障在可可靠模拟的非root环境或受控注入下验证。
- [x] 2.3 覆盖 H01–H05：查询真实执行、文件移走/连接失败/查询失败/超时及恢复、未知 API、405 Allow、测试专用500/标准HTTP异常；验收：状态/JSON键/固定code和message完全匹配，异常哨兵与内部数据不出现在响应，生产无测试路由。
- [x] 2.4 覆盖 H06–H08：UUID有效性/唯一性、恶意传入标识、HEAD、日志恰好一条/JSON字段类型/级别/耗时、LOG_LEVEL=ERROR仍有完成事件、所有敏感输入位置的哨兵；验收：日志逐行可解析且无哨兵、原始URL、异常或文本access log。
- [x] 2.5 在隔离测试副本引入受控失败，验证 pytest 非零退出及失败阻断，并移除故障恢复通过；验收：记录两次真实退出结果，正常项目库与主机库哨兵不变（R05），不得提交人为失败用例。

## 3. 配置示例与可复现运行（C3）

- [x] 3.1 创建 .env.example、.gitignore 和 .dockerignore，解释必填/可选/默认/范围及主机绝对路径；验收：R06规定的运行数据均被排除、示例和锁文件保留、无真实密钥，记录规则匹配或 Git 忽略检查证据。
- [x] 3.2 创建固定3.12补丁/digest的多阶段 Dockerfile：生产仅运行锁，测试目标安装测试锁，应用UID/GID10001；验收：镜像洁净构建成功、实际Python版本正确、生产不含pytest，记录平台/镜像digest（R02）。
- [x] 3.3 创建 compose.yaml 和专属卷初始化脚本：init校验HOST_PORT、限定卷权限、降权执行init-db，app依赖初始化成功；环境白名单、容器固定/data路径、项目隔离named volume、仅127.0.0.1端口、healthcheck、SIGTERM和15秒宽限；验收：一条up命令启动、初始化失败阻断app、非法HOST_PORT拒绝、容器健康且非root（R02）。
- [x] 3.4 建立无持久卷/无主机env依赖/无端口的Compose test服务（测试profile，默认up不启动测试，显式run可执行）；验收：`docker compose --env-file .env run --rm --no-deps test`通过，故障测试非零退出，不触碰运行数据（R05）。
- [x] 3.5 验证隔离卷重建后哨兵保留、普通down保留数据，验证SIGTERM宽限内退出及临时备份恢复；验收：R03/R04证据包含命令、退出码、时间、恢复查询结果，禁止操作真实库。

## 4. README 与工程规范（C4）

- [x] 4.1 创建README：项目定位/边界/路线图、真实代码获取方式、前置版本、配置表、显式.env加载、本地/容器路径、初始化责任；列出本地完整命令、容器一条命令启动、/health、两种测试命令和保留卷的停止方式；验收：对照design D2/D6无隐藏步骤，满足R01/R02/G01，无虚构远程地址。
- [x] 4.2 创建根AGENTS.md及docs/standards/product.md、backend.md、security.md、testing.md、operations.md、ai.md，逐条落地design D7的强制规则/阶段/读取时机/检查方法；验收：G01/G02/G04文档检查通过，六态/操作者/取消及退回规则完整，所有未来业务和AI明确待实现，初始化工作流文件未改。
- [x] 4.3 在工程文档维护design D8对应的能力–Scenario–测试/审查–任务–证据映射和完成定义，建立实现验证记录模板；验收：26个Scenario全部有去向，记录含日期/环境/命令/退出结果/证据/限制，未执行为待验证，完成判据含测试和文档/规约一致（G03）。

## 5. 综合验证与证据（C1–C4）

- [x] 5.1 在洁净本地环境逐条执行README初始化/启动/健康/测试/停止流程，并在隔离Compose项目执行构建/启动/健康/测试/重建/停机/备份恢复；验收：F01、R01–R05全部可复现，失败/限制如实记录，不以只运行容器config检查替代运行验收。
- [x] 5.2 将26个Scenario的自动化或文档检查结果逐项写入docs/verification/实现记录，核对日志/脱敏证据、运行数据排除和初始化文件保护；验收：F01–F08、H01–H08、R01–R06、G01–G04均有真实证据，未来业务仍待验证（G03/R06）。
- [x] 5.3 执行`openspec validate bootstrap-project-foundation --type change --strict --no-interactive`并复核代码、tests、README、标准、specs与任务一致；验收：严格校验及所有必需测试/运行检查通过才勾选完成，有失败或待验证则阻断，不自动提交、推送或归档。

最终结果：20/20任务完成。63项pytest、洁净本地与容器验收、原生忽略/真实Docker上下文检查及严格校验通过；证据见 `docs/verification/implementation.md`。课程附加的教师权限、骨架提交/tag、真正新会话、另一人异机peer review未冒充完成，见 `docs/lesson-07/README.md`。
