"""Tests for the print_session_pack view and modal."""

import re
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.views.dashboard import _compute_print_diff
from ledger.services import Line, record

pytestmark = pytest.mark.django_db


def pack_url(club, character):
    return reverse("characters:print_session_pack", args=[club.slug, character.pk])


def modal_url(club, character):
    return reverse("accounts:print_session_pack_modal", args=[club.slug, character.pk])


@pytest.mark.story("S10")
def test_owner_sees_pack(login, club, player, funded, item):
    """Owner can access the session pack page."""
    r = login(player).get(pack_url(club, funded))
    assert r.status_code == 200
    body = r.content.decode()
    # Should have character name
    assert funded.name in body
    # Should have all sections (sheet, items, quests)
    assert "Character Sheet" in body or "Abilities" in body
    assert "Item Cards" in body or "wm-item-card" in body
    assert "Ready Quests" in body or "wm-notice" in body


@pytest.mark.story("S10")
@pytest.mark.parametrize("who", ["game_master", "club_admin", "site_admin"])
def test_viewers_get_200(request, login, club, funded, who):
    """GM, club admin, site admin can view the session pack."""
    r = login(request.getfixturevalue(who)).get(pack_url(club, funded))
    assert r.status_code == 200


@pytest.mark.story("S10")
def test_other_player_forbidden(login, club, other_player, funded):
    """Other players cannot view the session pack."""
    assert login(other_player).get(pack_url(club, funded)).status_code == 403


@pytest.mark.story("S10")
def test_cross_club_404(login, club, other_club, player, foreign_member, foreign_character):
    """Cross-club access returns 404."""
    assert login(player).get(pack_url(club, foreign_character)).status_code == 404
    assert login(player).get(pack_url(other_club, foreign_character)).status_code == 404


@pytest.mark.story("S10")
def test_pack_includes_item_cards(login, club, player, funded, item):
    """Session pack includes item cards when items option is on."""
    r = login(player).get(pack_url(club, funded))
    body = r.content.decode()
    assert "wm-item-card" in body


@pytest.mark.story("S10")
def test_pack_options_exclude_sheet(login, club, player, funded, item):
    """Can exclude character sheet with sheet=0."""
    r = login(player).get(pack_url(club, funded) + "?sheet=0")
    assert r.status_code == 200
    body = r.content.decode()
    # Should not have sheet sections
    assert "Abilities" not in body


@pytest.mark.story("S10")
def test_pack_options_exclude_items(login, club, player, funded, item):
    """Can exclude item cards with items=0."""
    r = login(player).get(pack_url(club, funded) + "?items=0")
    assert r.status_code == 200
    body = r.content.decode()
    assert "wm-item-card" not in body


@pytest.mark.story("S10")
def test_pack_options_exclude_quests(login, club, player, funded, item):
    """Can exclude quests with quests=0."""
    r = login(player).get(pack_url(club, funded) + "?quests=0")
    assert r.status_code == 200
    body = r.content.decode()
    # Should not have quest notice elements
    assert "wm-notice" not in body


@pytest.mark.story("S10")
def test_print_button_present(login, club, player, funded):
    """Print button is present in the output."""
    r = login(player).get(pack_url(club, funded))
    body = r.content.decode()
    assert "window.print()" in body


@pytest.mark.story("S10")
def test_modal_endpoint_returns_form(login, club, player, funded):
    """Print session pack modal endpoint returns the options form."""
    r = login(player).get(modal_url(club, funded))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Print Session Pack" in body
    assert "Character Sheet" in body
    assert "Item Cards" in body
    assert "Ready Quests" in body
    assert "Map" in body
    assert 'name="sheet"' in body
    assert 'name="items"' in body
    assert 'name="quests"' in body
    assert 'name="map"' in body


@pytest.mark.story("S10")
def test_modal_forbidden_for_other_player(login, club, other_player, funded):
    """Other players cannot access the modal."""
    assert login(other_player).get(modal_url(club, funded)).status_code == 404


@pytest.mark.story("S10")
def test_modal_cross_club_404(login, club, other_club, player, foreign_member, foreign_character):
    """Cross-club modal access returns 404."""
    assert login(player).get(modal_url(club, foreign_character)).status_code == 404
    assert login(player).get(modal_url(other_club, foreign_character)).status_code == 404


