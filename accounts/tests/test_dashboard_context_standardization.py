"""Regression tests for dashboard template context standardization.

These tests verify that all provider templates use `provider_context` consistently
and that the `dashboard_partial` endpoint wraps context correctly.

Related to task 01a1e697-bf0b-76cb-8edb-f2a9b0530e14.

Note: HeaderDashboardProvider (key="header") is intentionally excluded from the
provider grid loop and dashboard_partial endpoint. Header data is rendered in the
header via explicit include with flat keys.
"""

import pytest

from accounts.dashboard_providers import get_provider
from downtime.models import DowntimeAction, DowntimeEntry
from ledger.services import Line, record_many
from player_characters.junk import set_junk


@pytest.fixture
def player_with_junk(club, player, character, item):
    """Create a player with junk marked on their character."""
    # Make the item usable (retired=False)
    item.retired = False
    item.save(update_fields=["retired"])

    # Award the item to the character so they own it
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=item, quantity=5)],
                note="Test junk setup",
                actor=player,
            )
        ]
    )
    # Mark the item as junk
    set_junk(character, item, 3, player)
    return player


@pytest.fixture
def live_downtime_action(club, player, character):
    """Create a live downtime action with one entry for testing partials."""
    action = DowntimeAction.objects.create(
        club=club,
        name="Work at a bakery",
        cost=1,
    )
    DowntimeEntry.objects.create(action=action, label="Explore the area")
    return action


@pytest.mark.django_db
def test_page_render_shows_sell_junk_button_when_junk_exists(
    club, player_with_junk, character, login
):
    """Page render with a junk mark shows the 'Sell Junk' button.

    Symptom A: Previously, the Quick Actions card showed "No quick actions available."
    because the template read flat keys (`has_junk`) instead of `provider_context.has_junk`.
    """
    c = login(player_with_junk)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Sell Junk" in content, "Sell Junk button should be visible when character has junk"


@pytest.mark.django_db
def test_dashboard_partial_downtime_shows_action_row(
    club, live_downtime_action, player, character, login
):
    """dashboard_partial for downtime shows the action row and Spend button.

    Symptom B: Previously, the partial endpoint rendered with flat context,
    so templates reading provider_context.* failed to find their data.
    """
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/partial/downtime/")
    assert resp.status_code == 200
    content = resp.content.decode()
    # Should show the action row, not "No downtime actions available"
    assert "No downtime actions available" not in content, (
        "Downtime partial should show action row, not empty message"
    )
    assert "Spend" in content, "Spend button should be visible in downtime partial"


@pytest.mark.django_db
def test_all_provider_templates_use_provider_context(club, player, character, login):
    """Verify that all provider templates consistently use provider_context.* pattern.

    This is a documentation test that ensures we maintain the pattern.
    """
    # Check templates exist and use provider_context
    import os

    template_dir = "templates/accounts"
    # HeaderDashboardProvider uses flat keys via explicit include in dashboard.html
    template_names = [
        "_dashboard_quick_actions.html",
        "_dashboard_quests.html",
        "_dashboard_downtime.html",
        "_dashboard_map.html",
        "_dashboard_messages.html",
        "_dashboard_my_messages.html",
        "_dashboard_consumables.html",
        "_dashboard_player_shop.html",
    ]

    provider = get_provider("quick_actions")
    assert provider is not None, "QuickActionsProvider should be registered"

    # Read each template and verify it uses provider_context
    for template_name in template_names:
        template_path = os.path.join(template_dir, template_name)
        with open(template_path) as f:
            content = f.read()

        # Each template should reference provider_context somewhere
        # (The header template is excluded - it's handled separately)
        if "header" not in template_name.lower():
            # At least one reference to provider_context expected
            # This is a soft check - the template might use other patterns
            # The key is that ALL templates now work consistently
            assert "provider_context" in content, f"{template_name} should use provider_context"
