"""Tests for player-written item add, edit and remove views and services."""

import pytest
from django.urls import reverse

from player_characters.models import Character
from player_items.models import (
    MAX_ITEMS_PER_CHARACTER,
    PlayerItem,
    PlayerItemChange,
)
from player_items.services import add_player_item
from quests.models import Quest, QuestReward
from shops.models import Shop

pytestmark = [pytest.mark.story("U159"), pytest.mark.django_db]


# --- helpers -------------------------------------------------------------


def entries_url(club, character):
    return reverse("characters:detail", args=[club.slug, character.pk])


def add_url(club, character):
    return reverse("player_items:add", args=[club.slug, character.pk])


def edit_url(club, character, item):
    return reverse("player_items:edit", args=[club.slug, character.pk, item.pk])


def remove_url(club, character, item):
    return reverse("player_items:remove", args=[club.slug, character.pk, item.pk])


def make_item(club, character, name="Sword", quantity=1, note=""):
    return PlayerItem.objects.create(
        club=club, character=character, name=name, quantity=quantity, note=note
    )


def post_add(client, club, character, data=None):
    if data is None:
        data = {"name": "Magic Sword", "quantity": 1, "note": "A note."}
    return client.post(add_url(club, character), data)


@pytest.fixture
def other_character(club, other_player):
    owner = club.memberships.get(user=other_player)
    return Character.objects.create(club=club, owner=owner, name="Borin")


@pytest.fixture
def shop(club):
    return Shop.objects.create(
        club=club, name="Lantern", keeper_name="Marta", sell_percent=100, buy_percent=50
    )


# --- permissions: add -----------------------------------------------------


def test_owner_can_add(club, login, player, character):
    c = login(player)
    assert c.get(add_url(club, character)).status_code == 200
    r = post_add(c, club, character)
    assert r.status_code == 302
    assert r["Location"] == entries_url(club, character)
    assert PlayerItem.objects.for_club(club).filter(character=character).count() == 1


def test_game_master_can_add(club, login, game_master, character):
    c = login(game_master)
    r = post_add(c, club, character)
    assert r.status_code == 302
    assert PlayerItem.objects.for_club(club).filter(character=character).count() == 1


def test_club_admin_can_add(club, login, club_admin, character):
    c = login(club_admin)
    r = post_add(c, club, character)
    assert r.status_code == 302
    assert PlayerItem.objects.for_club(club).filter(character=character).count() == 1


def test_other_player_cannot_add(club, login, other_player, character):
    c = login(other_player)
    r = post_add(c, club, character)
    assert r.status_code == 403
    assert PlayerItem.objects.for_club(club).count() == 0


# --- permissions: edit ----------------------------------------------------


def test_owner_can_edit(club, login, player, character):
    item = make_item(club, character, name="Old")
    c = login(player)
    r = c.post(
        edit_url(club, character, item),
        {"name": "New", "quantity": 2, "note": "updated"},
    )
    assert r.status_code == 302
    item.refresh_from_db()
    assert item.name == "New"
    assert item.quantity == 2
    assert item.note == "updated"


def test_game_master_can_edit(club, login, game_master, character):
    item = make_item(club, character, name="Old")
    c = login(game_master)
    r = c.post(
        edit_url(club, character, item),
        {"name": "New", "quantity": 2, "note": "updated"},
    )
    assert r.status_code == 302
    item.refresh_from_db()
    assert item.name == "New"


def test_club_admin_can_edit(club, login, club_admin, character):
    item = make_item(club, character, name="Old")
    c = login(club_admin)
    r = c.post(
        edit_url(club, character, item),
        {"name": "New", "quantity": 2, "note": "updated"},
    )
    assert r.status_code == 302
    item.refresh_from_db()
    assert item.name == "New"


def test_other_player_cannot_edit(club, login, other_player, character):
    item = make_item(club, character, name="Old")
    c = login(other_player)
    r = c.post(
        edit_url(club, character, item),
        {"name": "New", "quantity": 2, "note": "updated"},
    )
    assert r.status_code == 403
    item.refresh_from_db()
    assert item.name == "Old"


# --- permissions: remove --------------------------------------------------


def test_owner_can_remove(club, login, player, character):
    item = make_item(club, character, name="Old")
    c = login(player)
    r = c.post(remove_url(club, character, item))
    assert r.status_code == 302
    assert PlayerItem.objects.for_club(club).count() == 0


def test_game_master_can_remove(club, login, game_master, character):
    item = make_item(club, character, name="Old")
    c = login(game_master)
    r = c.post(remove_url(club, character, item))
    assert r.status_code == 302
    assert PlayerItem.objects.for_club(club).count() == 0


