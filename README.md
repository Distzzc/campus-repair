# 校园报修与 AI 工单辅助系统

面向学生、后勤管理员和维修人员的校园后勤服务。当前已提供完整中文工作台与真实业务闭环，采用Python3.12、Flask、SQLite、Jinja2、原生HTML/CSS/JavaScript、pytest与Docker Compose。

## 打开应用

本机Docker部署后打开 **http://127.0.0.1:8000/**。未登录会进入登录页；**http://127.0.0.1:8000/register** 可真实注册三种账户类型。

| 角色 | 可使用的功能 | 注册条件 |
| --- | --- | --- |
| 学生 | 提交报修、查看本人、补充信息/图片、允许阶段取消、确认/退回、评价 | 直接注册 |
| 后勤管理员 | 全部工单、分类/优先级、分配维修人员、数据概览 | 管理员邀请码 |
| 维修人员 | 获派任务、接单、处理记录、提交结果、数据概览 | 维修人员邀请码 |

工作台、工单筛选/搜索/分页、详情时间线、附件、统计、个人信息和帮助页面均为实际功能。基础描述提示只依据关键词与缺失信息规则，**未调用AI**、不判断原因、不自动提交。真实模型、相似检索、邮件短信和找回密码尚未实现。

## 代码与准备

```sh
git clone https://github.com/Distzzc/campus-repair.git
cd campus-repair
cp .env.example .env
```

已有.env不要覆盖。代码是否已推送、教师权限及另一人异机评审需独立确认。没有公开的默认密码：演示账号student/admin/worker的密码来自本机.env的DEMO_PASSWORD，交付时另行直接提供，不写进Git文档。数据库只保存Argon2id散列。

生成演示配置和角色邀请码（仅填缺失项，不覆盖既有值）：

```sh
python3.12 scripts/configure_demo.py
```

需要Python3.12；Docker本身不需要本机安装Python依赖。也可手工编辑.env：DEMO_MODE=true，填写至少12字符的DEMO_PASSWORD，以及两个至少16字符的邀请码。学生注册不需要邀请码。首次seed创建6条演示工单；真实注册账号和新增工单独立持久化。

## Docker启动与测试

```sh
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
curl -i http://127.0.0.1:8000/health
docker compose --env-file .env run --rm --no-deps --build test
```

默认127.0.0.1:8000，修改HOST_PORT时同步改访问地址。init服务准备专属卷、降权，依次init-db→migrate-db→可选seed；app以UID10001运行，镜像固定Python补丁版和digest，生产不装pytest。named volume存/data/campus-repair.sqlite3，包含业务、会话与校验后的附件BLOB；不挂载本机源码。init或配置失败时app不启动。

```sh
docker compose --env-file .env logs --tail 100 app
docker compose --env-file .env down
```

down保留数据卷；不要用down -v日常停机。Gunicorn单worker、timeout30、graceful10，停机宽限15秒；healthcheck每10秒、超时3秒、3次重试、启动宽限10秒。

