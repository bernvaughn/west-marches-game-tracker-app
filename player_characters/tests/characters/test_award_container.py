"""Award Loot preview, and bulk award and adjust grant a container unopened (slice D2)."""

import pytest
from django.urls import reverse

from items.models import ContainerOpening, Item
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import available_items

pytestmark = [pytest.mark.django_db, pytest.mark.story("D2")]


def _assert_unopened(character, container, qty):
    have = available_items(character)
    assert have[container.pk] == qty
    assert not LedgerEntry.objects.filter(character=character, kind="opened").exists()
    assert not ContainerOpening.objects.exists()
    contents = Item.objects.filter(container_option_uses__slot__container=container).distinct()
    for item in contents:
        assert have.get(item.pk, 0) == 0
    lines = LedgerLine.objects.filter(entry__character=character, item=container)
    assert [ln.quantity for ln in lines] == [qty]


def _bulk_payload(character, item, qty):
    pk = character.pk
    return {
        "characters": [pk],
        "note": "Party award",
        "date": "2024-01-01",
        f"coins_{pk}": "",
        f"items_{pk}-TOTAL_FORMS": "1",
        f"items_{pk}-INITIAL_FORMS": "0",
        f"items_{pk}-MIN_NUM_FORMS": "0",
        f"items_{pk}-MAX_NUM_FORMS": "1",
        f"items_{pk}-0-item": str(item.pk),
        f"items_{pk}-0-item_id": str(item.pk),
        f"items_{pk}-0-quantity": str(qty),
        f"items_{pk}-0-value_override": "",
    }


def test_bulk_award_page_has_preview_template_per_container(
    login, club, game_master, character, diplomats_pack, item
):
    body = login(game_master).get(reverse("characters:bulk_award", args=[club.slug]))
    body = body.content.decode()
    assert f'<template id="loot-preview-{diplomats_pack.pk}">' in body
    assert f'id="loot-preview-{item.pk}"' not in body
    # Bulk award is GM-only, so the preview shows real names.
    assert "Fine clothes" in body
    assert "Sealed letter" in body
    # One preview slot under each item row.
    assert body.count('class="col-12 wm-loot-slot"') == 3


def test_bulk_award_grants_container_unopened(login, club, game_master, character, diplomats_pack):
    resp = login(game_master).post(
        reverse("characters:bulk_award", args=[club.slug]),
        _bulk_payload(character, diplomats_pack, 2),
    )
    assert resp.status_code == 302
    _assert_unopened(character, diplomats_pack, 2)


def test_adjust_grants_container_unopened(login, club, game_master, character, diplomats_pack):
    url = reverse("characters:adjust", kwargs={"club_slug": club.slug, "pk": character.pk})
    data = {
        "note": "Found a pack",
        "date": "2025-01-02",
        "coins_cp": "",
        "direction": "give",
        "items-TOTAL_FORMS": "3",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "3",
        "items-0-item": diplomats_pack.pk,
        "items-0-quantity": "1",
    }
    resp = login(game_master).post(url, data)
    assert resp.status_code == 302
    _assert_unopened(character, diplomats_pack, 1)
