"""
资源分享网站 - 项目配置

所有可变配置一律从环境变量读取，仓库内不出现任何密钥。
本地开发可复制 .env.example 为 .env（.env 已在 .gitignore 中排除）。
"""
import os
from pathlib import Path

from django.db.backends.signals import connection_created
from django.dispatch import receiver

BASE_DIR = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# 环境变量读取辅助函数
# --------------------------------------------------------------------------
def env_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def env_list(key: str, default: str = "") -> list:
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# --------------------------------------------------------------------------
# 安全
# --------------------------------------------------------------------------
DEBUG = env_bool("DEBUG", False)

SECRET_KEY = env_str("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        # 仅本地开发用的占位密钥
        SECRET_KEY = "django-insecure-dev-only-key-change-me"
    else:
        # 拒绝带着默认密钥上线：密钥泄漏等于会话与 CSRF 全部失守
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            "生产环境（DEBUG=False）必须通过环境变量提供 SECRET_KEY。\n"
            "生成方式：python -c \"from django.core.management.utils import "
            "get_random_secret_key as g; print(g())\"\n"
            "然后写入 .env 并重启容器。"
        )

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")

# 反向代理 / 域名访问时填写，例如 https://pan.example.com
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# 部署在 nginx / 飞牛网关之后时，让 Django 识别 https
if env_bool("USE_X_FORWARDED_PROTO", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if env_bool("SECURE_COOKIES", False):
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # 前端 JS 需要读取 csrftoken
X_FRAME_OPTIONS = "SAMEORIGIN"


# --------------------------------------------------------------------------
# 应用
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # 本项目
    "accounts",
    "resources",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "resources.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --------------------------------------------------------------------------
# 数据库（SQLite，开启 WAL 缓解并发写锁）
# --------------------------------------------------------------------------
DB_PATH = Path(env_str("DB_PATH", str(BASE_DIR / "data" / "db.sqlite3")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(DB_PATH),
        "OPTIONS": {"timeout": env_int("SQLITE_TIMEOUT", 20)},
    }
}


@receiver(connection_created)
def _set_sqlite_pragmas(sender, connection, **kwargs):
    """每个新连接都应用 PRAGMA：WAL 提升并发读，busy_timeout 避免立刻报锁。"""
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute(f"PRAGMA busy_timeout={env_int('SQLITE_TIMEOUT', 20) * 1000};")
        cursor.execute("PRAGMA foreign_keys=ON;")


# --------------------------------------------------------------------------
# 认证
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# --------------------------------------------------------------------------
# 国际化
# --------------------------------------------------------------------------
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = env_str("TZ", "Asia/Shanghai")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# 静态文件与媒体文件
# --------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# 生产环境用压缩+哈希清单；本地 DEBUG 下退回普通存储，避免未 collectstatic 时报错
if DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }

WHITENOISE_MAX_AGE = 31536000 if not DEBUG else 0
WHITENOISE_KEEP_ONLY_HASHED_FILES = False

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env_str("MEDIA_ROOT", str(BASE_DIR / "media")))
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# True：由 Django 提供 /media/ 访问（部署简单）
# False：交给前置 nginx / 飞牛网关，吞吐更好
SERVE_MEDIA = env_bool("SERVE_MEDIA", True)

# 允许的图片上传类型与体积上限
MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 2048)  # 单个本地文件上限 2GB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------
# 站点自有配置
# --------------------------------------------------------------------------
SITE_NAME = env_str("SITE_NAME", "资源小站")
SITE_SUBTITLE = env_str("SITE_SUBTITLE", "只分享干净、无捆绑的资源")
SITE_FOOTER = env_str(
    "SITE_FOOTER", "本站资源多为第三方网盘外链，可能失效，请以实际为准。"
)

PAGE_SIZE = env_int("PAGE_SIZE", 12)
EXTERNAL_LINK_CHECK_TIMEOUT = env_int("EXTERNAL_LINK_CHECK_TIMEOUT", 8)


# --------------------------------------------------------------------------
# 日志
# --------------------------------------------------------------------------
LOG_LEVEL = env_str("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"}
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
