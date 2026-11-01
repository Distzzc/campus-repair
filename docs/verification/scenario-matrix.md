# 能力、Scenario、测试及证据映射

当前实现路径如下；真实执行结果见 implementation.md，不以映射存在推定通过。业务/AI未来功能均未实现。

| 能力 | Scenario | 自动化/文档检查 | 任务 |
| --- | --- | --- | --- |
| C1 | F01、F02 | test_foundation.py：启动/独立实例；test_runtime.py：真实服务 | 1.1、1.4、2.2 |
| C1 | F03、F04、F05 | test_foundation.py：必填、非法输入、边界、子进程监听前失败 | 1.2、2.2 |
| C1 | F06、F07、F08 | test_foundation.py：CLI幂等、启动依赖失败、连接关闭 | 1.3、2.2 |
| C2 | H01、H02 | test_health.py：查询观测、实际锁超时、文件移除恢复；test_runtime.py：真实HTTP故障恢复 | 1.4、2.3 |
| C2 | H03、H04、H05 | test_health.py：404/405/500/标准错误与协议头/脱敏 | 2.3 |
| C2 | H06、H07、H08 | test_health.py：UUID/HEAD/一行JSON/字段级别/哨兵；真实Gunicorn日志检查 | 2.4 |
| C3 | R01 | README洁净本地复现、test_runtime.py | 4.1、5.1 |
| C3 | R02 | Compose洁净构建/init/app健康/非root/端口校验 | 3.2、3.3、5.1 |
| C3 | R03 | 隔离Compose卷写哨兵、down/up、重复初始化再查询 | 3.5、5.1 |
| C3 | R04 | test_runtime.py：备份/恢复/停机；隔离容器备份恢复/停机 | 3.5、5.1 |
| C3 | R05 | test_runtime.py：受控失败/恢复/宿主哨兵；Compose test | 2.1、2.5、3.4 |
| C3 | R06 | test_governance.py、Git忽略检查、真实Docker上下文夹具检查 | 3.1、5.2 |
| C4 | G01、G02、G04 | test_governance.py文档/AST/隔离代码变异；六份领域规范与AGENTS审阅 | 4.2 |
| C4 | G03 | test_governance.py映射完整性；实施记录逐项核验 | 4.3、5.2 |

治理自动化只能证明所检查的依赖/命名/文档约束；真正另起会话和另一人异机评审需独立证据，不能冒充已执行。
