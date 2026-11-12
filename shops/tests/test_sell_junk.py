import pytest
from django.urls import reverse

from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import Line, available_coins, item_quantities, record
from player_characters.junk import junk_rows, set_junk
from quests.models import Quest, QuestRequirement
from shops.selling import SellLineError, sell_many
from shops.services import ShopError

pytestmark = [pytest.mark.story("U47"), pytest.mark.django_db]


@pytest.fixture
def torch(club):
    return Item.objects.create(club=club, name="Torch", value_cp=10)


@pytest.fixture
def foreign_item(other_club):
    return Item.objects.create(club=other_club, name="Foreign Rope", value_cp=100)


@pytest.fixture
def junked(character, item, torch, player, always_open):
    record(character, "award", [Line(item=item, quantity=3), Line(item=torch, quantity=4)])
    set_junk(character, item, 3, player)
    set_junk(character, torch, 4, player)
    return character


def url(club, shop):
    return reverse("shops:sell_junk", args=[club.slug, shop.pk])


def test_sell_many_sells_all_and_reduces_junk(junked, shop, item, torch, player):
    sell_many(junked, shop, [(item, 2), (torch, 4)], actor=player)
    assert item_quantities(junked)[item.pk] == 1
    assert item_quantities(junked).get(torch.pk, 0) == 0
    assert available_coins(junked) == 100 + 20
    assert [(r.item, r.quantity) for r in junk_rows(junked)] == [(item, 1)]


def test_one_bad_line_sells_nothing(junked, shop, item, torch, player, foreign_item):
    entries = LedgerEntry.objects.count()
    with pytest.raises(SellLineError):
        sell_many(junked, shop, [(item, 1), (torch, 99)], actor=player)
    with pytest.raises(SellLineError):
        sell_many(junked, shop, [(item, 1), (foreign_item, 1)], actor=player)
    assert LedgerEntry.objects.count() == entries
    assert {r.item: r.quantity for r in junk_rows(junked)} == {item: 3, torch: 4}


def test_no_lines_and_closed_shop(junked, shop, item, closed_shop):
    with pytest.raises(ShopError):
        sell_many(junked, shop, [])
    with pytest.raises(ShopError, match="closed"):
        sell_many(junked, closed_shop, [(item, 1)])
    assert len(junk_rows(junked)) == 2


def test_view_lists_rows_ticked_and_quest_unticked(club, login, player, junked, shop, item):
    quest = Quest.objects.create(club=club, name="Rope Run")
    QuestRequirement.objects.create(quest=quest, item=item, quantity=1)
    body = login(player).get(url(club, shop), HTTP_HX_REQUEST="true").content.decode()
    assert "Needed for quest: Rope Run" in body
    assert f'value="{item.pk}" id="junk-tick-{item.pk}" aria-label' in body
    assert "checked" not in body.split(f'id="junk-tick-{item.pk}"')[1].split(">")[0]


def test_post_sells_only_ticked(club, login, player, junked, shop, item, torch):
    r = login(player).post(
        url(club, shop),
        {"item": [torch.pk], f"qty_{torch.pk}": "3", f"qty_{item.pk}": "3"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204
    assert r.headers["HX-Redirect"] == reverse("shops:detail", args=[club.slug, shop.pk])
    assert item_quantities(junked)[item.pk] == 3
    assert item_quantities(junked)[torch.pk] == 1
    assert [(x.item, x.quantity) for x in junk_rows(junked)] == [(item, 3), (torch, 1)]


def test_error_shown_and_nothing_sold(club, login, player, junked, shop, item, torch):
    record(junked, "adjustment", [Line(item=torch, quantity=-4)])
    r = login(player).post(
        url(club, shop),
        {"item": [item.pk, torch.pk], f"qty_{item.pk}": "1", f"qty_{torch.pk}": "1"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    assert item_quantities(junked)[item.pk] == 3


def test_none_ticked_and_bad_quantity(club, login, player, junked, shop, item):
    c = login(player)
    assert "Tick at least one item." in c.post(url(club, shop), {}).content.decode()
    r = c.post(url(club, shop), {"item": [item.pk], f"qty_{item.pk}": "9"})
    assert r.status_code == 200 and item_quantities(junked)[item.pk] == 3


def test_foreign_item_id_refused(club, login, player, junked, shop, foreign_item):
    r = login(player).post(
        url(club, shop), {"item": [foreign_item.pk], f"qty_{foreign_item.pk}": "1"}
    )
    assert r.status_code == 200
    assert len(junk_rows(junked)) == 2


def test_plain_page_works_without_htmx(club, login, player, junked, shop, item):
    c = login(player)
    assert "<html" in c.get(url(club, shop)).content.decode()
    r = c.post(url(club, shop), {"item": [item.pk], f"qty_{item.pk}": "1"})
    assert r.status_code == 302
    assert item_quantities(junked)[item.pk] == 2


def test_cross_club_shop_404_and_closed_404(club, login, player, junked, other_shop, closed_shop):
    c = login(player)
    assert c.get(url(club, other_shop)).status_code == 404
    assert c.get(url(club, closed_shop)).status_code == 404


def test_no_character_empty_state(club, login, other_player, always_open, shop):
    body = login(other_player).get(url(club, shop)).content.decode()
    assert "no character" in body


def test_shop_page_and_buy_modal_junk_lines(club, login, player, junked, shop, item, stock):
    c = login(player)
    body = c.get(reverse("shops:detail", args=[club.slug, shop.pk])).content.decode()
    assert "Junk: " in body and "sells here for" in body and "Sell junk" in body
    buy = c.get(reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])).content.decode()
    assert "Junk: " in buy


def test_htmx_sale_total_reaches_the_user(club, login, player, junked, shop, item, torch):
    c = login(player)
    r = c.post(
        url(club, shop),
        {"item": [item.pk, torch.pk], f"qty_{item.pk}": "2", f"qty_{torch.pk}": "4"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204
    # htmx follows HX-Redirect with a full page load, which shows the message.
    page = c.get(r.headers["HX-Redirect"]).content.decode()
    assert "Sold junk to Lantern for 1 gp 2 sp." in page


def test_total_follows_ticks_and_quantities(club, login, player, junked, shop, item, torch):
    c = login(player)

    def total(params):
        body = c.get(url(club, shop), {"recalc": "1", **params}, HTTP_HX_REQUEST="true")
        body = body.content.decode()
        return body[body.index('id="junk-total"') :].split("</p>")[0]

    assert "0 cp" in total({f"qty_{item.pk}": "3", f"qty_{torch.pk}": "4"})
    assert "1 gp</span></strong>" in total(
        {"item": [item.pk], f"qty_{item.pk}": "2", f"qty_{torch.pk}": "4"}
    )
    both = {"item": [item.pk, torch.pk], f"qty_{item.pk}": "2", f"qty_{torch.pk}": "4"}
    assert "2 sp" in total(both)
