"""Test settings optimized for speed."""

from .settings import *  # noqa: F403,F401

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

# Disable CSRF for tests (not needed for API tests)
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

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
