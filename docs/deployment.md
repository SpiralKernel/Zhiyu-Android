# 云端个人部署

应用镜像使用Python 3.12与`uv.lock`导出的带哈希依赖，包含Poppler的PDF转图工具。镜像只含代码和前端；账号、学习记录、图片及API配置独立存放。

## 文件和数据

本地构建入口为根目录`Dockerfile`，部署模板在`deploy/`。云端运行目录为`/opt/ai-teacher/`：

| 路径 | 用途 |
| --- | --- |
| `compose.yaml`、`Caddyfile` | 独立Compose项目和HTTPS代理 |
| `.env` | 镜像标签与访问域名，不放API密钥 |
| `runtime.env` | 服务端AI配置，权限0600，禁止提交 |
| `data/ai-teacher.sqlite3` | 迁移时刻的SQLite在线快照 |
| `data/imports/`、`data/bank_answers/`、`data/teacher_images/` | 学生上传材料 |
| `data/backups/` | 数据库及上传材料的备份 |
| `snapshot.json` | 部署快照的校验和、表数量和代码指纹 |

云端和本地数据库是独立副本；迁移后应以云端作为新的学习记录来源，不能直接覆盖回本地或假设会自动双向合并。第一次迁移前使用SQLite在线备份并核对全部表数量，不复制正在写入的数据库文件。

## 运行约定

`app`为单个非root进程，512MiB内存上限、768MiB内存加swap上限、0.75核CPU；`proxy`上限128MiB、0.25核。数据目录需归属UID/GID 10001；Fedora的绑定卷使用独立SELinux标签。不要把其他项目的数据目录挂载进来。

应用容器没有发布8010端口，只由同项目HTTPS代理访问。代理转发原Host和HTTPS协议，应用才能正确检查Origin和设置Secure会话Cookie。不要把此镜像的应用端口直接发布到公网，因为其转发头信任适用于这个封闭代理网络。

`AUTH_REQUIRED=true`，云端`REGISTRATION_ENABLED=true`、`REGISTRATION_REQUIRES_INVITE=true`。已有账号沿用原用户名和密码；新学生填写用户名、密码、学习阶段及一次性邀请码。缺失、无效或已使用的码不能注册。邀请码消费与账号、学习范围、会话创建在同一个写事务中完成；失败回滚，竞争同一码只有一人成功。数据库只保存160位随机码的SHA256摘要。本地默认保留开放注册，设置相同环境变量即可改为邀请制；`REGISTRATION_ENABLED=false`仍可完全关闭注册。

维护者生成一批邀请码（文件必须尚不存在，权限0600，请私下分发，不提交Git）：

```bash
docker compose exec -T app python -m app.manage create-invites --count 10 --output /app/data/invitation-codes-日期.txt
```

邀请码没有自动过期时间，每个只能创建一个账号。名单包含注册凭证，应按密钥保管。备份数据库同时会保留邀请码的消费状态；恢复旧备份可能重新启用备份后已使用的码，恢复时须检查，不可直接开放注册。数据库迁移到版本10；版本9的旧镜像会拒绝降级打开，回滚需要兼容版本10的代码或同时恢复部署前备份并核对新增记录。

使用临时域名仍受云服务商接入规则约束，不等于免备案；HTTPS证书和外网访问必须实际验收。新增安全组规则只涉及所部署入口的TCP 80和443，不修改现有服务端口。

## 构建和维护

```bash
uv export --frozen --no-dev --no-emit-project --format requirements.txt --output-file deploy/requirements.txt
docker build -t ai-teacher:版本号 .
```

在云端运行目录执行以下命令。不要输出`runtime.env`、完整`docker inspect`环境变量或不带`--quiet`的完整Compose配置。

```bash
docker compose config --quiet
docker compose up -d --pull never
docker compose ps
docker compose logs --tail 50 app
docker compose exec -T app python -m app.manage backup
```

`deploy/ai-teacher-backup.service`与对应timer用于每天备份；需要安装到systemd后启用timer，模板存在不表示已启用。应定期把云端备份下载到其它设备，并关注备份占用。容器自动重启不代表数据库、密钥和材料已有异地备份。

更新前先备份数据并保留旧镜像标签，更新只替换本项目镜像。回滚代码需核对数据库版本兼容性；不要通过删除数据卷来回滚。

后台工作台入口为 `/admin`；授权、题目维护和未来安卓端联网题库更新见[题库维护与更新](content-maintenance.md)。本次新增迁移11，升级前先备份；文中邀请码迁移10的说明仅对应上一版本，旧镜像不能直接打开当前版本11数据库。

## 本地、GitHub 与云端同步

先通过回归检查并提交本地改动，正常推送 `main`，使用同一提交的代码构建镜像。构建时添加 `org.opencontainers.image.revision` 标签记录完整 Git 提交号，部署后核对远端 `main`、本地 HEAD、运行镜像标签以及应用/前端文件摘要。部署验收记录保存在被忽略的 `output/evals/`，不包含运行密钥。

数据库不会通过 Git 同步，也不自动双向合并学生记录。候选数学标注使用 `python -m app.manage import-math-annotations --annotations 分片路径...` 先做只读检查，备份后再加 `--apply` 原子应用；来源指纹变化或已有人工审核时拒绝覆盖。导入前后核对账号、作答和其他保留表的内容摘要。候选标注仍需审核，不能通过部署自动进入已审核题库更新包。完整批次文件留在各端私有运行目录；仓库保存规范、生成器、样例与交叉审核修正记录。

批次导入使用流式解析和有界写入缓冲，保留整个批次的单事务原子性。小内存服务器的维护任务建议另设不高于 192MiB 的内存上限并禁用该任务的额外 swap，防止批量任务影响正在学习的用户。不要让维护任务绕开应用既有数据权限与备份；检查服务器余量后再运行。

物理候选使用 `import-physics-bank` 与 `import-physics-annotations`，先按[物理批次记录](physics-bank-annotation-20261012.md)检查固定来源，再备份、检查和应用。部署可单独传输仅含题目内容的私有包，不能上传本地数据库覆盖云端；同步后比较题库内容摘要，并核对原学生表及数学内容保持不变。

## 2026-10-17 教学边界与训练闭环升级

当前代码支持数据库schema14。升级包含教学身份边界、问答学情证据校验、时间加权状态及受限训练计划。后台训练记录由服务端关联到作答ID；加练不计掌握证据，独立复测求助后也不计独立证据。详细规则见[AI职责与学情边界](ai-learning-contract.md)。

部署保留云端数据库及上传目录，禁止用本地数据库覆盖。升级前备份云端数据库与材料，保留旧镜像；先在云端数据库副本试迁移，核对账号、作答、会话、邀请等受保护记录，再切换新镜像。旧代码不能打开schema14；若启动失败，在保持入口维护状态且没有新写入时恢复升级前数据库和旧镜像，不能仅切回旧镜像。已完成冻结的内容按原启动流程加载，暂停核查中的数学批次不在启动导入入口。
