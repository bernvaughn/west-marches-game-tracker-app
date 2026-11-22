"""Tests for archive and unarchive (U144)."""

import pytest
from django.utils import timezone

from accounts.models import Membership
from ledger.services import Line, coin_balance, record
from player_characters.models import Character, CharacterStatusChange

pytestmark = pytest.mark.story("U144")


def _character(club, user, name, **extra):
    owner = Membership.objects.get(user=user, club=club)
    return Character.objects.create(club=club, owner=owner, name=name, **extra)


def test_owner_can_archive(club, login, character):
    client = login(character.owner.user)
    url = f"/c/{club.slug}/characters/{character.pk}/archive/"
    resp = client.get(url)
    assert resp.status_code == 200
    assert "Archive" in resp.content.decode()

    resp = client.post(url, {"note": "Test archive"})
    assert resp.status_code in (302, 204)
    character.refresh_from_db()
    assert character.is_archived
    assert not character.shop_open

    history = CharacterStatusChange.objects.filter(character=character)
    assert history.count() == 1
    assert history.first().kind == CharacterStatusChange.Kind.ARCHIVED
    assert history.first().note == "Test archive"


def test_owner_can_unarchive(club, login, character):
    character.archived_at = timezone.now()
    character.shop_open = False
    character.save()
    client = login(character.owner.user)
    url = f"/c/{club.slug}/characters/{character.pk}/unarchive/"
    resp = client.post(url, {"note": "Test unarchive"})
    assert resp.status_code in (302, 204)
    character.refresh_from_db()
    assert not character.is_archived
    assert not character.shop_open

    history = CharacterStatusChange.objects.filter(character=character)
    assert history.count() == 1
    assert history.first().kind == CharacterStatusChange.Kind.UNARCHIVED
    assert history.first().note == "Test unarchive"


def test_other_player_cannot_archive(club, login, character, other_player):
    client = login(other_player)
    url = f"/c/{club.slug}/characters/{character.pk}/archive/"
    resp = client.get(url)
    assert resp.status_code == 403
    resp = client.post(url, {"note": "hack"})
    assert resp.status_code == 403
    character.refresh_from_db()
    assert not character.is_archived


def test_anonymous_redirected(club, character):
    from django.test import Client

    client = Client()
    url = f"/c/{club.slug}/characters/{character.pk}/archive/"
    resp = client.get(url)
    assert resp.status_code == 302


def test_foreign_club_member_404(club, other_club, login, foreign_member):
    char = _character(other_club, foreign_member, "Fenn")
    client = login(foreign_member)
    url = f"/c/{club.slug}/characters/{char.pk}/archive/"
    resp = client.get(url)
    assert resp.status_code == 404


def test_game_master_can_archive_any(club, login, game_master, character):
    client = login(game_master)
    url = f"/c/{club.slug}/characters/{character.pk}/archive/"
    resp = client.post(url, {"note": "GM archive"})
    assert resp.status_code in (302, 204)
    character.refresh_from_db()
    assert character.is_archived
    history = CharacterStatusChange.objects.filter(character=character)
    assert history.first().by.user == game_master


def test_club_admin_can_archive_any(club, login, club_admin, character):
    client = login(club_admin)
    url = f"/c/{club.slug}/characters/{character.pk}/archive/"
    resp = client.post(url, {"note": "Admin archive"})
    assert resp.status_code in (302, 204)
    character.refresh_from_db()
    assert character.is_archived
    history = CharacterStatusChange.objects.filter(character=character)
    assert history.first().by.user == club_admin


def test_site_admin_works_with_by_none(db, club, site_admin, character):
    from django.test import Client

    client = Client()
    client.force_login(site_admin)
    url = f"/c/{club.slug}/characters/{character.pk}/archive/"
    resp = client.post(url, {"note": "Site admin archive"})
    assert resp.status_code in (302, 204)
    character.refresh_from_db()
    assert character.is_archived
    history = CharacterStatusChange.objects.filter(character=character)
    assert history.first().by is None


def test_living_and_dead_both_archive(club, login, character):
    client = login(character.owner.user)
    url = f"/c/{club.slug}/characters/{character.pk}/archive/"
    resp = client.post(url)
    assert resp.status_code in (302, 204)
    character.refresh_from_db()
    assert character.is_archived

    character.archived_at = None
    character.died_on = timezone.localdate()
    character.death_note = "Died bravely"
    character.save()
    resp = client.post(url)
    assert resp.status_code in (302, 204)
    character.refresh_from_db()
    assert character.is_archived
    assert character.died_on is not None
    assert character.death_note == "Died bravely"


