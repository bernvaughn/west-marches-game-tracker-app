"""Tests for U140: buy/spend buttons replaced by death reason."""

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from ledger.services import Line, record

pytestmark = [pytest.mark.django_db, pytest.mark.story("U140")]
HX = {"HTTP_HX_REQUEST": "true"}


def _select_character(client, character):
    """Set the selected character in session."""
    url = reverse("characters:select", args=[character.club.slug])
    client.post(url, {"character": character.pk})


@pytest.fixture
def logged_in_client(player):
    """A test client with the player logged in."""
    client = Client()
    client.force_login(player)
    return client


@pytest.fixture
def other_logged_in_client(other_player):
    """A test client with the other_player logged in."""
    client = Client()
    client.force_login(other_player)
    return client


# --- Club shop browse stock fragment ---


def test_stock_fragment_dead_selected_shows_reason(
    club, shop, always_open, stock, character, rich_character, logged_in_client
):
    """Stock fragment (htmx) shows reason instead of Buy when selected character is dead."""
    character.died_on = timezone.localdate()
    character.save(update_fields=["died_on"])
    _select_character(logged_in_client, character)

    url = reverse("shops:stock_fragment", args=[club.slug, shop.pk])
    body = logged_in_client.get(url, **HX).content.decode()

    assert "Aria died on" in body
    assert "Buy" not in body.split("actions")[1].split("</td>")[0]


def test_stock_fragment_archived_selected_shows_reason(
    club, shop, always_open, stock, character, rich_character, logged_in_client
):
    """Stock fragment shows reason when selected character is archived."""
    character.archived_at = timezone.now()
    character.save(update_fields=["archived_at"])
    _select_character(logged_in_client, character)

    url = reverse("shops:stock_fragment", args=[club.slug, shop.pk])
    body = logged_in_client.get(url, **HX).content.decode()

    assert "Aria is archived" in body
    assert "Buy" not in body.split("actions")[1].split("</td>")[0]


def test_stock_fragment_living_shows_buy(
    club, shop, always_open, stock, character, rich_character, logged_in_client
):
    """Stock fragment shows Buy link for living character."""
    _select_character(logged_in_client, character)

    url = reverse("shops:stock_fragment", args=[club.slug, shop.pk])
    body = logged_in_client.get(url, **HX).content.decode()

    assert "Buy" in body
    assert "died on" not in body
    assert "is archived" not in body


# --- Club shop buy modal and page ---


def test_buy_modal_dead_hides_submit_and_quantity(
    club, shop, always_open, stock, character, rich_character, logged_in_client
):
    """Buy modal hides 'Buy as' submit and quantity when character is dead."""
    character.died_on = timezone.localdate()
    character.save(update_fields=["died_on"])
    _select_character(logged_in_client, character)

    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    body = logged_in_client.get(url, **HX).content.decode()

    assert "Aria died on" in body
    assert "Buy as Aria" not in body
    assert 'name="quantity"' not in body


def test_buy_modal_archived_hides_submit_and_quantity(
    club, shop, always_open, stock, character, rich_character, logged_in_client
):
    """Buy modal hides submit and quantity when character is archived."""
    character.archived_at = timezone.now()
    character.save(update_fields=["archived_at"])
    _select_character(logged_in_client, character)

    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    body = logged_in_client.get(url, **HX).content.decode()

    assert "Aria is archived" in body
    assert "Buy as Aria" not in body
    assert 'name="quantity"' not in body


def test_buy_page_dead_hides_submit(
    club, shop, always_open, stock, character, rich_character, logged_in_client
):
    """Buy page (non-modal) hides submit when character is dead."""
    character.died_on = timezone.localdate()
    character.save(update_fields=["died_on"])
    _select_character(logged_in_client, character)

    url = reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])
    body = logged_in_client.get(url).content.decode()

    assert "Aria died on" in body
    # The buy form should not have a submit button
    assert "Buy as Aria" not in body


# --- Player stall detail page ---


def test_player_stall_detail_dead_buyer_shows_reason(
    club, character, item, other_character, other_player, other_logged_in_client
):
    """Player stall detail shows reason instead of Buy when buyer is dead."""
    # Set up seller's shop
    record(character, "award", [Line(item=item, quantity=5)])
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=character, item=item, quantity=3)
    character.shop_open = True
    character.save()

    # Make buyer dead
    other_character.died_on = timezone.localdate()
    other_character.save(update_fields=["died_on"])
    _select_character(other_logged_in_client, other_character)

    url = reverse("shops:player_shop", args=[club.slug, character.pk])
    body = other_logged_in_client.get(url).content.decode()

    assert "Borin died on" in body
    assert 'class="btn btn-sm btn-primary"' not in body


def test_player_stall_detail_living_buyer_shows_buy(
    club, character, item, other_character, other_player, other_logged_in_client
):
    """Player stall detail shows Buy for living buyer."""
    record(character, "award", [Line(item=item, quantity=5)])
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=character, item=item, quantity=3)
    character.shop_open = True
    character.save()

    _select_character(other_logged_in_client, other_character)

    url = reverse("shops:player_shop", args=[club.slug, character.pk])
    body = other_logged_in_client.get(url).content.decode()

    assert "Buy" in body
    assert "died on" not in body
    assert "is archived" not in body


# --- Player stall buy modal and page ---


def test_player_shop_buy_modal_dead_hides_submit(
    club, character, item, other_character, other_player, other_logged_in_client
):
    """Player shop buy modal hides 'Buy as' when buyer is dead."""
    record(character, "award", [Line(item=item, quantity=5)])
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=character, item=item, quantity=3)
    character.shop_open = True
    character.save()

    other_character.died_on = timezone.localdate()
    other_character.save(update_fields=["died_on"])
    _select_character(other_logged_in_client, other_character)

    url = reverse("shops:player_shop_buy", args=[club.slug, character.pk, item.pk])
    body = other_logged_in_client.get(url, **HX).content.decode()

    assert "Borin died on" in body
    assert "Buy as Borin" not in body
    assert 'name="quantity"' not in body


def test_player_shop_buy_page_dead_hides_submit(
    club, character, item, other_character, other_player, other_logged_in_client
):
    """Player stall buy page hides submit when buyer is dead."""
    record(character, "award", [Line(item=item, quantity=5)])
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=character, item=item, quantity=3)
    character.shop_open = True
    character.save()

    other_character.died_on = timezone.localdate()
    other_character.save(update_fields=["died_on"])
    _select_character(other_logged_in_client, other_character)

    url = reverse("shops:player_shop_buy", args=[club.slug, character.pk, item.pk])
    body = other_logged_in_client.get(url).content.decode()

    assert "Borin died on" in body
    assert "Buy as Borin" not in body
