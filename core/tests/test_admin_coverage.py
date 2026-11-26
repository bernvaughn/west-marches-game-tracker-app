"""Shared admin coverage test for all first-party apps.

Every model in a first-party app must either be registered in the admin
or be listed in the allowlist below with a reason.
"""

from django.apps import apps
from django.contrib import admin as django_admin


def test_every_first_party_model_is_in_the_admin():
    """All first-party models are registered in the admin or allowlisted."""
    first_party_apps = [
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
        "core",  # core may have models too
    ]

    registered = {m.__name__ for m in django_admin.site._registry}

    # Allowlist: models intentionally not in the admin, with reasons.
    left_out_on_purpose = {
        # mail: holds message body with live tokens, deleted after sending
        "EmailPayload",
        # Django built-ins
        "User",
        "Group",
        "Permission",
        "ContentType",
        "Session",
        "LogEntry",
        "Migration",
        # oauth2_provider (third-party)
        "AccessToken",
        "RefreshToken",
        "Application",
        "Grant",
        "IDToken",
        # character_options: will be registered in task C2
        "Species",
        "CharacterClass",
        "Background",
        # player_characters: will be registered in task C3
        "SelectedCharacter",
        "JunkMark",
        "ItemNote",
        # items: will be registered in task C4
        "ContainerSlot",
        "ContainerSlotOption",
        "RecentItemPick",
        "ClubWeightSettings",
        "ContainerOpening",
        # map: not part of admin improvements epic
        "CreditGrant",
        "FoundMark",
        # downtime: will be registered in task C5
        "DowntimePointEntry",
        "DowntimeAction",
        "DowntimeEntry",
        "DowntimeEntryItem",
        "DowntimeResult",
        "DowntimePointRequest",
    }

    all_missing = {}
    for app_label in first_party_apps:
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            # App might not be installed in this test run
            continue
        models = {m.__name__ for m in app_config.get_models()}
        missing = models - registered - left_out_on_purpose
        if missing:
            all_missing[app_label] = sorted(missing)

    assert not all_missing, (
        "Unregistered models found in first-party apps:\n"
        + "\n".join(f"  {app}: {', '.join(models)}" for app, models in all_missing.items())
        + "\n\nRegister them in their respective admin.py files, or add to the "
        "allowlist in core/tests/test_admin_coverage.py with a reason."
    )
