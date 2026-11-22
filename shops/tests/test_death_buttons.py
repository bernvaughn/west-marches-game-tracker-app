"""Tests for U140: buy/spend buttons replaced by death reason."""

import pytest
from django.urls import reverse
from django.utils import timezone

from ledger.services import Line, record

pytestmark = [pytest.mark.django_db, pytest.mark.story("U140")]
HX = {"HTTP_HX_REQUEST": "true"}


def _make_dead(character):
    character.died_on = timezone.localdate()
    character.save(update_fields=["died_on"])


def _make_archived(character):
    character.archived_at = timezone.now()
    character.save(update_fields=["archived_at"])


def _select_character(client, character):
    """Set the selected character in session."""
    url = reverse("characters:select", args=[character.club.slug])
    client.post(url, {"character": character.pk})


# --- Club shop browse stock fragment ---


def test_stock_fragment_dead_selected_shows_reason(
    club, shop, always_open, stock, character, rich_character, player, login
):
    """Stock fragment (htmx) shows reason instead of Buy when selected character is dead."""
    _make_dead(character)
    _select_character(login(player), character)

    url = reverse("shops:stock_fragment", args=[club.slug, shop.pk])
    body = login(player).get(url, **HX).content.decode()

    assert "Aria died on" in body
    assert "Buy" not in body.split("actions")[1].split("</td>")[0]


def test_stock_fragment_archived_selected_shows_reason(
    club, shop, always_open, stock, character, rich_character, player, login
):
    """Stock fragment shows reason when selected character is archived."""
    _make_archived(character)
    _select_character(login(player), character)

    url = reverse("shops:stock_fragment", args=[club.slug, shop.pk])
    body = login(player).get(url, **HX).content.decode()

    assert "Aria is archived" in body
    assert "Buy" not in body.split("actions")[1].split("</td>")[0]


def test_stock_fragment_living_shows_buy(
    club, shop, always_open, stock, character, rich_character, player, login
):
    """Stock fragment shows Buy link for living character."""
    _select_character(login(player), character)

    url = reverse("shops:stock_fragment", args=[club.slug, shop.pk])
    body = login(player).get(url, **HX).content.decode()

    assert "Buy" in body
    assert "died on" not in body
    assert "is archived" not in body


# --- Club shop buy modal and page ---


def test_buy_modal_dead_hides_submit_and_quantity(
    club, shop, always_open, stock, character, rich_character, player, login
):
    """Buy modal hides 'Buy as' submit and quantity when character is dead."""
    _make_dead(character)
    _select_character(login(player), character)

    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    body = login(player).get(url, **HX).content.decode()

    assert "Aria died on" in body
    assert "Buy as Aria" not in body
    assert 'name="quantity"' not in body


def test_buy_modal_archived_hides_submit_and_quantity(
    club, shop, always_open, stock, character, rich_character, player, login
):
    """Buy modal hides submit and quantity when character is archived."""
    _make_archived(character)
    _select_character(login(player), character)

    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    body = login(player).get(url, **HX).content.decode()

    assert "Aria is archived" in body
    assert "Buy as Aria" not in body
    assert 'name="quantity"' not in body


def test_buy_page_dead_hides_submit(
    club, shop, always_open, stock, character, rich_character, player, login
):
    """Buy page (non-modal) hides submit when character is dead."""
    _make_dead(character)
    _select_character(login(player), character)

    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    body = login(player).get(url).content.decode()

    assert "Aria died on" in body
    # The buy form should not have a submit button
    assert "Buy as Aria" not in body


# --- Player stall detail page ---


def test_player_stall_detail_dead_buyer_shows_reason(
    club, character, item, other_character, other_player, login
):
    """Player stall detail shows reason instead of Buy when buyer is dead."""
    # Set up seller's shop
    record(character, "award", [Line(item=item, quantity=5)])
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=character, item=item, quantity=3)
    character.shop_open = True
    character.save()

    # Make buyer dead
    _make_dead(other_character)
    _select_character(login(other_player), other_character)

    url = reverse("shops:player_shop", args=[club.slug, character.pk])
    body = login(other_player).get(url).content.decode()

    assert "Borin died on" in body
    assert 'class="btn btn-sm btn-primary"' not in body


def test_player_stall_detail_living_buyer_shows_buy(
    club, character, item, other_character, other_player, login
):
    """Player stall detail shows Buy for living buyer."""
    record(character, "award", [Line(item=item, quantity=5)])
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=character, item=item, quantity=3)
    character.shop_open = True
    character.save()

    _select_character(login(other_player), other_character)

    url = reverse("shops:player_shop", args=[club.slug, character.pk])
    body = login(other_player).get(url).content.decode()

    assert "Buy" in body
    assert "died on" not in body
    assert "is archived" not in body


# --- Player stall buy modal and page ---


def test_player_shop_buy_modal_dead_hides_submit(
    club, character, item, other_character, other_player, login
):
    """Player shop buy modal hides 'Buy as' when buyer is dead."""
    record(character, "award", [Line(item=item, quantity=5)])
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=character, item=item, quantity=3)
    character.shop_open = True
    character.save()

    _make_dead(other_character)
    _select_character(login(other_player), other_character)

    url = reverse("shops:player_shop_buy", args=[club.slug, character.pk, item.pk])
    body = login(other_player).get(url, **HX).content.decode()

    assert "Borin died on" in body
    assert "Buy as Borin" not in body
    assert 'name="quantity"' not in body


def test_player_shop_buy_page_dead_hides_submit(
    club, character, item, other_character, other_player, login
):
    """Player shop buy page hides submit when buyer is dead."""
    record(character, "award", [Line(item=item, quantity=5)])
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=character, item=item, quantity=3)
    character.shop_open = True
    character.save()

    _make_dead(other_character)
    _select_character(login(other_player), other_character)

    url = reverse("shops:player_shop_buy", args=[club.slug, character.pk, item.pk])
    body = login(other_player).get(url).content.decode()

    assert "Borin died on" in body
    assert "Buy as Borin" not in body
