"""Tests for archived character markers on starting equipment approvals (U146)."""

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Message
from ledger.models import LedgerEntry
from starting_equipment.models import StartingEquipmentRequest

pytestmark = [pytest.mark.django_db]


def request_decide_url(club, pk, decision):
    return reverse(
        "starting_equipment:request_decide",
        kwargs={"club_slug": club.slug, "pk": pk, "decision": decision},
    )


def _archive(character):
    character.archived_at = timezone.now()
    character.save(update_fields=["archived_at"])


def _create_pending_request(club, character, item):
    """Create a PENDING StartingEquipmentRequest and its inbox message."""
    req = StartingEquipmentRequest.objects.create(
        club=club,
        character=character,
        item=item,
        quantity=1,
        status=StartingEquipmentRequest.Status.PENDING,
    )
    msg = Message.objects.create(
        club=club,
        sender=character.owner,
        character=character,
        body=f"{character.name} requests 1x {item.name} as starting equipment.",
        kind=Message.Kind.STARTING_REQUEST,
        status=Message.Status.OPEN,
    )
    req.message = msg
    req.save(update_fields=["message"])
    return req


def test_inbox_shows_archived_next_to_character(
    login, club, player, game_master, character_with_class_bg, magic_item
):
    """The inbox shows "Archived" next to the character for a starting_request
    message."""
    _archive(character_with_class_bg)
    _create_pending_request(club, character_with_class_bg, magic_item)

    page = (
        login(game_master).get(reverse("accounts:message_inbox", args=[club.slug])).content.decode()
    )
    assert "Archived" in page
    assert character_with_class_bg.name in page


def test_inbox_shows_living_character_without_marker(
    login, club, player, game_master, character_with_class_bg, magic_item
):
    """A living character shows no "Archived" marker in the inbox."""
    _create_pending_request(club, character_with_class_bg, magic_item)

    page = (
        login(game_master).get(reverse("accounts:message_inbox", args=[club.slug])).content.decode()
    )
    assert ">Archived<" not in page


def test_confirm_modal_shows_archived_badge(
    login, club, game_master, character_with_class_bg, magic_item
):
    """The confirm modal shows the "Archived" badge after the character name."""
    _archive(character_with_class_bg)
    req = _create_pending_request(club, character_with_class_bg, magic_item)

    url = reverse(
        "starting_equipment:request_decide_confirm",
        kwargs={"club_slug": club.slug, "pk": req.pk, "decision": "approve"},
    )
    page = login(game_master).get(url, HTTP_HX_REQUEST="true").content.decode()
    assert "Archived" in page
    assert character_with_class_bg.name in page


def test_gm_can_approve_archived_character_starting_request(
    login, club, game_master, character_with_class_bg, magic_item
):
    """GM can still approve a starting equipment request from an archived character."""
    _archive(character_with_class_bg)
    req = _create_pending_request(club, character_with_class_bg, magic_item)

    resp = login(game_master).post(
        request_decide_url(club, req.pk, "approve"), HTTP_HX_REQUEST="true"
    )
    assert resp.status_code == 204

    req.refresh_from_db()
    assert req.status == StartingEquipmentRequest.Status.APPROVED

    entry = LedgerEntry.objects.get(character=character_with_class_bg, kind=LedgerEntry.Kind.AWARD)
    assert entry.note == f"Starting equipment: {magic_item.name}"


def test_gm_can_decline_archived_character_starting_request(
    login, club, game_master, character_with_class_bg, magic_item
):
    """GM can still decline a starting equipment request from an archived character."""
    _archive(character_with_class_bg)
    req = _create_pending_request(club, character_with_class_bg, magic_item)

    resp = login(game_master).post(
        request_decide_url(club, req.pk, "decline"),
        {"decision_note": "Not appropriate"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204

    req.refresh_from_db()
    assert req.status == StartingEquipmentRequest.Status.DECLINED
