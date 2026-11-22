"""Tests for death and archive guards on club and stall shops (U140, U141, U144)."""

from datetime import date

import pytest
from django.urls import reverse
from django.utils import timezone

from ledger.models import LedgerEntry
from ledger.services import Line, record
from player_characters.player_shop import buy_from
from shops.buying import buy as buy_service
from shops.selling import sell as sell_service
from shops.selling import sell_many

pytestmark = [pytest.mark.django_db, pytest.mark.story("U140-U141")]


def buy_url(club, shop, stock):
    return reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])


def sell_url(club, shop, item):
    return reverse("shops:sell_item", args=[club.slug, shop.id, item.id])


def sell_junk_url(club, shop):
    return reverse("shops:sell_junk", args=[club.slug, shop.pk])


def stall_url(club, seller):
    return reverse("shops:player_shop", args=[club.slug, seller.pk])


def stall_buy_url(club, seller, item):
    return reverse("shops:player_shop_buy", args=[club.slug, seller.pk, item.pk])


def _mark_dead(character):
    character.died_on = date(2026, 11, 14)
    character.save(update_fields=["died_on", "death_note"])
    character.refresh_from_db()


def _archive(character):
    character.archived_at = timezone.now()
    character.shop_open = False
    character.save(update_fields=["archived_at", "shop_open"])
    character.refresh_from_db()


def _fund(character, amount=1000):
    record(character, "award", [Line(coins=amount)])
    return character


def _award_item(character, item, quantity=3):
    record(character, "award", [Line(item=item, quantity=quantity)])
    return character


# ---------------------------------------------------------------- dead buyer


def test_dead_buyer_service_refused(club, shop, always_open, stock, character, player):
    _mark_dead(character)
    with pytest.raises(Exception) as exc:
        buy_service(character, stock, actor=player)
    assert "died on" in str(exc.value)


def test_dead_buyer_post_refused(club, shop, always_open, stock, character, player, login):
    _mark_dead(character)
    before = LedgerEntry.objects.count()
    stock_qty = stock.quantity
    client = login(player)
    resp = client.post(buy_url(club, shop, stock), {"character": character.pk, "quantity": 1})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "died on" in body
    assert LedgerEntry.objects.count() == before
    stock.refresh_from_db()
    assert stock.quantity == stock_qty


def test_archived_buyer_service_refused(club, shop, always_open, stock, character, player):
    _archive(character)
    with pytest.raises(Exception) as exc:
        buy_service(character, stock, actor=player)
    assert "is archived" in str(exc.value)


def test_archived_buyer_post_refused(club, shop, always_open, stock, character, player, login):
    _archive(character)
    before = LedgerEntry.objects.count()
    client = login(player)
    resp = client.post(buy_url(club, shop, stock), {"character": character.pk, "quantity": 1})
    assert resp.status_code == 200
    assert "is archived" in resp.content.decode()
    assert LedgerEntry.objects.count() == before


def test_dead_buyer_stall_service_refused(club, character, item, other_character, player):
    _mark_dead(other_character)
    character.shop_open = True
    character.save()
    _award_item(character, item, 1)
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=character, item=item, quantity=1)
    _fund(other_character)
    with pytest.raises(Exception) as exc:
        buy_from(other_character, character, item, 1, actor=player)
    assert "died on" in str(exc.value)


def test_dead_buyer_stall_post_refused(club, character, item, other_character, player, login):
    _mark_dead(other_character)
    seller = character
    seller.shop_open = True
    seller.save()
    _award_item(seller, item, 1)
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=seller, item=item, quantity=1)
    _fund(other_character)
    client = login(other_character.owner.user)
    resp = client.post(stall_buy_url(club, seller, item), {"quantity": 1})
    assert resp.status_code == 200
    assert "died on" in resp.content.decode()


def test_archived_buyer_stall_post_refused(club, character, item, other_character, player, login):
    _archive(other_character)
    seller = character
    seller.shop_open = True
    seller.save()
    _award_item(seller, item, 1)
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=seller, item=item, quantity=1)
    _fund(other_character)
    client = login(other_character.owner.user)
    resp = client.post(stall_buy_url(club, seller, item), {"quantity": 1})
    assert resp.status_code == 200
    assert "is archived" in resp.content.decode()


# ------------------------------------------------- dead character can still sell


def test_dead_can_sell_service(club, shop, always_open, character, item, player):
    _mark_dead(character)
    _award_item(character, item, 3)
    entry = sell_service(character, shop, item, 2, actor=player)
    assert entry.kind == "sale"


def test_dead_can_sell_post(club, shop, always_open, character, item, player, login):
    _mark_dead(character)
    _award_item(character, item, 3)
    client = login(player)
    resp = client.post(
        sell_url(club, shop, item),
        {"quantity": 2, "confirmed": "1"},
    )
    assert resp.status_code == 302
    assert LedgerEntry.objects.filter(kind="sale").count() == 1


