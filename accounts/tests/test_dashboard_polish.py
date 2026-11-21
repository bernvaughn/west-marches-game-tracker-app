"""Polish checks for the player dashboard: subtitle, stat grid, Spend button, quests card."""

import re
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership
from downtime import services as downtime_services
from downtime.models import DowntimeAction, DowntimeEntry
from player_characters.models import Character


@pytest.fixture
def action(club):
    return DowntimeAction.objects.create(
        club=club,
        name="Work at a bakery",
        cost=1,
        start_date=timezone.localdate() - timedelta(days=1),
    )


@pytest.fixture
def entries(action):
    return [
        DowntimeEntry.objects.create(action=action, label="Bread", weight=3, coins=10, order=0),
        DowntimeEntry.objects.create(action=action, label="Nothing", weight=1, order=1),
    ]


def _dashboard(client, club_slug):
    return client.get(reverse("accounts:player_dashboard", args=[club_slug]))


def _subtitle(html):
    match = re.search(r'<p class="wm-page-subtitle">(.*?)</p>', html, re.S)
    assert match, "wm-page-subtitle not found"
    return match.group(1).strip()


# ---------------------------------------------------------------------------
# Subtitle
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_subtitle_is_quick_actions(club, player, character, login):
    """Subtitle reads exactly "Quick actions" with no trailing blank text."""
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    assert _subtitle(resp.content.decode()) == "Quick actions"


# ---------------------------------------------------------------------------
# Stat grid
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_stats_use_grid_without_xp(club, player, character, login):
    """Without XP there are four stats, all children of .wm-dashboard-stats, no col-md-3."""
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "col-md-3" not in html
    assert html.count('class="wm-dashboard-stat"') == 4
    assert "wm-dashboard-stats" in html


@pytest.mark.django_db
def test_dashboard_stats_include_xp_in_grid(club, player, character, login):
    """With XP set, XP joins the grid as a fifth stat, none orphaned."""
    character.xp = 1250
    character.save(update_fields=["xp"])
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "col-md-3" not in html
    assert html.count('class="wm-dashboard-stat"') == 5
    assert "1,250" in html


# ---------------------------------------------------------------------------
# Spend button
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_spend_button_is_outline(club, player, character, action, entries, login):
    """Spend action in the Downtime card is an outline button, not wm-chalk-button."""
    downtime_services.award(character, 1, note="t", by=player)
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Spend" in html
    assert "btn-outline-secondary" in html
    assert "wm-chalk-button" not in html


# ---------------------------------------------------------------------------
# Quests card
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_ready_quest_stacked_block(club, player, character, quest, item, give, login):
    """Ready quest name and "Ready to turn in" sit in one flex-column block."""
    give(character, item, 2)
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert quest.name in html
    assert "Ready to turn in" in html
    # Name and subtext share one flex-column wrapper; Turn in stays on one line.
    assert "flex-column" in html
    assert "text-nowrap" in html


# ---------------------------------------------------------------------------
# Icon polish
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_quests_header_icon(club, player, character, login):
    """Quests card header uses journal-text icon (exists in sprite), not scroll."""
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Quests" in html
    assert "#journal-text" in html
    assert "#scroll" not in html


@pytest.mark.django_db
def test_dashboard_switch_button_icon(club, player, character, login):
    """Switch button shows person icon when the player has multiple characters."""
    owner = Membership.objects.get(user=player, club=club)
    Character.objects.create(club=club, owner=owner, name="Second Character")
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Switch" in html
    assert "#person" in html
    assert "#user" not in html


@pytest.mark.django_db
def test_dashboard_no_character_icon(club, other_player, login):
    """No-character empty state shows its person icon."""
    c = login(other_player)
    resp = c.get(reverse("accounts:player_dashboard", args=[club.slug]))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "No Character Selected" in html
    assert "#person" in html
    assert "#user" not in html


@pytest.mark.django_db
def test_dashboard_spend_confirm_primary_button(club, player, character, action, entries, login):
    """Spend confirm "Take the job" is a primary button, not wm-chalk-button."""
    downtime_services.award(character, 1, note="test", by=player)
    c = login(player)
    spend_url = f"/c/{club.slug}/accounts/dashboard/partial/downtime_spend/{action.pk}/"
    resp = c.get(spend_url, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Take the job" in body
    assert "btn btn-primary" in body
    assert "wm-chalk-button" not in body
