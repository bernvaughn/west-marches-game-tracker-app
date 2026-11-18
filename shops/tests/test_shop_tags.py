"""Unit tests for the shop_switcher inclusion tag."""

import pytest
from django.template import Context, Template
from django.utils import timezone

from shops.models import Rotation, Shop

pytestmark = [pytest.mark.django_db, pytest.mark.story("FOUNDATION")]


def _render(club):
    return Template("{% load shop_tags %}{% shop_switcher club %}").render(
        Context({"club": club})
    )


def test_shop_switcher_lists_open_shops_only(club):
    today = timezone.localdate()
    open_shop = Shop.objects.create(club=club, name="Hammer Anvil")
    Rotation.objects.create(club=club, name="Spring Market", open_date=today).shops.add(
        open_shop
    )
    Shop.objects.create(club=club, name="Shuttered")

    html = _render(club)

    assert "Hammer Anvil" in html
    assert "Shuttered" not in html
    assert f'href="/c/{club.slug}/shops/{open_shop.pk}/"' in html


def test_shop_switcher_hidden_when_no_open_shops(club):
    Shop.objects.create(club=club, name="Shuttered")
    assert _render(club).strip() == ""
