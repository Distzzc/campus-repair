# 运维规范

读取时机：依赖、构建、配置、启动、部署、数据与发布前。当前适用：锁文件、镜像、健康、日志、停机、备份恢复；业务表迁移在后续阶段适用，尚未实现。

| 强制规则 | 检查方法 / 缺陷判据 |
| --- | --- |
| Python3.12，传递依赖精确锁定，基础镜像固定补丁和digest；生产不装pytest | 洁净本地/容器安装、pip check、镜像检查；不可复现/生产含测试依赖即缺陷 |
| 普通启动不建库；显式init-db幂等；本地绝对路径，容器/data专属卷 | F06/F07、R02/R03；隐式空库替代/重启丢数据即缺陷 |
| /health真实查询；10秒间隔、3秒超时、3次重试、10秒启动宽限 | H01/H02及Docker健康状态；只测文件/永远返回200即缺陷 |
| 一行一JSON，响应/日志同一request_id，不记录敏感值 | H06–H08与真实服务器日志；无法关联/隐私外泄即缺陷 |
| 单worker，timeout30，graceful10，Compose停机宽限15秒；SIGTERM正确处理 | R04真实停机记录耗时/退出码；SIGKILL或超时即缺陷 |
| 非root应用、环境白名单、不挂载源码、默认端口127.0.0.1 | inspect进程/挂载/端口；应用root/意外暴露/主机路径透传即缺陷 |
| 发布记录镜像digest与验证；保留前一镜像；未来schema迁移版本化并有回滚及备份方案 | 洁净发布与回退演练；不可回退或无记录即缺陷 |
| 备份用sqlite3 backup API或停服复制；在隔离副本恢复并查询校验；不热拷单个活动数据库文件 | R04恢复演练对照哨兵/完整性检查；备份不可恢复即缺陷 |

## 备份与恢复

以下操作仅在隔离验证库/卷中演练；生产数据由授权运维人员执行。使用 `scripts/database_backup.py backup SOURCE DEST`，来源须存在，目标须不存在；恢复用 `scripts/database_backup.py restore BACKUP NEW_DATABASE`。脚本采用backup API，禁止覆盖目标；先恢复至新路径、运行 `PRAGMA integrity_check` 并比较已知记录，确认后再安排切换，不直接覆盖活动数据库。

容器示例（目标放在已挂载的/data内，确保目的文件尚不存在）：

```sh
docker compose --env-file .env exec -T app python scripts/database_backup.py backup /data/campus-repair.sqlite3 /data/check-backup.sqlite3
docker compose --env-file .env exec -T app python scripts/database_backup.py restore /data/check-backup.sqlite3 /data/check-restored.sqlite3
```

脚本输出只含固定事件和完整性状态，不回显路径/SQL/异常。备份须另按授权策略导出到安全存储。以上命令不会自动切换运行库。

日常停止 `docker compose --env-file .env down` 保留卷。删除卷操作仅用于已确认的隔离数据。发布失败先停新容器并使用旧镜像；若未来迁移不兼容，恢复备份后再启旧版本，记录恢复点与数据损失窗口。

## 当前业务阶段（complete-repair-workflow）

身份、工单六态、角色授权、附件、评价、统计及UI已进入本次实现；原文“当前仅骨架/未来业务”的阶段描述保留为初始化基线，具体当前边界以本变更设计、规约及验证记录为准。当前密码使用Argon2id；服务端不透明会话8小时，退出即撤销；注册admin/worker须角色邀请码；COOKIE_SECURE在本机HTTP为false，HTTPS部署必须true。新增业务路由为真实实现，原“仅/health”的历史检查不再用于禁止本次端点。

检查方法：tests/test_workflow.py覆盖A01–A04、W01–W06、U01/U03/U04；浏览器检查实际三角色操作。授权绕过、非法状态变化、失效CSRF通过、事务部分提交、附件越权、UI操作无真实响应均为缺陷。
