import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_app_version(base_dir: Path = BASE_DIR, environ: dict | None = None) -> str:
    """Load the application version.

    Priority: DJANGO_APP_VERSION env var (if non-empty after stripping),
    then the first line of base_dir/VERSION (stripped), then empty string.
    Never raises.
    """
    if environ is None:
        environ = os.environ
    env_val = environ.get("DJANGO_APP_VERSION", "").strip()
    if env_val:
        return env_val
    version_file = base_dir / "VERSION"
    try:
        content = version_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    first_line = content.splitlines()[0].strip() if content.splitlines() else ""
    return first_line


APP_NAME = "Downtime Market"
APP_VERSION = load_app_version()
APP_TAGLINE = "Spend your loot between sessions."
SITE_COPYRIGHT_YEAR = 2026

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") not in ("0", "false", "False", "")

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-change-me"
    else:
        raise RuntimeError(
            "DJANGO_SECRET_KEY environment variable is required in production (non-DEBUG mode)"
        )

# Validate that the dev default secret key is not used in production
if not DEBUG and SECRET_KEY == "dev-only-insecure-key-change-me":
    raise RuntimeError(
        "The default insecure SECRET_KEY cannot be used in production. Set DJANGO_SECRET_KEY."
    )
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if h.strip()
]

CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
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
    "character_options",
    "player_characters",
    "items",
    "core",
    "shops",
    "ledger",
    "map",
    "quests",
    "downtime",
    "agent_access",
    "starting_equipment",
    "mail",
    "play_sessions",
    "player_items",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.SecurityHeadersMiddleware",
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
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "accounts.passwords.ComplexityValidator"},
    {
        "NAME": "accounts.passwords.PasswordHistoryValidator",
        "OPTIONS": {"history_count": 5},
    },
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

# Mail settings
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
RESEND_WEBHOOK_SECRET = os.environ.get("RESEND_WEBHOOK_SECRET")
EMAIL_FROM = os.environ.get("EMAIL_FROM", f"{APP_NAME} <noreply@localhost>")

# SITE_URL for email links and base_context
_allowed = ALLOWED_HOSTS[0] if ALLOWED_HOSTS else "localhost"
SITE_URL = os.environ.get("SITE_URL", f"https://{_allowed}")

# Mail enabled: true when key is set or DEBUG
MAIL_ENABLED = bool(RESEND_API_KEY) or DEBUG

# Email backend selection (lazy import via dotted path)
if RESEND_API_KEY:
    EMAIL_BACKEND = "mail.backends.ResendBackend"
elif DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "mail.backends.DisabledBackend"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Cache configuration
# Production: Redis, Development: LocMemCache, Tests: DummyCache (in test_settings.py)
CACHES = {
    "default": {
        "BACKEND": os.environ.get(
            "DJANGO_CACHE_BACKEND",
            "django.core.cache.backends.locmem.LocMemCache",
        ),
        "LOCATION": os.environ.get("DJANGO_CACHE_LOCATION", "default"),
        "OPTIONS": {
            "MAX_ENTRIES": 10000,
        },
    }
}

if not DEBUG:
    # In production, use Redis if configured
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        CACHES["default"] = {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
            "OPTIONS": {
                "MAX_ENTRIES": 10000,
            },
        }

# Rate limiting configuration (configurable via environment variables)
RATELIMIT_LOGIN_ATTEMPTS = int(os.environ.get("RATELIMIT_LOGIN_ATTEMPTS", "5"))
RATELIMIT_LOGIN_WINDOW = int(os.environ.get("RATELIMIT_LOGIN_WINDOW", "60"))  # seconds
RATELIMIT_PASSWORD_ATTEMPTS = int(os.environ.get("RATELIMIT_PASSWORD_ATTEMPTS", "3"))
RATELIMIT_PASSWORD_WINDOW = int(os.environ.get("RATELIMIT_PASSWORD_WINDOW", "3600"))  # seconds
RATELIMIT_OAUTH_TOKEN_ATTEMPTS = int(os.environ.get("RATELIMIT_OAUTH_TOKEN_ATTEMPTS", "10"))
RATELIMIT_OAUTH_TOKEN_WINDOW = int(os.environ.get("RATELIMIT_OAUTH_TOKEN_WINDOW", "60"))  # seconds
RATELIMIT_MCP_ATTEMPTS = int(os.environ.get("RATELIMIT_MCP_ATTEMPTS", "60"))
RATELIMIT_MCP_WINDOW = int(os.environ.get("RATELIMIT_MCP_WINDOW", "60"))  # seconds
# Trust X-Forwarded-For for rate-limit client IPs.
# X-Forwarded-For is sent by the client and can be spoofed, so keying rate
# limits on it lets a sender evade per-IP limits. Only enable this behind a
# single trusted proxy that replaces the header with the real client IP.
RATELIMIT_TRUST_XFF = os.environ.get("RATELIMIT_TRUST_XFF", "0") not in (
    "0",
    "false",
    "False",
    "",
)
# Personal Access Token expiration (configurable via environment variable)
AGENT_TOKEN_EXPIRY_DAYS = int(os.environ.get("AGENT_TOKEN_EXPIRY_DAYS", "365"))

# HTTPS / SSL
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "1") not in (
    "0",
    "false",
    "False",
    "",
)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "1"
) not in ("0", "false", "False", "")
SECURE_HSTS_PRELOAD = os.environ.get("DJANGO_SECURE_HSTS_PRELOAD", "1") not in (
    "0",
    "false",
    "False",
    "",
)

# Content Security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Secure Cookies
SESSION_COOKIE_SECURE = os.environ.get("DJANGO_SESSION_COOKIE_SECURE", "1") not in (
    "0",
    "false",
    "False",
    "",
)
CSRF_COOKIE_SECURE = os.environ.get("DJANGO_CSRF_COOKIE_SECURE", "1") not in (
    "0",
    "false",
    "False",
    "",
)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Clickjacking
X_FRAME_OPTIONS = "DENY"

# Content Security Policy
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ("'self'",),
        "script-src": ("'self'",),
        "style-src": ("'self'", "'unsafe-inline'"),
        "img-src": ("'self'", "data:"),
        "font-src": ("'self'",),
        "connect-src": ("'self'",),
        "frame-ancestors": ("'none'",),
        "form-action": ("'self'",),
        "base-uri": ("'self'",),
        "object-src": ("'none'",),
    }
}

OAUTH2_PROVIDER = {
    "SCOPES": {"mcp": f"Use the {APP_NAME} tools for one club"},
    "DEFAULT_SCOPES": ["mcp"],
    "PKCE_REQUIRED": True,
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,  # S256 only
    "REQUEST_APPROVAL_PROMPT": "force",
    "ACCESS_TOKEN_EXPIRE_SECONDS": 3600,
    "ROTATE_REFRESH_TOKEN": True,
    "DCR_ENABLED": True,
    "DCR_REGISTRATION_PERMISSION_CLASSES": (
        "agent_access.oauth.permissions.ClubAdminOrGameMasterDCRPermission",
    ),
    "OAUTH2_PROTECTED_RESOURCE_NAME": f"{APP_NAME} MCP",
    # Redirect URI validation
    "ALLOW_URI_WILDCARDS": False,
    "ALLOW_LOCALHOST_LOOPBACK": DEBUG,
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"] if not DEBUG else ["http", "https"],
}
OAUTH2_PROVIDER_APPLICATION_MODEL = "oauth2_provider.Application"
