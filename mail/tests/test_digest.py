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


@pytest.fixture
def digest_setup():
    """Create a club, GM, players, characters, and a session."""
    club = Club.objects.create(name="Digest Club", slug="digest-club", timezone="America/New_York")

    gm_user = User.objects.create_user(
        email="gm@test.com", password="pass12345678", display_name="GM Name"
    )
    gm_membership = Membership.objects.create(user=gm_user, club=club, is_game_master=True)

    player1_user = User.objects.create_user(
        email="player1@test.com", password="pass12345678", display_name="Player One"
    )
    player1_membership = Membership.objects.create(user=player1_user, club=club)

    player2_user = User.objects.create_user(
        email="player2@test.com", password="pass12345678", display_name="Player Two"
    )
    player2_membership = Membership.objects.create(user=player2_user, club=club)

    char1 = Character.objects.create(name="Hero One", club=club, owner=player1_membership)
    char2 = Character.objects.create(name="Hero Two", club=club, owner=player1_membership)
    char3 = Character.objects.create(name="Hero Three", club=club, owner=player2_membership)

    # Session starts in ~24 hours
    PlaySession.objects.create(
        club=club,
        title="Test Session",
        starts_at=timezone.now() + timedelta(hours=24),
        ends_at=timezone.now() + timedelta(hours=27),
        game_master=gm_membership,
        location="Virtual Tabletop",
    )

    return {
        "club": club,
        "gm_user": gm_user,
        "gm_membership": gm_membership,
        "player1_user": player1_user,
        "player1_membership": player1_membership,
        "player2_user": player2_user,
        "player2_membership": player2_membership,
        "char1": char1,
        "char2": char2,
        "char3": char3,
    }


def test_digest_sent_only_to_gm(digest_setup):
    """Digest goes only to the session's game master, not to players."""
    gm_membership = digest_setup["gm_membership"]
    gm_user = digest_setup["gm_user"]

    # Enable digest preference for GM
    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )

    # Run the digest job
    send_digests()

    # Check that exactly one email was queued for the GM
    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST)
    assert messages.count() == 1
    assert messages.first().user == gm_user
    assert messages.first().to_address == gm_user.email


def test_digest_only_when_opted_in(digest_setup):
    """Digest only sent when EmailPreference digest enabled."""
    gm_membership = digest_setup["gm_membership"]

    # No preference created (default is off for digest)
    send_digests()

    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST)
    assert messages.count() == 0

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


def test_digest_groups_rsvps_correctly(digest_setup):
    """Digest lists yes, maybe, no and not answered by character with player name."""
    gm_membership = digest_setup["gm_membership"]
    char1 = digest_setup["char1"]
    char2 = digest_setup["char2"]
    char3 = digest_setup["char3"]
    player1_user = digest_setup["player1_user"]
    player2_user = digest_setup["player2_user"]

    # Enable digest preference for GM
    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )

    # Set up RSVPs: char1=yes, char2=maybe, char3=no, no char for player2's other
    # char (not_answered)
    SessionRSVP.objects.create(
        session=digest_setup["session"],
        character=char1,
        answer=SessionRSVP.Answer.YES,
        answered_by=player1_user,
    )
    SessionRSVP.objects.create(
        session=digest_setup["session"],
        character=char2,
        answer=SessionRSVP.Answer.MAYBE,
        answered_by=player1_user,
    )
    SessionRSVP.objects.create(
        session=digest_setup["session"],
        character=char3,
        answer=SessionRSVP.Answer.NO,
        answered_by=player2_user,
    )

    send_digests()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.DIGEST)
    payload = message.payload

    # Check text content has all groups
    text = payload.text
    assert "YES (1):" in text
    assert "Hero One — Player One" in text
    assert "MAYBE (1):" in text
    assert "Hero Two — Player One" in text
    assert "NO (1):" in text
    assert "Hero Three — Player Two" in text
    assert "NOT ANSWERED (0):" in text or "NOT ANSWERED:" in text


def test_digest_sent_once_dedupe(digest_setup):
    """Digest sent once; NoticeSent prevents duplicate sends."""
    gm_membership = digest_setup["gm_membership"]
    gm_user = digest_setup["gm_user"]

    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )

    # Run twice
    send_digests()
    send_digests()

    # Only one email should be queued
    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST)
    assert messages.count() == 1

    # NoticeSent record should exist
    session = digest_setup["session"]
    key = f"{session.id}:{session.starts_at.isoformat()}"
    assert NoticeSent.objects.filter(kind=NoticeSent.Kind.DIGEST, key=key, user=gm_user).exists()


