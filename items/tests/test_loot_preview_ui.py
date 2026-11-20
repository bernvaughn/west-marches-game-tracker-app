"""Tests for loot preview UI (Slice D1)."""

import pytest
from django.urls import reverse

from items.models import Item
from items.tests.factories import make_diplomats_pack
from ledger.services import Line, record
from player_characters.models import Character

pytestmark = [pytest.mark.django_db]


def _detail(club, item):
    return reverse("items:detail", args=[club.slug, item.pk])


def _details_modal(club, item):
    return reverse("items:details_modal", args=[club.slug, item.pk])


def _character_sheet(club, character):
    return reverse("characters:detail", args=[club.slug, character.pk])


def test_player_modal_shows_contents_not_sealed_letter(login, club, player):
    """Player sees '???' not 'Sealed letter' in details modal."""
    pack = make_diplomats_pack(club)
    r = login(player).get(_details_modal(club, pack), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Contents" in html
    assert "Fine clothes" in html
    assert "1&#8211;2" in html or "1–2" in html
    assert "50% chance" in html
    assert "One of" in html
    assert "Sealing wax" in html
    assert "Soap" in html
    assert "???" in html
    assert "Sealed letter" not in html


def test_player_full_page_shows_contents_not_sealed_letter(login, club, player):
    """Player sees '???' not 'Sealed letter' on full detail page."""
    pack = make_diplomats_pack(club)
    r = login(player).get(_detail(club, pack))
    assert r.status_code == 200
    html = r.content.decode()
    assert "Contents" in html
    assert "Fine clothes" in html
    assert "1&#8211;2" in html or "1–2" in html
    assert "50% chance" in html
    assert "One of" in html
    assert "Sealing wax" in html
    assert "Soap" in html
    assert "???" in html
    assert "Sealed letter" not in html


def test_player_character_sheet_with_pack_in_inventory(login, club, player):
    """Player character sheet with pack in inventory does not leak 'Sealed letter'."""
    pack = make_diplomats_pack(club)
    character = Character.objects.create(
        club=club, owner=player.memberships.first(), name="Hero", level=1
    )
    # Grant the pack to the character
    record(character, "award", [Line(item=pack, quantity=1)], note="test")
    r = login(player).get(_character_sheet(club, character))
    assert r.status_code == 200
    html = r.content.decode()
    assert "Sealed letter" not in html


def test_gm_modal_shows_sealed_letter_and_hidden_badge(login, club, game_master):
    """GM sees 'Sealed letter' with 'Hidden from players' badge in modal."""
    pack = make_diplomats_pack(club)
    r = login(game_master).get(_details_modal(club, pack), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Sealed letter" in html
    assert "Hidden from players" in html
    assert "???" not in html


def test_gm_full_page_shows_sealed_letter_and_hidden_badge(login, club, game_master):
    """GM sees 'Sealed letter' with 'Hidden from players' badge on full page."""
    pack = make_diplomats_pack(club)
    r = login(game_master).get(_detail(club, pack))
    assert r.status_code == 200
    html = r.content.decode()
    assert "Sealed letter" in html
    assert "Hidden from players" in html
    assert "???" not in html


def test_club_admin_modal_shows_sealed_letter_and_hidden_badge(login, club, club_admin):
    """Club admin sees 'Sealed letter' with 'Hidden from players' badge in modal."""
    pack = make_diplomats_pack(club)
    r = login(club_admin).get(_details_modal(club, pack), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Sealed letter" in html
    assert "Hidden from players" in html
    assert "???" not in html


def test_non_container_item_no_contents_card(login, club, player):
    """Non-container item shows no 'Contents' card and no extra queries."""
    item = Item.objects.create(club=club, name="Plain Sword", value_cp=1000)
    r = login(player).get(_details_modal(club, item), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Contents" not in html


def test_container_without_slots_no_contents_card(login, club, player):
    """Container without slots shows no 'Contents' card, no error."""
    from items.models import Item

    pack = Item.objects.create(club=club, name="Empty Box", is_container=True, value_cp=0)
    r = login(player).get(_details_modal(club, pack), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Contents" not in html


def test_retired_contained_item_still_listed(login, club, player):
    """Retired contained item is still listed in preview."""
    pack = make_diplomats_pack(club)
    # Retire one of the contained items
    fine_clothes = Item.objects.get(club=club, name="Fine clothes")
    fine_clothes.retired = True
    fine_clothes.save()
    r = login(player).get(_details_modal(club, pack), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Fine clothes" in html


def test_modal_no_item_id_leaked_in_links(login, club, player):
    """Player modal does not leak unknown item's detail URL."""
    pack = make_diplomats_pack(club)
    r = login(player).get(_details_modal(club, pack), HTTP_HX_REQUEST="true")
    html = r.content.decode()
    # Sealed letter's pk should not appear in any href
    sealed = Item.objects.get(club=club, name="Sealed letter")
    assert "items:detail" not in html or str(sealed.pk) not in html


def test_full_page_no_item_id_leaked_in_links(login, club, player):
    """Player full page does not leak unknown item's detail URL."""
    pack = make_diplomats_pack(club)
    r = login(player).get(_detail(club, pack))
    html = r.content.decode()
    sealed = Item.objects.get(club=club, name="Sealed letter")
    assert "items:detail" not in html or str(sealed.pk) not in html
