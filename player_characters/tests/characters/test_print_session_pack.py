"""Tests for the print_session_pack view."""

import pytest
from django.urls import reverse

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
def test_pack_options_include_trades(login, club, player, funded, item):
    """Can include trades with trades=1."""
    r = login(player).get(pack_url(club, funded) + "?trades=1")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Open Trades" in body


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
    assert "Open Trades" in body
    assert 'name="sheet"' in body
    assert 'name="items"' in body
    assert 'name="quests"' in body
    assert 'name="map"' in body
    assert 'name="trades"' in body


@pytest.mark.story("S10")
def test_modal_forbidden_for_other_player(login, club, other_player, funded):
    """Other players cannot access the modal."""
    assert login(other_player).get(modal_url(club, funded)).status_code == 404


@pytest.mark.story("S10")
def test_modal_cross_club_404(login, club, other_club, player, foreign_member, foreign_character):
    """Cross-club modal access returns 404."""
    assert login(player).get(modal_url(club, foreign_character)).status_code == 404
    assert login(player).get(modal_url(other_club, foreign_character)).status_code == 404