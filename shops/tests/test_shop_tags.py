"""Unit tests for the shop_switcher inclusion tag."""

import pytest
from django.template import Context, Template
from django.utils import timezone

from shops.models import Rotation, Shop

pytestmark = [pytest.mark.django_db, pytest.mark.story("FOUNDATION")]


def _render(club, current=None):
    return Template("{% load shop_tags %}{% shop_switcher club current %}").render(
        Context({"club": club, "current": current})
    )


def _make_open(club, name, position, keeper_name=""):
    shop = Shop.objects.create(
        club=club, name=name, street_position=position, keeper_name=keeper_name
    )
    Rotation.objects.create(club=club, name="Always", open_date=timezone.localdate()).shops.add(
        shop
    )
    return shop


def test_shop_switcher_lists_open_shops_only(club):
    today = timezone.localdate()
    open_shop = Shop.objects.create(club=club, name="Hammer Anvil", street_position=1)
    Rotation.objects.create(club=club, name="Spring Market", open_date=today).shops.add(open_shop)
    Shop.objects.create(club=club, name="Shuttered")

    html = _render(club)

    assert "Hammer Anvil" in html
    assert "Shuttered" not in html
    assert f'href="/c/{club.slug}/shops/{open_shop.pk}/"' in html


def test_shop_switcher_hidden_when_no_open_shops(club):
    Shop.objects.create(club=club, name="Shuttered")
    assert _render(club).strip() == ""


def test_shop_switcher_marks_current_shop_active(club):
    current = _make_open(club, "Current Shop", 1, "C Keeper")
    _make_open(club, "Other Shop", 2)

    html = _render(club, current=current)

    assert 'aria-current="page"' in html
    assert html.count('aria-current="page"') == 1


def test_shop_switcher_lists_in_street_order(club):
    _make_open(club, "C Shop", 3)
    _make_open(club, "A Shop", 1)
    _make_open(club, "B Shop", 2)

    html = _render(club)

    first_idx = html.index("A Shop")
    second_idx = html.index("B Shop")
    third_idx = html.index("C Shop")
    assert first_idx < second_idx < third_idx


def test_shop_switcher_excludes_other_clubs(club, other_club):
    _make_open(club, "Our Shop", 1)
    _make_open(other_club, "Their Shop", 1)

    html = _render(club)

    assert "Our Shop" in html
    assert "Their Shop" not in html
