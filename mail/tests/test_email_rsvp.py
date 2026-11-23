"""Tests for email RSVP (E6)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from mail.models import OneTimeToken
from mail.tokens import issue
from play_sessions.models import PlaySession, SessionRSVP
from player_characters.models import Character

pytestmark = [pytest.mark.django_db]


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


def _make_token(user, club, session, character, answer):
    """Helper to create an RSVP token."""
    ttl = session.starts_at - timezone.now()
    return issue(
        purpose="rsvp",
        user=user,
        club=club,
        ttl=ttl,
        extra={"session_id": session.pk, "character_id": character.pk, "answer": answer},
    )


def test_get_changes_nothing(client, rsvp_setup):
    """GET shows the page but creates/updates no RSVP."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    token = _make_token(player_user, club, session, char1, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    # No RSVP exists yet
    assert not SessionRSVP.objects.filter(session=session, character=char1).exists()

    response = client.get(url)
    assert response.status_code == 200

    # Still no RSVP after GET
    assert not SessionRSVP.objects.filter(session=session, character=char1).exists()

    # Page shows the selected answer
    content = response.content.decode()
    assert "Yes" in content
    assert "Confirm" in content


def test_post_records_rsvp_with_answered_by(client, rsvp_setup):
    """POST records the RSVP through play_sessions.core.set_rsvp with answered_by."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    token = _make_token(player_user, club, session, char1, "maybe")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    response = client.post(url)
    assert response.status_code == 200

    rsvp = SessionRSVP.objects.get(session=session, character=char1)
    assert rsvp.answer == "maybe"
    assert rsvp.answered_by == player_user
    assert rsvp.answered_at is not None

    # Page shows confirmed message
    content = response.content.decode()
    assert "RSVP Confirmed" in content


def test_token_expires_at_session_start(client, rsvp_setup):
    """Token expires at session start (expired token rejected)."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Move session to the past
    session.starts_at = timezone.now() - timedelta(hours=1)
    session.save()

    token = _make_token(player_user, club, session, char1, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    # GET should show expired
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "expired" in content.lower() or "invalid" in content.lower()

    # POST should also show expired
    response = client.post(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "expired" in content.lower() or "invalid" in content.lower()

    # No RSVP created
    assert not SessionRSVP.objects.filter(session=session, character=char1).exists()


def test_wrong_signed_in_user_gets_nothing(client, rsvp_setup):
    """Wrong signed-in person gets 'not for you' page and nothing changes."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Create another user
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    Membership.objects.create(user=other_user, club=club)

    token = _make_token(player_user, club, session, char1, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    # Sign in as the other user
    client.force_login(other_user)

    # GET shows "not for you"
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "not for you" in content.lower()

    # POST also shows "not for you" and creates no RSVP
    response = client.post(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "not for you" in content.lower()

    assert not SessionRSVP.objects.filter(session=session, character=char1).exists()


def test_wrong_character_fails(client, rsvp_setup):
    """Wrong character (not owned by token user) fails."""
    player_user = rsvp_setup["player_user"]
    char2 = rsvp_setup["char2"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Create another user who owns char2
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other_membership = Membership.objects.create(user=other_user, club=club)
    # Reassign char2 to other_user
    char2.owner = other_membership
    char2.save()

    # Token for player_user but with char2 (owned by other_user)
    token = _make_token(player_user, club, session, char2, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    response = client.post(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "invalid character" in content.lower() or "wrong character" in content.lower()

    # No RSVP created
    assert not SessionRSVP.objects.filter(session=session, character=char2).exists()


def test_latest_answer_wins(client, rsvp_setup):
    """Latest answer wins (update_or_create behavior)."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # First RSVP: yes
    token1 = _make_token(player_user, club, session, char1, "yes")
    url1 = reverse("mail_public:email_rsvp", kwargs={"token": token1})
    client.post(url1)

    rsvp = SessionRSVP.objects.get(session=session, character=char1)
    assert rsvp.answer == "yes"

    # Second RSVP: maybe (new token)
    token2 = _make_token(player_user, club, session, char1, "maybe")
    url2 = reverse("mail_public:email_rsvp", kwargs={"token": token2})
    client.post(url2)

    rsvp.refresh_from_db()
    assert rsvp.answer == "maybe"

    # Third RSVP: no (new token)
    token3 = _make_token(player_user, club, session, char1, "no")
    url3 = reverse("mail_public:email_rsvp", kwargs={"token": token3})
    client.post(url3)

    rsvp.refresh_from_db()
    assert rsvp.answer == "no"

    # Only one RSVP row exists
    assert SessionRSVP.objects.filter(session=session, character=char1).count() == 1


def test_extra_adds_buttons_per_owned_character(client, rsvp_setup, monkeypatch):
    """The email extra adds buttons per owned character and none for dead/archived ones."""
    from mail.builders_rsvp import build_rsvp_extra
    from play_sessions import core

    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    char2 = rsvp_setup["char2"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Create a dead character
    dead_char = Character.objects.create(
        name="Dead Hero",
        club=club,
        owner=rsvp_setup["player_membership"],
        died_on=timezone.now().date(),
    )

    # Create an archived character
    archived_char = Character.objects.create(
        name="Archived Hero",
        club=club,
        owner=rsvp_setup["player_membership"],
        archived_at=timezone.now(),
    )

    # Patch character_is_active to return False for dead and archived
    original_is_active = core.character_is_active

    def patched_is_active(character):
        if character in [dead_char, archived_char]:
            return False
        return original_is_active(character)

    monkeypatch.setattr(core, "character_is_active", patched_is_active)

    context = {
        "user": player_user,
        "club": club,
        "session": session,
        "characters": [char1, char2, dead_char, archived_char],
        "site_url": "http://testserver",
    }

    text, html = build_rsvp_extra(context)

    # Should have buttons for char1 and char2
    assert "Hero One" in text
    assert "Hero Two" in text
    assert "Hero One" in html
    assert "Hero Two" in html

    # Should NOT have buttons for dead or archived characters
    assert "Dead Hero" not in text
    assert "Archived Hero" not in text
    assert "Dead Hero" not in html
    assert "Archived Hero" not in html

    # Each active character should have three links (Yes, Maybe, No)
    assert text.count("Yes:") == 2
    assert text.count("Maybe:") == 2
    assert text.count("No:") == 2

    # HTML should have three buttons per character
    assert html.count(">Yes<") == 2
    assert html.count(">Maybe<") == 2
    assert html.count(">No<") == 2


def test_token_single_use_consumed_on_post(client, rsvp_setup):
    """Token is consumed on POST and cannot be reused."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    token = _make_token(player_user, club, session, char1, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    # First POST succeeds
    response = client.post(url)
    assert response.status_code == 200
    assert SessionRSVP.objects.filter(session=session, character=char1).exists()

    # Second POST with same token fails (token consumed)
    response = client.post(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "invalid" in content.lower() or "expired" in content.lower()


def test_get_does_not_consume_token(client, rsvp_setup):
    """GET does not consume the token (peek, not consume)."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    token = _make_token(player_user, club, session, char1, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    # Multiple GETs should all work
    for _ in range(3):
        response = client.get(url)
        assert response.status_code == 200
        assert "Confirm" in response.content.decode()

    # Token still exists and unused
    ot_token = OneTimeToken.objects.get(user=player_user, purpose="rsvp")
    assert ot_token.used_at is None

    # POST still works
    response = client.post(url)
    assert response.status_code == 200
    assert "RSVP Confirmed" in response.content.decode()


def test_cancelled_session_refused(client, rsvp_setup):
    """Cancelled session refuses RSVP."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    session.cancelled = True
    session.save()

    token = _make_token(player_user, club, session, char1, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    response = client.post(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "cancelled" in content.lower()

    assert not SessionRSVP.objects.filter(session=session, character=char1).exists()


def test_session_not_started_required(client, rsvp_setup):
    """Session must not have started."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Create token FIRST while session is in the future
    token = _make_token(player_user, club, session, char1, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    # NOW move session start to 1 hour ago
    session.starts_at = timezone.now() - timedelta(hours=1)
    session.save()

    response = client.post(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "started" in content.lower()

    assert not SessionRSVP.objects.filter(session=session, character=char1).exists()


def test_works_without_sign_in(client, rsvp_setup):
    """The page works without sign-in."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    token = _make_token(player_user, club, session, char1, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    # Not logged in
    response = client.get(url)
    assert response.status_code == 200
    assert "Confirm" in response.content.decode()

    response = client.post(url)
    assert response.status_code == 200
    assert "RSVP Confirmed" in response.content.decode()

    rsvp = SessionRSVP.objects.get(session=session, character=char1)
    assert rsvp.answered_by == player_user


def test_character_is_active_patched_dead_and_archived(rsvp_setup, monkeypatch):
    """Test that dead and archived characters get no buttons when character_is_active is patched."""
    from mail.builders_rsvp import build_rsvp_extra
    from play_sessions import core

    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    char2 = rsvp_setup["char2"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Create a dead character
    dead_char = Character.objects.create(
        name="Dead Hero",
        club=club,
        owner=rsvp_setup["player_membership"],
        died_on=timezone.now().date(),
    )

    # Create an archived character
    archived_char = Character.objects.create(
        name="Archived Hero",
        club=club,
        owner=rsvp_setup["player_membership"],
        archived_at=timezone.now(),
    )

    # Patch character_is_active to return False for dead and archived
    original_is_active = core.character_is_active

    def patched_is_active(character):
        if character in [dead_char, archived_char]:
            return False
        return original_is_active(character)

    monkeypatch.setattr(core, "character_is_active", patched_is_active)

    context = {
        "user": player_user,
        "club": club,
        "session": session,
        "characters": [char1, char2, dead_char, archived_char],
        "site_url": "http://testserver",
    }

    text, html = build_rsvp_extra(context)

    # Should have buttons for char1 and char2 only
    assert "Hero One" in text
    assert "Hero Two" in text
    assert "Dead Hero" not in text
    assert "Archived Hero" not in text


def test_token_with_nonexistent_session_or_character(client, rsvp_setup):
    """Token with invalid session_id or character_id shows error."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Token with non-existent session
    token = issue(
        purpose="rsvp",
        user=player_user,
        club=club,
        ttl=timedelta(hours=1),
        extra={"session_id": 99999, "character_id": char1.pk, "answer": "yes"},
    )
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "invalid" in content.lower()

    # Token with non-existent character
    token = issue(
        purpose="rsvp",
        user=player_user,
        club=club,
        ttl=timedelta(hours=1),
        extra={"session_id": session.pk, "character_id": 99999, "answer": "yes"},
    )
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "invalid" in content.lower()
