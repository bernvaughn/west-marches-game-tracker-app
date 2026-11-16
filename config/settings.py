import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

APP_NAME = "Downtime Market"
APP_TAGLINE = "Spend your loot between sessions."
SITE_COPYRIGHT_YEAR = 2026

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") not in ("0", "false", "False", "")

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-change-me"
    else:
        raise RuntimeError(
            "DJANGO_SECRET_KEY environment variable is required "
            "in production (non-DEBUG mode)"
        )

# Validate that the dev default secret key is not used in production
if not DEBUG and SECRET_KEY == "dev-only-insecure-key-change-me":
    raise RuntimeError(
        "The default insecure SECRET_KEY cannot be used in production. "
        "Set DJANGO_SECRET_KEY."
    )
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "oauth2_provider",
    "csp",
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

# HTTPS / SSL
SECURE_SSL_REDIRECT = os.environ.get(
    "DJANGO_SECURE_SSL_REDIRECT", "1"
) not in ("0", "false", "False", "")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS
SECURE_HSTS_SECONDS = int(
    os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "1"
) not in ("0", "false", "False", "")
SECURE_HSTS_PRELOAD = os.environ.get(
    "DJANGO_SECURE_HSTS_PRELOAD", "1"
) not in ("0", "false", "False", "")

# Content Security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Secure Cookies
SESSION_COOKIE_SECURE = os.environ.get(
    "DJANGO_SESSION_COOKIE_SECURE", "1"
) not in ("0", "false", "False", "")
CSRF_COOKIE_SECURE = os.environ.get(
    "DJANGO_CSRF_COOKIE_SECURE", "1"
) not in ("0", "false", "False", "")
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Clickjacking
X_FRAME_OPTIONS = "DENY"

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:")
CSP_FONT_SRC = ("'self'",)
CSP_CONNECT_SRC = ("'self'",)
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_FORM_ACTION = ("'self'",)
CSP_BASE_URI = ("'self'",)
CSP_OBJECT_SRC = ("'none'",)

OAUTH2_PROVIDER = {
    "SCOPES": {"mcp": f"Use the {APP_NAME} tools for one club"},
    "DEFAULT_SCOPES": ["mcp"],
    "PKCE_REQUIRED": True,
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,  # S256 only
    "REQUEST_APPROVAL_PROMPT": "force",
    "ACCESS_TOKEN_EXPIRE_SECONDS": 3600,
    "ROTATE_REFRESH_TOKEN": True,
    "DCR_ENABLED": True,
    "DCR_REGISTRATION_PERMISSION_CLASSES": ("oauth2_provider.dcr.AllowAllDCRPermission",),
    "OAUTH2_PROTECTED_RESOURCE_NAME": f"{APP_NAME} MCP",
}
OAUTH2_PROVIDER_APPLICATION_MODEL = "oauth2_provider.Application"