# =============================================================================
# Tests for _compute_print_diff
# =============================================================================
# Use `character` fixture (clean slate) instead of `funded` to avoid fixture's initial entries
# Use `record` with explicit dates to test date filtering


@pytest.mark.story("S10")
def test_compute_diff_first_print_returns_all_history(character, item, second_item, player):
    """When never printed, diff includes all ledger entries."""
    record(
        character,
        "award",
        [Line(item=item, quantity=2), Line(coins=500)],
        note="Initial loot",
        actor=player,
    )
    record(
        character,
        "purchase",
        [Line(item=second_item, quantity=1), Line(coins=-200)],
        note="Bought potion",
        actor=player,
    )
    # last_printed_at is None (never printed)
    diff = _compute_print_diff(character)
    assert diff["first_print"] is True
    assert diff["coins"] == 300  # 500 - 200
    assert (item.name, 2) in diff["items"]
    assert (second_item.name, 1) in diff["items"]


@pytest.mark.story("S10")
def test_compute_diff_after_print_returns_only_new_changes(character, item, second_item, player):
    """After printing, diff only shows entries since last_printed_at."""
    two_days_ago = timezone.localdate() - timedelta(days=2)
    yesterday = timezone.localdate() - timedelta(days=1)
    today = timezone.localdate()
    # Initial entry two days ago
    record(
        character,
        "award",
        [Line(item=item, quantity=2), Line(coins=500)],
        note="Initial loot",
        actor=player,
        date=two_days_ago,
    )
    # Simulate a print yesterday
    character.last_printed_at = timezone.make_aware(
        timezone.datetime.combine(yesterday, timezone.datetime.min.time())
    )
    character.save(update_fields=["last_printed_at"])

    # New entries today (after print)
    record(
        character,
        "purchase",
        [Line(item=second_item, quantity=1), Line(coins=-200)],
        note="Bought potion",
        actor=player,
        date=today,
    )
    record(character, "award", [Line(coins=1000)], note="Found coins", actor=player, date=today)
    diff = _compute_print_diff(character)
    assert diff["first_print"] is False
    assert diff["coins"] == 800  # -200 + 1000
    assert (second_item.name, 1) in diff["items"]
    assert (item.name, 2) not in diff["items"]  # Old entry not included


@pytest.mark.story("S10")
def test_compute_diff_quest_entries_not_double_counted(character, item, player):
    """Quest turn-in and reward entries appear under Quests, not Coins/Items."""
    two_days_ago = timezone.localdate() - timedelta(days=2)
    yesterday = timezone.localdate() - timedelta(days=1)
    today = timezone.localdate()
    # Setup: give character items two days ago, then "print" yesterday
    record(
        character,
        "award",
        [Line(item=item, quantity=3)],
        note="Found pelts",
        actor=player,
        date=two_days_ago,
    )
    character.last_printed_at = timezone.make_aware(
        timezone.datetime.combine(yesterday, timezone.datetime.min.time())
    )
    character.save(update_fields=["last_printed_at"])

    # Now do quest turn-in and reward today
    record(
        character,
        "quest_turn_in",
        [Line(item=item, quantity=-3)],
        note="Turned in for quest Pelts for the Tanner",
        actor=player,
        date=today,
    )
    record(
        character,
        "quest_reward",
        [Line(item=item, quantity=1), Line(coins=1000)],
        note="Reward for quest Pelts for the Tanner",
        actor=player,
        date=today,
    )
    diff = _compute_print_diff(character)
    # Quest entries should not contribute to coins/items totals
    assert diff["coins"] == 0
    assert diff["items"] == []
    # But should appear in quests
    assert "Pelts for the Tanner" in diff["quests"]


@pytest.mark.story("S10")
def test_compute_diff_downtime_entries_not_double_counted(character, item, player):
    """Downtime award entries appear under Downtime, not Coins/Items."""
    record(
        character,
        "award",
        [Line(item=item, quantity=2), Line(coins=500)],
        note="Downtime: Work at a bakery - Baker's thanks",
        actor=player,
    )
    diff = _compute_print_diff(character)
    # Downtime entries should not contribute to coins/items totals
    assert diff["coins"] == 0
    assert diff["items"] == []
    # But should appear in downtime
    assert len(diff["downtime"]) == 1
    dt = diff["downtime"][0]
    assert dt["action"] == "Work at a bakery - Baker's thanks"
    assert dt["coins"] == 500
    assert (item.name, 2) in dt["items"]


