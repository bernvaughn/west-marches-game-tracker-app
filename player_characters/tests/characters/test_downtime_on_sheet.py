"""Tests for downtime points displayed on the printable character sheet (U37, U87)."""

import re

import pytest

from downtime import services

from .test_sheet import u


def _dt_points_dd(html, expected_value):
    """Check that <dt>Downtime points</dt><dd> contains the expected value at start."""
    # The <dd> contains the number followed by action buttons/help text.
    # Match the number at the beginning of the <dd> content.
    pattern = rf"<dt>Downtime points</dt><dd>\s*{expected_value}\b"
    return re.search(pattern, html) is not None


@pytest.mark.story("U37")
@pytest.mark.story("U87")
@pytest.mark.django_db
def test_downtime_points_in_combat_box_with_balance(club, login, player, funded, game_master):
    """Downtime points appear in Combat/Stats box alongside AC, Max HP, XP and equal the balance."""
    c = login(player)

    # Initial state: zero balance shows 0
    html = c.get(u("characters:detail", club, funded.pk)).content.decode()
    assert "Downtime points" in html
    # The value should be 0 (or rendered as 0) in the <dd> after <dt>Downtime points</dt>
    # Check the Combat/Stats box has AC, Max HP, XP, and Downtime points
    assert "AC" in html
    assert "Max HP" in html
    assert "XP" in html
    assert _dt_points_dd(html, 0)

    # Award 3 downtime points
    services.award(funded, 3, "Session 3", by=game_master, club=club)
    assert services.balance(funded) == 3

    # Refresh the sheet
    html = c.get(u("characters:detail", club, funded.pk)).content.decode()
    # Downtime points should now show 3
    assert _dt_points_dd(html, 3)
    # Still alongside AC, Max HP, XP
    assert "AC" in html
    assert "Max HP" in html
    assert "XP" in html


@pytest.mark.story("U37")
@pytest.mark.story("U87")
@pytest.mark.django_db
def test_downtime_points_zero_balance_shows_zero(club, login, player, funded):
    """Zero downtime balance renders as 0 in the Combat/Stats box."""
    c = login(player)
    html = c.get(u("characters:detail", club, funded.pk)).content.decode()
    # New character has no downtime entries, balance should be 0
    assert services.balance(funded) == 0
    assert _dt_points_dd(html, 0)


@pytest.mark.story("U37")
@pytest.mark.story("U87")
@pytest.mark.django_db
def test_downtime_points_after_spend_shows_remaining(club, login, player, funded, game_master):
    """After spending downtime points, the sheet shows the remaining balance."""
    c = login(player)

    # Create a downtime action with cost 2
    from datetime import timedelta

    from django.utils import timezone

    from downtime.models import DowntimeAction, DowntimeEntry

    today = timezone.localdate()
    action = DowntimeAction.objects.create(
        club=club, name="Test Action", start_date=today - timedelta(days=1), cost=2
    )
    DowntimeEntry.objects.create(action=action, label="Reward", weight=1, coins=10, order=0)

    # Award 5 points
    services.award(funded, 5, "Big session", by=game_master, club=club)
    assert services.balance(funded) == 5

    html = c.get(u("characters:detail", club, funded.pk)).content.decode()
    assert _dt_points_dd(html, 5)

    # Spend 2 points on an action
    result = services.spend(funded, action, game_master)
    assert result is not None
    assert services.balance(funded) == 3

    # Refresh sheet - should show 3
    html = c.get(u("characters:detail", club, funded.pk)).content.decode()
    assert _dt_points_dd(html, 3)


@pytest.mark.story("U37")
@pytest.mark.story("U87")
@pytest.mark.django_db
def test_downtime_points_appears_in_printable_sheet(club, login, player, funded, game_master):
    """The printable character sheet (detail view) includes downtime points in Combat/Stats box."""
    c = login(player)

    # Award points
    services.award(funded, 4, "Session 4", by=game_master, club=club)

    # The detail view IS the printable sheet (Print button calls window.print())
    html = c.get(u("characters:detail", club, funded.pk)).content.decode()

    # Verify Combat/Stats box structure includes downtime points
    combat_box_match = re.search(
        r'<section class="wm-sheet-box wm-sheet-half"[^>]*aria-labelledby="sheet-combat"'
        r"[^>]*>.*?</section>",
        html,
        re.DOTALL,
    )
    assert combat_box_match, "Combat/Stats box not found in sheet"
    combat_html = combat_box_match.group(0)

    # Check all four stats are present
    assert "AC" in combat_html
    assert "Max HP" in combat_html
    assert "Passive Perception" in combat_html
    assert "XP" in combat_html
    assert "Downtime points" in combat_html

    # Check the value matches the balance (4)
    assert _dt_points_dd(combat_html, 4)