def test_club_admin_can_remove(club, login, club_admin, character):
    item = make_item(club, character, name="Old")
    c = login(club_admin)
    r = c.post(remove_url(club, character, item))
    assert r.status_code == 302
    assert PlayerItem.objects.for_club(club).count() == 0


def test_other_player_cannot_remove(club, login, other_player, character):
    item = make_item(club, character, name="Old")
    c = login(other_player)
    r = c.post(remove_url(club, character, item))
    assert r.status_code == 403
    assert PlayerItem.objects.for_club(club).count() == 1


# --- display: Player-written label ---------------------------------------


def test_sheet_shows_player_written_badge(club, login, player, character):
    make_item(club, character, name="Magic Sword", quantity=2, note="Sharp.")
    body = login(player).get(entries_url(club, character)).content.decode()
    assert "Magic Sword" in body
    assert "Player-written" in body


def test_sheet_shows_add_button(club, login, player, character):
    body = login(player).get(entries_url(club, character)).content.decode()
    assert add_url(club, character) in body
    assert "Add player-written item" in body


# --- limit error ----------------------------------------------------------


def test_limit_error_at_50_items(club, login, player, character):
    for i in range(MAX_ITEMS_PER_CHARACTER):
        add_player_item(club, character, f"Item {i}", 1, "", player)
    c = login(player)
    r = post_add(c, club, character, {"name": "Item 50", "quantity": 1, "note": ""})
    assert r.status_code == 200
    body = r.content.decode()
    assert "50" in body
    count = PlayerItem.objects.for_club(club).filter(character=character).count()
    assert count == MAX_ITEMS_PER_CHARACTER


# --- history rows ---------------------------------------------------------


def test_add_creates_history_row(club, login, player, character):
    c = login(player)
    post_add(c, club, character, {"name": "Sword", "quantity": 3, "note": "n"})
    change = PlayerItemChange.objects.for_club(club).filter(character=character).get()
    assert change.kind == PlayerItemChange.Kind.ADDED
    assert change.new_name == "Sword"
    assert change.quantity == 3
    assert change.by_id == player.id


def test_edit_creates_history_row(club, login, player, character):
    item = make_item(club, character, name="Old", quantity=1, note="n")
    c = login(player)
    c.post(
        edit_url(club, character, item),
        {"name": "New", "quantity": 2, "note": "updated"},
    )
    change = (
        PlayerItemChange.objects.for_club(club)
        .filter(character=character, kind=PlayerItemChange.Kind.EDITED)
        .get()
    )
    assert change.old_name == "Old"
    assert change.new_name == "New"
    assert change.quantity == 2
    assert change.by_id == player.id


def test_remove_creates_history_row(club, login, player, character):
    item = make_item(club, character, name="Old", quantity=2, note="n")
    c = login(player)
    c.post(remove_url(club, character, item))
    change = (
        PlayerItemChange.objects.for_club(club)
        .filter(character=character, kind=PlayerItemChange.Kind.REMOVED)
        .get()
    )
    assert change.old_name == "Old"
    assert change.quantity == 2
    assert change.by_id == player.id


# --- unsellable enforcement: one test per path ---------------------------


def test_player_item_not_in_shop(club, login, player, character, shop):
    make_item(club, character, name="Not for Sale")
    # Shops only stock catalogue Items; player-written items never appear.
    body = login(player).get(reverse("shops:detail", args=[club.slug, shop.id])).content.decode()
    assert "Not for Sale" not in body


def test_player_item_not_in_stall(club, login, player, character, other_character):
    make_item(club, character, name="Stall Item")
    # Player stalls list held (ledger) items only.
    body = (
        login(player)
        .get(reverse("shops:player_shop", args=[club.slug, other_character.pk]))
        .content.decode()
    )
    assert "Stall Item" not in body


def test_player_item_not_in_quest(club, login, player, character):
    make_item(club, character, name="Quest Item")
    quest = Quest.objects.create(club=club, name="The Quest")
    body = login(player).get(reverse("quests:detail", args=[club.slug, quest.pk])).content.decode()
    assert "Quest Item" not in body


def test_player_item_not_in_quest_reward(club, login, player, character):
    make_item(club, character, name="Reward Item")
    quest = Quest.objects.create(club=club, name="Rewarding Quest")
    QuestReward.objects.create(quest=quest, item=None, quantity=0, coins=10)
    body = login(player).get(reverse("quests:detail", args=[club.slug, quest.pk])).content.decode()
    assert "Reward Item" not in body
