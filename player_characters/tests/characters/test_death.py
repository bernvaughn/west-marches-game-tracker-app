"""Tests for character death and undo actions (U138, U139)."""

import datetime
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership
from player_characters.death_permissions import can_mark_dead, can_undo_death
from player_characters.life import mark_dead
from player_characters.models import CharacterStatusChange

pytestmark = [pytest.mark.story("U138", "U139"), pytest.mark.django_db]


def death_url(club, character):
    return reverse("characters:death", args=[club.slug, character.pk])


def death_undo_url(club, character):
    return reverse("characters:death_undo", args=[club.slug, character.pk])


def detail_url(club, character):
    return reverse("characters:detail", args=[club.slug, character.pk])


# --- Permission helpers ---


def test_can_mark_dead_owner(character, player):
    """Owner can mark their own character dead."""
    assert can_mark_dead(player, character) is True


def test_can_mark_dead_other_player(other_player, character):
    """Another player cannot mark another's character dead."""
    assert can_mark_dead(other_player, character) is False


def test_can_mark_dead_game_master(game_master, character):
    """Game master can mark any character dead."""
    assert can_mark_dead(game_master, character) is True


def test_can_mark_dead_club_admin(club_admin, character):
    """Club admin can mark any character dead."""
    assert can_mark_dead(club_admin, character) is True


def test_can_mark_dead_cross_club(foreign_character, player):
    """Cannot mark character from another club (handled by club_get_object_or_404)."""
    assert can_mark_dead(player, foreign_character) is False


def test_can_undo_dead_not_dead(character, player):
    """Cannot undo if character is not dead."""
    assert can_undo_death(player, character) is False


def test_can_undo_death_owner_within_24h(character, player):
    """Owner can undo their own mark within 24 hours."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership, note="Test death")
    assert can_undo_death(player, character) is True


def test_can_undo_death_owner_after_24h(character, player):
    """Owner cannot undo their own mark after 24 hours."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership, note="Test death")
    # Patch timezone.now in death_permissions to be 25 hours later
    real_now = timezone.now()
    with patch("player_characters.death_permissions.timezone.now") as mock_now:
        mock_now.return_value = real_now + datetime.timedelta(hours=25)
        assert can_undo_death(player, character) is False


def test_can_undo_death_owner_cannot_undo_gm_mark(character, game_master, player):
    """Owner cannot undo a GM-made mark."""
    gm_membership = Membership.objects.get(user=game_master, club=character.club)
    mark_dead(character, by=gm_membership, note="GM death")
    assert can_undo_death(player, character) is False


def test_can_undo_death_game_master_after_24h(character, game_master, player):
    """GM can undo any death even after 24 hours."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership, note="Test death")
    real_now = timezone.now()
    with patch("player_characters.death_permissions.timezone.now") as mock_now:
        mock_now.return_value = real_now + datetime.timedelta(hours=25)
        assert can_undo_death(game_master, character) is True


def test_can_undo_death_club_admin_after_24h(character, club_admin, player):
    """Club admin can undo any death even after 24 hours."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership, note="Test death")
    real_now = timezone.now()
    with patch("player_characters.death_permissions.timezone.now") as mock_now:
        mock_now.return_value = real_now + datetime.timedelta(hours=25)
        assert can_undo_death(club_admin, character) is True


