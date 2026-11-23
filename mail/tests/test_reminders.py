"""Tests for session reminders and cancel/change notices (E5)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import Club, Membership, User
from mail.models import EmailMessage, EmailPreference
from mail.reminders import send_reminders
from play_sessions.models import PlaySession, SessionRSVP
from player_characters.models import Character

pytestmark = [pytest.mark.django_db]


def _make_club_and_members(suffix: str, tz="America/New_York"):
    """Create a club, admin user, member users, memberships, and characters."""
    club = Club.objects.create(
        name=f"Reminder Club {suffix}",
        slug=f"reminder-club-{suffix}",
        timezone=tz,
    )
    # Create ClubMailSettings with default reminder_days
    from mail.models import ClubMailSettings

    ClubMailSettings.objects.create(club=club)
    admin_user = User.objects.create_user(
        email=f"admin{suffix}@test.com", password="pass12345678", display_name=f"Admin {suffix}"
    )
    admin_membership = Membership.objects.create(user=admin_user, club=club, is_club_admin=True)

    member1_user = User.objects.create_user(
        email=f"member1{suffix}@test.com",
        password="pass12345678",
        display_name=f"Member One {suffix}",
    )
    member1_membership = Membership.objects.create(user=member1_user, club=club)

    member2_user = User.objects.create_user(
        email=f"member2{suffix}@test.com",
        password="pass12345678",
        display_name=f"Member Two {suffix}",
    )
    member2_membership = Membership.objects.create(user=member2_user, club=club)

    char1 = Character.objects.create(name=f"Hero One {suffix}", club=club, owner=member1_membership)
    char2 = Character.objects.create(name=f"Hero Two {suffix}", club=club, owner=member1_membership)
    char3 = Character.objects.create(
        name=f"Hero Three {suffix}", club=club, owner=member2_membership
    )

    return {
        "club": club,
        "admin_user": admin_user,
        "admin_membership": admin_membership,
        "member1_user": member1_user,
        "member1_membership": member1_membership,
        "member2_user": member2_user,
        "member2_membership": member2_membership,
        "char1": char1,
        "char2": char2,
        "char3": char3,
    }


def _make_session(
    club,
    gm_membership,
    days_from_now=3,
    title="Test Session",
    cancelled=False,
    location="Virtual",
):
    """Create a play session starting at the given days from now (same time as now)."""
    # Create session at now + days, so it falls in the reminder window
    now = timezone.now()
    starts_at = now + timedelta(days=days_from_now)
    ends_at = starts_at + timedelta(hours=3)

    session = PlaySession.objects.create(
        club=club,
        title=title,
        starts_at=starts_at,
        ends_at=ends_at,
        game_master=gm_membership,
        location=location,
        cancelled=cancelled,
    )
    return session


def _enable_reminder(membership):
    """Enable reminder preference for a membership."""
    EmailPreference.objects.create(
        membership=membership,
        kind=EmailPreference.Kind.REMINDER,
        enabled=True,
    )


def _disable_reminder(membership):
    """Disable reminder preference for a membership."""
    EmailPreference.objects.create(
        membership=membership,
        kind=EmailPreference.Kind.REMINDER,
        enabled=False,
    )


def _enable_notice(membership):
    """Enable notice preference for a membership."""
    EmailPreference.objects.create(
        membership=membership,
        kind=EmailPreference.Kind.NOTICE,
        enabled=True,
    )


def _disable_notice(membership):
    """Disable notice preference for a membership."""
    EmailPreference.objects.create(
        membership=membership,
        kind=EmailPreference.Kind.NOTICE,
        enabled=False,
    )


# --- Reminder job tests ---


def test_default_reminder_3_days_before():
    """Default one reminder 3 days before session."""
    data = _make_club_and_members("1")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]

    # Default reminder_days is [3]
    _make_session(club, gm, days_from_now=3, title="Test Session")
    _enable_reminder(member1_mem)
    _enable_reminder(member2_mem)

    send_reminders()

    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.REMINDER)
    assert messages.count() == 2

    # Check subject
    for msg in messages:
        assert msg.subject == "Reminder: Test Session"
        assert msg.club == club


def test_run_twice_sends_once():
    """Running the job twice sends only once (dedupe)."""
    data = _make_club_and_members("2")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]

    _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)
    _disable_reminder(member2_mem)  # Disable for member2 to isolate test

    send_reminders()
    send_reminders()

    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.REMINDER)
    assert messages.count() == 1


def test_member_who_said_no_is_skipped():
    """Member whose character answered 'no' is skipped."""
    data = _make_club_and_members("3")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]
    char3 = data["char3"]

    session = _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)
    _enable_reminder(member2_mem)

    # member2's character says no
    SessionRSVP.objects.create(
        session=session,
        character=char3,
        answer=SessionRSVP.Answer.NO,
        answered_by=data["member2_user"],
    )

    send_reminders()

    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.REMINDER)
    assert messages.count() == 1
    assert messages.first().user == data["member1_user"]


def test_member_with_some_chars_not_no_gets_reminder():
    """Member with multiple chars where not all said 'no' gets reminder."""
    data = _make_club_and_members("3b")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]
    char1 = data["char1"]
    char2 = data["char2"]

    session = _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)
    _disable_reminder(member2_mem)  # Disable for member2 to isolate test

    # char1 says no, char2 says maybe
    SessionRSVP.objects.create(
        session=session,
        character=char1,
        answer=SessionRSVP.Answer.NO,
        answered_by=data["member1_user"],
    )
    SessionRSVP.objects.create(
        session=session,
        character=char2,
        answer=SessionRSVP.Answer.MAYBE,
        answered_by=data["member1_user"],
    )

    send_reminders()

    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.REMINDER)
    assert messages.count() == 1
    assert messages.first().user == data["member1_user"]


def test_opted_out_skipped():
    """Opted-out member (EmailPreference reminder enabled=False) is skipped."""
    data = _make_club_and_members("4")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]

    _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)
    _disable_reminder(member2_mem)  # Opted out

    send_reminders()

    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.REMINDER)
    assert messages.count() == 1
    assert messages.first().user == data["member1_user"]


def test_no_preference_defaults_to_on():
    """No EmailPreference row means reminders are on by default."""
    data = _make_club_and_members("5")
    club = data["club"]
    gm = data["admin_membership"]
    data["member1_membership"]
    data["member2_membership"]

    _make_session(club, gm, days_from_now=3)
    # No EmailPreference created for either member

    send_reminders()

    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.REMINDER)
    # Both members should get reminders (default on)
    assert messages.count() == 2
    user_emails = {msg.user.email for msg in messages}
    assert data["member1_user"].email in user_emails
    assert data["member2_user"].email in user_emails


def test_cancelled_session_sends_cancel_notice():
    """Cancelled session sends session_cancelled to reminder recipients + yes RSVPs."""
    data = _make_club_and_members("6")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]
    char1 = data["char1"]
    data["char3"]

    session = _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)
    _enable_reminder(member2_mem)
    _enable_notice(member1_mem)
    _enable_notice(member2_mem)

    # Send reminders first (creates NoticeSent)
    send_reminders()
    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.REMINDER).count() == 2

    # member1 says yes
    SessionRSVP.objects.create(
        session=session,
        character=char1,
        answer=SessionRSVP.Answer.YES,
        answered_by=data["member1_user"],
    )

    # Now cancel the session
    session.cancelled = True
    session.save()

    # Should send cancel to member1 (reminder + yes) and member2 (reminder only)
    cancel_messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.CANCEL)
    assert cancel_messages.count() == 2

    # Check subject
    for msg in cancel_messages:
        assert "Session cancelled: Test Session" in msg.subject


def test_cancelled_notice_sent_once():
    """Cancel notice sent only once per user (dedupe)."""
    data = _make_club_and_members("7")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]
    char1 = data["char1"]

    session = _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)
    _enable_notice(member1_mem)
    _disable_reminder(member2_mem)
    _disable_notice(member2_mem)

    send_reminders()

    SessionRSVP.objects.create(
        session=session,
        character=char1,
        answer=SessionRSVP.Answer.YES,
        answered_by=data["member1_user"],
    )

    # Cancel twice
    session.cancelled = True
    session.save()
    session.save()  # Second save, should not send again

    cancel_messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.CANCEL)
    assert cancel_messages.count() == 1


def test_changed_session_sends_change_notice():
    """Changed start time sends session_changed to eligible members."""
    data = _make_club_and_members("8")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]
    char3 = data["char3"]

    session = _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)
    _enable_reminder(member2_mem)
    _enable_notice(member1_mem)
    _enable_notice(member2_mem)

    send_reminders()

    # member2 says no
    SessionRSVP.objects.create(
        session=session,
        character=char3,
        answer=SessionRSVP.Answer.NO,
        answered_by=data["member2_user"],
    )

    # Change start time (also update end time to maintain constraint)
    from play_sessions.core import from_club_local

    target_date = timezone.now().date() + timedelta(days=3)
    naive_new = timezone.datetime(target_date.year, target_date.month, target_date.day, 20, 0, 0)
    new_start = from_club_local(club, naive_new)

    session.starts_at = new_start
    session.ends_at = new_start + timedelta(hours=3)
    session.save()

    # Should send change to member1 only (member2 said no)
    change_messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.CHANGE)
    assert change_messages.count() == 1
    assert change_messages.first().user == data["member1_user"]
    assert "Session changed: Test Session" in change_messages.first().subject


def test_change_notice_dedupe_includes_new_start():
    """Change notice dedupe key includes new start; changing again sends for new time."""
    data = _make_club_and_members("9")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]

    session = _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)
    _enable_notice(member1_mem)
    _disable_reminder(member2_mem)
    _disable_notice(member2_mem)

    send_reminders()

    from play_sessions.core import from_club_local

    # First change
    target_date = timezone.now().date() + timedelta(days=3)
    naive_new1 = timezone.datetime(target_date.year, target_date.month, target_date.day, 20, 0, 0)
    new_start1 = from_club_local(club, naive_new1)
    session.starts_at = new_start1
    session.ends_at = new_start1 + timedelta(hours=3)
    session.save()

    # Second change
    naive_new2 = timezone.datetime(target_date.year, target_date.month, target_date.day, 21, 0, 0)
    new_start2 = from_club_local(club, naive_new2)
    session.starts_at = new_start2
    session.ends_at = new_start2 + timedelta(hours=3)
    session.save()

    change_messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.CHANGE)
    assert change_messages.count() == 2


def test_past_session_sends_nothing():
    """Past sessions send no reminders."""
    data = _make_club_and_members("10")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]

    session = _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)

    # Move session to the past
    session.starts_at = timezone.now() - timedelta(hours=1)
    session.save()

    send_reminders()

    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.REMINDER).count() == 0


def test_cancelled_session_sends_no_reminder():
    """Cancelled sessions send no reminders."""
    data = _make_club_and_members("11")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]

    _make_session(club, gm, days_from_now=3, cancelled=True)
    _enable_reminder(member1_mem)

    send_reminders()

    assert EmailMessage.objects.filter(kind=EmailMessage.Kind.REMINDER).count() == 0


def test_time_shown_in_club_zone_across_dst():
    """Times shown in club timezone across a DST date."""
    # Use America/Los_Angeles which has DST
    data = _make_club_and_members("12", tz="America/Los_Angeles")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]

    _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)
    _disable_reminder(member2_mem)  # Disable for member2 to isolate test

    send_reminders()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.REMINDER)
    payload = message.payload

    # Should show time in club timezone (America/Los_Angeles)
    text = payload.text
    assert "PDT" in text or "PST" in text or club.timezone in text


def test_member_with_no_characters_gets_nothing():
    """Member with no characters gets no reminders."""
    data = _make_club_and_members("13")
    club = data["club"]
    gm = data["admin_membership"]

    # Create a member with no characters
    member3_user = User.objects.create_user(
        email="member3@test.com", password="pass12345678", display_name="Member Three"
    )
    member3_membership = Membership.objects.create(user=member3_user, club=club)
    _enable_reminder(member3_membership)

    # Existing members have characters
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]
    _enable_reminder(member1_mem)
    _disable_reminder(member2_mem)  # Disable for member2 to isolate test

    _make_session(club, gm, days_from_now=3)

    send_reminders()

    messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.REMINDER)
    assert messages.count() == 1
    assert messages.first().user == data["member1_user"]


# --- Settings page tests ---


def test_settings_page_get_shows_current_days():
    """GET shows current reminder days (default [3])."""
    from django.test import Client

    data = _make_club_and_members("14")
    club = data["club"]
    admin_user = data["admin_user"]

    client = Client()
    client.force_login(admin_user)

    response = client.get(f"/c/{club.slug}/mail/reminders/")
    assert response.status_code == 200
    assert b"3 days before" in response.content
    # Check checkbox is checked for 3
    assert b'value="3"' in response.content
    assert b"checked" in response.content


def test_settings_page_post_saves_valid_days():
    """POST saves valid days and rejects invalid."""
    from django.test import Client

    data = _make_club_and_members("15")
    club = data["club"]
    admin_user = data["admin_user"]

    client = Client()
    client.force_login(admin_user)

    response = client.post(
        f"/c/{club.slug}/mail/reminders/",
        {"reminder_days": ["1", "5", "99"]},  # 99 is invalid
    )
    assert response.status_code == 302

    from mail.models import ClubMailSettings

    settings_obj = ClubMailSettings.objects.get(club=club)
    assert settings_obj.reminder_days == [1, 5]


def test_settings_page_post_blank_disables_reminders():
    """POST with blank list disables reminders."""
    from django.test import Client

    data = _make_club_and_members("16")
    club = data["club"]
    admin_user = data["admin_user"]

    client = Client()
    client.force_login(admin_user)

    response = client.post(
        f"/c/{club.slug}/mail/reminders/",
        {"reminder_days": []},
    )
    assert response.status_code == 302

    from mail.models import ClubMailSettings

    settings_obj = ClubMailSettings.objects.get(club=club)
    assert settings_obj.reminder_days == []


def test_cancel_notice_no_email_preference_opt_out():
    """Cancel notice has no EmailPreference opt-out filter (recipients already engaged)."""
    data = _make_club_and_members("17")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]

    session = _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)
    _disable_reminder(member2_mem)  # Disable member2
    # No notice preference created (default is on for notices)
    # But even if disabled, cancel should still go to reminder recipients

    send_reminders()

    # Disable notice preference
    _disable_notice(member1_mem)

    session.cancelled = True
    session.save()

    cancel_messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.CANCEL)
    assert cancel_messages.count() == 1
    assert cancel_messages.first().user == data["member1_user"]


def test_change_notice_uses_notice_preference():
    """Change notice uses notice preference (not reminder preference)."""
    data = _make_club_and_members("18")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]

    session = _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)
    _disable_notice(member1_mem)  # Opted out of notices
    _disable_reminder(member2_mem)
    _disable_notice(member2_mem)

    send_reminders()

    from play_sessions.core import from_club_local

    target_date = timezone.now().date() + timedelta(days=3)
    naive_new = timezone.datetime(target_date.year, target_date.month, target_date.day, 20, 0, 0)
    new_start = from_club_local(club, naive_new)

    session.starts_at = new_start
    session.ends_at = new_start + timedelta(hours=3)
    session.save()

    change_messages = EmailMessage.objects.filter(kind=EmailMessage.Kind.CHANGE)
    assert change_messages.count() == 0


def test_reminder_email_contains_session_details():
    """Reminder email includes title, date, time, GM name, location."""
    data = _make_club_and_members("19")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]

    _make_session(club, gm, days_from_now=3, title="My Adventure", location="The Tavern")
    _enable_reminder(member1_mem)
    _disable_reminder(member2_mem)

    send_reminders()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.REMINDER)
    payload = message.payload

    text = payload.text
    assert "My Adventure" in text
    assert "The Tavern" in text
    assert gm.user.display_name in text
    assert "3 days before" in text


def test_cancel_email_contains_session_details():
    """Cancel email includes title, date, time, GM name, location."""
    data = _make_club_and_members("20")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]

    session = _make_session(club, gm, days_from_now=3, title="Cancelled Quest", location="The Keep")
    _enable_reminder(member1_mem)
    _enable_notice(member1_mem)
    _disable_reminder(member2_mem)
    _disable_notice(member2_mem)

    send_reminders()
    session.cancelled = True
    session.save()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.CANCEL)
    payload = message.payload

    text = payload.text
    assert "Cancelled Quest" in text
    assert "The Keep" in text
    assert gm.user.display_name in text


def test_change_email_contains_old_and_new_times():
    """Change email includes both old and new times."""
    data = _make_club_and_members("21")
    club = data["club"]
    gm = data["admin_membership"]
    member1_mem = data["member1_membership"]
    member2_mem = data["member2_membership"]

    session = _make_session(club, gm, days_from_now=3)
    _enable_reminder(member1_mem)
    _enable_notice(member1_mem)
    _disable_reminder(member2_mem)
    _disable_notice(member2_mem)

    send_reminders()

    from play_sessions.core import from_club_local

    target_date = timezone.now().date() + timedelta(days=3)
    naive_new = timezone.datetime(target_date.year, target_date.month, target_date.day, 20, 0, 0)
    new_start = from_club_local(club, naive_new)

    session.starts_at = new_start
    session.ends_at = new_start + timedelta(hours=3)
    session.save()

    message = EmailMessage.objects.get(kind=EmailMessage.Kind.CHANGE)
    payload = message.payload

    text = payload.text
    assert "Old date" in text
    assert "New date" in text
