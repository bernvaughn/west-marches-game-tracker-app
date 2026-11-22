from datetime import date

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from accounts.models import Membership
from ledger.services import Line, record
from player_characters import life
from player_characters.models import Character, JunkMark

pytestmark = [pytest.mark.django_db, pytest.mark.story("U142")]


def stall_url(club, character):
    return reverse("shops:player_shop", args=[club.slug, character.pk])


def street_url(club):
    return reverse("shops:index", args=[club.slug])


def street_editor_url(club):
    return reverse("shops:street_editor", args=[club.slug])


def where_to_buy_url(club, item):
    return reverse("items:where_to_buy", args=[club.slug, item.pk])


def open_stall(club, owner, name, item, quantity=1):
    """An open stall listing `quantity` of `item`. `owner` is a User or Membership."""
    if not isinstance(owner, Membership):
        owner = Membership.objects.get(user=owner, club=club)
    c = Character.objects.create(club=club, owner=owner, name=name, shop_open=True)
    record(c, "award", [Line(item=item, quantity=quantity)])
    JunkMark.objects.create(character=c, item=item, quantity=quantity)
    return c


def kill(character, by, died_on=None):
    life.mark_dead(character, by=by, died_on=died_on or date(2024, 1, 5))


def membership(club, user):
    return Membership.objects.get(user=user, club=club)


# --- stall page ----------------------------------------------------------


def test_dead_stall_page_shows_memorial(login, club, player, item):
    seller = open_stall(club, player, "Borin", item)
    kill(seller, membership(club, player))
    body = login(player).get(stall_url(club, seller)).content.decode()
    assert "In memory of Borin" in body
    assert "5 Jan 2024" in body
    assert 'datetime="2024-01-05"' in body
    assert "wm-player-shop-banner--memorial" in body
    assert 'role="note"' in body


def test_living_stall_page_has_no_memorial(login, club, player, item):
    seller = open_stall(club, player, "Borin", item)
    body = login(player).get(stall_url(club, seller)).content.decode()
    assert "wm-memorial" not in body
    assert "wm-player-shop-banner--memorial" not in body


def test_dead_stall_buyers_can_still_buy(login, club, player, other_player, item):
    seller = open_stall(club, player, "Borin", item)
    kill(seller, membership(club, player))
    buyer_membership = Membership.objects.get(user=other_player, club=club)
    buyer = Character.objects.create(club=club, owner=buyer_membership, name="Buyer")
    record(buyer, "award", [Line(coins=1000)])
    buy_url = reverse("shops:player_shop_buy", args=[club.slug, seller.pk, item.pk])
    resp = login(other_player).get(buy_url)
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "In memory of Borin" not in body  # buy page is unchanged for buyers
    assert "wm-memorial" not in body
    assert "Buying as" in body and "Buyer" in body


# --- street --------------------------------------------------------------


def test_dead_stall_shows_memorial_on_street(login, club, player, item):
    seller = open_stall(club, player, "Borin", item)
    kill(seller, membership(club, player))
    body = login(player).get(street_url(club)).content.decode()
    assert "wm-street-lot--memorial" in body
    assert "In memory of Borin" in body
    assert "5 Jan 2024" in body


def test_living_stall_shows_no_memorial_on_street(login, club, player, item):
    open_stall(club, player, "Borin", item)
    body = login(player).get(street_url(club)).content.decode()
    assert "wm-street-lot--memorial" not in body
    assert "wm-memorial" not in body


# --- street editor -------------------------------------------------------


def test_dead_stall_shows_memorial_in_street_editor(login, club, club_admin, item):
    seller = open_stall(club, club_admin, "Borin", item)
    kill(seller, membership(club, club_admin))
    body = login(club_admin).get(street_editor_url(club)).content.decode()
    assert "wm-street-lot--memorial" in body
    assert "In memory of Borin" in body


# --- where to buy --------------------------------------------------------


def test_dead_stall_shows_inline_memorial_in_where_to_buy(login, club, player, item):
    seller = open_stall(club, player, "Borin", item)
    kill(seller, membership(club, player))
    body = login(player).get(where_to_buy_url(club, item)).content.decode()
    assert "wm-memorial--inline" in body
    assert "† In memory" in body
    assert "5 Jan 2024" in body


def test_living_stall_shows_no_inline_memorial_in_where_to_buy(login, club, player, item):
    open_stall(club, player, "Borin", item)
    body = login(player).get(where_to_buy_url(club, item)).content.decode()
    assert "wm-memorial" not in body


# --- css -----------------------------------------------------------------


def test_base_links_memorial_css(settings):
    from django.template.loader import get_template

    body = get_template("base.html").template.source
    assert "css/areas/memorial.css" in body
    assert body.index("css/areas/shops.css") < body.index("css/areas/memorial.css")


def test_memorial_css_has_no_raw_hex():
    path = finders.find("css/areas/memorial.css")
    assert path is not None
    text = open(path).read()
    import re

    assert not re.findall(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b", text)
