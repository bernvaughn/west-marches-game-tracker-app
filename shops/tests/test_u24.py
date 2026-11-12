"""U24: shop pages default the character to the selected character."""

import pytest
from django.urls import reverse

from accounts.models import Membership
from ledger.models import LedgerEntry
from ledger.services import Line, record
from player_characters.models import Character, SelectedCharacter

pytestmark = [pytest.mark.django_db, pytest.mark.story("U24")]

NONE = "You have no character in this club."


def _mk(club, user, name):
    return Character.objects.create(
        club=club, owner=Membership.objects.get(user=user, club=club), name=name
    )


@pytest.fixture
def two(club, player, character):
    second = _mk(club, player, "Wren")
    m = Membership.objects.get(user=player, club=club)
    SelectedCharacter.objects.create(membership=m, character=second)
    return character, second


def _stored(player, club):
    return SelectedCharacter.objects.get(
        membership=Membership.objects.get(user=player, club=club)
    ).character


# --- shop buy
def test_buy_default_and_other(login, club, player, two, shop, always_open, stock):
    aria, wren = two
    record(aria, "award", [Line(coins=1000)])
    record(wren, "award", [Line(coins=1000)])
    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    c = login(player)
    r = c.get(url)
    assert r.context["character"] == wren
    assert "Buy as Wren" in r.content.decode()
    r = c.post(url, {"character": aria.pk, "quantity": 1})
    assert r.status_code == 302
    assert LedgerEntry.objects.get(kind="purchase").character == wren
    assert _stored(player, club) == wren


def test_buy_no_character(login, club, other_player, shop, always_open, stock):
    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    assert NONE in login(other_player).get(url).content.decode()


def test_buy_isolation(login, club, other_club, player, two, shop, always_open, stock):
    other = Membership.objects.create(user=player, club=other_club)
    c = _mk(other_club, player, "Zed")
    SelectedCharacter.objects.create(membership=other, character=c)
    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    assert login(player).get(url).context["character"] == two[1]


# --- shop sell
def test_sell_default_and_override(login, club, player, two, shop, always_open):
    aria, wren = two
    c = login(player)
    url = reverse("shops:sell", args=[club.slug, shop.pk])
    assert c.get(url).context["character"] == wren
    assert c.get(url, {"character": aria.pk}).context["character"] == wren
    assert "Sell as" not in c.get(url).content.decode()  # nothing to sell yet
    assert "Selling as <strong>Wren</strong>" in c.get(url).content.decode()
    assert _stored(player, club) == wren


def test_sell_no_character_and_isolation(login, club, other_club, other_player, shop, always_open):
    url = reverse("shops:sell", args=[club.slug, shop.pk])
    assert NONE in login(other_player).get(url).content.decode()
    Membership.objects.create(user=other_player, club=other_club)
    foreign = _mk(other_club, other_player, "Far")
    r = login(other_player).get(url, {"character": foreign.pk})
    assert NONE in r.content.decode()
    assert login(other_player).post(url, {"item": 1, "quantity": 1}).status_code in (200, 404)


@pytest.mark.story("U27")
def test_u27_buy_sell_pages_have_no_character_field(
    login, club, player, two, shop, always_open, stock
):
    c = login(player)
    buy_html = c.get(reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])).content.decode()
    sell_html = c.get(reverse("shops:sell", args=[club.slug, shop.pk])).content.decode()
    for html in (buy_html, sell_html):
        assert 'name="character"' not in html.split("<h1")[1]
    assert "Buying as <strong>Wren</strong>" in buy_html


@pytest.mark.story("U27")
def test_u27_buy_no_character_posts_nothing(login, club, other_player, shop, always_open, stock):
    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    r = login(other_player).post(url, {"quantity": 1})
    assert NONE in r.content.decode()
    assert not LedgerEntry.objects.filter(kind="purchase").exists()
