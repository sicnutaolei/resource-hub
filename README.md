# resource-hub

个人资源分享站：分享干净、无捆绑的软件与工具。参考成熟「资源站」的信息架构（卡片列表 + 分类侧栏 + 详情页下载区 + 更新日志），视觉与交互全新实现。

- 游客可浏览、可直接下载，**无需登录**
- 注册后可**收藏**资源、**发表评论**
- 管理员登录后进入后台，管理分类 / 标签 / 资源 / 下载链接 / 更新日志 / 评论
- 浅色 / 深色 / 跟随系统 三态主题，零外部 CDN 依赖，无网络也能正常显示

## 技术栈

| 项目 | 选择 | 说明 |
|---|---|---|
| 后端 | Django 5.2 LTS | 唯一在维护的 LTS，支持到 2028-04 |
| Python | 3.13 | Django 5.2 支持 3.10 – 3.14 |
| 数据库 | SQLite（WAL 模式） | 几百资源 + 几十用户的规模完全够用 |
| 前端 | Django 模板 + 手写 CSS 设计系统 | 无 Tailwind / 无 CDN，静态资源自托管 |
| WSGI | Gunicorn | 3 个 worker |
| 静态资源 | WhiteNoise | 不需要额外挂 nginx |
| 部署 | Docker + docker-compose | 默认端口 **8082** |

## 功能一览

- **资源条目**：名称、版本号、分类、标签、封面图、卡片摘要、详细介绍
- **多个下载入口**：同一个资源可同时挂「本地直链」和多个「网盘外链」
  - 本地文件走 `FileResponse` 流式下载，并校验路径必须落在媒体目录内
  - 外链可填**提取码**，前端一键复制
- **更新日志**：每个资源可记录多个版本的改动，详情页时间线展示，另有全站日志汇总页
- **搜索与筛选**：按标题 / 摘要 / 正文 / 版本 / 标签搜索，支持分类、标签、排序（最近更新 / 最新收录 / 最多浏览）
- **收藏与评论**：登录用户可用，评论支持管理员隐藏
- **外链失效检查**：后台批量检测 + 命令行 `check_links`，默认只出报告，加 `--apply` 才写库
- **浏览量 / 下载量统计**：用 `F()` 表达式自增，避免并发读改写竞态
- **健康检查**：`/healthz` 供容器编排与监控使用

## 目录结构

```
resource-hub/
├── config/                 项目配置（settings 全部读环境变量）
├── accounts/               用户：自定义 User、注册、登录、个人中心
├── resources/              核心业务：分类/标签/资源/下载链接/更新日志/评论/收藏
│   ├── context_processors.py   侧栏分类与标签注入全站
│   ├── utils.py                外链探测（仅用标准库 urllib）
│   └── management/commands/check_links.py
├── core/                   站点功能：关于、健康检查、robots、ensure_admin 命令
├── templates/              全部模板
├── static/css/             tokens.css（设计变量）+ main.css
├── static/js/              theme.js（主题）+ main.js（交互）
├── media/                  ★ 上传的封面图与本地文件（Docker volume）
├── data/                   ★ SQLite 数据库（Docker volume）
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh           迁移 → 建管理员 → 收集静态 → 启动 gunicorn
└── requirements.txt
```

## 快速开始（Docker 部署）

```bash
# 1. 拉取代码
git clone git@github.com:sicnutaolei/resource-hub.git
cd resource-hub

# 2. 配置环境变量
cp .env.example .env
# 生成一个 SECRET_KEY 填进去：
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

# 3. 启动
docker compose up -d --build

# 4. 查看日志，确认迁移与管理员创建成功
docker compose logs -f
```

打开 `http://<服务器IP>:8082` 即可访问，后台在 `http://<服务器IP>:8082/admin/`。

### 首次启动后必须做的事

默认管理员是 `admin` / `admin123`（来自 `.env.example`），**这个密码必须立刻改掉**：

```bash
# 1. 修改 .env 中的 ADMIN_PASSWORD 为强密码
# 2. 让它生效
docker compose exec web python manage.py ensure_admin --update-password
```

> `.env` 已在 `.gitignore` 中排除，真实密码不会被提交到仓库。
> `ensure_admin` 是幂等的：账号已存在时不会覆盖密码，除非显式加 `--update-password`。

### 数据持久化

`docker-compose.yml` 里挂载了两个目录，**容器重建不会丢数据**：

| 宿主机 | 容器内 | 内容 |
|---|---|---|
| `./data` | `/app/data` | SQLite 数据库 |
| `./media` | `/app/media` | 封面图 + 本地小文件 |

备份只需打包这两个目录：

```bash
tar czf resource-hub-backup-$(date +%F).tar.gz data media .env
```

