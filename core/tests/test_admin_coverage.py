"""Admin coverage test for all first-party apps.

Every model in a first-party app must either be registered in the admin
or be listed in LEFT_OUT_ON_PURPOSE below with a reason.

First-party apps are derived from ``apps.get_app_configs()``: an app is
first-party when its code lives under ``settings.BASE_DIR`` and not under
site-packages or a venv. A new first-party app is then covered with no edit
to this file. Django built-ins and third-party models are excluded by the
derivation and are not listed here.
"""

from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib import admin as django_admin

# Models intentionally not registered in the admin, keyed by
# "app_label.ModelName" so a same-named model in another app is not hidden.
# Django built-ins and third-party models are already excluded by the
# first-party derivation above and are deliberately not listed.
LEFT_OUT_ON_PURPOSE = {
    # mail: holds message bodies with live tokens, deleted after sending
    "mail.EmailPayload",
}


def first_party_app_configs():
    """First-party app configs: code under settings.BASE_DIR."""
    base_dir = Path(settings.BASE_DIR).resolve()
    configs = []
    for config in apps.get_app_configs():
        config_path = Path(config.path).resolve()
        parts = config_path.parts
        if "site-packages" in parts or ".venv" in parts:
            continue
        try:
            config_path.relative_to(base_dir)
        except ValueError:
            continue
        configs.append(config)
    return configs


def registered_model_keys():
    return {f"{model._meta.app_label}.{model.__name__}" for model in django_admin.site._registry}


def test_first_party_derivation():
    """The derivation covers map and accounts and excludes Django/third-party."""
    labels = {config.label for config in first_party_app_configs()}
    assert {"map", "accounts", "core"} <= labels
    assert "auth" not in labels and "admin" not in labels and "contenttypes" not in labels


def test_every_first_party_model_is_registered_or_allowlisted():
    """Every first-party model is registered in the admin or allowlisted."""
    registered = registered_model_keys()
    missing = {}
    for config in first_party_app_configs():
        for model in config.get_models():
            key = f"{model._meta.app_label}.{model.__name__}"
            if key not in registered and key not in LEFT_OUT_ON_PURPOSE:
                missing.setdefault(config.label, []).append(model.__name__)
    assert not missing, (
        "Unregistered models found in first-party apps:\n"
        + "\n".join(f"  {app}: {', '.join(sorted(models))}" for app, models in missing.items())
        + "\n\nRegister them in their respective admin.py files, or add to "
        "LEFT_OUT_ON_PURPOSE in core/tests/test_admin_coverage.py with a reason."
    )


def test_allowlist_entries_name_real_models():
    """Every allowlist key names a real model (catches typos)."""
    for key in LEFT_OUT_ON_PURPOSE:
        apps.get_model(key)  # raises LookupError on a bad key


def test_no_registered_model_is_allowlisted():
    """An allowlist entry whose model is registered is stale and must be removed."""
    registered = registered_model_keys()
    stale = sorted(registered & set(LEFT_OUT_ON_PURPOSE))
    assert not stale, (
        "Allowlist entries for models that are registered in the admin:\n"
        + "\n".join(f"  {key}" for key in stale)
        + "\n\nRemove stale entries from LEFT_OUT_ON_PURPOSE in "
        "core/tests/test_admin_coverage.py."
    )
