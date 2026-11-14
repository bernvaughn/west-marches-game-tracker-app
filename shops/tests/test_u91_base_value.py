from datetime import date

import pytest
from django.urls import reverse

from items.models import Item
from ledger.services import Line, record
from ledger.templatetags.coins import coins
from player_characters.models import JunkMark
from shops.models import Rotation

pytestmark = [pytest.mark.django_db, pytest.mark.story("U91")]


def card(body):
    return body[body.index('id="your-inventory"') :]


def browse_card(client, club, shop):
    Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1)).shops.add(shop)
    return card(client.get(reverse("shops:detail", args=[club.slug, shop.id])).content.decode())


def player_card(client, club, seller, junk_item):
    JunkMark.objects.create(character=seller, item=junk_item, quantity=1)
    seller.shop_open = True
    seller.save()
    url = reverse("shops:player_shop", args=[club.slug, seller.pk])
    return card(client.get(url).content.decode())


def stock(character, club):
    gem = Item.objects.create(club=club, name="Gem", value_cp=333)
    rope = Item.objects.create(club=club, name="Cord", value_cp=50)
    record(character, "award", [Line(item=gem, quantity=2), Line(item=rope, quantity=7)])
    return gem, rope


def check(c, gem, rope):
    head = c[c.index("<thead>") : c.index("</thead>")]
    assert head.index("Item") < head.index("Base value") < head.index("Qty")
    assert 'class="wm-table-scroll"' in c[: c.index("<table")]
    rows = c[c.index("<tbody>") :].split("<tr>")[1:]
    for item, qty in ((gem, "2"), (rope, "7")):
        row = next(r for r in rows if item.name in r)
        value = f'<td class="num">{coins(item.value_cp)}</td>'
        assert value in row
        assert row.index(item.name) < row.index(value) < row.index(f"<td>{qty}</td>")


def test_browse_column_order_value_and_scroll(login, player, club, shop, character):
    gem, rope = stock(character, club)
    check(browse_card(login(player), club, shop), gem, rope)


def test_player_shop_column_order_value_and_scroll(
    login, club, character, other_character, other_player
):
    gem, rope = stock(other_character, club)
    record(character, "award", [Line(item=gem, quantity=1)])
    c = player_card(login(other_character.owner.user), club, character, gem)
    check(c, gem, rope)
