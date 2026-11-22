"""Tests for character life state (death, archive, guards)."""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership
from ledger.models import AppendOnlyError
from player_characters.life import (
    LifeError,
    archive,
    buy_block_reason,
    can_act,
    can_buy,
    can_sell,
    mark_dead,
    require_can_buy,
    require_can_sell,
    sell_block_reason,
    unarchive,
    undo_death,
)
from player_characters.models import Character, CharacterStatusChange

pytestmark = pytest.mark.story("U138-U147")


# --- Fields and properties ---


def test_character_defaults(character):
    """New characters have empty death/archive fields."""
    assert character.died_on is None
    assert character.death_note == ""
    assert character.archived_at is None
    assert character.is_dead is False
    assert character.is_archived is False
    assert character.is_active is True


def test_is_dead_and_is_archived_independent(character):
    """Dead and archived are independent states."""
    # Neither
    assert not character.is_dead
    assert not character.is_archived

    # Dead only
    character.died_on = timezone.localdate()
    character.save()
    character.refresh_from_db()
    assert character.is_dead
    assert not character.is_archived

    # Archived only (reset death)
    character.died_on = None
    character.archived_at = timezone.now()
    character.save()
    character.refresh_from_db()
    assert not character.is_dead
    assert character.is_archived

    # Both
    character.died_on = timezone.localdate()
    character.save()
    character.refresh_from_db()
    assert character.is_dead
    assert character.is_archived


# --- Queryset methods ---


def test_queryset_not_archived(character, player, club):
    """not_archived() filters out archived characters."""
    owner = Membership.objects.get(user=player, club=club)
    c2 = Character.objects.create(club=club, owner=owner, name="Archived")
    c2.archived_at = timezone.now()
    c2.save()

    qs = Character.objects.not_archived()
    assert character in qs
    assert c2 not in qs


def test_queryset_living_and_dead(character, player, club):
    """living() and dead() filter by died_on, ignore archive."""
    owner = Membership.objects.get(user=player, club=club)
    c2 = Character.objects.create(club=club, owner=owner, name="Dead")
    c2.died_on = timezone.localdate()
    c2.save()

    c3 = Character.objects.create(club=club, owner=owner, name="DeadArchived")
    c3.died_on = timezone.localdate()
    c3.archived_at = timezone.now()
    c3.save()

    living = Character.objects.living()
    dead = Character.objects.dead()

    assert character in living
    assert c2 in dead
    assert c3 in dead


def test_lookup_finds_archived_by_pk(character):
    """Character.objects.get(pk=...) still finds archived rows."""
    character.archived_at = timezone.now()
    character.save()
    found = Character.objects.get(pk=character.pk)
    assert found.pk == character.pk


def test_for_club_not_archived_chains(character, club, player):
    """for_club().not_archived() chains correctly."""
    Membership.objects.get(user=player, club=club)
    other_club = club  # same club for this test
    qs = Character.objects.for_club(other_club).not_archived()
    assert character in qs


# --- Guards ---


def test_can_buy_dead(character):
    """Dead characters cannot buy."""
    character.died_on = timezone.localdate()
    character.save()
    assert can_buy(character) is False


def test_can_buy_archived(character):
    """Archived characters cannot buy."""
    character.archived_at = timezone.now()
    character.save()
    assert can_buy(character) is False


def test_can_buy_living_not_archived(character):
    """Living, not archived characters can buy."""
    assert can_buy(character) is True


def test_can_sell_dead(character):
    """Dead characters can sell."""
    character.died_on = timezone.localdate()
    character.save()
    assert can_sell(character) is True


def test_can_sell_archived(character):
    """Archived characters cannot sell."""
    character.archived_at = timezone.now()
    character.save()
    assert can_sell(character) is False


def test_can_sell_living_not_archived(character):
    """Living, not archived characters can sell."""
    assert can_sell(character) is True


def test_can_act_alias(character):
    """can_act has same behavior as can_buy."""
    from player_characters.life import can_buy

    # can_act should have same behavior as can_buy
    assert can_act(character) == can_buy(character)
    # Test with dead character
    character.died_on = timezone.localdate()
    character.save()
    assert can_act(character) == can_buy(character) is False
    # Test with archived character
    character.died_on = None
    character.archived_at = timezone.now()
    character.save()
    assert can_act(character) == can_buy(character) is False
    # Test with living, not archived
    character.archived_at = None
    character.save()
    assert can_act(character) == can_buy(character) is True


