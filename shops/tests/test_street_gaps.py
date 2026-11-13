from datetime import date

import pytest
from django.urls import reverse

from shops.models import Rotation, Shop
from shops.services import ordered_shops
from shops.views.browse import street_lots

pytestmark = [pytest.mark.django_db]


def open_shop(club, name, **kw):
    shop = Shop.objects.create(club=club, name=name, **kw)
    rotation, _ = Rotation.objects.get_or_create(
        club=club, name="Always", defaults={"open_date": date(2000, 1, 1)}
    )
    rotation.shops.add(shop)
    return shop


def names(lots):
    return [x["shop"].name if x["shop"] else None for x in lots]


@pytest.mark.story("U62")
def test_gap_capped_at_two(club):
    a = open_shop(club, "A", street_position=0)
    b = open_shop(club, "B", street_position=10)
    assert names(street_lots([a, b]))[:4] == ["A", None, None, "B"]


@pytest.mark.story("U62")
def test_leading_filler_capped(club):
    far = open_shop(club, "Far", street_position=500)
    assert names(street_lots([far]))[:3] == [None, None, "Far"]
    one = open_shop(club, "One", street_position=1)
    assert names(street_lots([one]))[:2] == [None, "One"]
    zero = open_shop(club, "Zero", street_position=0)
    assert names(street_lots([zero]))[0] == "Zero"


@pytest.mark.story("U62")
def test_whole_rows_and_filler_only_row(club):
    shops = [open_shop(club, f"S{i}", street_position=i) for i in range(8)]
    assert len(street_lots(shops)) == 8
    far = open_shop(club, "Far", street_position=500)
    lots = street_lots([far], per_row=2)
    assert names(lots) == [None, None, "Far", None]
    assert all(x["shop"] is None for x in lots[:2])


@pytest.mark.story("U64")
def test_tie_break_order(club):
    ids = [
        open_shop(club, "beta", street_position=3),
        open_shop(club, "Alpha", street_position=3, keeper_name="zoe"),
        open_shop(club, "Alpha", street_position=3, keeper_name="Ann"),
        open_shop(club, "Alpha", street_position=3, keeper_name="Ann"),
    ]
    got = [s.pk for s in ordered_shops(Shop.objects.all())]
    assert got == [ids[2].pk, ids[3].pk, ids[1].pk, ids[0].pk]
    assert [s.pk for s in Shop.objects.all()] == got
    shuffled = [ids[0], ids[1], ids[3], ids[2]]
    placed = [x["shop"].pk for x in street_lots(shuffled) if x["shop"]]
    assert placed == got


@pytest.mark.story("U64")
def test_admin_and_rotations_same_order(login, club_admin, club):
    from shops.forms.rotations import RotationForm

    open_shop(club, "beta", street_position=1)
    open_shop(club, "Alpha", street_position=1)
    open_shop(club, "Early", street_position=0)
    client = login(club_admin)
    html = client.get(reverse("shops:manage_list", args=[club.slug])).content.decode()
    assert html.index("Early") < html.index("Alpha") < html.index("beta")
    form = RotationForm(club=club)
    assert [s.name for s in form.fields["shops"].queryset] == ["Early", "Alpha", "beta"]
