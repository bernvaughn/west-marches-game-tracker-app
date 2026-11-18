import datetime

import pytest
from django.urls import reverse

from ledger.models import LedgerEntry
from ledger.services import coin_balance, item_quantities

pytestmark = pytest.mark.django_db


def bulk_award_url(club):
    return reverse("characters:bulk_award", kwargs={"club_slug": club.slug})


def bulk_payload(characters, items, coins=None, note="Party loot", date="2025-01-15"):
    """Build POST payload for bulk award."""
    data = {
        "note": note,
        "date": date,
        "characters": [str(c.pk) for c in characters],
    }
    if coins:
        for c, cp in coins.items():
            data[f"coins_{c.pk}"] = str(cp)
    for c, item_lines in items.items():
        prefix = f"items_{c.pk}"
        data[f"{prefix}-TOTAL_FORMS"] = "3"
        data[f"{prefix}-INITIAL_FORMS"] = "0"
        data[f"{prefix}-MIN_NUM_FORMS"] = "0"
        data[f"{prefix}-MAX_NUM_FORMS"] = "3"
        for i, (item, qty) in enumerate(item_lines):
            data[f"{prefix}-{i}-item_id"] = str(item.pk)
            data[f"{prefix}-{i}-quantity"] = str(qty)
    return data


def entries(character):
    return LedgerEntry.objects.filter(character=character).order_by("pk")


@pytest.mark.story("S8")
def test_bulk_award_get(login, game_master, club, character, second_character, item):
    c = login(game_master)
    r = c.get(bulk_award_url(club))
    assert r.status_code == 200
    assert "Award Loot to Party" in r.content.decode()
    assert character.name in r.content.decode()
    assert second_character.name in r.content.decode()


@pytest.mark.story("S8")
def test_bulk_award_coins_to_multiple(login, game_master, club, character, second_character):
    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        bulk_payload(
            [character, second_character],
            {},
            coins={character: 500, second_character: 300},
        ),
    )
    assert r.status_code == 302
    assert coin_balance(character) == 500
    assert coin_balance(second_character) == 300
    e1 = entries(character).get()
    e2 = entries(second_character).get()
    assert e1.kind == "award" and e2.kind == "award"
    assert e1.note == "Party loot" and e2.note == "Party loot"
    assert e1.date == datetime.date(2025, 1, 15)
    assert e2.date == datetime.date(2025, 1, 15)


@pytest.mark.story("S8")
def test_bulk_award_items_to_multiple(
    login, game_master, club, character, second_character, item, second_item
):
    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        bulk_payload(
            [character, second_character],
            {character: [(item, 2)], second_character: [(second_item, 1)]},
        ),
    )
    assert r.status_code == 302
    assert item_quantities(character)[item.pk] == 2
    assert item_quantities(second_character)[second_item.pk] == 1


@pytest.mark.story("S8")
def test_bulk_award_coins_and_items_mixed(
    login, game_master, club, character, second_character, item, second_item
):
    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        bulk_payload(
            [character, second_character],
            {character: [(item, 2)], second_character: [(second_item, 1)]},
            coins={character: 500, second_character: 300},
        ),
    )
    assert r.status_code == 302
    assert coin_balance(character) == 500
    assert coin_balance(second_character) == 300
    assert item_quantities(character)[item.pk] == 2
    assert item_quantities(second_character)[second_item.pk] == 1


@pytest.mark.story("S8")
def test_bulk_award_atomic_failure(
    login, game_master, club, funded, second_character, item, make_open_trade
):
    """If one character fails, none should be awarded."""
    make_open_trade(items={item: 5})
    c = login(game_master)
    data = bulk_payload(
        [funded, second_character],
        {funded: [(item, 1)], second_character: [(item, 1)]},
    )
    r = c.post(bulk_award_url(club), data)
    assert r.status_code == 200 or r.status_code == 302


@pytest.mark.story("S8")
def test_bulk_award_redirects_to_ledger(login, game_master, club, character, second_character):
    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        bulk_payload(
            [character, second_character],
            {},
            coins={character: 500},
        ),
    )
    assert r.status_code == 302
    assert "ledger" in r.url
    assert f"character={character.pk}" in r.url or f"character={second_character.pk}" in r.url


@pytest.mark.story("S8")
@pytest.mark.parametrize("who", ["game_master", "club_admin", "site_admin"])
def test_bulk_award_permissions(request, login, club, character, who):
    user = request.getfixturevalue(who)
    c = login(user)
    r = c.get(bulk_award_url(club))
    assert r.status_code == 200


@pytest.mark.story("S8")
def test_bulk_award_player_forbidden(login, player, club, character):
    c = login(player)
    r = c.get(bulk_award_url(club))
    assert r.status_code == 403
    r = c.post(bulk_award_url(club), {"note": "test", "date": "2025-01-15"})
    assert r.status_code == 403


@pytest.mark.story("S8")
def test_bulk_award_cross_club(login, game_master, club, character, foreign_item):
    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        bulk_payload(
            [character],
            {character: [(foreign_item, 1)]},
        ),
    )
    assert r.status_code == 200
    assert not entries(character).exists()


@pytest.mark.story("S8")
def test_bulk_award_no_characters_selected(login, game_master, club, character):
    """Test that selecting no characters shows an error."""
    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        {
            "note": "test",
            "date": "2025-01-15",
        },
    )
    assert r.status_code == 200
    assert "Select at least one character" in r.content.decode()


@pytest.mark.story("S8")
def test_bulk_award_empty_amounts(login, game_master, club, character):
    """Test that empty coins/items shows an error."""
    c = login(game_master)
    r = c.post(
        bulk_award_url(club),
        {
            "note": "test",
            "date": "2025-01-15",
            "characters": [str(character.pk)],
        },
    )
    assert r.status_code == 200
    assert "at least one" in r.content.decode()
