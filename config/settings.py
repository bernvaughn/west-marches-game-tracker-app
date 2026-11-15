import logging.config
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

APP_NAME = "Downtime Market"
APP_TAGLINE = "Spend your loot between sessions."

DEBUG = os.environ.get("DJANGO_DEBUG", "0") in ("1", "true", "True")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-change-me"
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if h.strip()
]

# CORS settings for MCP/OAuth endpoints
ALLOWED_MCP_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_MCP_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]

# Production security settings
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "csp",
    "rest_framework",
    "oauth2_provider",
    "accounts",
    "player_characters",
    "items",
    "shops",
    "ledger",
    "map",
    "quests",
    "downtime",
    "agent_access",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.ClubMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.app_name",
                "accounts.context_processors.clubs",
                "player_characters.context_processors.selection",
                "accounts.approvals.context_processor",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DATABASE_PATH", str(BASE_DIR / "db.sqlite3")),
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "init_command": (
                "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000;"
            ),
        },
    }
}

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
FORMAT_MODULE_PATH = ["config.formats"]  # the one date format (config/formats/en/formats.py)
TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

FORM_RENDERER = "config.form_renderer.BootstrapFormRenderer"

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Static URLs carry ?v=<content hash>: no stale CSS/JS, no collectstatic needed.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "config.static_storage.VersionedStaticFilesStorage"},
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

OAUTH2_PROVIDER = {
    "SCOPES": {"mcp": f"Use the {APP_NAME} tools for one club"},
    "DEFAULT_SCOPES": ["mcp"],
    "PKCE_REQUIRED": True,
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,  # S256 only
    "REQUEST_APPROVAL_PROMPT": "force",
    "ACCESS_TOKEN_EXPIRE_SECONDS": 3600,
    "ROTATE_REFRESH_TOKEN": True,
    "DCR_ENABLED": True,
    "DCR_REGISTRATION_PERMISSION_CLASSES": ("agent_access.permissions.RestrictedDCRPermission",),
    "OAUTH2_PROTECTED_RESOURCE_NAME": f"{APP_NAME} MCP",
    # RFC 9700 compliance settings
    "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT": True,
    "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT": True,
    "COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT": True,
    "COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS": True,
    "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,
    "REFRESH_TOKEN_REUSE_PROTECTION": True,
    "COMPLIANT_BCP_RFC9700_REDIRECT_URI_SCHEME": True,
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"] if not DEBUG else ["http", "https"],
}
OAUTH2_PROVIDER_APPLICATION_MODEL = "oauth2_provider.Application"

# REST Framework rate limiting
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/minute",
        "user": "1000/minute",
        "auth": "20/minute",      # Login, password reset
        "oauth": "30/minute",     # OAuth authorize, token
        "mcp": "60/minute",       # MCP tool calls
        "dcr": "10/hour",         # Dynamic client registration
    }
}

# Content Security Policy (CSP) configuration (django-csp 4.0+ format)
# htmx requires 'unsafe-inline' for inline scripts and styles
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-inline'", "'nonce-{{ csp_nonce }}'"],
        "style-src": ["'self'", "'unsafe-inline'", "'nonce-{{ csp_nonce }}'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "form-action": ["'self'"],
        "base-uri": ["'self'"],
    }
}

# Security logging configuration

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "security": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "security",
        },
    },
    "loggers": {
        "security.auth": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "security.oauth": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "security.mcp": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "security.password": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "security.batch": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

logging.config.dictConfig(LOGGING)
