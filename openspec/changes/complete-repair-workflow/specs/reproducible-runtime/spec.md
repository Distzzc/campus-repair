## MODIFIED Requirements

### Requirement: Documented local and container startup
项目 MUST 提供依赖锁定、配置示例和 README，列明每项配置的必填性、默认值、合法范围、加载方式及本地与容器路径差异。容器 MUST 支持 `docker compose --env-file .env up --build -d` 一条命令完成构建、显式初始化、版本化迁移、可选演示seed和启动；应用不得依赖主机全局包、隐式 .env 或预建数据库。HOST_PORT 默认8000，只接受1024–65535整数，主机绑定127.0.0.1。生产禁止调试器和开发服务器。

#### Scenario: R01 本地独立复现
- **GIVEN** 洁净 Python 3.12 环境和代码副本，无全局依赖、.env 或现成数据库
- **WHEN** 操作者按 README 创建虚拟环境、按锁文件安装、复制并填写 .env、创建父目录、显式初始化和启动
- **THEN** GET /health 返回200，`python -m pytest -q` 可运行；仅修改本机绝对路径即可复现，不需要隐含配置

#### Scenario: R02 Compose一条命令启动
- **GIVEN** Docker Compose 可用、无既存项目卷，.env 按示例填写，本机 DATABASE_PATH 与容器路径不同
- **WHEN** 执行 `docker compose --env-file .env up --build -d`
- **THEN** 数据库在容器 /data 显式初始化后应用以非 root 用户启动，容器健康探测成功，主机 /health 返回200；运行库不使用主机路径
- **AND** HOST_PORT 取1024和65535可被配置接受（实际启动选空闲端口），取1023/65536/非整数/空值时启动前明确失败

### Requirement: Persistent data and operational lifecycle
容器数据库 MUST 挂载专属持久卷，重复初始化和重建应用不得清空已有数据。日常停止命令保留卷。服务 MUST 正确响应 SIGTERM，在15秒停机宽限内结束；提供不接触真实数据的备份恢复操作说明，恢复后能验证数据可查询。

#### Scenario: R03 数据卷持久化
- **GIVEN** 隔离 Compose 项目已成功启动，在卷中数据库写入专用测试哨兵数据
- **WHEN** 执行 down（不带 -v）再 up --build -d，并重复初始化
- **THEN** 哨兵数据保持不变，数据库路径仍指向同一卷，健康返回200；已有业务表及真实注册数据保持完整

#### Scenario: R04 优雅停机和备份恢复
- **GIVEN** 独立验证卷中的已知哨兵数据，服务可健康查询
- **WHEN** 按文档生成一致备份，发送 SIGTERM 停止服务，再将备份恢复到另一临时库并查询
- **THEN** 服务在15秒内正常退出、无被强制杀死证据，恢复库可查询相同哨兵，备份/恢复命令、退出结果和验证证据均被记录

