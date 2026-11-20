"""Loot preview on starting equipment surfaces, and container grants (slice D2)."""

import pytest
from django.urls import reverse

from items.models import ContainerOpening, Item
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import available_items
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassLine,
    StartingEquipmentRequest,
)
from starting_equipment.services import apply_starting_equipment

pytestmark = [pytest.mark.django_db, pytest.mark.story("D2")]


def _assert_unopened(character, container, qty):
    have = available_items(character)
    assert have[container.pk] == qty
    assert not LedgerEntry.objects.filter(character=character, kind="opened").exists()
    assert not ContainerOpening.objects.exists()
    contents = Item.objects.filter(container_option_uses__slot__container=container).distinct()
    for item in contents:
        assert have.get(item.pk, 0) == 0


@pytest.fixture
def pack_class_line(class_entry, diplomats_pack):
    return StartingEquipmentClassLine.objects.create(
        class_entry=class_entry, item=diplomats_pack, quantity=1
    )


@pytest.fixture
def pack_bg_line(bg_entry, diplomats_pack):
    return StartingEquipmentBackgroundLine.objects.create(
        background_entry=bg_entry, item=diplomats_pack, quantity=2
    )


@pytest.fixture
def pack_option(template, diplomats_pack):
    return MagicItemStartingOption.objects.create(
        template=template, item=diplomats_pack, max_per_character=1
    )


def _get(client, name, **kwargs):
    resp = client.get(reverse(f"starting_equipment:{name}", kwargs=kwargs), HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    return resp.content.decode()


def _assert_full_preview(body):
    assert "Fine clothes" in body
    assert "One of" in body
    assert "Sealed letter" in body


# --- Admin surfaces: the viewer is a club admin, so real names show. ---


def test_template_detail_shows_preview(
    login, club, club_admin, template, pack_class_line, pack_bg_line, pack_option
):
    body = _get(login(club_admin), "template_detail", club_slug=club.slug, pk=template.pk)
    assert body.count('wm-loot-preview"') == 3
    _assert_full_preview(body)


@pytest.mark.parametrize("name", ["class_entry_list", "background_entry_list", "magic_option_list"])
def test_entry_lists_show_preview(
    login, club, club_admin, template, pack_class_line, pack_bg_line, pack_option, name
):
    body = _get(login(club_admin), name, club_slug=club.slug, template_pk=template.pk)
    _assert_full_preview(body)


def test_plain_line_has_no_preview(login, club, club_admin, template, class_line):
    body = _get(login(club_admin), "template_detail", club_slug=club.slug, pk=template.pk)
    assert "Longsword" in body
    assert "wm-loot-preview" not in body


# --- Request modal: the owner is a player, so unknown rows are masked. ---


def test_request_modal_masks_unknown_for_player(
    login, club, player, character_with_class_bg, pack_option
):
    body = _get(
        login(player), "request_new", club_slug=club.slug, character_pk=character_with_class_bg.pk
    )
    assert f'<template id="loot-preview-{pack_option.item.pk}">' in body
    assert "Fine clothes" in body
    assert "???" in body
    assert "Sealed letter" not in body


def test_request_modal_shows_unknown_for_gm(
    login, club, game_master, character_with_class_bg, pack_option
):
    body = _get(
        login(game_master),
        "request_new",
        club_slug=club.slug,
        character_pk=character_with_class_bg.pk,
    )
    assert "Sealed letter" in body


def test_request_modal_plain_option_has_no_template(
    login, club, player, character_with_class_bg, magic_option
):
    body = _get(
        login(player), "request_new", club_slug=club.slug, character_pk=character_with_class_bg.pk
    )
    assert "<template" not in body


# --- Decide confirm: GM view. ---


@pytest.fixture
def pack_request(character_with_class_bg, diplomats_pack):
    return StartingEquipmentRequest.objects.create(
        club=character_with_class_bg.club,
        character=character_with_class_bg,
        item=diplomats_pack,
        quantity=1,
        status=StartingEquipmentRequest.Status.PENDING,
    )


def test_decide_confirm_shows_preview(login, club, game_master, pack_request):
    body = _get(
        login(game_master),
        "request_decide_confirm",
        club_slug=club.slug,
        pk=pack_request.pk,
        decision="approve",
    )
    _assert_full_preview(body)


# --- Grants: each path gives the container unopened. ---


def test_apply_starting_equipment_grants_container_unopened(
    character_with_class_bg, template, pack_class_line, pack_bg_line, diplomats_pack, club_admin
):
    entry = apply_starting_equipment(character_with_class_bg, template, actor=club_admin)
    assert entry is not None
    lines = LedgerLine.objects.filter(entry=entry, item=diplomats_pack)
    assert sorted(ln.quantity for ln in lines) == [1, 2]
    _assert_unopened(character_with_class_bg, diplomats_pack, 3)


def test_request_approve_grants_container_unopened(
    login, club, game_master, pack_request, diplomats_pack
):
    url = reverse(
        "starting_equipment:request_decide",
        kwargs={"club_slug": club.slug, "pk": pack_request.pk, "decision": "approve"},
    )
    resp = login(game_master).post(url, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    character = pack_request.character
    lines = LedgerLine.objects.filter(entry__character=character, item=diplomats_pack)
    assert [ln.quantity for ln in lines] == [1]
    _assert_unopened(character, diplomats_pack, 1)
