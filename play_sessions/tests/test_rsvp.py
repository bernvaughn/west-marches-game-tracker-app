"""Tests for RSVP (P4)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions import core
from play_sessions.models import PlaySession, SessionRSVP
from player_characters.models import Character, SelectedCharacter

pytestmark = [pytest.mark.django_db, pytest.mark.story("P4")]


@pytest.fixture
def rsvp_setup():
    """Create a club, GM, player, characters, and a session."""
    club = Club.objects.create(name="RSVP Club", slug="rsvp-club", timezone="America/New_York")

    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    gm_membership = Membership.objects.create(user=gm_user, club=club, is_game_master=True)

    player_user = User.objects.create_user(email="player@test.com", password="pass12345678")
    player_membership = Membership.objects.create(user=player_user, club=club)

    char1 = Character.objects.create(name="Hero One", club=club, owner=player_membership)
    char2 = Character.objects.create(name="Hero Two", club=club, owner=player_membership)

    session = PlaySession.objects.create(
        club=club,
        title="Test Session",
        starts_at=timezone.now() + timedelta(days=1),
        game_master=gm_membership,
    )

    return {
        "club": club,
        "gm_user": gm_user,
        "gm_membership": gm_membership,
        "player_user": player_user,
        "player_membership": player_membership,
        "char1": char1,
        "char2": char2,
        "session": session,
    }


def test_player_answers_for_own_character(client, rsvp_setup):
    """Player can RSVP for their own character; one row created, answered_by set."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes", "character": char1.pk})

    assert response.status_code in (200, 302)
    rsvp = SessionRSVP.objects.get(session=session, character=char1)
    assert rsvp.answer == "yes"
    assert rsvp.answered_by == player_user


def test_another_players_character_refused(client, rsvp_setup):
    """Another player's character gives 403 and writes no row."""
    club = rsvp_setup["club"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]

    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other_membership = Membership.objects.create(user=other_user, club=club)
    Character.objects.create(name="Other Hero", club=club, owner=other_membership)

    client.force_login(other_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes", "character": char1.pk})

    assert response.status_code == 403
    assert not SessionRSVP.objects.filter(session=session, character=char1).exists()


def test_no_character_posted_uses_selected(client, rsvp_setup):
    """No character posted uses the selected character."""
    player_user = rsvp_setup["player_user"]
    char2 = rsvp_setup["char2"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]
    player_membership = rsvp_setup["player_membership"]

    # Select char2
    SelectedCharacter.objects.create(membership=player_membership, character=char2)

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "maybe"})  # No character in POST

    assert response.status_code in (200, 302)
    rsvp = SessionRSVP.objects.get(session=session, character=char2)
    assert rsvp.answer == "maybe"


def test_after_start_player_refused_gm_allowed(client, rsvp_setup):
    """After the start, a player gets 403; GM answers for anyone; admin answers after start."""
    club = rsvp_setup["club"]
    gm_user = rsvp_setup["gm_user"]
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]

    # Move session to the past
    session.starts_at = timezone.now() - timedelta(hours=1)
    session.save()

    # Player tries to answer after start -> 403
    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes", "character": char1.pk})
    assert response.status_code == 403

    # GM can answer for anyone after start
    client.force_login(gm_user)
    response = client.post(url, {"answer": "yes", "character": char1.pk})
    assert response.status_code in (200, 302)
    rsvp = SessionRSVP.objects.get(session=session, character=char1)
    assert rsvp.answer == "yes"
    assert rsvp.answered_by == gm_user

    # Admin (superuser) can also answer
    admin_user = User.objects.create_superuser(email="admin@test.com", password="pass12345678")
    client.force_login(admin_user)
    response = client.post(url, {"answer": "no", "character": char1.pk})
    assert response.status_code in (200, 302)
    rsvp.refresh_from_db()
    assert rsvp.answer == "no"
    assert rsvp.answered_by == admin_user


def test_inactive_character_refused_for_everyone(client, rsvp_setup, monkeypatch):
    """Patch character_is_active to false: absent from detail HTML options,
    POST refused (also for GM)."""
    club = rsvp_setup["club"]
    gm_user = rsvp_setup["gm_user"]
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]

    # Patch character_is_active to return False for char1
    monkeypatch.setattr(core, "character_is_active", lambda c: c.pk != char1.pk)

    # Detail page should not show char1 in RSVP section options
    client.force_login(player_user)
    detail_url = reverse(
        "play_sessions:session_detail",
        kwargs={"club_slug": club.slug, "pk": session.pk},
    )
    response = client.get(detail_url)
    # Check the RSVP section specifically - char1 should not be in the form select
    assert b'<option value="' + str(char1.pk).encode() + b'">' not in response.content
    assert b"Hero Two" in response.content  # char2 should still be there

    # POST for inactive character refused for player
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes", "character": char1.pk})
    assert response.status_code == 403

    # POST for inactive character refused for GM too
    client.force_login(gm_user)
    response = client.post(url, {"answer": "yes", "character": char1.pk})
    assert response.status_code == 403