def test_buy_block_reason_dead(character):
    """buy_block_reason returns death message for dead character."""
    character.died_on = date(2026, 11, 14)
    character.save()
    reason = buy_block_reason(character)
    assert reason == "Aria died on 2026-11-14"


def test_buy_block_reason_archived(character):
    """buy_block_reason returns archived message for archived character."""
    character.archived_at = timezone.now()
    character.save()
    reason = buy_block_reason(character)
    assert reason == "Aria is archived"


def test_buy_block_reason_archived_wins_over_dead(character):
    """Archived wins over dead in buy_block_reason."""
    character.died_on = date(2026, 11, 14)
    character.archived_at = timezone.now()
    character.save()
    reason = buy_block_reason(character)
    assert reason == "Aria is archived"


def test_buy_block_reason_none_returns_empty():
    """buy_block_reason returns empty string for None character."""
    assert buy_block_reason(None) == ""


def test_sell_block_reason_archived(character):
    """sell_block_reason returns archived message for archived character."""
    character.archived_at = timezone.now()
    character.save()
    reason = sell_block_reason(character)
    assert reason == "Aria is archived"


def test_sell_block_reason_dead_returns_empty(character):
    """sell_block_reason returns empty for dead (not archived) character."""
    character.died_on = timezone.localdate()
    character.save()
    reason = sell_block_reason(character)
    assert reason == ""


def test_sell_block_reason_none_returns_empty():
    """sell_block_reason returns empty string for None character."""
    assert sell_block_reason(None) == ""


def test_require_can_buy_raises_on_dead(character):
    """require_can_buy raises LifeError for dead character."""
    character.died_on = timezone.localdate()
    character.save()
    with pytest.raises(LifeError) as exc:
        require_can_buy(character)
    assert "died on" in str(exc.value)


def test_require_can_buy_raises_on_archived(character):
    """require_can_buy raises LifeError for archived character."""
    character.archived_at = timezone.now()
    character.save()
    with pytest.raises(LifeError) as exc:
        require_can_buy(character)
    assert "archived" in str(exc.value)


def test_require_can_sell_raises_on_archived(character):
    """require_can_sell raises LifeError for archived character."""
    character.archived_at = timezone.now()
    character.save()
    with pytest.raises(LifeError) as exc:
        require_can_sell(character)
    assert "archived" in str(exc.value)


def test_require_can_sell_allows_dead(character):
    """require_can_sell does not raise for dead character."""
    character.died_on = timezone.localdate()
    character.save()
    require_can_sell(character)  # should not raise


# --- Services ---


def test_mark_dead_writes_history(character, player):
    """mark_dead writes one CharacterStatusChange row."""
    membership = Membership.objects.get(user=player, club=character.club)
    history = mark_dead(character, by=membership)

    character.refresh_from_db()

    assert history.kind == CharacterStatusChange.Kind.DIED
    assert history.character == character
    assert history.by == membership
    assert history.date == character.died_on
    assert history.note == ""
    assert character.is_dead


def test_mark_dead_defaults_to_today(character, player):
    """mark_dead defaults died_on to today."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership)
    character.refresh_from_db()
    assert character.died_on == timezone.localdate()


def test_mark_dead_refuses_future_date(character, player):
    """mark_dead refuses a future death date."""
    membership = Membership.objects.get(user=player, club=character.club)
    future = timezone.localdate() + timedelta(days=1)
    with pytest.raises(LifeError) as exc:
        mark_dead(character, by=membership, died_on=future)
    assert "future" in str(exc.value).lower()


def test_mark_dead_refuses_already_dead(character, player):
    """mark_dead refuses if already dead."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership)
    with pytest.raises(LifeError) as exc:
        mark_dead(character, by=membership)
    assert "already dead" in str(exc.value).lower()


