"""
Django settings for CosRay-Backend.

使用 django-environ 管理环境变量配置。
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# 初始化环境变量
env = environ.Env(
    DEBUG=(bool, False),
)

# 读取 .env 文件（如果存在）
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

# 核心配置
SECRET_KEY = os.environ.get("SECRET_KEY", "!!!SET-SECRET-KEY-IN-PRODUCTION!!!")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("ALLOWED_HOSTS", "").split(",") if host.strip()]
IS_TESTING = bool(os.environ.get("PYTEST_CURRENT_TEST")) or any("pytest" in arg for arg in sys.argv)
# pre-commit 和 pre-commit.ci 在运行时会设置 PRE_COMMIT_HOME 环境变量
# 当在 pre-commit 或 mypy 插件上下文中导入 Django settings 时，允许回退到本地缓存以避免配置阻断静态检查
IS_PRE_COMMIT = bool(os.environ.get("PRE_COMMIT_HOME") or os.environ.get("PRE_COMMIT"))
REDIS_URL = os.environ.get("REDIS_URL", "").strip()


# Application definition

INSTALLED_APPS = [
    "unfold",  # 必须在 django.contrib.admin 之前
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 第三方应用
    "corsheaders",
    "ninja_jwt",
    # 本地应用
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # 静态文件服务
    "core.middleware.RequestIdMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # CORS 必须在 CommonMiddleware 之前
    "django.contrib.sessions.middleware.SessionMiddleware",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

_test_database_url = os.environ.get("TEST_DATABASE_URL", "").strip()

if IS_TESTING and not _test_database_url:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / ".test.db"),
        }
    }
elif IS_TESTING and _test_database_url:
    DATABASES = {"default": env.db_url_config(_test_database_url)}
else:
    _database_url = os.environ.get("DATABASE_URL")
    DATABASES = {
        "default": env.db_url_config(_database_url or "postgres://localhost/dummy"),
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "zh-hans"

TIME_ZONE = "Asia/Shanghai"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Whitenoise 配置
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# CORS 配置
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=False)
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]

# 生产安全配置
USE_X_FORWARDED_HOST = env.bool("USE_X_FORWARDED_HOST", default=not DEBUG and not IS_TESTING)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=not DEBUG and not IS_TESTING)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=not DEBUG and not IS_TESTING)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=not DEBUG and not IS_TESTING)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000 if not DEBUG and not IS_TESTING else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=not DEBUG and not IS_TESTING,
)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=not DEBUG and not IS_TESTING)
SECURE_CONTENT_TYPE_NOSNIFF = env.bool("SECURE_CONTENT_TYPE_NOSNIFF", default=True)
SECURE_REFERRER_POLICY = os.environ.get("SECURE_REFERRER_POLICY", "same-origin")
X_FRAME_OPTIONS = os.environ.get("X_FRAME_OPTIONS", "DENY")

# IoTDB 配置
IOTDB_HOST = os.environ.get("IOTDB_HOST", "localhost")
IOTDB_PORT = env.int("IOTDB_PORT", default=6667)
IOTDB_USER = os.environ.get("IOTDB_USER", "root")
IOTDB_PASSWORD = os.environ.get("IOTDB_PASSWORD", "root")

# 缓存配置
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    # 在非 DEBUG 且非测试且非 pre-commit 环境下强制要求 Redis
    if not DEBUG and not IS_TESTING and not IS_PRE_COMMIT:
        raise ImproperlyConfigured("生产环境必须配置 REDIS_URL, 禁止回退到进程内缓存")
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "cosray-backend-cache",
        }
    }

# JWT 配置
NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=env.int("JWT_ACCESS_TOKEN_LIFETIME_HOURS", default=24)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=3)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# 安全限流配置
RATE_LIMIT_CACHE_PREFIX = os.environ.get("RATE_LIMIT_CACHE_PREFIX", "ratelimit")
LOGIN_RATE_LIMIT_COUNT = env.int("LOGIN_RATE_LIMIT_COUNT", default=5)
LOGIN_RATE_LIMIT_WINDOW_SECONDS = env.int("LOGIN_RATE_LIMIT_WINDOW_SECONDS", default=300)
REGISTER_RATE_LIMIT_COUNT = env.int("REGISTER_RATE_LIMIT_COUNT", default=3)
REGISTER_RATE_LIMIT_WINDOW_SECONDS = env.int("REGISTER_RATE_LIMIT_WINDOW_SECONDS", default=3600)
UPLOAD_RATE_LIMIT_COUNT = env.int("UPLOAD_RATE_LIMIT_COUNT", default=120)
UPLOAD_RATE_LIMIT_WINDOW_SECONDS = env.int("UPLOAD_RATE_LIMIT_WINDOW_SECONDS", default=60)

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
