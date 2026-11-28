"""Tests for the promote view and modal (U161).

Covers admin GET 200, POST promotes and redirects to the review page,
non-admin 403, and an existing name on POST re-rendering the modal with an
error.
"""

import pytest
from django.urls import reverse

from items.models import Item
from ledger.models import LedgerEntry
from player_characters.models import Character
from player_items.models import PlayerItem, PlayerItemChange, PlayerNotice

pytestmark = [pytest.mark.story("U161"), pytest.mark.django_db]


# --- helpers -------------------------------------------------------------


@pytest.fixture
def other_character(club, other_player):
    owner = club.memberships.get(user=other_player)
    return Character.objects.create(club=club, owner=owner, name="Borin")


def promote_url(club, name_key="potion"):
    return reverse("player_items:promote", args=[club.slug, name_key])


def review_url(club):
    return reverse("player_items:review", args=[club.slug])


def make_item(club, character, name="Potion", quantity=1):
    return PlayerItem.objects.create(club=club, character=character, name=name, quantity=quantity)


# --- permissions ---------------------------------------------------------


def test_promote_modal_submit_button_has_form_attribute(club, login, club_admin, character):
    make_item(club, character, "Potion", 2)
    c = login(club_admin)
    r = c.get(promote_url(club), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert 'form="promote-form"' in body
    assert 'id="promote-form"' in body


def test_club_admin_get_promote_modal(club, login, club_admin, character):
    make_item(club, character, "Potion", 2)
    c = login(club_admin)
    r = c.get(promote_url(club), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Aria" in body
    assert "Promote player-written items" in body


def test_player_cannot_promote(club, login, player, character):
    make_item(club, character, "Potion", 2)
    c = login(player)
    assert c.get(promote_url(club), HTTP_HX_REQUEST="true").status_code == 403


def test_game_master_cannot_promote(club, login, game_master, character):
    make_item(club, character, "Potion", 2)
    c = login(game_master)
    assert c.get(promote_url(club), HTTP_HX_REQUEST="true").status_code == 403


def test_other_player_cannot_promote(club, login, other_player, character):
    make_item(club, character, "Potion", 2)
    c = login(other_player)
    assert c.get(promote_url(club), HTTP_HX_REQUEST="true").status_code == 403


# --- promote -------------------------------------------------------------


def test_post_promotes_and_redirects_to_review(club, login, club_admin, character, other_character):
    make_item(club, character, "Potion", 2)
    make_item(club, character, "potion", 3)
    make_item(club, other_character, "Potion", 4)
    c = login(club_admin)
    r = c.post(
        promote_url(club),
        {"name": "Healing Potion", "quantity_factor": "1"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204
    assert r["HX-Redirect"] == review_url(club)

    new_item = Item.objects.for_club(club).get(name="Healing Potion")
    assert not new_item.is_stacked

    # All entries resolved.
    open_qs = PlayerItem.objects.for_club(club).filter(name_key="potion", review="open")
    resolved_qs = PlayerItem.objects.for_club(club).filter(name_key="potion", review="resolved")
    assert open_qs.count() == 0
    assert resolved_qs.count() == 3

    # One ledger entry per holder, coins unchanged.
    promoted = LedgerEntry.objects.for_club(club).filter(
        kind="adjustment", note="player-written item promoted"
    )
    assert promoted.count() == 2
    assert promoted.get(character=character).lines.get().quantity == 5
    assert promoted.get(character=character).lines.get().coins == 0
    assert promoted.get(character=other_character).lines.get().quantity == 4

    # History rows keep old names.
    changes = PlayerItemChange.objects.for_club(club).filter(kind="promoted")
    assert changes.count() == 3
    assert set(changes.values_list("old_name", flat=True)) == {"Potion", "potion"}
    assert all(c.new_name == "Healing Potion" for c in changes)

    # One notice per holder.
    assert PlayerNotice.objects.for_club(club).filter(kind="item_promoted").count() == 2


def test_post_stacked_uses_units_and_factor(club, login, club_admin, character):
    make_item(club, character, "Arrow", 10)
    c = login(club_admin)
    r = c.post(
        promote_url(club, "arrow"),
        {
            "name": "Arrow Bundle",
            "is_stacked": "on",
            "unit_name": "arrow",
            "quantity_factor": "10",
        },
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204
    new_item = Item.objects.for_club(club).get(name="Arrow Bundle")
    assert new_item.is_stacked
    assert new_item.unit_name == "arrow"
    assert LedgerEntry.objects.for_club(club).get(character=character).lines.get().quantity == 100


def test_post_existing_name_re_renders_modal_with_error(club, login, club_admin, character, item):
    # ``item`` fixture: an Item named "Rope" in this club.
    make_item(club, character, "Rope", 1)
    c = login(club_admin)
    r = c.post(
        promote_url(club, "rope"),
        {"name": "Rope", "quantity_factor": "1"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    body = r.content.decode()
    assert "already exists" in body
    assert "Rope" in body
    # Nothing promoted.
    assert PlayerItemChange.objects.for_club(club).count() == 0
    assert PlayerNotice.objects.for_club(club).count() == 0