def test_undo_death_clears_fields_and_writes_history(character, player):
    """undo_death clears died_on and death_note, writes revived row."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership, note="Original death note")
    character.refresh_from_db()

    history = undo_death(character, by=membership, note="Revived!")

    assert history.kind == CharacterStatusChange.Kind.REVIVED
    assert history.note == "Revived!"

    character.refresh_from_db()
    assert character.died_on is None
    assert character.death_note == ""
    assert character.is_dead is False


def test_undo_death_refuses_not_dead(character, player):
    """undo_death refuses if character is not dead."""
    membership = Membership.objects.get(user=player, club=character.club)
    with pytest.raises(LifeError) as exc:
        undo_death(character, by=membership)
    assert "not dead" in str(exc.value).lower()


def test_archive_closes_stall_and_writes_history(character, player):
    """archive sets archived_at and shop_open=False, writes archived row."""
    membership = Membership.objects.get(user=player, club=character.club)
    character.shop_open = True
    character.save()

    history = archive(character, by=membership)

    assert history.kind == CharacterStatusChange.Kind.ARCHIVED
    character.refresh_from_db()
    assert character.is_archived
    assert character.shop_open is False


def test_archive_refuses_already_archived(character, player):
    """archive refuses if already archived."""
    membership = Membership.objects.get(user=player, club=character.club)
    archive(character, by=membership)
    with pytest.raises(LifeError) as exc:
        archive(character, by=membership)
    assert "already archived" in str(exc.value).lower()


def test_unarchive_keeps_stall_closed_and_dead_state(character, player):
    """unarchive clears archived_at, leaves shop_open and died_on alone."""
    membership = Membership.objects.get(user=player, club=character.club)
    character.died_on = timezone.localdate()
    character.shop_open = True
    character.save()
    archive(character, by=membership)
    character.refresh_from_db()

    history = unarchive(character, by=membership)

    assert history.kind == CharacterStatusChange.Kind.UNARCHIVED
    character.refresh_from_db()
    assert character.is_archived is False
    assert character.shop_open is False  # stays closed
    assert character.is_dead is True  # stays dead


def test_unarchive_refuses_not_archived(character, player):
    """unarchive refuses if not archived."""
    membership = Membership.objects.get(user=player, club=character.club)
    with pytest.raises(LifeError) as exc:
        unarchive(character, by=membership)
    assert "not archived" in str(exc.value).lower()


def test_service_fails_write_no_history_row(character, player):
    """A failed service call writes no history row."""
    membership = Membership.objects.get(user=player, club=character.club)
    # First, archive
    archive(character, by=membership)
    count_after_archive = CharacterStatusChange.objects.count()

    # Try to archive again (should fail)
    with pytest.raises(LifeError):
        archive(character, by=membership)

    # Count should be unchanged
    assert CharacterStatusChange.objects.count() == count_after_archive


# --- History append-only ---


def test_history_save_raises(character, player):
    """Saving an existing CharacterStatusChange row raises AppendOnlyError."""
    membership = Membership.objects.get(user=player, club=character.club)
    history = CharacterStatusChange.objects.create(
        character=character,
        kind=CharacterStatusChange.Kind.DIED,
        by=membership,
        at=timezone.now(),
        note="test",
        date=timezone.localdate(),
    )
    history.note = "changed"
    with pytest.raises(AppendOnlyError):
        history.save()


def test_history_delete_raises(character, player):
    """Deleting a CharacterStatusChange row raises AppendOnlyError."""
    membership = Membership.objects.get(user=player, club=character.club)
    history = CharacterStatusChange.objects.create(
        character=character,
        kind=CharacterStatusChange.Kind.DIED,
        by=membership,
        at=timezone.now(),
        note="test",
        date=timezone.localdate(),
    )
    with pytest.raises(AppendOnlyError):
        history.delete()


def test_history_queryset_update_raises(character, player):
    """Queryset update on CharacterStatusChange raises AppendOnlyError."""
    membership = Membership.objects.get(user=player, club=character.club)
    CharacterStatusChange.objects.create(
        character=character,
        kind=CharacterStatusChange.Kind.DIED,
        by=membership,
        at=timezone.now(),
        note="test",
        date=timezone.localdate(),
    )
    with pytest.raises(AppendOnlyError):
        CharacterStatusChange.objects.update(note="changed")


def test_history_queryset_delete_raises(character, player):
    """Queryset delete on CharacterStatusChange raises AppendOnlyError."""
    membership = Membership.objects.get(user=player, club=character.club)
    CharacterStatusChange.objects.create(
        character=character,
        kind=CharacterStatusChange.Kind.DIED,
        by=membership,
        at=timezone.now(),
        note="test",
        date=timezone.localdate(),
    )
    with pytest.raises(AppendOnlyError):
        CharacterStatusChange.objects.all().delete()


# --- URLs ---


def test_url_death_reverses(club):
    """death URL reverses."""
    url = reverse("characters:death", args=[club.slug, 1])
    assert url == f"/c/{club.slug}/characters/1/death/"


def test_url_death_undo_reverses(club):
    """death_undo URL reverses."""
    url = reverse("characters:death_undo", args=[club.slug, 1])
    assert url == f"/c/{club.slug}/characters/1/death/undo/"


def test_url_archive_reverses(club):
    """archive URL reverses."""
    url = reverse("characters:archive", args=[club.slug, 1])
    assert url == f"/c/{club.slug}/characters/1/archive/"


def test_url_unarchive_reverses(club):
    """unarchive URL reverses."""
    url = reverse("characters:unarchive", args=[club.slug, 1])
    assert url == f"/c/{club.slug}/characters/1/unarchive/"


def test_url_archived_reverses(club):
    """archived URL reverses."""
    url = reverse("characters:archived", args=[club.slug])
    assert url == f"/c/{club.slug}/characters/archived/"


def test_url_fallen_reverses(club):
    """fallen URL reverses."""
    url = reverse("characters:fallen", args=[club.slug])
    assert url == f"/c/{club.slug}/characters/fallen/"


def test_stub_views_return_404(login, player, character):
    """Remaining stub views (archived, fallen) return 404 for logged-in member.
    Death, undo, archive and unarchive are now implemented (C2, U144)."""
    client = login(player)
    urls = [
        reverse("characters:archived", args=[character.club.slug]),
        reverse("characters:fallen", args=[character.club.slug]),
    ]
        reverse("characters:archived", args=[character.club.slug]),
        reverse("characters:fallen", args=[character.club.slug]),
    ]
    for url in urls:
        assert client.get(url).status_code == 404
        assert client.post(url).status_code == 404


# --- Pages still render ---


def test_detail_renders_200(login, player, character):
    """Detail page renders 200 with new includes."""
    client = login(player)
    url = reverse("characters:detail", args=[character.club.slug, character.pk])
    resp = client.get(url)
    assert resp.status_code == 200


def test_index_renders_200(login, club_admin, club):
    """Index page renders 200 with new includes."""
    client = login(club_admin)
    url = reverse("characters:index", args=[club.slug])
    resp = client.get(url)
    assert resp.status_code == 200


def test_directory_renders_200(login, player, club):
    """Directory page renders 200 with new includes."""
    client = login(player)
    url = reverse("characters:directory", args=[club.slug])
    resp = client.get(url)
    assert resp.status_code == 200


def test_print_items_renders_200(login, player, character):
    """Print items page renders 200 with new includes."""
    client = login(player)
    url = reverse("characters:print_items", args=[character.club.slug, character.pk])
    resp = client.get(url)
    assert resp.status_code == 200


# --- Template filters ---


def test_buy_block_reason_filter_renders(character):
    """The filter is named buy_block_reason in templates."""
    from django.template import Context, Template

    character.name = "Aria Windrunner"
    character.died_on = date(2026, 11, 14)
    tpl = Template("{% load life_tags %}{{ c|buy_block_reason }}")
    assert tpl.render(Context({"c": character})) == "Aria Windrunner died on 2026-11-14"
    assert tpl.render(Context({"c": None})) == ""


def test_is_dead_filter_renders(character):
    """The is_dead filter works through a template."""
    from django.template import Context, Template

    tpl = Template("{% load life_tags %}{% if c|is_dead %}dead{% else %}alive{% endif %}")
    assert tpl.render(Context({"c": character})) == "alive"
    character.died_on = date(2026, 11, 14)
    assert tpl.render(Context({"c": character})) == "dead"
    assert tpl.render(Context({"c": None})) == "alive"


# --- Services refresh the passed instance ---


def test_mark_dead_refreshes_passed_instance(character, player):
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership, note="Dragon")
    assert character.is_dead
    assert character.died_on == timezone.localdate()
    assert character.death_note == "Dragon"


def test_undo_death_refreshes_passed_instance(character, player):
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership, note="Dragon")
    undo_death(character, by=membership)
    assert not character.is_dead
    assert character.death_note == ""


def test_archive_refreshes_passed_instance(character, player):
    membership = Membership.objects.get(user=player, club=character.club)
    character.shop_open = True
    character.save(update_fields=["shop_open"])
    archive(character, by=membership)
    assert character.is_archived
    assert character.shop_open is False


def test_unarchive_refreshes_passed_instance(character, player):
    membership = Membership.objects.get(user=player, club=character.club)
    archive(character, by=membership)
    unarchive(character, by=membership)
    assert not character.is_archived
    assert character.shop_open is False
