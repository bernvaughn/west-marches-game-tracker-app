"""Guards: a dead or archived character cannot claim starting equipment."""

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership
from ledger.models import LedgerEntry
from player_characters.models import Character

pytestmark = [pytest.mark.django_db]


def claim_url(club, character):
    return reverse(
        "starting_equipment:claim",
        kwargs={"club_slug": club.slug, "character_pk": character.pk},
    )


def choices_url(club, character):
    return reverse(
        "starting_equipment:choices",
        kwargs={"club_slug": club.slug, "character_pk": character.pk},
    )


def reveal_url(club, character):
    return reverse(
        "characters:starting_reveal",
        kwargs={"club_slug": club.slug, "pk": character.pk},
    )


def flash_messages(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


def _kill(character, *, died_on=None, archived_at=None):
    character.died_on = died_on
    character.archived_at = archived_at
    character.save(update_fields=["died_on", "archived_at"])


def test_dead_claim_refused(club, login, player, character_with_class_bg, template):
    _kill(character_with_class_bg, died_on=timezone.localdate())
    c = login(player)
    r = c.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    assert r["HX-Refresh"] == "true"
    character_with_class_bg.refresh_from_db()
    assert character_with_class_bg.starting_equipment_claimed is False
    assert LedgerEntry.objects.filter(character=character_with_class_bg).count() == 0
    assert any("died on" in m for m in flash_messages(r))


def test_archived_claim_refused(club, login, player, character_with_class_bg, template):
    _kill(character_with_class_bg, archived_at=timezone.now())
    c = login(player)
    r = c.post(claim_url(club, character_with_class_bg), HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    assert r["HX-Refresh"] == "true"
    character_with_class_bg.refresh_from_db()
    assert character_with_class_bg.starting_equipment_claimed is False
    assert LedgerEntry.objects.filter(character=character_with_class_bg).count() == 0
    assert any("is archived" in m for m in flash_messages(r))


def test_dead_choices_view_refused(club, login, player, character_with_class_bg, template):
    _kill(character_with_class_bg, died_on=timezone.localdate())
    c = login(player)
    r = c.get(choices_url(club, character_with_class_bg))
    assert r.status_code == 302
    assert r.url == reverse(
        "characters:detail", kwargs={"club_slug": club.slug, "pk": character_with_class_bg.pk}
    )
    assert any("died on" in m for m in flash_messages(r))


def test_living_replacement_still_claims(
    club, login, player, character_with_class_bg, template, class_entry, bg_entry
):
    owner = Membership.objects.get(user=player, club=club)
    replacement = Character.objects.create(
        club=club,
        owner=owner,
        name="Replacement",
        char_class="Fighter",
        class_option=character_with_class_bg.class_option,
        background="Acolyte",
        background_option=character_with_class_bg.background_option,
        level=1,
    )
    c = login(player)
    r = c.post(claim_url(club, replacement), HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    assert r["HX-Refresh"] == "true"
    replacement.refresh_from_db()
    assert replacement.starting_equipment_claimed is True
    assert LedgerEntry.objects.filter(
        character=replacement, kind=LedgerEntry.Kind.AWARD, note="Starting equipment"
    ).exists()


def test_reveal_still_opens_for_dead_character(
    club, login, player, character_with_class_bg, template
):
    _kill(character_with_class_bg, died_on=timezone.localdate())
    character_with_class_bg.starting_equipment_claimed = True
    character_with_class_bg.save(update_fields=["died_on", "starting_equipment_claimed"])
    LedgerEntry.objects.create(
        character=character_with_class_bg,
        club=club,
        kind=LedgerEntry.Kind.AWARD,
        note="Starting equipment",
    )
    c = login(player)
    r = c.get(reveal_url(club, character_with_class_bg))
    assert r.status_code == 200