@pytest.mark.story("S10")
def test_compute_diff_net_items_aggregates_quantities(character, item, player):
    """Multiple entries for same item are netted."""
    record(character, "award", [Line(item=item, quantity=3)], note="Found 3", actor=player)
    record(character, "consumed", [Line(item=item, quantity=-1)], note="Used 1", actor=player)
    diff = _compute_print_diff(character)
    assert diff["items"] == [(item.name, 2)]


@pytest.mark.story("S10")
def test_compute_diff_zero_net_items_omitted(character, item, player):
    """Items with zero net quantity are omitted."""
    record(character, "award", [Line(item=item, quantity=2)], note="Found 2", actor=player)
    record(character, "consumed", [Line(item=item, quantity=-2)], note="Used 2", actor=player)
    diff = _compute_print_diff(character)
    assert diff["items"] == []


@pytest.mark.story("S10")
def test_compute_diff_no_entries_returns_empty(character):
    """Character with no ledger entries returns empty diff."""
    diff = _compute_print_diff(character)
    assert diff["first_print"] is True
    assert diff["coins"] == 0
    assert diff["items"] == []
    assert diff["quests"] == []
    assert diff["downtime"] == []


# =============================================================================
# Tests for POST updating last_printed_at
# =============================================================================


@pytest.mark.story("S10")
def test_print_session_pack_post_updates_last_printed_at(login, club, player, funded):
    """POST to print_session_pack updates last_printed_at."""
    assert funded.last_printed_at is None
    url = reverse("characters:print_session_pack", args=[club.slug, funded.pk])
    r = login(player).post(url, {"sheet": "1", "items": "1", "quests": "1"})
    assert r.status_code == 200
    funded.refresh_from_db()
    assert funded.last_printed_at is not None


@pytest.mark.story("S10")
def test_print_items_post_updates_last_printed_at(login, club, player, funded):
    """POST to print_items updates last_printed_at."""
    assert funded.last_printed_at is None
    url = reverse("characters:print_items", args=[club.slug, funded.pk])
    r = login(player).post(url + "?copies=type")
    assert r.status_code == 200
    funded.refresh_from_db()
    assert funded.last_printed_at is not None


@pytest.mark.story("S10")
def test_detail_view_post_updates_last_printed_at(login, club, player, funded):
    """POST to character detail (Print sheet) updates last_printed_at."""
    assert funded.last_printed_at is None
    url = reverse("characters:detail", args=[club.slug, funded.pk])
    r = login(player).post(url)
    assert r.status_code == 200
    funded.refresh_from_db()
    assert funded.last_printed_at is not None


@pytest.mark.story("S10")
def test_print_sheet_script_loads_once(login, club, player, funded):
    """The print handler script loads once, so one click prints once."""
    url = reverse("characters:detail", args=[club.slug, funded.pk])
    body = login(player).get(url).content.decode()
    assert body.count("js/print_sheet.js") == 1
    assert "hx-on::after-request" not in body


@pytest.mark.story("S10")
def test_print_sheet_post_with_dom_csrf_token(club, player, funded):
    """The CSRF cookie is HttpOnly, so the JS reads the token from the button.

    A POST with that token passes CSRF checks and records the print.
    """
    client = Client(enforce_csrf_checks=True)
    client.force_login(player)
    url = reverse("characters:detail", args=[club.slug, funded.pk])
    body = client.get(url).content.decode()
    match = re.search(r'data-print-sheet [^>]*data-csrf-token="([^"]+)"', body)
    assert match, "Print sheet button must carry the CSRF token"

    assert client.post(url, HTTP_X_CSRFTOKEN="").status_code == 403
    funded.refresh_from_db()
    assert funded.last_printed_at is None

    r = client.post(url, HTTP_X_CSRFTOKEN=match.group(1))
    assert r.status_code == 200
    funded.refresh_from_db()
    assert funded.last_printed_at is not None


@pytest.mark.story("S10")
def test_modal_renders_diff_section(login, club, player, funded, item):
    """Modal includes Changes since last print section with diff data."""
    record(
        funded,
        "award",
        [Line(item=item, quantity=2), Line(coins=500)],
        note="Initial loot",
        actor=player,
    )
    url = reverse("accounts:print_session_pack_modal", args=[club.slug, funded.pk])
    r = login(player).get(url)
    assert r.status_code == 200
    body = r.content.decode()
    assert "Changes since last print" in body
    assert "First print" in body
    # First print only shows the message, not detailed breakdown
    assert "First print — showing all history" in body


