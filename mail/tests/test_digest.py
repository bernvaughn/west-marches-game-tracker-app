"""Tests for Game Master digest (E7)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import Club, Membership, User
from mail.digest import send_digests
from mail.models import EmailMessage, EmailPreference, NoticeSent
from play_sessions.models import PlaySession, SessionRSVP
from player_characters.models import Character

pytestmark = [pytest.mark.django_db]


def _make_club_and_gm(suffix: str):
    """Create a club, GM user, and GM membership with unique identifiers."""
    club = Club.objects.create(
        name=f"Digest Club {suffix}", slug=f"digest-club-{suffix}", timezone="America/New_York"
    )
    gm_user = User.objects.create_user(
        email=f"gm{suffix}@test.com", password="pass12345678", display_name=f"GM {suffix}"
    )
    gm_membership = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    return club, gm_user, gm_membership


def _make_players_and_chars(club, suffix: str):
    """Create player users, memberships, and characters."""
    player1_user = User.objects.create_user(
        email=f"player1{suffix}@test.com",
        password="pass12345678",
        display_name=f"Player One {suffix}",
    )
    player1_membership = Membership.objects.create(user=player1_user, club=club)

    player2_user = User.objects.create_user(
        email=f"player2{suffix}@test.com",
        password="pass12345678",
        display_name=f"Player Two {suffix}",
    )
    player2_membership = Membership.objects.create(user=player2_user, club=club)

    char1 = Character.objects.create(name=f"Hero One {suffix}", club=club, owner=player1_membership)
    char2 = Character.objects.create(name=f"Hero Two {suffix}", club=club, owner=player1_membership)
    char3 = Character.objects.create(
        name=f"Hero Three {suffix}", club=club, owner=player2_membership
    )

    return {
        "player1_user": player1_user,
        "player1_membership": player1_membership,
        "player2_user": player2_user,
        "player2_membership": player2_membership,
        "char1": char1,
        "char2": char2,
        "char3": char3,
    }


def _make_session(club, gm_membership, hours_from_now=24, title="Test Session", cancelled=False):
    """Create a play session."""
    session = PlaySession.objects.create(
        club=club,
        title=title,
        starts_at=timezone.now() + timedelta(hours=hours_from_now),
        ends_at=timezone.now() + timedelta(hours=hours_from_now + 3),
        game_master=gm_membership,
        location="Virtual Tabletop",
        cancelled=cancelled,
    )
    return session


def _enable_digest(gm_membership):
    """Enable digest preference for a GM."""
    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )


def test_digest_sent_only_to_gm():
    """Digest goes only to the session's game master, not to players."""
    club, gm_user, gm_membership = _make_club_and_gm("1")
    _make_players_and_chars(club, "1")
    _make_session(club, gm_membership)
    _enable_digest(gm_membership)

    send_digests()

    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST)
    assert messages.count() == 1
    assert messages.first().user == gm_user
    assert messages.first().to_address == gm_user.email


def test_digest_only_when_opted_in():
    """Digest only sent when EmailPreference digest enabled."""
    club, gm_user, gm_membership = _make_club_and_gm("2")
    _make_players_and_chars(club, "2")
    _make_session(club, gm_membership)

    # No preference created (default is off for digest)
    send_digests()
    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 0

    # Create preference but disabled
    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=False,
    )
    send_digests()
    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 0

    # Enable it
    EmailPreference.objects.filter(
        membership=gm_membership, kind=EmailPreference.Kind.DIGEST
    ).update(enabled=True)
    send_digests()
    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 1

    # Check it went to the right user
    message = EmailMessage.objects.get(kind=EmailMessage.Kind.DIGEST)
    assert message.user == gm_user


def test_digest_groups_rsvps_correctly():
    """Digest lists yes, maybe, no and not answered by character with player name."""
    club, gm_user, gm_membership = _make_club_and_gm("3")
    players = _make_players_and_chars(club, "3")
    session = _make_session(club, gm_membership)
    _enable_digest(gm_membership)

    # Set up RSVPs: char1=yes, char2=maybe, char3=no, no char for player2's other
    # char (not_answered)
    SessionRSVP.objects.create(
        session=session,
        character=players["char1"],
        answer=SessionRSVP.Answer.YES,
        answered_by=players["player1_user"],
    )
    SessionRSVP.objects.create(
        session=session,
        character=players["char2"],
        answer=SessionRSVP.Answer.MAYBE,
        answered_by=players["player1_user"],
    )
    SessionRSVP.objects.create(
        session=session,
        character=players["char3"],
        answer=SessionRSVP.Answer.NO,
        answered_by=players["player2_user"],
    )

    send_digests()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.DIGEST)
    payload = message.payload

    # Check text content has all groups
    text = payload.text
    assert "YES (1):" in text
    assert "Hero One 3 — Player One 3" in text
    assert "MAYBE (1):" in text
    assert "Hero Two 3 — Player One 3" in text
    assert "NO (1):" in text
    assert "Hero Three 3 — Player Two 3" in text
    assert "NOT ANSWERED (0):" in text or "NOT ANSWERED:" in text


def test_digest_sent_once_dedupe():
    """Digest sent once; NoticeSent prevents duplicate sends."""
    club, gm_user, gm_membership = _make_club_and_gm("4")
    _make_players_and_chars(club, "4")
    session = _make_session(club, gm_membership)
    _enable_digest(gm_membership)

    # Run twice
    send_digests()
    send_digests()

    # Only one email should be queued
    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST)
    assert messages.count() == 1

    # NoticeSent record should exist
    key = f"{session.id}:{session.starts_at.isoformat()}"
    assert NoticeSent.objects.filter(kind=NoticeSent.Kind.DIGEST, key=key, user=gm_user).exists()


