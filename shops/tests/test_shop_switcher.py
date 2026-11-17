"""N2: shop switcher dropdown functional tests."""

from datetime import date

import pytest
from django.urls import reverse

from ledger.services import Line, record
from player_characters.models import SelectedCharacter
from shops.models import Rotation, Shop

pytestmark = [pytest.mark.django_db, pytest.mark.story("N2")]


@pytest.fixture
def open_shop(club, shop):
    Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1)).shops.add(shop)
    return shop


@pytest.fixture
def two_open(club, shop, item):
    first = shop
    second = Shop.objects.create(
        club=club, name="Mystic Brew", sell_percent=100, buy_percent=50, street_position=2
    )
    Rotation.objects.create(
        club=club, name="Always", open_date=date(2000, 1, 1)
    ).shops.add(first, second)
    return first, second


@pytest.fixture
def other_open_shop(other_club):
    shop = Shop.objects.create(
        club=other_club, name="Elsewhere", sell_percent=100, buy_percent=50
    )
    Rotation.objects.create(
        club=other_club, name="Always", open_date=date(2000, 1, 1)
    ).shops.add(shop)
    return shop


@pytest.fixture
def closed_shop(club):
    return Shop.objects.create(club=club, name="Shuttered")


def detail_url(club, shop):
    return reverse("shops:detail", args=[club.slug, shop.pk])


def page(login, player, club, shop):
    return login(player).get(detail_url(club, shop)).content.decode()


def fragment(login, player, club, shop):
    return login(player).get(
        detail_url(club, shop), HTTP_HX_REQUEST="true"
    ).content.decode()


# --- dropdown presence and contents ---


def test_dropdown_in_banner_before_leave(login, player, club, two_open, open_shop):
    first, second = two_open
    html = page(login, player, club, first)
    dropdown = html[html.index("shop-switcher") : html.index('aria-label="Leave the shop"')]
    assert "shop-switcher" in html
    assert first.name in dropdown and second.name in dropdown
    assert html.index("shop-switcher") < html.index('aria-label="Leave the shop"')


def test_dropdown_lists_detail_urls(login, player, club, two_open):
    first, second = two_open
    html = page(login, player, club, first)
    assert detail_url(club, first) in html
    assert detail_url(club, second) in html


def test_dropdown_marks_current_shop_active(login, player, club, two_open):
    first, second = two_open
    html = page(login, player, club, first)
    # current shop is first; check aria-current on its item
    start = html.index(detail_url(club, first))
    end = html.index(">", start)
    item = html[html.rindex("<a", 0, start) : end + 1]
    assert 'aria-current="page"' in item
    assert item.count("aria-current") == 1


def test_dropdown_excludes_closed_shop(login, player, club, open_shop, closed_shop):
    html = page(login, player, club, open_shop)
    assert "Shuttered" not in html


def test_dropdown_excludes_other_club(login, player, club, open_shop, other_open_shop):
    html = page(login, player, club, open_shop)
    assert "Elsewhere" not in html


def test_dropdown_hidden_when_no_open_shops(login, player, club, closed_shop):
    html = page(login, player, club, closed_shop)
    assert "shop-switcher" not in html


# --- item attributes ---


def test_item_has_hx_attributes_and_href(login, player, club, two_open):
    first, second = two_open
    html = page(login, player, club, first)
    url = detail_url(club, second)
    start = html.index(url)
    end = html.index(">", start)
    item = html[html.rindex("<a", 0, start) : end + 1]
    assert f'href="{url}"' in item
    assert f'hx-get="{url}"' in item
    assert 'hx-target="#main"' in item
    assert 'hx-swap="innerHTML"' in item
    assert 'hx-push-url="true"' in item
    assert "scroll:" not in item and "show:" not in item


# --- HTMX fragment ---


def test_fragment_has_no_top_bar(login, player, club, two_open):
    first, second = two_open
    html = fragment(login, player, club, first)
    assert "<nav" not in html and "site-header" not in html


def test_fragment_has_banner_stock_inventory(login, player, club, two_open):
    first, second = two_open
    html = fragment(login, player, club, first)
    assert "wm-shop-banner" in html
    assert 'id="stock"' in html
    assert 'id="your-inventory"' in html


def test_fragment_starts_with_title(login, player, club, two_open):
    first, second = two_open
    html = fragment(login, player, club, first)
    assert html.lstrip().startswith("<title>")
    assert f"<title>{first.name}</title>" in html


def test_fragment_varies_on_hx_request(login, player, club, two_open):
    first, second = two_open
    resp = login(player).get(detail_url(club, first), HTTP_HX_REQUEST="true")
    assert "HX-Request" in resp.get("Vary", "")


def test_normal_request_returns_full_page(login, player, club, two_open):
    first, second = two_open
    html = page(login, player, club, first)
    assert "<nav" in html or "site-header" in html
    assert "<!doctype html>" in html.lower()


# --- character context preserved ---


def test_fragment_keeps_selected_character(login, club, player, open_shop, item):
    from accounts.models import Membership
    from player_characters.models import Character

    membership = Membership.objects.get(user=player, club=club)
    aria = Character.objects.create(club=club, owner=membership, name="Aria")
    wren = Character.objects.create(club=club, owner=membership, name="Wren")
    record(aria, "award", [Line(item=item, quantity=3)])
    record(wren, "award", [Line(item=item, quantity=7)])

    SelectedCharacter.objects.create(membership=membership, character=aria)
    html_a = fragment(login, player, club, open_shop)
    assert "Aria" in html_a
    assert ">3<" in html_a

    SelectedCharacter.objects.update_or_create(
        membership=membership, defaults={"character": wren}
    )
    html_b = fragment(login, player, club, open_shop)
    assert "Wren" in html_b
    assert ">7<" in html_b