@pytest.mark.story("S10")
def test_modal_shows_no_changes_when_empty(login, club, player, character):
    """Modal shows 'No changes since last print' when diff is empty."""
    # Use clean character fixture, not funded
    character.last_printed_at = timezone.now()
    character.save(update_fields=["last_printed_at"])
    url = reverse("accounts:print_session_pack_modal", args=[club.slug, character.pk])
    r = login(player).get(url)
    assert r.status_code == 200
    body = r.content.decode()
    assert "No changes since last print" in body


# =============================================================================
# Options sent by the dashboard modal (POST body)
# =============================================================================


@pytest.mark.story("S10")
def test_modal_post_only_quests_hides_sheet_and_items(login, club, player, funded, item):
    """Unchecked boxes are absent from the POST body and turn the option off."""
    r = login(player).post(pack_url(club, funded), {"pack": "1", "quests": "1"})
    assert r.status_code == 200
    body = r.content.decode()
    assert "wm-item-card" not in body
    assert "wm-sheet-abilities" not in body
    assert "No quests ready to turn in." in body


@pytest.mark.story("S10")
def test_modal_post_nothing_checked_prints_nothing(login, club, player, funded, item):
    """With every box unchecked, no section prints."""
    body = login(player).post(pack_url(club, funded), {"pack": "1"}).content.decode()
    assert "wm-item-card" not in body
    assert "wm-sheet-abilities" not in body
    assert "No quests ready to turn in." not in body
    assert "wm-map-print" not in body


@pytest.mark.story("S10")
def test_modal_form_sends_pack_marker(login, club, player, funded):
    """The modal form carries the marker that makes the view read its POST body."""
    body = login(player).get(modal_url(club, funded)).content.decode()
    assert 'name="pack" value="1"' in body


@pytest.mark.story("S10")
def test_reprint_form_keeps_chosen_options(login, club, player, funded, item):
    """The page's own Print button posts back the options it was opened with."""
    body = login(player).get(pack_url(club, funded) + "?sheet=0&map=1").content.decode()
    assert 'name="pack" value="1"' in body
    assert 'name="sheet"' not in body
    assert '<input type="hidden" name="items" value="1">' in body
    assert '<input type="hidden" name="quests" value="1">' in body
    assert '<input type="hidden" name="map" value="1">' in body


@pytest.mark.story("S10")
def test_post_without_marker_reads_query(login, club, player, funded, item):
    """A POST without the marker reads the query string like a GET."""
    body = login(player).post(pack_url(club, funded) + "?items=0").content.decode()
    assert "wm-item-card" not in body
    assert "wm-sheet-abilities" in body


# =============================================================================
# Map option
# =============================================================================


@pytest.mark.story("S10")
def test_map_off_by_default(login, club, player, funded):
    from map.models import HexMap

    HexMap.objects.create(club=club, name="The Marches")
    body = login(player).get(pack_url(club, funded)).content.decode()
    assert "wm-map-print" not in body


@pytest.mark.story("S10")
def test_map_option_prints_character_view(login, club, player, funded):
    """The map prints the character's view of each active club map."""
    from map.models import HexMap, Location, Tile, TileVisit

    hex_map = HexMap.objects.create(club=club, name="The Marches")
    HexMap.objects.create(club=club, name="Old Map", archived=True)
    seen = Tile.objects.create(map=hex_map, q=1, r=0, color="green")
    hidden = Tile.objects.create(map=hex_map, q=-1, r=0, color="red")
    Location.objects.create(tile=hidden, name="Secret Lair", symbol="X")
    TileVisit.objects.create(map=hex_map, character=funded, q=seen.q, r=seen.r)

    body = login(player).post(pack_url(club, funded), {"pack": "1", "map": "1"}).content.decode()
    assert "wm-map-print" in body
    assert "The Marches" in body
    assert "Old Map" not in body
    assert 'class="hexmap' in body
    assert "Map legend" in body
    assert "hex-visited" in body
    assert "Secret Lair" not in body
    assert "not yet implemented" not in body


@pytest.mark.story("S10")
def test_map_option_without_maps(login, club, player, funded):
    body = login(player).get(pack_url(club, funded) + "?map=1").content.decode()
    assert "No maps to print." in body