def test_dead_can_sell_many(club, shop, always_open, character, item, player):
    _mark_dead(character)
    _award_item(character, item, 3)
    entries = sell_many(character, shop, [(item, 2)], actor=player)
    assert len(entries) == 1


def test_dead_can_set_junk(club, character, item, player):
    _mark_dead(character)
    _award_item(character, item, 3)
    from player_characters.junk import set_junk

    mark = set_junk(character, item, 2, player)
    assert mark is not None
    assert mark.quantity == 2


def test_dead_can_post_sell_junk(club, shop, always_open, character, item, player, login):
    _mark_dead(character)
    _award_item(character, item, 3)
    from player_characters.junk import set_junk

    set_junk(character, item, 2, player)
    client = login(player)
    resp = client.post(
        sell_junk_url(club, shop),
        {"item": [item.pk], f"qty_{item.pk}": "1"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204


# ------------------------------------------------- dead seller's stall pays the dead seller


def test_dead_seller_stall_pays_seller(club, character, item, other_character, player, login):
    _mark_dead(character)
    _award_item(character, item, 3)
    character.shop_open = True
    character.save()
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=character, item=item, quantity=3)
    _fund(other_character, 1000)
    before = LedgerEntry.objects.filter(character=character, kind="player_shop").count()
    buy_from(other_character, character, item, 1, actor=player)
    after = LedgerEntry.objects.filter(character=character, kind="player_shop").count()
    assert after == before + 1
    entry = (
        LedgerEntry.objects.filter(character=character, kind="player_shop").order_by("-pk").first()
    )
    assert any(line.coins > 0 for line in entry.lines.all())


# ------------------------------------------------- archived seller cannot sell


def test_archived_cannot_sell_service(club, shop, always_open, character, item, player):
    _archive(character)
    _award_item(character, item, 3)
    with pytest.raises(Exception) as exc:
        sell_service(character, shop, item, 1, actor=player)
    assert "is archived" in str(exc.value)


def test_archived_cannot_sell_many(club, shop, always_open, character, item, player):
    _archive(character)
    _award_item(character, item, 3)
    with pytest.raises(Exception) as exc:
        sell_many(character, shop, [(item, 1)], actor=player)
    assert "is archived" in str(exc.value)


def test_archived_cannot_set_junk(club, character, item, player):
    _archive(character)
    _award_item(character, item, 3)
    from player_characters.junk import set_junk

    with pytest.raises(Exception) as exc:
        set_junk(character, item, 1, player)
    assert "is archived" in str(exc.value)


def test_archived_seller_buy_from_refused(club, character, item, other_character, player):
    _archive(character)
    character.shop_open = True
    character.save()
    _award_item(character, item, 1)
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=character, item=item, quantity=1)
    _fund(other_character, 1000)
    with pytest.raises(Exception) as exc:
        buy_from(other_character, character, item, 1, actor=player)
    assert "is archived" in str(exc.value)


def test_archived_cannot_post_sell(club, shop, always_open, character, item, player, login):
    _archive(character)
    _award_item(character, item, 3)
    before = LedgerEntry.objects.count()
    client = login(player)
    resp = client.post(
        sell_url(club, shop, item),
        {"quantity": 1, "confirmed": "1"},
    )
    assert resp.status_code == 302
    assert LedgerEntry.objects.count() == before


def test_archived_cannot_set_junk_service(club, character, item, player):
    _archive(character)
    _award_item(character, item, 3)
    from player_characters.junk import set_junk

    with pytest.raises(Exception) as exc:
        set_junk(character, item, 1, player)
    assert "is archived" in str(exc.value)


def test_archived_cannot_post_sell_junk(club, shop, always_open, character, item, player, login):
    _archive(character)
    _award_item(character, item, 3)
    before = LedgerEntry.objects.count()
    client = login(player)
    resp = client.post(
        sell_junk_url(club, shop),
        {"item": [item.pk], f"qty_{item.pk}": "1"},
    )
    assert resp.status_code == 200
    assert LedgerEntry.objects.count() == before


# ------------------------------------------------- GM adjustment on dead character still works


def test_gm_adjust_on_dead_character(club, character, player, game_master):
    _mark_dead(character)
    before = LedgerEntry.objects.count()
    record(
        character,
        "adjustment",
        [Line(coins=100)],
        note="GM aid",
        actor=game_master,
    )
    assert LedgerEntry.objects.count() == before + 1


# ------------------------------------------------- refusal text


def test_buy_block_reason_text(character):
    _mark_dead(character)
    from player_characters.life import buy_block_reason

    assert buy_block_reason(character) == "Aria died on 2026-11-14"


def test_sell_block_reason_archived_text(character):
    _archive(character)
    from player_characters.life import sell_block_reason

    assert sell_block_reason(character) == "Aria is archived"
