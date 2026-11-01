# bootstrap-project-foundation 实施验证记录

日期：2026-11-02（Asia/Shanghai）。范围：design/tasks当前工程骨架；后续登录、工单、附件、分配、评价、统计、AI/检索/MCP均未实现。之前planning/config-docs记录保留为历史阶段证据，当前状态以本记录为准。

## 环境与构建

- 本机：macOS arm64，Python3.12.14；Docker Desktop4.92.0、Engine29.8.0、Compose5.5.1（兼容Compose v2工作流），镜像信息见environment.json。
- 基础镜像：python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e。
- Flask3.1.3、Gunicorn23.0.0、python-dotenv1.2.4、pytest8.4.2及全部传递依赖精确锁定。requirements-dev.lock引入运行锁和固定setuptools；可编辑构建禁用build isolation。
- 干净本地验证使用临时源码副本及全新venv；容器验证使用唯一Compose项目前缀，未触碰用户项目/卷；结束仅清理本次验证卷。没有以更改业务规则降低验收要求。

## 实际命令与结果

| 命令/方法 | 实际结果 | 原始证据 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q --junitxml=docs/verification/pytest-local.xml` | 63 passed，退出0；覆盖F01–F08/H01–H08及R01/R04/R05、治理检查 | pytest-local.txt、pytest-local.xml |
| `.venv/bin/python scripts/check_standards.py` | Standards defects: 0，退出0 | standards.txt |
| 隔离副本修改db.py加入routes导入、错误命名BadFunction，再恢复 | 两种违规均被拒绝（退出非零），恢复后通过；非生产源码修改 | pytest-governance用例与JUnit |
| `.venv/bin/python scripts/verify_local.py` | 从全新venv按锁安装、pip check、显式dotenv/init、真实HTTP200、全量pytest、SIGTERM退出0；整体退出0 | clean-local-transcript.txt、clean-local-results.json |
| `.venv/bin/python scripts/verify_compose.py` | 从空卷一条up --build -d启动；app UID10001、容器路径正确、生产无pytest；完整容器测试；down/up和重复初始化保留哨兵；一致备份恢复、优雅停机；非法端口阻断应用 | compose-transcript.txt、compose-results.json |
| `.venv/bin/python scripts/verify_context.py` | 真实Docker构建/COPY验证30项排除、7项保留；Git原生检查28项排除/7项保留；退出0 | context-transcript.txt、context-results.json |
| pytest内受控失败→修复→重跑 | 临时失败用例退出1，恢复退出0；主机指向的哨兵库内容不变 | test_R05_controlled_failure_is_nonzero_without_touching_host_database及JUnit |
| `openspec validate bootstrap-project-foundation --type change --strict --no-interactive --json` | 结果见strict-validation.json；最终必须valid=true、issues=[] | strict-validation.json |
| 本地可获取历史与工作区常见密钥格式扫描 | 1个本地提交、24个唯一历史blob，扫描时76个工作区文件；0个常见格式候选，不保证任意秘密/远端历史 | secret-scan.json |
| 文档和源码检查 | README链接存在、命令语法有效；AGENTS及六规范有阶段/读取时机/检查/缺陷判据；26个Scenario均映射 | scenario-matrix.md、pytest治理用例、document-checks.json |

## 场景结果

- F01–F08：通过。独立工厂/启动、配置缺失/非法/边界、CLI幂等、启动依赖失败、连接异常释放均有测试。启动失败子进程确认非零且未监听；权限故障同时检查文件权限，避免root测试失真。
- H01–H08：通过。真实查询、数据库移走/连接/查询故障及实际独占锁超时、恢复后成功、404/405/500/其他HTTP错误、协议头、UUID/HEAD、JSON日志及哨兵脱敏均验证；真实Gunicorn日志逐行解析。
- R01–R06：通过。洁净本地及容器运行、隔离测试、持久化、停机、备份恢复、实际构建上下文排除见上述原始证据。容器端口非法字符串可能先被Compose语法拒绝，合法数值范围和空值由init校验，均在app启动前失败；边界1024/65535通过同一校验器，实际服务使用空闲18080。
- G01–G04：通过当前文档/工程检查。产品角色/术语/页面与六态、阶段/规范/读取入口、26场景映射、AI边界齐备。这里不代表未来业务/AI运行能力通过。

## 修复与限制

首轮运行发现沙箱禁止临时端口、405日志断言将未匹配的方法误判为已匹配路由，以及AI文档缺少明确尚未实现标记。放开经授权的本地测试端口权限后执行；修正405测试预期（符合路由模板或unmatched契约）并补足文档阶段说明。最终以通过的完整运行证据为准，不把初次失败隐藏为从未发生。

教师仓库权限、真正另起会话的Harness实验、组内另一人自己机器上的peer review均待验证，不能由本机自动化冒充。当前没有创建实现提交、骨架tag、推送或归档；这些交付动作与人工验收见docs/lesson-07索引。Git历史密钥检查只覆盖可获取的历史及扫描规则，不是绝对无密钥的数学证明。

现有数据不作schema迁移；备份恢复只在隔离临时库/卷执行。课程新增验收与当前tasks的完成状态分别记录，避免将人工评审混同于本机实现完成。
