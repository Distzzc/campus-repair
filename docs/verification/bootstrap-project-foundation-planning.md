# bootstrap-project-foundation 规划验证记录

日期：2026-11-02（Asia/Shanghai）。阶段：propose，仅规划；没有执行 apply。

规划位置：`openspec/changes/bootstrap-project-foundation/`。项目初始状态仅含 OpenSpec 初始化和技能文件，无代码、测试、README、AGENTS.md 或 .git。当前记录只证明规划文件检查结果，不证明系统已运行。

| 检查 | 实际命令/方法 | 结果与证据 |
| --- | --- | --- |
| CLI版本 | `openspec --version` | 已执行，退出0，1.13.0 |
| 权威项目根 | `openspec context --json` | 已执行，退出0；root.path=/Users/zzc/Desktop/campus-repair，source=nearest |
| 配置与目录 | 读取config.yaml，`ls -la`、`rg --files --hidden` | 已执行；schema=spec-driven，无context或定制rules，无既有业务实现 |
| 既有能力 | `openspec list --specs` | 已执行，退出0，No specs found；本次新增4能力，无覆盖/修改既有能力 |
| 工作流 | 各artifact的`openspec instructions … --change bootstrap-project-foundation --json`及status | 已执行；按proposal→design/specs→tasks创建，未跳过产物；保留CLI生成.openspec.yaml |
| 严格校验 | `openspec validate bootstrap-project-foundation --type change --strict --no-interactive --json` | 已执行，退出0，valid=true、issues=[]，1项通过/0项失败；原始输出见同目录bootstrap-project-foundation-openspec-validation.json |
| 规划齐备 | `openspec status --change bootstrap-project-foundation` | 已执行，退出0，4/4 artifacts complete；仅代表规划产物齐备 |
| 场景结构与映射 | 一次性Python检查：逐文件解析Requirement/Scenario标题，检查每需求有Scenario、WHEN/THEN、Purpose长度>=50、ID唯一及design D8覆盖 | 已执行，退出0；15个Requirement、26个Scenario（F01–F08/H01–H08/R01–R06/G01–G04），全部出现在D8映射中 |
| 实现任务未执行 | `openspec list --json`及复选框检查 | 已执行；0/20完成，所有实现复选框未勾选 |
| 文件边界 | 对照初始目录与最终文件清单，审阅本次写入位置 | 本次仅新增变更规划目录和docs/verification记录；未改config.yaml、既有.gitkeep、.agents/skills及其标记文件，无代码/运行文件新增 |

能力映射和验收路径见 design.md D8，强制规范草案和后续读取时机见 D7。根AGENTS.md、六份docs/standards文档、README、.env.example、依赖、代码和Docker文件均待apply创建。

| 后续验证 | 当前状态 | 运行时必须保留的证据 |
| --- | --- | --- |
| F01–F08 应用/配置/数据库 | 待验证（未实现） | pytest测试名/命令、退出码、配置边界/初始化幂等/故障注入结果 |
| H01–H08 健康/错误/标识/日志 | 待验证（未实现） | HTTP状态/响应键、真实查询/故障恢复、JSON日志与敏感哨兵检查 |
| R01 本地洁净启动 | 待验证（未实现） | Python补丁版、平台、安装/初始化/启动/健康/测试命令及退出结果 |
| R02 容器洁净启动 | 待验证（未实现） | Docker/Compose版本、平台、锁文件/镜像digest、构建与容器健康结果 |
| R03/R04 持久化/停机/备份恢复 | 待验证（未实现） | 隔离项目卷、哨兵查询、停机耗时/退出结果、备份恢复命令与查询 |
| R05/R06 测试隔离/失败阻断/忽略规则 | 待验证（未实现） | 测试通过/受控失败退出码、原数据不变及Git或规则工具检查 |
| G01–G04 最终规范与证据 | 待验证（最终文件尚未创建） | 当前仅审阅规划草案，最终须检查AGENTS/六份规范/README/完整映射 |
| 登录/工单/分配/评价/附件/统计/AI/检索/MCP | 待验证（不属本次实现） | 在后续独立变更中定义和执行，不计作本次通过 |

限制：严格CLI校验主要检查OpenSpec结构和规约格式，不替代语义审查或代码测试。本次未安装依赖、运行pytest、启动Flask、访问运行中的/health或执行Docker。不得根据CLI的isComplete或4/4将实现任务标记完成；以tasks复选框及实际证据为准。未执行提交、推送、归档。
