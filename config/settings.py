"""
Django settings for the Student Management System (SMS).

All sensitive configuration is read from environment variables (see
``.env.example``).  Nothing secret is hard coded in this file.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.env import BASE_DIR, env, env_bool, env_int, env_list

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = BASE_DIR

SECRET_KEY = env("DJANGO_SECRET_KEY", "")
# A checkout with no ``.env`` file at all is a local development setup, so we
# default to DEBUG=True and an ephemeral key. As soon as a secret key is
# configured we assume a real deployment and keep DEBUG off by default.
DEV_MODE = not SECRET_KEY
DEBUG = env_bool("DJANGO_DEBUG", DEV_MODE)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-development-only-key-do-not-use-in-production"
    else:  # pragma: no cover - safety net
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is missing. Copy .env.example to .env and set a "
            "long random value before running with DEBUG=False."
        )

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Third party
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    # Project applications
    "core",
    "academics",
    "accounts",
    "teachers",
    "students",
    "attendance",
    "exams",
    "fees",
    "notifications",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Project middleware (audit trail / request context)
    "core.middleware.RequestAuditMiddleware",
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
                "core.context_processors.application_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# No .env => development mode => SQLite so the project runs with zero setup.
# Any configured deployment gets MySQL unless it explicitly asks for SQLite.
DB_ENGINE = (env("DB_ENGINE", "sqlite" if DEV_MODE else "mysql") or "mysql").lower()

if DB_ENGINE in {"mysql", "mysql2", "mariadb"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("DB_NAME", "sms_db"),
            "USER": env("DB_USER", "sms_user"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "127.0.0.1"),
            "PORT": env("DB_PORT", "3306"),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
                **({"ssl": {"ca": env("DB_SSL_CA")}} if env("DB_SSL_CA") else {}),
            },
            "TEST": {
                "NAME": env("DB_TEST_NAME", "test_sms_db"),
                "CHARSET": "utf8mb4",
                "COLLATION": "utf8mb4_unicode_ci",
            },
        }
    }
elif DB_ENGINE == "sqlite":
    # Convenience fallback for quick local experiments (not recommended).
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("DB_NAME", str(BASE_DIR / "db.sqlite3")),
        }
    }
else:  # pragma: no cover
    raise ImproperlyConfigured(f"Unsupported DB_ENGINE: {DB_ENGINE}")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
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

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 hours
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = env("DJANGO_LANGUAGE_CODE", "en-us")
TIME_ZONE = env("DJANGO_TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

DATE_FORMAT = "d M Y"
DATETIME_FORMAT = "d M Y, h:i A"
SHORT_DATE_FORMAT = "d/m/Y"

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))

MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 5)
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

LOG_DIR = BASE_DIR / "logs"
try:  # pragma: no cover - best effort
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@example.com")

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
CSRF_COOKIE_HTTPONLY = False  # required so JS can read the token on AJAX posts
CSRF_TRUSTED_ORIGINS = [
    origin for origin in env_list("DJANGO_CSRF_TRUSTED_ORIGINS") if origin
]

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", False)
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 0)
if SECURE_HSTS_SECONDS:
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.api_pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DATETIME_FORMAT": "iso-8601",
}

# ---------------------------------------------------------------------------
# Project specific defaults
# ---------------------------------------------------------------------------
SMS = {
    "DEFAULT_PER_PAGE": 10,
    "MAX_PER_PAGE": 100,
    "ACADEMIC_YEAR": env("ACADEMIC_YEAR", "2024-2025"),
    "CURRENT_SEMESTER": env_int("CURRENT_SEMESTER", 1),
    "PASS_PERCENTAGE": env_int("PASS_PERCENTAGE", 40),
    "ATTENDANCE_SHORTAGE_PERCENTAGE": env_int("ATTENDANCE_SHORTAGE_PERCENTAGE", 75),
    "RECEIPT_PREFIX": env("RECEIPT_PREFIX", "RCPT"),
    "INSTITUTE_NAME": env("INSTITUTE_NAME", "Springfield Institute of Technology"),
    "INSTITUTE_CODE": env("INSTITUTE_CODE", "SIT"),
    "CURRENCY": env("CURRENCY", "INR"),
    "CURRENCY_SYMBOL": env("CURRENCY_SYMBOL", "₹"),
}

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "sms.log"),
            "maxBytes": 2 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO" if DEBUG else "WARNING",
            "propagate": False,
        },
        "sms": {
            "handlers": ["console", "file"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}
