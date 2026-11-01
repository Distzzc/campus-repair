# 配置与 README 交付检查

日期：2026-11-02（Asia/Shanghai）。变更：bootstrap-project-foundation。

用户明确要求按既有设计创建 README，并完成任务3.1的全部文件；本次仅实施该范围。新增 `.env.example`、`.gitignore`、`.dockerignore`、`README.md`，更新任务状态。没有实现应用、安装依赖、启动服务、执行 pytest 或构建容器。此前 planning.md 是 propose 阶段的历史记录，本记录描述其后的部分实施。

## 实际执行与结果

以下检查均通过一次性 Python 脚本执行（无新增永久测试脚本），总进程退出0：

| 检查 | 方法 | 实际结果 |
| --- | --- | --- |
| Git 忽略规则 | `/private/tmp` 创建隔离临时仓库，复制实际 `.gitignore`，创建候选文件；逐项执行 `git -C <临时目录> -c core.excludesFile=/dev/null check-ignore --no-index -q -- <路径>` | 38项应忽略路径返回0，10项应保留路径返回1；退出值均符合预期。未初始化或修改项目自己的Git元数据 |
| Docker 忽略规则 | 对实际 `.dockerignore` 执行静态规则匹配，支持本文件所用 `**/`、`*`、`?`、`[cod]`、顺序取反及祖先目录匹配 | 40项应排除/10项应保留全部符合；这是规则检查，未调用Docker/BuildKit，不等同实际镜像构建验证 |
| 环境示例 | 解析非注释键值并与design D2/D6逐项比较 | 恰好5项：APP_ENV、DATABASE_PATH、LOG_LEVEL、DB_TIMEOUT_SECONDS、HOST_PORT；值分别为development、占位绝对路径、INFO、2、8000，无密钥字段 |
| README链接 | 提取Markdown相对链接并检查目标存在 | 全部解析成功；未把未来文件写成可点击但不存在的链接 |
| 命令语法 | 提取README中11个sh代码块，各执行 `bash -n` | 全部退出0；没有执行安装、初始化、启动、测试或停机命令 |
| 文档一致性 | 对照tasks 3.1/4.1与design D1–D8审阅 | 覆盖定位/边界/路线图、配置规则、显式加载、本地与容器路径、初始化责任、目标运行/测试/停止流程；注明前置文件尚缺和待验证状态，无虚构远程URL |
| OpenSpec严格校验 | `openspec validate bootstrap-project-foundation --type change --strict --no-interactive` | 退出0，输出 `Change 'bootstrap-project-foundation' is valid` |

候选路径覆盖：根及嵌套 `.env`、`.env.local`/production/testing、instance数据库、`.sqlite`/`.sqlite3`/`.db` 及journal/WAL/SHM、上传、JSON/文本日志、虚拟环境、字节码、pytest/mypy/ruff/通用缓存、coverage及构建产物。Docker另外检查根及嵌套Git元数据。

保留候选为：`.env.example`、`nested/.env.example`、`requirements.lock`、`requirements-dev.lock`、`README.md`、`campus_repair/config.py`、`tests/test_health.py`、`docs/verification/result.md`、`openspec/config.yaml`、`.agents/skills/openspec-propose/SKILL.md`。尚不存在的锁文件/源码仅在临时夹具中测试其规则匹配，不代表它们已实现。

## 任务与待验证项

- 3.1：完成，全部三个文件交付并满足本任务要求的规则匹配/示例检查。
- 4.1：README内容已交付，暂不勾选整项；R01/R02实际复现依赖尚未创建的骨架、依赖锁及容器文件。
- R06：忽略规则和环境示例部分已检查；真实Docker构建上下文仍待容器阶段验证，不宣称整个Scenario通过。
- 其余应用、健康、日志、pytest、持久化、优雅停机、备份恢复及业务验证：待验证。

本次未修改初始化配置、规约或技能文件，未提交、推送或归档。
