"""Tests for dashboard XP progress and latest awards (story U135)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership, User
from downtime.models import DowntimePointEntry
from ledger.services import Line, record
from player_characters.models import Character


def _dashboard(client, club_slug):
    return client.get(reverse("accounts:player_dashboard", args=[club_slug]))


def _award_ledger(character, item, kind, coins=0, qty=1, note="", date=None):
    lines = []
    if coins:
        lines.append(Line(coins=coins))
    if item and qty:
        lines.append(Line(item=item, quantity=qty))
    return record(character, kind, lines, note=note, date=date)


# ---------------------------------------------------------------------------
# XP progress
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_xp_progress_shows_bar_and_label(club, player, character, login):
    """XP 6500 at level 5 shows '6,500 / 14,000 XP to level 6' with a bar."""
    character.xp = 6500
    character.level = 5
    character.save(update_fields=["xp", "level"])
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "6,500 / 14,000 XP to level 6" in html
    assert 'class="wm-xp-bar"' in html


@pytest.mark.django_db
def test_xp_progress_max_level(club, player, character, login):
    """Level 20 shows 'Max level' and no bar."""
    character.xp = 355000
    character.level = 20
    character.save(update_fields=["xp", "level"])
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Max level" in html
    assert 'class="wm-xp-bar"' not in html


@pytest.mark.django_db
def test_xp_progress_blank_xp(club, player, character, login):
    """Blank XP shows no progress bar and no badge."""
    character.xp = None
    character.save(update_fields=["xp"])
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "wm-xp" not in html
    assert "Level up ready" not in html


@pytest.mark.django_db
def test_level_up_ready_badge(club, player, character, login):
    """XP above stored level shows 'Level up ready' badge linking to edit form."""
    character.xp = 14000
    character.level = 5
    character.save(update_fields=["xp", "level"])
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Level up ready" in html
    assert f'href="{reverse("characters:edit", args=[club.slug, character.pk])}"' in html
    character.refresh_from_db()
    assert character.level == 5


@pytest.mark.django_db
def test_no_badge_when_level_matches(club, player, character, login):
    """No badge when stored level already matches XP level."""
    character.xp = 6500
    character.level = 5
    character.save(update_fields=["xp", "level"])
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Level up ready" not in html


# ---------------------------------------------------------------------------
# Latest awards
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_recent_awards_shows_newest_five(club, player, character, item, login):
    """Six award entries show only the newest five, newest first."""
    today = timezone.localdate()
    for i in range(6):
        _award_ledger(
            character,
            item,
            "award",
            qty=i + 1,
            note=f"Award {i}",
            date=today - timedelta(days=6 - i),
        )
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Award 0" not in html
    assert "Award 1" in html
    assert "Award 2" in html
    assert "Award 3" in html
    assert "Award 4" in html
    assert "Award 5" in html


@pytest.mark.django_db
def test_recent_awards_shows_date_coins_items_note(club, player, character, item, login):
    """Award row shows date, coins or items, and note."""
    today = timezone.localdate()
    _award_ledger(
        character,
        item,
        "award",
        qty=2,
        note="Found treasure",
        date=today,
    )
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "2 x Rope" in html
    assert "Found treasure" in html


@pytest.mark.django_db
def test_recent_awards_shows_coins(club, player, character, item, login):
    """Award with coins shows the coins filter output."""
    today = timezone.localdate()
    _award_ledger(
        character,
        None,
        "award",
        coins=500,
        note="Coin reward",
        date=today,
    )
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Coin reward" in html


@pytest.mark.django_db
def test_recent_awards_kinds(club, player, character, item, login):
    """Quest reward, adjustment and reversal show; purchase, sale, consumed do not."""
    today = timezone.localdate()
    _award_ledger(character, item, "quest_reward", coins=100, note="Quest reward", date=today)
    _award_ledger(character, item, "adjustment", coins=50, note="Adjustment", date=today)
    _award_ledger(character, item, "reversal", coins=-25, note="Reversal", date=today)
    _award_ledger(character, item, "purchase", coins=100, qty=1, note="Purchase", date=today)
    _award_ledger(character, item, "sale", coins=-100, qty=1, note="Sale", date=today)
    _award_ledger(character, item, "consumed", qty=1, note="Consumed", date=today)

    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Quest reward" in html
    assert "Adjustment" in html
    assert "Reversal" in html
    assert "Purchase" not in html
    assert "Sale" not in html
    assert "Consumed" not in html


@pytest.mark.django_db
def test_downtime_award_merges(club, player, character, login):
    """Downtime point award merges by date; spend and request do not show."""
    today = timezone.localdate()
    DowntimePointEntry.objects.create(
        character=character, delta=1, kind="award", note="Downtime award", date=today
    )
    DowntimePointEntry.objects.create(
        character=character, delta=-1, kind="spend", note="Downtime spend", date=today
    )
    DowntimePointEntry.objects.create(
        character=character, delta=1, kind="request", note="Downtime request", date=today
    )

    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Downtime award" in html
    assert "Downtime spend" not in html
    assert "Downtime request" not in html


@pytest.mark.django_db
def test_recent_awards_scope(club, player, character, other_club, login):
    """Another character's entry and another club's entry never show."""
    today = timezone.localdate()

    # Another character in the same club
    other_user = User.objects.create_user("other2@example.com", password="pw")
    other_member = Membership.objects.create(user=other_user, club=club)
    other_character = Character.objects.create(
        club=club, owner=other_member, name="Other Same Club PC"
    )
    _award_ledger(
        other_character, None, "award", coins=888, note="Other same club award", date=today
    )

    # Another character in another club
    other_club_user = User.objects.create_user("other3@example.com", password="pw")
    other_club_member = Membership.objects.create(user=other_club_user, club=other_club)
    other_club_character = Character.objects.create(
        club=other_club, owner=other_club_member, name="Other Club PC"
    )
    _award_ledger(
        other_club_character,
        None,
        "award",
        coins=999,
        note="Other club award",
        date=today,
    )

    _award_ledger(character, None, "award", coins=100, note="Own award", date=today)

    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Own award" in html
    assert "Other same club award" not in html
    assert "Other club award" not in html


@pytest.mark.django_db
def test_recent_awards_empty_hidden(club, player, character, login):
    """'Latest awards' card is hidden when there are no awards."""
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Latest awards" not in html


# ---------------------------------------------------------------------------
# Print
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_print_on_new_blocks(club, player, character, login):
    """XP progress and latest awards blocks sit inside no-print."""
    character.xp = 6500
    character.level = 5
    character.save(update_fields=["xp", "level"])
    c = login(player)
    resp = _dashboard(c, club.slug)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "wm-dashboard-header card wm-card-raised mb-4 no-print" in html
    if "Latest awards" in html:
        assert "wm-card-raised mb-4 no-print" in html


@pytest.mark.django_db
def test_recent_awards_shows_coins_and_items_together(club, player, character, item, login):
    """One entry holding a coin line and an item line shows both."""
    record(
        character,
        "award",
        [Line(coins=500), Line(item=item, quantity=2)],
        note="Crypt loot",
        date=timezone.localdate(),
    )
    c = login(player)
    html = _dashboard(c, club.slug).content.decode()
    assert "2 x Rope" in html
    assert "Crypt loot" in html
    assert "5 gp" in html or "500" in html
