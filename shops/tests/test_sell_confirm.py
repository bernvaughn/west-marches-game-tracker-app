import pytest
from django.urls import reverse

from ledger.models import LedgerEntry
from ledger.services import Line, record
from player_characters.junk import set_junk
from player_characters.models import JunkMark, Trade, TradeLine


@pytest.fixture
def loot(character, item):
    record(character, "award", [Line(item=item, quantity=3)])
    return item


def url(club, shop):
    return reverse("shops:sell", args=[club.slug, shop.id])


def post(client, club, shop, character, item, quantity, **extra):
    data = {"character": character.id, "item": item.id, "quantity": quantity, **extra}
    return client.post(url(club, shop), data)


def sales():
    return LedgerEntry.objects.filter(kind="sale").count()


@pytest.mark.story("U57")
def test_banner_leave_and_sell(club, player, login, shop, always_open):
    r = login(player).get(reverse("shops:detail", args=[club.slug, shop.id]))
    html = r.content.decode()
    index = reverse("shops:index", args=[club.slug])
    assert f'class="btn btn-outline-secondary" href="{index}"' in html
    assert "Leave" in html
    assert f'class="btn btn-primary" href="{url(club, shop)}"' in html


@pytest.mark.story("U58")
def test_non_junk_asks_to_confirm(club, player, login, character, shop, always_open, loot):
    r = post(login(player), club, shop, character, loot, 1)
    assert r.status_code == 200
    assert "This item isn't marked as junk." in r.content.decode()
    assert sales() == 0


@pytest.mark.story("U58")
def test_htmx_confirm_is_modal(club, player, login, character, shop, always_open, loot):
    c = login(player)
    r = c.post(
        url(club, shop),
        {"character": character.id, "item": loot.id, "quantity": 1},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    assert b"modal-header" in r.content
    assert "HX-Request" in r["Vary"]
    assert sales() == 0


@pytest.mark.story("U58")
def test_confirmed_sells(club, player, login, character, shop, always_open, loot):
    r = post(login(player), club, shop, character, loot, 1, confirmed="1")
    assert r.status_code == 302
    assert sales() == 1


@pytest.mark.story("U58")
def test_confirmed_htmx(club, player, login, character, shop, always_open, loot):
    r = login(player).post(
        url(club, shop),
        {"character": character.id, "item": loot.id, "quantity": 1, "confirmed": "1"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204
    assert r["HX-Redirect"] == reverse("shops:detail", args=[club.slug, shop.id])
    assert sales() == 1


@pytest.mark.story("U58")
def test_junk_within_quantity_sells_straight(
    club, player, login, character, shop, always_open, loot
):
    set_junk(character, loot, 2, player)
    r = post(login(player), club, shop, character, loot, 2)
    assert r.status_code == 302
    assert sales() == 1
    assert not JunkMark.objects.filter(character=character).exists()


@pytest.mark.story("U58")
def test_junk_partial_lowers_mark(club, player, login, character, shop, always_open, loot):
    set_junk(character, loot, 2, player)
    post(login(player), club, shop, character, loot, 1)
    assert JunkMark.objects.get(character=character).quantity == 1


@pytest.mark.story("U58")
def test_over_junk_quantity_confirms(club, player, login, character, shop, always_open, loot):
    set_junk(character, loot, 2, player)
    r = post(login(player), club, shop, character, loot, 3)
    assert r.status_code == 200
    assert b"Only 2 of this item are marked as junk." in r.content
    assert sales() == 0


@pytest.mark.story("U58")
def test_cancel_goes_back_and_sells_nothing(
    club, player, login, character, shop, always_open, loot
):
    c = login(player)
    r = post(c, club, shop, character, loot, 1)
    assert f'href="{url(club, shop)}">Cancel' in r.content.decode()
    assert c.get(url(club, shop)).status_code == 200
    assert sales() == 0


@pytest.mark.story("U58")
def test_over_available_errors(club, player, login, character, shop, always_open, loot):
    r = post(login(player), club, shop, character, loot, 9)
    assert r.status_code == 200
    assert b"Not enough Rope available to sell." in r.content
    assert b"marked as junk" not in r.content
    assert sales() == 0


@pytest.mark.story("U58")
def test_held_line_only_when_held(
    club, player, login, character, other_character, shop, always_open, loot
):
    c = login(player)
    r = post(c, club, shop, character, loot, 1)
    assert b"In open trades" not in r.content
    trade = Trade.objects.create(club=club, sender=character, receiver=other_character)
    TradeLine.objects.create(trade=trade, from_sender=True, item=loot, quantity=1)
    r = post(c, club, shop, character, loot, 1)
    assert b"In open trades" in r.content
    assert b"Held" not in r.content
