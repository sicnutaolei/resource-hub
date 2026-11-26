# 资源小站 · SaaS 工具型资源库

基于 Django 5.2 + SQLite 的轻量软件资源站。前台只展示公开软件，后台是自建的简约
SaaS 工具界面：左侧窄侧边栏、顶部搜索、横向筛选标签、圆角卡片网格。

当前维护分支：**SaaSUI**。

---

## 功能

### 前台

- 首页只展示公开软件，服务端分页（每页 20 / 24 / 30），默认按更新时间倒序。
- 搜索覆盖软件名称、简短标题、描述、标签；搜索 / 标签筛选 / 分页全部走服务端。
- 横向筛选标签固定取自标签表，单选，和搜索、分页可组合。
- 等宽卡片网格：顶部预览缩略图，底部一行标题，超出截断。
- 缩略图自动生成（640×400），`loading="lazy"`，固定宽高比，避免布局抖动。
- 首页不展示更新日志；只保留站点名和一句可在后台修改的 slogan。
- 深色 / 浅色 / 跟随系统主题切换。
- 关于页采用 README 风格，内容精炼。

### 后台 `/manage/`

- 概览：软件总数、公开 / 非公开数量、资源库、标签、疑似失效外链。
- 软件管理：搜索 + 公开状态筛选 + 资源库筛选组合；新增 / 编辑 / 删除。
- 软件编辑：基本信息、封面、标签、下载链接（本地文件或网盘外链）、更新日志。
- **是否公开**开关（`is_public`，默认公开）。非公开软件只对已登录管理员可见。
- 资源库管理：仅做分类；资源库下还有软件时禁止删除，避免影响软件归属。
- 标签管理：首页筛选标签来源；被软件使用时禁止删除。
- 站点设置：修改站点名称与首页 slogan，保存后缓存立即失效。
- 账号安全：修改管理员密码；自动创建的管理员首次登录必须先改密。

### 已移除

- 注册页面 / 注册 API / 注册入口全部删除（访问 `/accounts/register/` 返回 404）。
- Django admin 整体移除（`/admin/` 仅 302 跳转到 `/manage/`）。
- 权限管理、组管理不再有菜单 / 路由 / 页面 / API；`auth_group`、`auth_permission`
  表保留但不再使用。
- 普通用户注册、收藏、评论入口从前台移除；相关数据表保留以兼容旧数据。

---

## 快速开始（Docker）

```bash
cp .env.example .env
# 至少修改 SECRET_KEY 和 ALLOWED_HOSTS
docker compose up -d --build
docker compose logs -f web
```

首次部署时 `ensure_admin` 会创建管理员并打印一次初始密码：

```
====================================================================
  管理员账号已创建
  用户名：admin
  初始密码：xxxxxxxxxxxxxxxx
  首次登录后必须修改密码；此密码只在本次日志中输出一次。
====================================================================
```

打开 `http://<宿主机IP>:8082/manage/`，用上面的账号登录，按提示修改密码。

> 如果数据库里已经有超级管理员，重建容器不会重置密码，也不会再打印凭据。

重置已有管理员密码：

```bash
docker compose exec web python manage.py ensure_admin --update-password
```

---

## 数据与备份

| 内容 | 容器内路径 | 宿主机路径 |
| --- | --- | --- |
| SQLite 数据库 | `/app/data/db.sqlite3` | `./data/db.sqlite3` |
| 迁移前备份 | `/app/data/backups/` | `./data/backups/` |
| 封面 / 本地文件 | `/app/media/` | `./media/` |
| 站点设置缓存 | `/app/data/cache/` | `./data/cache/` |

- 容器每次启动都会先执行 `python manage.py backup_db`，再做数据库迁移。
- 备份使用 SQLite 在线备份 API（包含 WAL 内容），默认保留最近 20 份。
- 升级时保留 `./data` 与 `./media` 即可保留全部数据。

手动备份：

```bash
docker compose exec web python manage.py backup_db
```

---

## 可见性与安全

- 未登录访客：首页、搜索、标签筛选、详情、下载接口只能访问 `is_public=true` 的软件。
- 非公开软件：未登录访客访问详情或下载统一返回 **404**，不泄露是否存在。
- 只有管理员（`is_staff` / `is_superuser`）可以登录；普通用户会被登录表单拒绝，
  旧的普通用户会话会被中间件立刻注销。
- 非管理员账号在迁移和 `ensure_admin` 时被停用（数据保留）。
- 站点名称与 slogan 在模板中自动转义，后台保存时也会剥离 HTML 标签。
- 管理员首次登录必须改密（`must_change_password`），改密后才可进入后台其他页面。

---

## 首页查询与缓存

- 默认每页 24 条，可通过 `?size=20|24|30` 切换。
- 搜索参数 `q`、标签 `tag`、分页 `page`、每页条数 `size` 全部由服务端处理。
- 站点设置与筛选标签使用共享文件缓存（`data/cache/`），多 gunicorn worker 都能立即
  读到后台保存的新值；标签缓存 TTL 60 秒，站点设置缓存 TTL 300 秒并在保存时主动失效。