def test_changing_answer_keeps_one_row(client, rsvp_setup):
    """Changing an answer keeps one row per session and character."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})

    # First answer: yes
    client.post(url, {"answer": "yes", "character": char1.pk})
    # Second answer: maybe
    client.post(url, {"answer": "maybe", "character": char1.pk})
    # Third answer: no
    client.post(url, {"answer": "no", "character": char1.pk})

    rsvps = SessionRSVP.objects.filter(session=session, character=char1)
    assert rsvps.count() == 1
    rsvp = rsvps.first()
    assert rsvp.answer == "no"
    assert rsvp.answered_by == player_user


def test_cancelled_session_refuses_player(client, rsvp_setup):
    """Cancelled session refuses a player's answer; GM and admin may still answer."""
    club = rsvp_setup["club"]
    gm_user = rsvp_setup["gm_user"]
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]

    session.cancelled = True
    session.save()

    # Player refused
    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes", "character": char1.pk})
    assert response.status_code == 403

    # GM allowed
    client.force_login(gm_user)
    response = client.post(url, {"answer": "yes", "character": char1.pk})
    assert response.status_code in (200, 302)
    rsvp = SessionRSVP.objects.get(session=session, character=char1)
    assert rsvp.answer == "yes"


def test_another_club_session_404(client, rsvp_setup):
    """Another club's session gives 404."""
    other_club = Club.objects.create(name="Other Club", slug="other-club")
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    Membership.objects.create(user=other_user, club=other_club)

    session = rsvp_setup["session"]
    client.force_login(other_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": other_club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes"})
    assert response.status_code == 404


def test_invalid_answer_400(client, rsvp_setup):
    """Invalid answer gives 400."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "invalid", "character": char1.pk})
    assert response.status_code == 400


def test_next_redirect_safe(client, rsvp_setup):
    """next redirect is safe; external URL is ignored."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})

    # Safe next (relative path)
    response = client.post(url, {"answer": "yes", "character": char1.pk, "next": "/some/path"})
    assert response.status_code == 302
    assert response.url == "/some/path"

    # External URL ignored
    response = client.post(
        url, {"answer": "maybe", "character": char1.pk, "next": "http://evil.com"}
    )
    assert response.status_code == 302
    # Should redirect to session detail (relative URL)
    assert response.url.startswith("/c/")
    assert "sessions" in response.url


def test_htmx_post_returns_section_fragment(client, rsvp_setup):
    """HTMX POST returns the section fragment."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes", "character": char1.pk}, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"rsvp-section" in response.content
    assert b'name="answer"' in response.content


def test_dashboard_card_shows_answer(client, rsvp_setup):
    """Dashboard card shows the answer for the selected character."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]
    player_membership = rsvp_setup["player_membership"]

    # Set RSVP for char1
    SessionRSVP.objects.create(
        session=session, character=char1, answer="yes", answered_by=player_user
    )

    # Select char1
    SelectedCharacter.objects.create(membership=player_membership, character=char1)

    client.force_login(player_user)
    dashboard_url = reverse("accounts:player_dashboard", kwargs={"club_slug": club.slug})
    response = client.get(dashboard_url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Test Session" in content
    assert "Yes" in content  # The badge for Yes


def test_sheet_page_shows_section_for_owner(client, rsvp_setup):
    """Sheet page shows the section for the owner."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Set RSVP
    SessionRSVP.objects.create(
        session=session, character=char1, answer="yes", answered_by=player_user
    )

    client.force_login(player_user)
    sheet_url = reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": char1.pk})
    response = client.get(sheet_url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Session RSVPs" in content
    assert "Test Session" in content
    assert "Yes" in content


def test_sheet_section_absent_for_inactive_character(client, rsvp_setup, monkeypatch):
    """Sheet section is absent for an inactive character."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    club = rsvp_setup["club"]

    # Patch character_is_active to return False for char1
    monkeypatch.setattr(core, "character_is_active", lambda c: c.pk != char1.pk)

    client.force_login(player_user)
    sheet_url = reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": char1.pk})
    response = client.get(sheet_url)

    assert response.status_code == 200
    content = response.content.decode()
    # The section should not be rendered for inactive character
    assert "Session RSVPs" not in content
