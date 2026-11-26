"""Tests for email RSVP (E6)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from mail.builders_rsvp import build_rsvp_extra
from mail.models import OneTimeToken
from mail.tokens import issue
from play_sessions.models import PlayerRSVP, PlaySession
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


def _make_member_token(user, club, session, membership, answer):
    """Helper to create a member-carrying RSVP token."""
    ttl = session.starts_at - timezone.now()
    return issue(
        purpose="rsvp",
        user=user,
        club=club,
        ttl=ttl,
        extra={"session_id": session.pk, "member_id": membership.pk, "answer": answer},
    )


def _make_character_token(user, club, session, character, answer):
    """Helper to create a legacy character-carrying RSVP token."""
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
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    token = _make_member_token(player_user, club, session, player_membership, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    # No RSVP exists yet
    assert not PlayerRSVP.objects.filter(session=session, member=player_membership).exists()

    response = client.get(url)
    assert response.status_code == 200

    # Still no RSVP after GET
    assert not PlayerRSVP.objects.filter(session=session, member=player_membership).exists()

    # Page shows the selected answer
    content = response.content.decode()
    assert "Yes" in content
    assert "Confirm" in content


def test_post_records_player_rsvp(client, rsvp_setup):
    """POST records a PlayerRSVP for the member."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    token = _make_member_token(player_user, club, session, player_membership, "maybe")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    response = client.post(url)
    assert response.status_code == 200

    rsvp = PlayerRSVP.objects.get(session=session, member=player_membership)
    assert rsvp.answer == "maybe"
    assert rsvp.answered_by == player_user
    assert rsvp.answered_at is not None

    # Page shows confirmed message
    content = response.content.decode()
    assert "RSVP Confirmed" in content


def test_token_expires_at_session_start(client, rsvp_setup):
    """Token expires at session start (expired token rejected)."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Move session to the past
    session.starts_at = timezone.now() - timedelta(hours=1)
    session.save()

    token = _make_member_token(player_user, club, session, player_membership, "yes")
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
    assert not PlayerRSVP.objects.filter(session=session, member=player_membership).exists()


def test_wrong_signed_in_user_gets_nothing(client, rsvp_setup):
    """Wrong signed-in person gets 'not for you' page and nothing changes."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Create another user
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    Membership.objects.create(user=other_user, club=club)

    token = _make_member_token(player_user, club, session, player_membership, "yes")
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

    assert not PlayerRSVP.objects.filter(session=session, member=player_membership).exists()


def test_latest_answer_wins(client, rsvp_setup):
    """Latest answer wins (update_or_create behavior)."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # First RSVP: yes
    token1 = _make_member_token(player_user, club, session, player_membership, "yes")
    url1 = reverse("mail_public:email_rsvp", kwargs={"token": token1})
    client.post(url1)

    rsvp = PlayerRSVP.objects.get(session=session, member=player_membership)
    assert rsvp.answer == "yes"

    # Second RSVP: maybe (new token)
    token2 = _make_member_token(player_user, club, session, player_membership, "maybe")
    url2 = reverse("mail_public:email_rsvp", kwargs={"token": token2})
    client.post(url2)

    rsvp.refresh_from_db()
    assert rsvp.answer == "maybe"

    # Third RSVP: no (new token)
    token3 = _make_member_token(player_user, club, session, player_membership, "no")
    url3 = reverse("mail_public:email_rsvp", kwargs={"token": token3})
    client.post(url3)

    rsvp.refresh_from_db()
    assert rsvp.answer == "no"

    # Only one RSVP row exists
    assert PlayerRSVP.objects.filter(session=session, member=player_membership).count() == 1


def test_legacy_character_token_resolves_to_owner(client, rsvp_setup):
    """Old character-carrying token resolves to the character's owner membership."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    token = _make_character_token(player_user, club, session, char1, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    response = client.post(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "RSVP Confirmed" in content

    # A PlayerRSVP exists for the owner membership, not per-character
    rsvp = PlayerRSVP.objects.get(session=session, member=player_membership)
    assert rsvp.answer == "yes"
    assert rsvp.answered_by == player_user


def test_legacy_character_token_expires_at_start(client, rsvp_setup):
    """Legacy character token also expires at session start."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Move session to the past
    session.starts_at = timezone.now() - timedelta(hours=1)
    session.save()

    token = _make_character_token(player_user, club, session, char1, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    response = client.post(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "expired" in content.lower() or "invalid" in content.lower()

    assert not PlayerRSVP.objects.filter(session=session, member=player_membership).exists()


def test_cancelled_session_refused(client, rsvp_setup):
    """Cancelled session refuses RSVP."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    session.cancelled = True
    session.save()

    token = _make_member_token(player_user, club, session, player_membership, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    response = client.post(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "cancelled" in content.lower()

    assert not PlayerRSVP.objects.filter(session=session, member=player_membership).exists()


def test_works_without_sign_in(client, rsvp_setup):
    """The page works without sign-in."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    token = _make_member_token(player_user, club, session, player_membership, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    # Not logged in
    response = client.get(url)
    assert response.status_code == 200
    assert "Confirm" in response.content.decode()

    response = client.post(url)
    assert response.status_code == 200
    assert "RSVP Confirmed" in response.content.decode()

    rsvp = PlayerRSVP.objects.get(session=session, member=player_membership)
    assert rsvp.answered_by == player_user


def test_token_single_use_consumed_on_post(client, rsvp_setup):
    """Token is consumed on POST and cannot be reused."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    token = _make_member_token(player_user, club, session, player_membership, "yes")
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    # First POST succeeds
    response = client.post(url)
    assert response.status_code == 200
    assert PlayerRSVP.objects.filter(session=session, member=player_membership).exists()

    # Second POST with same token fails (token consumed)
    response = client.post(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "invalid" in content.lower() or "expired" in content.lower()


def test_get_does_not_consume_token(client, rsvp_setup):
    """GET does not consume the token (peek, not consume)."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    token = _make_member_token(player_user, club, session, player_membership, "yes")
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


def test_extra_adds_three_buttons_per_member(rsvp_setup):
    """The email extra adds one set of Yes/Maybe/No buttons for the member."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    context = {
        "user": player_user,
        "club": club,
        "session": session,
        "membership": player_membership,
        "site_url": "http://testserver",
    }

    text, html = build_rsvp_extra(context)

    # Member name appears
    assert player_user.display_name in text or player_user.email in text
    assert player_user.display_name in html or player_user.email in html

    # One set of three links/buttons per member (not per character)
    assert text.count("Yes:") == 1
    assert text.count("Maybe:") == 1
    assert text.count("No:") == 1

    assert html.count(">Yes<") == 1
    assert html.count(">Maybe<") == 1
    assert html.count(">No<") == 1


def test_token_with_nonexistent_session(client, rsvp_setup):
    """Token with invalid session_id shows error."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    club = rsvp_setup["club"]

    token = issue(
        purpose="rsvp",
        user=player_user,
        club=club,
        ttl=timedelta(hours=1),
        extra={"session_id": 99999, "member_id": player_membership.pk, "answer": "yes"},
    )
    url = reverse("mail_public:email_rsvp", kwargs={"token": token})

    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "invalid" in content.lower()
