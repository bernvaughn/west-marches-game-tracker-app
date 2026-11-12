"""U24: shop pages default the character to the selected character."""

import pytest
from django.urls import reverse

from accounts.models import Membership
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
    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    c = login(player)
    r = c.get(url)
    assert r.context["form"].initial["character"] == wren
    r = c.post(url, {"character": aria.pk, "quantity": 1})
    assert r.status_code == 302
    assert _stored(player, club) == wren


def test_buy_no_character(login, club, other_player, shop, always_open, stock):
    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    assert NONE in login(other_player).get(url).content.decode()


def test_buy_isolation(login, club, other_club, player, two, shop, always_open, stock):
    other = Membership.objects.create(user=player, club=other_club)
    c = _mk(other_club, player, "Zed")
    SelectedCharacter.objects.create(membership=other, character=c)
    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    assert login(player).get(url).context["form"].initial["character"] == two[1]


# --- shop sell
def test_sell_default_and_override(login, club, player, two, shop, always_open):
    aria, wren = two
    c = login(player)
    url = reverse("shops:sell", args=[club.slug, shop.pk])
    assert c.get(url).context["character"] == wren
    assert c.get(url, {"character": aria.pk}).context["character"] == aria
    assert _stored(player, club) == wren


def test_sell_no_character_and_isolation(login, club, other_club, other_player, shop, always_open):
    url = reverse("shops:sell", args=[club.slug, shop.pk])
    assert NONE in login(other_player).get(url).content.decode()
    Membership.objects.create(user=other_player, club=other_club)
    foreign = _mk(other_club, other_player, "Far")
    assert login(other_player).get(url, {"character": foreign.pk}).status_code == 404