飞牛 NAS 等环境可以把它们换成绝对路径，例如 `- /vol1/1000/docker/resource-hub/data:/app/data`。

## 环境变量

完整清单见 `.env.example`，常用的几个：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SECRET_KEY` | 无（**必填**） | Django 密钥。`DEBUG=False` 时未提供会直接拒绝启动，防止带着默认密钥上线 |
| `ADMIN_USERNAME` | `admin` | 管理员用户名 |
| `ADMIN_PASSWORD` | 无（必填） | 管理员密码，**只从环境变量读，不写进代码** |
| `DEBUG` | `False` | 生产必须保持 False |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | 用域名访问必须加进去，否则 400 |
| `CSRF_TRUSTED_ORIGINS` | 空 | 用 https 域名访问时填 `https://你的域名` |
| `SITE_NAME` | `资源小站` | 站名，显示在页头与页脚 |
| `PAGE_SIZE` | `12` | 列表页每页条数 |
| `SERVE_MEDIA` | `True` | True 由 Django 提供 `/media/`；交给前置 nginx 时设 False |
| `GUNICORN_WORKERS` | `3` | gunicorn 进程数 |

## 日常使用（后台操作）

1. 登录 `/admin/`
2. **资源库 → 分类**：先建几个分类（数字越小越靠前）
3. **资源库 → 标签**：建标签，例如「绿色版」「便携免安装」「开源免费」
4. **资源库 → 资源 → 新增**：
   - 填名称、版本号、分类、标签、卡片摘要、详细介绍
   - 页面下方的 **下载链接** 内联区：选「本地文件」就上传文件，选「外部链接」就填网盘地址和提取码
   - **更新日志** 内联区：一条记录写一个版本，内容一行一条
   - `首页置顶` 勾上就出现在首页顶部「站长推荐」
5. 列表页可直接勾选「已发布 / 首页置顶」批量修改，也有批量发布、批量下架、批量置顶、检查外链的批量操作

### 外链失效检查

```bash
# 默认只出报告，不改数据库
docker compose exec web python manage.py check_links

# 只复检上轮标记为失效的
docker compose exec web python manage.py check_links --only-broken

# 确认规则无误后再写回
docker compose exec web python manage.py check_links --apply
```

后台「资源」和「下载链接」列表页也有对应的批量操作。

> 说明：检测只能判断链接**能否访问**。网盘分享过期后部分平台仍返回 200，所以结果仅供参考。标记为失效只是在详情页多一个「疑似失效」徽标，**不会自动删除或隐藏链接**。

## 本地开发

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # 把 DEBUG 改成 True

export SECRET_KEY=dev-only
export DEBUG=True
python manage.py migrate
python manage.py ensure_admin
python manage.py runserver 8082
```

运行测试（37 个用例）：

```bash
python manage.py test
```

其中包含两条**防 N+1 回归**的断言：分别比较「2 条资源」与「8 条资源」时的 SQL 查询次数，要求完全相等。标签是多对多，必须用 `prefetch_related` 预取——如果用 `select_related`，这两条测试会立刻失败。

## 常见问题

**容器启动就退出，日志里是 `ImproperlyConfigured: 生产环境（DEBUG=False）必须通过环境变量提供 SECRET_KEY`**
这是故意的保护。`.env` 里没填 `SECRET_KEY`，填上再 `docker compose up -d` 即可。

**访问出现 400 Bad Request**
`ALLOWED_HOSTS` 没包含你访问用的域名或 IP。改 `.env` 后 `docker compose up -d` 重建。

**提交表单报 CSRF 错误**
用域名访问时把 `CSRF_TRUSTED_ORIGINS=https://你的域名` 加进 `.env`。

**上传大文件失败**
`.env` 里的 `MAX_UPLOAD_SIZE_MB` 只是记录用途，实际限制还受 nginx / 网关的 `client_max_body_size` 影响。大文件建议走网盘外链。

**本地文件的下载速度慢**
默认由 Django（gunicorn）提供 `/media/` 与下载流。如果前置了 nginx，把 `SERVE_MEDIA=False` 并在 nginx 里直接 `location /media/ { alias ...; }`，性能更好。

**SQLite 会不会被并发写锁住**
不会。已开启 WAL 模式 + 20 秒 `busy_timeout`，代码里也避免了长事务。本项目规模（几百资源、几十用户）远未触及瓶颈。

**想换端口**
只改 `docker-compose.yml` 里 `ports` 的左边（宿主机端口），容器内固定 8082。

## 免责声明

本站仅收录来自官方或可信来源的软件，仅供学习交流使用，请勿用于商业用途。如有侵权请联系删除。