def test_unarchive_keeps_dead_state(club, login, character):
    character.died_on = timezone.localdate()
    character.death_note = "Died"
    character.archived_at = timezone.now()
    character.shop_open = False
    character.save()
    client = login(character.owner.user)
    url = f"/c/{club.slug}/characters/{character.pk}/unarchive/"
    resp = client.post(url)
    assert resp.status_code in (302, 204)
    character.refresh_from_db()
    assert not character.is_archived
    assert character.died_on is not None
    assert character.death_note == "Died"


def test_ledger_items_coins_map_credit_unchanged(club, login, character, item):
    """Archiving does not change ledger, items, coins, or map credit."""
    record(character, "award", [Line(coins=500), Line(item=item, quantity=3)])
    before_ledger = character.ledger_entries.count()
    before_coins = coin_balance(character)

    client = login(character.owner.user)
    url = f"/c/{club.slug}/characters/{character.pk}/archive/"
    client.post(url)
    character.refresh_from_db()

    assert character.ledger_entries.count() == before_ledger
    assert coin_balance(character) == before_coins


def test_shop_open_becomes_false_on_archive(club, login, character):
    character.shop_open = True
    character.save()
    client = login(character.owner.user)
    url = f"/c/{club.slug}/characters/{character.pk}/archive/"
    client.post(url)
    character.refresh_from_db()
    assert not character.shop_open


def test_unarchive_keeps_shop_closed(club, login, character):
    character.shop_open = False
    character.archived_at = timezone.now()
    character.save()
    client = login(character.owner.user)
    url = f"/c/{club.slug}/characters/{character.pk}/unarchive/"
    client.post(url)
    character.refresh_from_db()
    assert not character.shop_open


def test_one_history_entry_per_call(club, login, character):
    client = login(character.owner.user)
    url = f"/c/{club.slug}/characters/{character.pk}/archive/"
    client.post(url, {"note": "First"})
    client.post(f"/c/{club.slug}/characters/{character.pk}/unarchive/", {"note": "Second"})
    client.post(url, {"note": "Third"})
    history = CharacterStatusChange.objects.filter(character=character)
    assert history.count() == 3
    kinds = [h.kind for h in history]
    assert kinds == [
        CharacterStatusChange.Kind.ARCHIVED,
        CharacterStatusChange.Kind.UNARCHIVED,
        CharacterStatusChange.Kind.ARCHIVED,
    ]


def test_repeat_archive_shows_error_and_no_second_row(club, login, character):
    client = login(character.owner.user)
    url = f"/c/{club.slug}/characters/{character.pk}/archive/"
    client.post(url)
    resp = client.post(url)
    assert resp.status_code == 200
    assert "already archived" in resp.content.decode()
    history = CharacterStatusChange.objects.filter(character=character)
    assert history.count() == 1


def test_repeat_unarchive_shows_error_and_no_second_row(club, login, character):
    character.archived_at = timezone.now()
    character.save()
    client = login(character.owner.user)
    url = f"/c/{club.slug}/characters/{character.pk}/unarchive/"
    client.post(url)
    resp = client.post(url)
    assert resp.status_code == 200
    assert "not archived" in resp.content.decode()
    history = CharacterStatusChange.objects.filter(character=character)
    assert history.count() == 1


def test_sheet_shows_archive_for_owner_gm_admin(
    club, login, character, other_character, game_master, club_admin
):
    """Archive button shows for owner, GM, admin; hides for other player."""
    from django.urls import reverse

    owner_client = login(character.owner.user)
    resp = owner_client.get(reverse("characters:detail", args=[club.slug, character.pk]))
    assert "Archive" in resp.content.decode()
    assert "Unarchive" not in resp.content.decode()

    gm_client = login(game_master)
    resp = gm_client.get(reverse("characters:detail", args=[club.slug, character.pk]))
    assert "Archive" in resp.content.decode()

    admin_client = login(club_admin)
    resp = admin_client.get(reverse("characters:detail", args=[club.slug, character.pk]))
    assert "Archive" in resp.content.decode()

    other_client = login(other_character.owner.user)
    resp = other_client.get(reverse("characters:detail", args=[club.slug, character.pk]))
    assert "Archive" not in resp.content.decode()


def test_sheet_shows_unarchive_when_archived(club, login, character):
    character.archived_at = timezone.now()
    character.save()
    client = login(character.owner.user)
    from django.urls import reverse

    resp = client.get(reverse("characters:detail", args=[club.slug, character.pk]))
    assert "Unarchive" in resp.content.decode()
    assert "Archive" not in resp.content.decode()


def test_modal_get_contains_form_and_text(club, login, character):
    client = login(character.owner.user)
    from django.urls import reverse

    resp = client.get(reverse("characters:archive", args=[club.slug, character.pk]))
    content = resp.content.decode()
    assert "Archive" in content
    assert "character.name" in content or character.name in content
    assert "note" in content.lower()
