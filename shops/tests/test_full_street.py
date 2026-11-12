import re
from datetime import date
from pathlib import Path

import pytest
from django.urls import reverse

from shops.models import Rotation, Shop
from shops.views.browse import street_lots

pytestmark = [pytest.mark.django_db, pytest.mark.story("U54")]

CSS = Path(__file__).resolve().parents[2] / "static" / "css" / "areas" / "shops.css"


def open_shop(club, name, **kw):
    shop = Shop.objects.create(club=club, name=name, **kw)
    rotation, _ = Rotation.objects.get_or_create(
        club=club, name="Always", defaults={"open_date": date(2000, 1, 1)}
    )
    rotation.shops.add(shop)
    return shop


def names(lots):
    return [x["shop"].name if x["shop"] else None for x in lots]


def page(login, player, club):
    return login(player).get(reverse("shops:index", args=[club.slug])).content.decode()


def test_positions_and_filler(club):
    a = open_shop(club, "A", street_position=1)
    b = open_shop(club, "B", street_position=4)
    assert names(street_lots([a, b])) == [None, "A", None, None, "B", None, None, None]


def test_ties_fill_in_name_order(club):
    shops = [open_shop(club, n, street_position=0) for n in ("Zed", "Amy", "Bob")]
    assert names(street_lots(shops))[:4] == ["Amy", "Bob", "Zed", None]


def test_rows_of_eight(club):
    shops = [open_shop(club, f"S{i}", street_position=i) for i in range(8)]
    assert len(street_lots(shops)) == 8
    shops.append(open_shop(club, "S9", street_position=0))
    assert len(street_lots(shops)) == 16


def test_huge_position_capped(club):
    shop = open_shop(club, "Far", street_position=500)
    assert len(street_lots([shop])) == 8


def test_empty_street():
    assert street_lots([]) == []


def test_filler_hidden_and_links(login, player, club, other_club):
    open_shop(club, "One", street_position=2)
    open_shop(club, "Two", street_position=5)
    Shop.objects.create(club=club, name="Shut")
    open_shop(other_club, "Elsewhere")
    body = page(login, player, club)
    ul = body[body.index('<ul class="wm-street"') :]
    ul = ul[: ul.index("</ul>")]
    items = re.findall(r"<li.*?</li>", ul, re.S)
    assert len(items) == 8
    filler = [i for i in items if "wm-street-lot--filler" in i]
    assert len(filler) == 6
    for i in filler:
        assert 'aria-hidden="true"' in i and "<a " not in i and "wm-street-sign" not in i
    assert ul.count("<a ") == 2
    assert "Shut" not in body and "Elsewhere" not in body


def test_deterministic(login, player, club):
    for i in range(9):
        open_shop(club, f"S{i}")

    def street(body):
        body = body[body.index('<ul class="wm-street"') :]
        return body[: body.index("</ul>")]

    first = street(page(login, player, club))
    assert first.count("<li") == 16
    assert street(page(login, player, club)) == first


def test_css_columns():
    css = CSS.read_text()
    assert "repeat(4, minmax(0, 1fr))" in css and "repeat(8, minmax(0, 1fr))" in css