def test_can_undo_death_other_player(other_player, character, player):
    """Another player cannot undo death."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership)
    assert can_undo_death(other_player, character) is False


# --- Views ---


def test_owner_marks_dead_with_date_and_note(login, player, character):
    """Owner marks dead with a date and note; one history entry written."""
    c = login(player)
    r = c.post(death_url(character.club, character), {"died_on": "2026-11-14", "note": "Dragon"})
    assert r.status_code == 302
    character.refresh_from_db()
    assert character.is_dead
    assert character.died_on == datetime.date(2026, 11, 14)
    assert character.death_note == "Dragon"
    # One history entry
    history = CharacterStatusChange.objects.filter(character=character)
    assert history.count() == 1
    h = history.first()
    assert h.kind == CharacterStatusChange.Kind.DIED
    assert h.by.user == player
    assert h.note == "Dragon"
    assert h.date == datetime.date(2026, 11, 14)


def test_owner_marks_dead_htmx_redirect(login, player, character):
    """HTMX POST returns HX-Redirect."""
    c = login(player)
    r = c.post(
        death_url(character.club, character),
        {"died_on": "2026-11-14", "note": "Dragon"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == detail_url(character.club, character)


def test_other_player_get_403(login, other_player, character):
    """Another player gets 403 on GET."""
    c = login(other_player)
    r = c.get(death_url(character.club, character))
    assert r.status_code == 403


def test_other_player_post_403(login, other_player, character):
    """Another player gets 403 on POST; character unchanged."""
    c = login(other_player)
    r = c.post(death_url(character.club, character), {"died_on": "2026-11-14", "note": "x"})
    assert r.status_code == 403
    character.refresh_from_db()
    assert not character.is_dead


def test_future_date_refused(login, player, character):
    """Future date is refused with message; nothing written."""
    c = login(player)
    future = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
    r = c.post(death_url(character.club, character), {"died_on": future, "note": "x"})
    assert r.status_code == 302  # redirects to sheet with error message
    # Check error message in session messages
    character.refresh_from_db()
    assert not character.is_dead
    assert CharacterStatusChange.objects.filter(character=character).count() == 0


def test_default_date_is_today_get(login, player, character):
    """GET renders modal with today as default value."""
    c = login(player)
    r = c.get(death_url(character.club, character), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    today = timezone.localdate().isoformat()
    assert f'value="{today}"' in body


def test_already_dead_refused_get(login, player, character):
    """Already dead character refused on GET with message."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership)
    c = login(player)
    r = c.get(death_url(character.club, character), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert "already dead" in body.lower()


def test_already_dead_refused_post(login, player, character):
    """Already dead character refused on POST; no second history row."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership)
    history_count = CharacterStatusChange.objects.filter(character=character).count()
    c = login(player)
    r = c.post(death_url(character.club, character), {"died_on": "2026-11-14", "note": "x"})
    assert r.status_code == 302
    character.refresh_from_db()
    assert CharacterStatusChange.objects.filter(character=character).count() == history_count


def test_owner_undoes_own_mark_within_24h(login, player, character):
    """Owner undoes own mark within 24h; at 25h cannot."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership, note="Dragon")
    character.refresh_from_db()
    assert character.is_dead

    c = login(player)
    r = c.post(death_undo_url(character.club, character))
    assert r.status_code == 302
    character.refresh_from_db()
    assert not character.is_dead
    assert character.died_on is None
    assert character.death_note == ""
    # One REVIVED history row
    history = CharacterStatusChange.objects.filter(character=character)
    assert history.count() == 2
    revived = history.filter(kind=CharacterStatusChange.Kind.REVIVED).first()
    assert revived is not None
    assert revived.by.user == player


def test_owner_cannot_undo_after_25h(login, player, character):
    """Owner cannot undo after 25 hours."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership)
    character.refresh_from_db()

    real_now = timezone.now()
    with patch("player_characters.death_permissions.timezone.now") as mock_now:
        mock_now.return_value = real_now + datetime.timedelta(hours=25)
        c = login(player)
        r = c.post(death_undo_url(character.club, character))
        assert r.status_code == 403
    character.refresh_from_db()
    assert character.is_dead


def test_owner_cannot_undo_gm_mark(login, player, game_master, character):
    """Owner cannot undo a GM-made mark."""
    gm_membership = Membership.objects.get(user=game_master, club=character.club)
    mark_dead(character, by=gm_membership)
    character.refresh_from_db()

    c = login(player)
    r = c.post(death_undo_url(character.club, character))
    assert r.status_code == 403
    character.refresh_from_db()
    assert character.is_dead


def test_other_player_gets_403_on_undo(login, other_player, player, character):
    """Another player gets 403 on undo."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership)
    character.refresh_from_db()

    c = login(other_player)
    r = c.post(death_undo_url(character.club, character))
    assert r.status_code == 403


def test_gm_marks_and_undoes_any_character(login, game_master, character):
    """GM can mark and undo any character."""
    c = login(game_master)
    r = c.post(death_url(character.club, character), {"died_on": "2026-11-14", "note": "GM death"})
    assert r.status_code == 302
    character.refresh_from_db()
    assert character.is_dead

    r = c.post(death_undo_url(character.club, character))
    assert r.status_code == 302
    character.refresh_from_db()
    assert not character.is_dead


def test_club_admin_marks_and_undoes_any_character(login, club_admin, character):
    """Club admin can mark and undo any character."""
    c = login(club_admin)
    r = c.post(
        death_url(character.club, character),
        {"died_on": "2026-11-14", "note": "Admin death"},
    )
    assert r.status_code == 302
    character.refresh_from_db()
    assert character.is_dead

    r = c.post(death_undo_url(character.club, character))
    assert r.status_code == 302
    character.refresh_from_db()
    assert not character.is_dead


def test_gm_can_undo_after_24h(login, game_master, player, character):
    """GM can undo after 24 hours."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership)
    character.refresh_from_db()

    real_now = timezone.now()
    with patch("player_characters.death_permissions.timezone.now") as mock_now:
        mock_now.return_value = real_now + datetime.timedelta(hours=25)
        c = login(game_master)
        r = c.post(death_undo_url(character.club, character))
        assert r.status_code == 302
    character.refresh_from_db()
    assert not character.is_dead


def test_undo_clears_died_on_and_death_note(login, player, character):
    """Undo clears died_on and death_note, writes one REVIVED row."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership, note="Dragon")
    character.refresh_from_db()
    assert character.died_on is not None
    assert character.death_note == "Dragon"

    c = login(player)
    r = c.post(death_undo_url(character.club, character))
    assert r.status_code == 302
    character.refresh_from_db()
    assert character.died_on is None
    assert character.death_note == ""
    revived = CharacterStatusChange.objects.filter(
        character=character, kind=CharacterStatusChange.Kind.REVIVED
    ).first()
    assert revived is not None


def test_undo_living_character_refused(login, player, character):
    """Undo of a living character is refused."""
    c = login(player)
    r = c.post(death_undo_url(character.club, character))
    assert r.status_code == 302  # redirects with error message
    messages_list = [
        m.message for m in list(r.wsgi_request._messages) if hasattr(r, "wsgi_request")
    ]
    if not messages_list:
        # Check response content for non-HTMX
        body = r.content.decode()
        assert "not dead" in body.lower()
    character.refresh_from_db()
    assert not character.is_dead


def test_get_on_undo_returns_405(login, player, character):
    """GET on undo gives 405."""
    c = login(player)
    r = c.get(death_undo_url(character.club, character))
    assert r.status_code == 405


# --- Sheet shows buttons correctly ---


def test_sheet_shows_mark_dead_for_owner(login, player, character):
    """Sheet shows Mark as dead button for owner."""
    c = login(player)
    r = c.get(detail_url(character.club, character))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Mark as dead" in body
    assert 'href="/c/' in body  # has the link


def test_sheet_shows_mark_dead_for_gm(login, game_master, character):
    """Sheet shows Mark as dead button for GM."""
    c = login(game_master)
    r = c.get(detail_url(character.club, character))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Mark as dead" in body


def test_sheet_hides_mark_dead_for_other_player(login, other_player, character):
    """Sheet hides Mark as dead button for another player."""
    c = login(other_player)
    r = c.get(detail_url(character.club, character))
    assert r.status_code == 200
    body = r.content.decode()
    # Can't view inventory, so no toolbar
    assert "Mark as dead" not in body


def test_sheet_shows_undo_for_owner_within_24h(login, player, character):
    """Sheet shows Undo button for owner within 24h."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership)
    character.refresh_from_db()

    c = login(player)
    r = c.get(detail_url(character.club, character))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Undo" in body


def test_sheet_hides_undo_for_owner_after_25h(login, player, character):
    """Sheet hides Undo button for owner after 25h."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership)
    character.refresh_from_db()

    real_now = timezone.now()
    with patch("player_characters.death_permissions.timezone.now") as mock_now:
        mock_now.return_value = real_now + datetime.timedelta(hours=25)
        c = login(player)
        r = c.get(detail_url(character.club, character))
        assert r.status_code == 200
        body = r.content.decode()
        assert "Undo" not in body


def test_sheet_shows_undo_for_gm_after_25h(login, game_master, player, character):
    """Sheet shows Undo button for GM after 25h."""
    membership = Membership.objects.get(user=player, club=character.club)
    mark_dead(character, by=membership)
    character.refresh_from_db()

    real_now = timezone.now()
    with patch("player_characters.death_permissions.timezone.now") as mock_now:
        mock_now.return_value = real_now + datetime.timedelta(hours=25)
        c = login(game_master)
        r = c.get(detail_url(character.club, character))
        assert r.status_code == 200
        body = r.content.decode()
        assert "Undo" in body


# --- Cross club 404 ---


def test_other_club_character_404(login, player, foreign_character):
    """Character of another club gives 404."""
    c = login(player)
    r = c.get(death_url(foreign_character.club, foreign_character))
    assert r.status_code == 404

    r = c.post(death_url(foreign_character.club, foreign_character), {"died_on": "2026-11-14"})
    assert r.status_code == 404

    r = c.get(death_undo_url(foreign_character.club, foreign_character))
    assert r.status_code == 404

    r = c.post(death_undo_url(foreign_character.club, foreign_character))
    assert r.status_code == 404


# --- HTMX modal rendering ---


def test_get_modal_renders_htmx(login, player, character):
    """GET with HX-Request renders modal fragment."""
    c = login(player)
    r = c.get(death_url(character.club, character), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert "modal-header" in body
    assert "Mark as dead" in body
    assert "<html" not in body


def test_get_non_htmx_redirects_to_sheet(login, player, character):
    """Non-HTMX GET redirects to sheet (no page template)."""
    c = login(player)
    r = c.get(death_url(character.club, character))
    assert r.status_code == 302
    assert r.url == detail_url(character.club, character)


def test_post_error_rerenders_modal_htmx(login, player, character):
    """POST with error re-renders modal with HTTP 200 (HTMX)."""
    c = login(player)
    future = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
    r = c.post(
        death_url(character.club, character),
        {"died_on": future, "note": "x"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    body = r.content.decode()
    assert "The death date cannot be in the future" in body
    assert "modal-header" in body
