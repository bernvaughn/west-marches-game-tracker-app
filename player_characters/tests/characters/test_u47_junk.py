import re

import pytest
from django.db import IntegrityError
from django.urls import reverse

from accounts.models import Membership
from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import Line, record
from player_characters.junk import JunkError, junk_rows, junk_value, junk_value_at, set_junk
from player_characters.models import Character, JunkMark
from shops.models import Shop, ShopStock

pytestmark = [pytest.mark.story("U47"), pytest.mark.django_db]


@pytest.fixture
def owned(character, item):
    record(character, "award", [Line(item=item, quantity=5), Line(coins=100)])
    return character


def junk_url(club, character, item):
    return reverse("characters:junk", args=[club.slug, character.pk, item.pk])


def test_unique_per_character_and_item(owned, item):
    JunkMark.objects.create(character=owned, item=item, quantity=1)
    with pytest.raises(IntegrityError):
        JunkMark.objects.create(character=owned, item=item, quantity=2)


def test_set_change_unmark(owned, item, player):
    set_junk(owned, item, 3, player)
    assert [(r.quantity) for r in junk_rows(owned)] == [3]
    set_junk(owned, item, 2, player)
    assert junk_rows(owned)[0].quantity == 2
    set_junk(owned, item, 0, player)
    assert junk_rows(owned) == []


def test_refuses_over_owned_negative_and_cross_club(owned, item, player, foreign_item):
    with pytest.raises(JunkError):
        set_junk(owned, item, 6, player)
    with pytest.raises(JunkError):
        set_junk(owned, item, -1, player)
    with pytest.raises(JunkError):
        set_junk(owned, foreign_item, 1, player)


def test_cap_applies_when_items_leave(owned, item, player):
    set_junk(owned, item, 5, player)
    record(owned, "adjustment", [Line(item=item, quantity=-3)])
    assert junk_rows(owned)[0].quantity == 2
    record(owned, "adjustment", [Line(item=item, quantity=-2)])
    assert junk_rows(owned) == []


def test_values_use_buy_percent_override(club, owned, item, player):
    set_junk(owned, item, 2, player)
    shop = Shop.objects.create(club=club, name="S", buy_percent=50)
    assert junk_value(owned) == 200
    assert junk_value_at(owned, shop) == 100
    ShopStock.objects.create(shop=shop, item=item, quantity=1, buy_percent=10)
    assert junk_value_at(owned, shop) == 20


@pytest.mark.parametrize("who", ["player", "game_master", "club_admin"])
def test_can_mark_through_view(club, login, request, owned, item, who):
    before = LedgerEntry.objects.count()
    r = login(request.getfixturevalue(who)).post(junk_url(club, owned, item), {"quantity": "2"})
    assert r.status_code == 302
    assert junk_rows(owned)[0].quantity == 2
    assert LedgerEntry.objects.count() == before


def test_other_player_forbidden(club, login, other_player, owned, item):
    c = login(other_player)
    assert c.get(junk_url(club, owned, item)).status_code == 403
    assert c.post(junk_url(club, owned, item), {"quantity": "1"}).status_code == 403
    assert JunkMark.objects.count() == 0


def test_over_owned_refused_in_view(club, login, player, owned, item):
    r = login(player).post(junk_url(club, owned, item), {"quantity": "9"})
    assert r.status_code == 200
    assert JunkMark.objects.count() == 0


def test_cross_club_is_404(club, login, player, owned, item, foreign_character, foreign_item):
    c = login(player)
    assert c.get(junk_url(club, foreign_character, item)).status_code == 404
    assert c.get(junk_url(club, owned, foreign_item)).status_code == 404


def test_htmx_modal_and_plain_page(club, login, player, owned, item):
    c = login(player)
    modal = c.get(junk_url(club, owned, item), HTTP_HX_REQUEST="true").content.decode()
    page = c.get(junk_url(club, owned, item)).content.decode()
    assert "modal-header" in modal and "<html" not in modal
    assert "<html" in page
    r = c.post(junk_url(club, owned, item), {"quantity": "1"}, HTTP_HX_REQUEST="true")
    assert r.status_code == 204 and "HX-Redirect" in r.headers


def test_sheet_shows_badge_coins_line_and_quest_warning(club, login, player, owned, item):
    from quests.models import Quest, QuestRequirement

    quest = Quest.objects.create(club=club, name="Rope Run")
    QuestRequirement.objects.create(quest=quest, item=item, quantity=1)
    set_junk(owned, item, 2, player)
    body = login(player).get(reverse("characters:detail", args=[club.slug, owned.pk])).content
    body = body.decode()
    assert re.search(r"Junk: <span class=\"coin coin-gp\">2 gp", body)
    assert "&times;2" in body
    assert "Needed for quest: Rope Run" in body


def test_isolation_of_junk_between_characters(club, login, other_player, owned, item, player):
    other = Character.objects.create(
        club=club, owner=Membership.objects.get(user=other_player, club=club), name="Zed"
    )
    set_junk(owned, item, 1, player)
    assert junk_rows(other) == []
    Item.objects.filter(pk=item.pk).exists()
