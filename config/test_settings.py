"""Test settings optimized for speed."""

import os

# Set test environment variables BEFORE importing base settings
os.environ.setdefault("DJANGO_DEBUG", "1")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("DJANGO_SECURE_SSL_REDIRECT", "0")
os.environ.setdefault("DJANGO_SECURE_HSTS_SECONDS", "0")
os.environ.setdefault("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "0")
os.environ.setdefault("DJANGO_SECURE_HSTS_PRELOAD", "0")
os.environ.setdefault("DJANGO_SESSION_COOKIE_SECURE", "0")
os.environ.setdefault("DJANGO_CSRF_COOKIE_SECURE", "0")

from .settings import *  # noqa: F403,F401

# Override security settings for test environment
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# CSP settings - more permissive for tests
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ("'self'", "'unsafe-inline'"),
        "script-src": ("'self'", "'unsafe-inline'"),
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

# Use in-memory SQLite for faster tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
        },
    }
}

# Disable migrations for faster test setup
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Use faster password hasher (already in conftest.py, but belt-and-suspenders)
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Disable logging during tests
LOGGING = {}

# Use dummy cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Faster template loading
TEMPLATE_LOADERS = [
    ("django.template.loaders.cached.Loader", [
        "django.template.loaders.filesystem.Loader",
        "django.template.loaders.app_directories.Loader",
    ]),
]

# Disable debug toolbar if present
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "debug_toolbar"]  # noqa: F405
MIDDLEWARE = [m for m in MIDDLEWARE if "debug_toolbar" not in m]  # noqa: F405

# Speed up static files
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Disable email backend overhead
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"