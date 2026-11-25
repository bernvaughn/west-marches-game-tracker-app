"""Tests for PlayerNotice: creation, dismiss, pruning, and text content (U163)."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from items.models import Item
from player_characters.models import Character
from player_items.models import PlayerItem, PlayerNotice
from player_items.resolve import Target, resolve

pytestmark = [pytest.mark.story("U163"), pytest.mark.django_db]


# --- helpers -------------------------------------------------------------


def make_entry(club, character, name="Potion", quantity=1):
    return PlayerItem.objects.create(
        club=club, character=character, name=name, quantity=quantity, review="open"
    )


def other_character(club, other_player):
    owner = club.memberships.get(user=other_player)
    return Character.objects.create(club=club, owner=owner, name="Borin")


# --- notice text content -------------------------------------------------


def test_notice_names_old_and_new_item(club, character, club_admin):
    make_entry(club, character, "Potion", 2)
    item = Item.objects.create(club=club, name="Healing Potion", value_cp=0)
    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    resolve(club, entries, Target(item=item), club_admin, mode="promote")

    notice = PlayerNotice.objects.for_club(club).get()
    assert 'Item "Potion"' in notice.text
    assert 'to "Healing Potion"' in notice.text


def test_notice_includes_value_when_visible(club, character, club_admin):
    make_entry(club, character, "Potion", 2)
    item = Item.objects.create(club=club, name="Healing Potion", value_cp=5000)
    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    resolve(club, entries, Target(item=item), club_admin, mode="promote")

    notice = PlayerNotice.objects.for_club(club).get()
    assert "(value: 50 gp)" in notice.text


def test_notice_omits_value_when_not_visible(club, character, club_admin):
    make_entry(club, character, "Potion", 2)
    item = Item.objects.create(club=club, name="Healing Potion", value_cp=0)
    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    resolve(club, entries, Target(item=item), club_admin, mode="promote")

    notice = PlayerNotice.objects.for_club(club).get()
    assert "(value:" not in notice.text


# --- one notice per holder ----------------------------------------------


def test_one_notice_per_holder_merge(club, character, other_player, club_admin):
    character_b = other_character(club, other_player)
    make_entry(club, character, "Potion", 2)
    make_entry(club, character_b, "potion", 3)  # same name_key, other holder
    item = Item.objects.create(club=club, name="Healing Potion")
    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    resolve(club, entries, Target(item=item), club_admin, mode="merge")

    notices = PlayerNotice.objects.for_club(club).filter(kind="item_merged")
    assert notices.count() == 2  # one per holder
    assert set(notices.values_list("membership", flat=True)) == {
        character.owner_id,
        character_b.owner_id,
    }


def test_one_notice_per_holder_match(club, character, other_player, club_admin):
    character_b = other_character(club, other_player)
    make_entry(club, character, "Potion", 2)
    make_entry(club, character_b, "potion", 3)
    item = Item.objects.create(club=club, name="Healing Potion", value_cp=200)
    entries = PlayerItem.objects.for_club(club).filter(name_key="potion")
    resolve(club, entries, Target(item=item), club_admin, mode="match")

    notices = PlayerNotice.objects.for_club(club).filter(kind="item_matched")
    assert notices.count() == 2  # one per holder
    for notice in notices:
        assert "(value: 2 gp)" in notice.text


# --- pruning -------------------------------------------------------------


def test_prune_notices_deletes_older_than_30_days(club, player):
    owner = club.memberships.get(user=player)
    character = Character.objects.create(club=club, owner=owner, name="Aria")

    recent = PlayerNotice.objects.create(
        membership=owner,
        club=club,
        character=character,
        kind=PlayerNotice.Kind.ITEM_PROMOTED,
        text="Recent notice.",
    )
    old = PlayerNotice.objects.create(
        membership=owner,
        club=club,
        character=character,
        kind=PlayerNotice.Kind.ITEM_PROMOTED,
        text="Old notice.",
    )
    PlayerNotice.objects.filter(pk=old.pk).update(created=timezone.now() - timedelta(days=31))

    call_command("prune_notices")

    assert PlayerNotice.objects.filter(pk=recent.pk).exists()
    assert not PlayerNotice.objects.filter(pk=old.pk).exists()


def test_prune_notices_keeps_notices_under_30_days(club, player):
    owner = club.memberships.get(user=player)
    character = Character.objects.create(club=club, owner=owner, name="Aria")
    notice = PlayerNotice.objects.create(
        membership=owner,
        club=club,
        character=character,
        kind=PlayerNotice.Kind.ITEM_PROMOTED,
        text="Fresh notice.",
    )
    PlayerNotice.objects.filter(pk=notice.pk).update(
        created=timezone.now() - timedelta(days=29, hours=23)
    )

    call_command("prune_notices")

    assert PlayerNotice.objects.filter(pk=notice.pk).exists()


def test_prune_notices_logs_deleted_count(club, player, capsys):
    owner = club.memberships.get(user=player)
    character = Character.objects.create(club=club, owner=owner, name="Aria")
    for _ in range(2):
        notice = PlayerNotice.objects.create(
            membership=owner,
            club=club,
            character=character,
            kind=PlayerNotice.Kind.ITEM_PROMOTED,
            text="Old notice.",
        )
        PlayerNotice.objects.filter(pk=notice.pk).update(
            created=timezone.now() - timedelta(days=31)
        )

    call_command("prune_notices")

    assert "Pruned 2 notice(s)" in capsys.readouterr().out