def test_no_digest_for_cancelled_session():
    """No digest sent for cancelled sessions."""
    club, gm_user, gm_membership = _make_club_and_gm("5")
    _make_players_and_chars(club, "5")
    _make_session(club, gm_membership, cancelled=True)
    _enable_digest(gm_membership)

    send_digests()

    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 0


def test_no_digest_for_past_session():
    """No digest sent for past sessions."""
    club, gm_user, gm_membership = _make_club_and_gm("6")
    _make_players_and_chars(club, "6")
    session = _make_session(club, gm_membership)

    # Move session to the past
    session.starts_at = timezone.now() - timedelta(hours=1)
    session.save()

    _enable_digest(gm_membership)

    send_digests()

    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 0


def test_no_digest_when_gm_email_suppressed_invalid():
    """No digest when GM email ends with .invalid."""
    club, gm_user, gm_membership = _make_club_and_gm("7")
    _make_players_and_chars(club, "7")
    _make_session(club, gm_membership)

    gm_user.email = "gm7@test.invalid"
    gm_user.save()

    _enable_digest(gm_membership)

    send_digests()

    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 0


def test_no_digest_when_gm_email_in_do_not_email():
    """No digest when GM email is in DoNotEmail."""
    from mail.models import DoNotEmail

    club, gm_user, gm_membership = _make_club_and_gm("8")
    _make_players_and_chars(club, "8")
    _make_session(club, gm_membership)

    DoNotEmail.objects.create(address=gm_user.email, reason=DoNotEmail.Reason.BOUNCE)

    _enable_digest(gm_membership)

    send_digests()

    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 0


def test_digest_time_in_club_zone():
    """Time shown in club timezone (DST edge case)."""
    # Use a fresh club to avoid fixture session interference
    club = Club.objects.create(name="TZ Club", slug="tz-club", timezone="America/Los_Angeles")
    gm_user = User.objects.create_user(email="gm3@test.com", password="pass12345678")
    gm_membership = Membership.objects.create(user=gm_user, club=club, is_game_master=True)

    _enable_digest(gm_membership)

    # Session at 24 hours from now
    now = timezone.now()
    target_utc = now + timedelta(hours=24)

    PlaySession.objects.create(
        club=club,
        title="TZ Session",
        starts_at=target_utc,
        game_master=gm_membership,
    )

    send_digests()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.DIGEST)
    payload = message.payload

    # Should show time in club timezone (America/Los_Angeles)
    assert club.timezone in payload.text or "PDT" in payload.text or "PST" in payload.text


def test_digest_only_active_characters():
    """Digest only includes non-archived characters."""
    club, gm_user, gm_membership = _make_club_and_gm("9")
    players = _make_players_and_chars(club, "9")
    _make_session(club, gm_membership)

    # Create an archived character
    Character.objects.create(
        name="Archived Hero 9",
        club=club,
        owner=players["player1_membership"],
        archived_at=timezone.now(),
    )

    _enable_digest(gm_membership)

    send_digests()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.DIGEST)
    payload = message.payload

    # Should not include archived character
    assert "Archived Hero 9" not in payload.text
    # Should include active characters
    assert "Hero One 9" in payload.text
    assert "Hero Two 9" in payload.text


def test_digest_excludes_dead_characters():
    """Digest excludes dead characters (died_on set)."""
    club, gm_user, gm_membership = _make_club_and_gm("10")
    players = _make_players_and_chars(club, "10")
    _make_session(club, gm_membership)

    # Create a dead character
    Character.objects.create(
        name="Dead Hero 10",
        club=club,
        owner=players["player1_membership"],
        died_on=timezone.now().date(),
    )

    _enable_digest(gm_membership)

    send_digests()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.DIGEST)
    payload = message.payload

    # Should not include dead character
    assert "Dead Hero 10" not in payload.text


def test_digest_window_23_to_25_hours():
    """Digest only sent for sessions in the 23-25 hour window."""
    club = Club.objects.create(name="Window Club", slug="window-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm2@test.com", password="pass12345678")
    gm_membership = Membership.objects.create(user=gm_user, club=club, is_game_master=True)

    _enable_digest(gm_membership)

    # Session at 22 hours (too early)
    PlaySession.objects.create(
        club=club,
        title="Early Session",
        starts_at=timezone.now() + timedelta(hours=22),
        game_master=gm_membership,
    )

    # Session at 26 hours (too late)
    PlaySession.objects.create(
        club=club,
        title="Late Session",
        starts_at=timezone.now() + timedelta(hours=26),
        game_master=gm_membership,
    )

    # Session at 24 hours (just right)
    PlaySession.objects.create(
        club=club,
        title="Good Session",
        starts_at=timezone.now() + timedelta(hours=24),
        game_master=gm_membership,
    )

    send_digests()

    # Only the good session should trigger a digest
    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST)
    assert messages.count() == 1
    assert messages.first().subject == "Session digest: Good Session"


def test_digest_no_gm_no_digest():
    """Session without a game master sends no digest."""
    club, gm_user, gm_membership = _make_club_and_gm("11")
    _make_players_and_chars(club, "11")

    # Session with no GM
    PlaySession.objects.create(
        club=club,
        title="No GM Session",
        starts_at=timezone.now() + timedelta(hours=24),
        game_master=None,
    )

    send_digests()

    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 0


def test_digest_subject_contains_session_title():
    """Digest subject contains the session title."""
    club, gm_user, gm_membership = _make_club_and_gm("12")
    _make_players_and_chars(club, "12")
    _make_session(club, gm_membership, title="Test Session")
    _enable_digest(gm_membership)

    send_digests()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.DIGEST)
    assert "Test Session" in message.subject
