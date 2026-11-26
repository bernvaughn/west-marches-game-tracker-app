"""Shared admin coverage test for all first-party apps.

Iterates all first-party apps and asserts every model is either registered
in the admin or in the allowlist with a documented reason.
"""

from django.apps import apps
from django.contrib import admin as django_admin

# All first-party app labels in this project
FIRST_PARTY_APPS = [
    "accounts",
    "character_options",
    "player_characters",
    "items",
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


# Models intentionally not registered in the admin, with reasons
ALLOWLIST = {
    # mail: holds message body with live tokens, deleted after sending
    "EmailPayload",
    # items: will be registered in task C4
    "ContainerSlot",
    "ContainerSlotOption",
    "RecentItemPick",
    "ClubWeightSettings",
    "ContainerOpening",
    # map: not part of admin improvements epic
    "CreditGrant",
    "FoundMark",
}


def test_every_first_party_model_is_in_the_admin():
    """All first-party models must be registered in admin, or in ALLOWLIST."""
    registered = {m.__name__ for m in django_admin.site._registry}
    missing_by_app = {}

    for app_label in FIRST_PARTY_APPS:
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            # App not installed (e.g., downtime not yet created)
            continue

        missing = {m.__name__ for m in app_config.get_models()} - registered - ALLOWLIST

        if missing:
            missing_by_app[app_label] = sorted(missing)

    assert not missing_by_app, (
        "Register these models in their respective admin.py files:\n"
        + "\n".join(f"  {app}: {models}" for app, models in missing_by_app.items())
    )