## 本地运行

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
mkdir -p instance
```

把.env中DATABASE_PATH换成本机项目instance/campus-repair.sqlite3的绝对路径；路径有空格须用引号包住。应用不隐式发现.env，以下命令显式加载：

```sh
FLASK_SKIP_DOTENV=1 dotenv -f .env run -- python -m flask --app campus_repair.cli:create_cli_app init-db
FLASK_SKIP_DOTENV=1 dotenv -f .env run -- python -m flask --app campus_repair.cli:create_cli_app migrate-db
FLASK_SKIP_DOTENV=1 dotenv -f .env run -- python -m flask --app campus_repair.cli:create_cli_app seed-demo
dotenv -f .env run -- gunicorn -c gunicorn.conf.py --bind 127.0.0.1:8000 wsgi:app
```

不需要示例数据时跳过seed-demo。init-db仅建空库；迁移显式创建001业务表、user_version记录，重复执行不清空；普通启动仍不隐式建库。Ctrl+C停止前台进程。

## 配置表

| 变量 | 默认/必填 | 规则 |
| --- | --- | --- |
| APP_ENV | 必填 | development/testing/production |
| DATABASE_PATH | 必填 | 绝对.sqlite3文件；父目录已存在可写；禁止URI/内存库/目录/相对路径 |
| LOG_LEVEL | INFO | DEBUG/INFO/WARNING/ERROR；请求完成日志始终保留 |
| DB_TIMEOUT_SECONDS | 2 | 十进制整数1–10 |
| HOST_PORT | 8000（Compose） | 十进制整数1024–65535，仅绑定127.0.0.1 |
| COOKIE_SECURE | false | 精确true/false；本机HTTP为false；HTTPS正式部署必须true |
| DEMO_MODE | false | 精确true/false；仅控制容器自动seed |
| DEMO_PASSWORD | 空，seed时必填 | >=12字符，真实值只写忽略的.env；首次创建演示账户使用 |
| ADMIN_INVITE_CODE | 空 | 非空>=16字符；空则拒绝管理员注册 |
| WORKER_INVITE_CODE | 空 | 非空>=16字符；空则拒绝维修人员注册 |

基础必填缺失/空值CONFIG_MISSING，非法CONFIG_INVALID，数据库不可达DATABASE_INIT_FAILED；可选日志/超时显式空值非法，邀请码/演示密码空值代表禁用或未配置。Compose固定传入APP_ENV=production、DATABASE_PATH=/data/campus-repair.sqlite3及上述白名单，不透传主机绝对路径。会话是不透明随机令牌，摘要存数据库，8小时过期，退出删除，Cookie HttpOnly/SameSite=Lax；没有硬编码Flask签名密钥。

## 演示数据重置

seed默认幂等，不覆盖既有用户密码或真实数据。只有明确需要时执行：

```sh
docker compose --env-file .env exec -T app python -m flask --app campus_repair.cli:create_cli_app seed-demo --reset --yes
```

重置仅删除demo标记的示例工单、重建示例数据、用当前DEMO_PASSWORD更新demo账号并撤销其会话。真实注册用户及非demo标记工单保留。修改.env后需重新up以更新容器环境。不会自动执行此重置。

## 业务规则与API

状态：待分配→待接单→处理中→待确认→已完成；学生在待确认反馈未解决→处理中并保留负责人。学生仅待分配/待接单可取消→已取消；终态不可再变更。每次动作原子保存操作人、时间、前后状态、说明与version；已完成工单仅本人可评价一次。

API前缀/api/v1：session、register/login/logout、tickets、tickets/id/actions、tickets/id/review、tickets/id/attachments、attachments/id、workers、stats。成功为data/request_id；错误为error(code/message/details)/request_id。业务写入需CSRF及UUID Idempotency-Key；同主体同操作同键同体24小时重放，异体409；动作需version，过期409。未登录401、越权403、未知404、校验400、状态冲突409、登录限流429。

每角色逐工单/附件授权；学生本人、维修获派、管理员全部。图片PNG/JPEG/WebP，每张<=5MB，每单<=10张，校验实际内容和像素尺寸。筛选status/category/priority/q、page>=1、page_size1–100默认20，非法或未知筛选报400；按created_at DESC,id DESC稳定排序。

GET /health免认证，每次读数据库元信息并SELECT 1；正常200及status/checks.database/request_id，依赖失败503统一错误。服务器生成请求UUID，响应头/正文/单行JSON日志一致，不记录正文、Cookie、密码、令牌、邀请码、原始URL、SQL或敏感报修信息。

## 验证与工程规范

```sh
python -m pytest -q
python scripts/check_standards.py
openspec validate --all --strict --no-interactive
```

[AGENTS.md](AGENTS.md)引用六领域规范和读取时机。路由→服务→仓储→SQLite，无反向依赖；service划事务，无事务内外部调用。基础测试和新业务测试均使用临时库；[新业务验证](docs/verification/workflow.md)关联A01–A04/W01–W06/U01–U04及浏览器/Docker证据。[当前变更](openspec/changes/complete-repair-workflow/)持续记录实施，不自动提交、推送或归档。

备份恢复见[运维规范](docs/standards/operations.md)，使用scripts/database_backup.py和SQLite backup API，不热拷活动单文件；升级前备份、保留旧镜像及恢复点，迁移回滚需恢复备份。新业务表向旧骨架增加，旧基础数据保留。

.env、数据库、日志、缓存和虚拟环境均被Git/Docker排除；锁文件/示例可提交。历史[骨架归档](openspec/changes/archive/2026-11-02-bootstrap-project-foundation/)与[课程索引](docs/lesson-07/README.md)保留，历史运行结果不代表新版本或人工peer review已通过。