---

## 数据库与索引

- `resources_resource`：
  - `is_public + updated_at` 组合索引：`resources_public_updated_idx`
  - 软件名称索引：`resources_title_idx`
- 迁移 `resources.0003` 把旧字段 `is_published` **重命名**为 `is_public`，保留历史值。
- 缩略图不落数据库字段，按 `covers/.../thumbs/<name>-640x400.jpg` 规则生成并缓存。

---

## 部署到 krypton（覆盖现有实例）

现有实例目录：`/vol1/1000/docker/resource-hub`，容器名 `resource-hub`，端口 `8082`。

```bash
ssh taolei@192.168.195.107
cd /vol1/1000/docker/resource-hub

# 1) 先做一次在线备份（容器运行中也可安全执行）
docker compose exec -T web python -c "import sqlite3,pathlib,datetime; p=pathlib.Path('/app/data/backups'); p.mkdir(parents=True, exist_ok=True); d=datetime.datetime.now().strftime('%Y%m%d-%H%M%S'); s=sqlite3.connect('/app/data/db.sqlite3'); t=sqlite3.connect(str(p/f'db-{d}.sqlite3')); s.backup(t); t.close(); s.close(); print('backup ok')"

# 2) 拉取 SaaSUI 分支并重建
git fetch origin
git checkout SaaSUI
git pull --ff-only origin SaaSUI

# 3) 覆盖部署（data / media 是 bind mount，不会丢）
docker compose up -d --build
docker compose ps
docker compose logs --tail 40 web
```

启动日志应包含：

- `数据库已备份：/app/data/backups/db-...sqlite3`
- `管理员已存在（admin），跳过初始化，不会重置密码。`（已有管理员时）
- `已写入默认站点设置...`（首次升级）
- gunicorn 正常监听 8082

验证：

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8082/healthz   # 200
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8082/accounts/register/  # 404
```

---

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `SECRET_KEY` | 无（生产必填） | Django 密钥 |
| `ADMIN_USERNAME` | `admin` | 管理员用户名 |
| `ADMIN_PASSWORD` | 空 | 空则首次部署自动生成并打印一次 |
| `ADMIN_EMAIL` | 空 | 管理员邮箱 |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | 允许的域名 / IP |
| `DEBUG` | `False` | 生产保持 False |
| `SITE_NAME` | `资源小站` | 站点名称初始值 |
| `SITE_SUBTITLE` | `只分享干净、无捆绑的资源` | 站点副标题初始值 |
| `SITE_SLOGAN` | 同 `SITE_SUBTITLE` | 首页 slogan 初始值 |
| `PAGE_SIZE` | `24` | 首页默认每页条数（20/24/30） |
| `SECURE_COOKIES` | `False` | HTTPS 反代时设为 True |
| `SERVE_MEDIA` | `True` | 由 Django 提供 /media/ |
| `DB_PATH` | `/app/data/db.sqlite3` | SQLite 路径 |
| `CACHE_DIR` | `/app/data/cache` | 共享文件缓存目录 |
| `PORT` | `8082` | 容器内端口 |
| `GUNICORN_WORKERS` | `3` | gunicorn 进程数 |

---

## 常用命令

```bash
# 本地开发（Windows PowerShell）
$env:DEBUG = "True"
$env:DB_PATH = "E:\...\resource-hub\.venv\dev.sqlite3"
$env:MEDIA_ROOT = "E:\...\resource-hub\.venv\media-dev"
python manage.py migrate
python manage.py ensure_admin
python manage.py init_site
python manage.py runserver 127.0.0.1:8090

# 测试
$env:DEBUG = "True"
python manage.py test

# 演示数据（仅本地）
python manage.py seed_demo
```

---

## 目录结构

```
config/             # 项目配置与根路由
accounts/           # 管理员登录 / 注销（注册已移除）
resources/          # 软件、资源库、标签、下载链接、更新日志
core/               # 站点设置、健康检查、关于页、中间件、初始化/备份命令
dashboard/          # 自建 SaaS 后台（/manage/）
templates/
  resources/        # 首页、详情、卡片、分页
  manage/           # 后台布局与页面
  accounts/         # 管理员登录
static/css/         # tokens / main / manage
static/js/          # theme / main / manage
data/               # SQLite、备份、缓存（git 忽略）
media/              # 封面、缩略图、本地文件（git 忽略）
```

---

## 验收清单

- [x] 分支 `SaaSUI`
- [x] 未登录只见公开软件；非公开详情 / 下载返回 404
- [x] 注册页面与 API 返回 404，前台无注册入口
- [x] 仅管理员可登录；非管理员账号停用
- [x] 首次部署打印管理员初始密码，首次登录强制改密
- [x] 搜索 + 标签 + 分页组合正常，服务端查询
- [x] 首页每页 20/24/30，图片懒加载与缩略图
- [x] 后台站点设置修改 slogan 后首页生效
- [x] 后台无权限管理 / 组管理菜单、路由、API
- [x] 迁移前自动备份；`is_published` 重命名为 `is_public` 保留数据