def test_no_digest_for_cancelled_session(digest_setup):
    """No digest sent for cancelled sessions."""
    session = digest_setup["session"]
    gm_membership = digest_setup["gm_membership"]

    session.cancelled = True
    session.save()

    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )

    send_digests()

    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 0


def test_no_digest_for_past_session(digest_setup):
    """No digest sent for past sessions."""
    session = digest_setup["session"]
    gm_membership = digest_setup["gm_membership"]

    # Move session to the past
    session.starts_at = timezone.now() - timedelta(hours=1)
    session.save()

    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )

    send_digests()

    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 0


def test_no_digest_when_gm_email_suppressed_invalid(digest_setup):
    """No digest when GM email ends with .invalid."""
    gm_user = digest_setup["gm_user"]
    gm_membership = digest_setup["gm_membership"]

    gm_user.email = "gm@test.invalid"
    gm_user.save()

    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )

    send_digests()

    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 0


def test_no_digest_when_gm_email_in_do_not_email(digest_setup):
    """No digest when GM email is in DoNotEmail."""
    from mail.models import DoNotEmail

    gm_user = digest_setup["gm_user"]
    gm_membership = digest_setup["gm_membership"]

    DoNotEmail.objects.create(address=gm_user.email, reason=DoNotEmail.Reason.BOUNCE)

    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )

    send_digests()

    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 0


def test_digest_time_in_club_zone():
    """Time shown in club timezone (DST edge case)."""
    # Use a fresh club to avoid fixture session interference
    club = Club.objects.create(name="TZ Club", slug="tz-club", timezone="America/Los_Angeles")
    gm_user = User.objects.create_user(email="gm3@test.com", password="pass12345678")
    gm_membership = Membership.objects.create(user=gm_user, club=club, is_game_master=True)

    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )

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


def test_digest_only_active_characters(digest_setup):
    """Digest only includes non-archived characters."""
    gm_membership = digest_setup["gm_membership"]
    player1_membership = digest_setup["player1_membership"]

    # Create an archived character
    Character.objects.create(
        name="Archived Hero",
        club=digest_setup["club"],
        owner=player1_membership,
        archived_at=timezone.now(),
    )

    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )

    send_digests()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.DIGEST)
    payload = message.payload

    # Should not include archived character
    assert "Archived Hero" not in payload.text
    # Should include active characters
    assert "Hero One" in payload.text
    assert "Hero Two" in payload.text


def test_digest_excludes_dead_characters(digest_setup):
    """Digest excludes dead characters (died_on set)."""
    gm_membership = digest_setup["gm_membership"]
    player1_membership = digest_setup["player1_membership"]

    # Create a dead character
    Character.objects.create(
        name="Dead Hero",
        club=digest_setup["club"],
        owner=player1_membership,
        died_on=timezone.now().date(),
    )

    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )

    send_digests()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.DIGEST)
    payload = message.payload

    # Should not include dead character
    assert "Dead Hero" not in payload.text


def test_digest_window_23_to_25_hours():
    """Digest only sent for sessions in the 23-25 hour window."""
    # Use a fresh club to avoid fixture session interference
    club = Club.objects.create(name="Window Club", slug="window-club", timezone="UTC")
    gm_user = User.objects.create_user(email="gm2@test.com", password="pass12345678")
    gm_membership = Membership.objects.create(user=gm_user, club=club, is_game_master=True)

    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )

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


def test_digest_no_gm_no_digest(digest_setup):
    """Session without a game master sends no digest."""
    club = digest_setup["club"]

    # Session with no GM
    PlaySession.objects.create(
        club=club,
        title="No GM Session",
        starts_at=timezone.now() + timedelta(hours=24),
        game_master=None,
    )

    send_digests()

    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.DIGEST).count() == 0


def test_digest_subject_contains_session_title(digest_setup):
    """Digest subject contains the session title."""
    gm_membership = digest_setup["gm_membership"]

    EmailPreference.objects.create(
        membership=gm_membership,
        kind=EmailPreference.Kind.DIGEST,
        enabled=True,
    )

    send_digests()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.DIGEST)
    assert "Test Session" in message.subject
