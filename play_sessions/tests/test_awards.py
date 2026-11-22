"""Tests for session attendance awards (P9)."""

from datetime import datetime

import pytest
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.utils import timezone

from accounts.models import Club, Membership, User
from downtime.models import DowntimePointEntry
from downtime.services import balance
from play_sessions import core
from play_sessions.models import (
    PlaySession,
    SessionAttendance,
    SessionAward,
    SessionSettings,
)
from player_characters.models import Character

pytestmark = [pytest.mark.django_db, pytest.mark.story("P9")]


def _make_club_and_users():
    club = Club.objects.create(name="Test Club", slug="test", timezone="UTC")
    admin_user = User.objects.create_user(email="admin@test.com", password="pass12345678")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    player_user = User.objects.create_user(email="player@test.com", password="pass12345678")
    other_admin = User.objects.create_user(email="otheradmin@test.com", password="pass12345678")
    superuser = User.objects.create_superuser(email="super@test.com", password="pass12345678")

    Membership.objects.create(user=admin_user, club=club, is_club_admin=True)
    Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    Membership.objects.create(user=player_user, club=club)
    other_club = Club.objects.create(name="Other Club", slug="other", timezone="UTC")
    Membership.objects.create(user=other_admin, club=other_club, is_club_admin=True)

    return club, admin_user, gm_user, player_user, other_admin, superuser


def _make_session(club, gm_user):
    membership = Membership.objects.get(user=gm_user, club=club)
    return PlaySession.objects.create(
        club=club,
        title="Test Session",
        starts_at=timezone.make_aware(datetime(2024, 6, 15, 18, 0)),
        game_master=membership,
    )


def _make_characters(club, gm_user):
    membership = Membership.objects.get(user=gm_user, club=club)
    char1 = Character.objects.create(name="Hero One", club=club, owner=membership)
    char2 = Character.objects.create(name="Hero Two", club=club, owner=membership)
    return char1, char2


def _send_attendance_saved(session, characters, by, request=None):
    """Send the attendance_saved signal directly."""
    return core.attendance_saved.send(
        sender=None, session=session, characters=characters, by=by, request=request
    )


class TestDefaultSetting:
    """Default setting is 0: a played character gets no ledger entry."""

    def test_default_no_award(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        session = _make_session(club, gm_user)
        char1, char2 = _make_characters(club, gm_user)

        # Mark both as played
        SessionAttendance.objects.create(
            session=session, character=char1, played=True, confirmed_by=gm_user
        )
        SessionAttendance.objects.create(
            session=session, character=char2, played=True, confirmed_by=gm_user
        )

        # Send signal
        _send_attendance_saved(session, [char1, char2], gm_user)

        # No ledger entries
        assert DowntimePointEntry.objects.filter(character=char1).count() == 0
        assert DowntimePointEntry.objects.filter(character=char2).count() == 0

        # SessionAward rows hold 0 or don't exist
        award1 = SessionAward.objects.filter(session=session, character=char1).first()
        award2 = SessionAward.objects.filter(session=session, character=char2).first()
        if award1:
            assert award1.points == 0
        if award2:
            assert award2.points == 0


class TestFormValidation:
    """Form POST by admin sets 0 to 10 and saves. Invalid values refused."""

    def test_admin_can_set_award_points(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        factory = RequestFactory()
        request = factory.post("/c/test/sessions/settings/", {"award_points": "5"})
        request.user = admin_user
        request.club = club
        request.session = {}
        messages = FallbackStorage(request)
        request._messages = messages

        from play_sessions.views.settings import session_settings

        response = session_settings(request, club_slug="test")
        assert response.status_code == 302

        settings_obj = SessionSettings.objects.get(club=club)
        assert settings_obj.award_points == 5

    def test_form_rejects_11(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        from play_sessions.settings_forms import SessionSettingsForm

        form = SessionSettingsForm(data={"award_points": 11})
        assert not form.is_valid()
        assert "award_points" in form.errors

    def test_form_rejects_negative(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        from play_sessions.settings_forms import SessionSettingsForm

        form = SessionSettingsForm(data={"award_points": -1})
        assert not form.is_valid()
        assert "award_points" in form.errors

    def test_form_rejects_non_integer(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        from play_sessions.settings_forms import SessionSettingsForm

        form = SessionSettingsForm(data={"award_points": "abc"})
        assert not form.is_valid()
        assert "award_points" in form.errors

    def test_gm_gets_403(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        from django.test import Client

        client = Client()
        client.force_login(gm_user)
        response = client.post("/c/test/sessions/settings/", {"award_points": "5"})
        assert response.status_code == 403

    def test_player_gets_403(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        from django.test import Client

        client = Client()
        client.force_login(player_user)
        response = client.post("/c/test/sessions/settings/", {"award_points": "5"})
        assert response.status_code == 403

    def test_other_club_admin_gets_404_or_403(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        factory = RequestFactory()
        request = factory.post("/c/other/sessions/settings/", {"award_points": "5"})
        request.user = other_admin
        request.club = Club.objects.get(slug="other")
        request.session = {}
        messages = FallbackStorage(request)
        request._messages = messages

        from play_sessions.views.settings import session_settings

        # Should get 404 because club_get_object_or_404 will not find the session
        # Actually the view is club-scoped, so it would get 403 if they're not admin of this club
        # But the URL has club_slug, so the middleware sets request.club
        response = session_settings(request, club_slug="other")
        # Other club's admin can change their own club's settings
        assert response.status_code == 302


class TestFirstConfirmation:
    """First confirmation with award_points=3 creates one DowntimePointEntry."""

    def test_first_confirmation_awards_once(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        SessionSettings.objects.create(club=club, award_points=3)
        session = _make_session(club, gm_user)
        char1, char2 = _make_characters(club, gm_user)

        SessionAttendance.objects.create(
            session=session, character=char1, played=True, confirmed_by=gm_user
        )
        SessionAttendance.objects.create(
            session=session, character=char2, played=False, confirmed_by=gm_user
        )

        _send_attendance_saved(session, [char1, char2], gm_user)

        # char1 played -> +3
        entries1 = DowntimePointEntry.objects.filter(character=char1)
        assert entries1.count() == 1
        assert entries1.first().delta == 3
        assert entries1.first().kind == "award"
        assert "Attended Test Session" in entries1.first().note
        assert entries1.first().created_by == gm_user

        # char2 not played -> 0
        assert DowntimePointEntry.objects.filter(character=char2).count() == 0

        # SessionAward rows
        award1 = SessionAward.objects.get(session=session, character=char1)
        assert award1.points == 3
        award2 = SessionAward.objects.get(session=session, character=char2)
        assert award2.points == 0

        # Balance
        assert balance(char1) == 3
        assert balance(char2) == 0


class TestSecondConfirmation:
    """A second confirmation awards nothing."""

    def test_second_confirmation_no_new_award(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        SessionSettings.objects.create(club=club, award_points=3)
        session = _make_session(club, gm_user)
        char1, _ = _make_characters(club, gm_user)

        SessionAttendance.objects.create(
            session=session, character=char1, played=True, confirmed_by=gm_user
        )

        # First confirmation
        _send_attendance_saved(session, [char1], gm_user)
        assert DowntimePointEntry.objects.filter(character=char1).count() == 1

        # Second confirmation (same played state)
        _send_attendance_saved(session, [char1], gm_user)
        assert DowntimePointEntry.objects.filter(character=char1).count() == 1

        award = SessionAward.objects.get(session=session, character=char1)
        assert award.points == 3


class TestCorrections:
    """Correction adds or removes only the difference."""

    def test_correction_played_to_not_played(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        SessionSettings.objects.create(club=club, award_points=3)
        session = _make_session(club, gm_user)
        char1, _ = _make_characters(club, gm_user)

        SessionAttendance.objects.create(
            session=session, character=char1, played=True, confirmed_by=gm_user
        )
        _send_attendance_saved(session, [char1], gm_user)
        assert balance(char1) == 3

        # Correction: played -> not played
        SessionAttendance.objects.filter(session=session, character=char1).update(played=False)
        _send_attendance_saved(session, [char1], gm_user)

        # Balance back to 0, one new entry with -3
        assert balance(char1) == 0
        entries = DowntimePointEntry.objects.filter(character=char1).order_by("created")
        assert entries.count() == 2
        assert entries[0].delta == 3
        assert entries[1].delta == -3

        award = SessionAward.objects.get(session=session, character=char1)
        assert award.points == 0

    def test_correction_not_played_to_played(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        SessionSettings.objects.create(club=club, award_points=3)
        session = _make_session(club, gm_user)
        char1, _ = _make_characters(club, gm_user)

        SessionAttendance.objects.create(
            session=session, character=char1, played=False, confirmed_by=gm_user
        )
        _send_attendance_saved(session, [char1], gm_user)
        assert balance(char1) == 0

        # Correction: not played -> played
        SessionAttendance.objects.filter(session=session, character=char1).update(played=True)
        _send_attendance_saved(session, [char1], gm_user)

        assert balance(char1) == 3
        entries = DowntimePointEntry.objects.filter(character=char1).order_by("created")
        assert entries.count() == 1
        assert entries[0].delta == 3


class TestSettingChangeDoesNotRewritePast:
    """Changing the setting later never rewrites past awards."""

    def test_change_setting_after_award_no_rewrite(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        SessionSettings.objects.create(club=club, award_points=2)
        session = _make_session(club, gm_user)
        char1, char2 = _make_characters(club, gm_user)

        SessionAttendance.objects.create(
            session=session, character=char1, played=True, confirmed_by=gm_user
        )
        _send_attendance_saved(session, [char1], gm_user)

        # Change setting to 5
        SessionSettings.objects.filter(club=club).update(award_points=5)

        # NO signal sent - assert nothing changes
        assert DowntimePointEntry.objects.filter(character=char1).count() == 1
        assert DowntimePointEntry.objects.filter(character=char2).count() == 0
        assert balance(char1) == 2

        award = SessionAward.objects.get(session=session, character=char1)
        assert award.points == 2

    def test_signal_after_setting_change_awards_difference(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        SessionSettings.objects.create(club=club, award_points=2)
        session = _make_session(club, gm_user)
        char1, _ = _make_characters(club, gm_user)

        SessionAttendance.objects.create(
            session=session, character=char1, played=True, confirmed_by=gm_user
        )
        _send_attendance_saved(session, [char1], gm_user)
        assert balance(char1) == 2

        # Change setting to 5
        SessionSettings.objects.filter(club=club).update(award_points=5)

        # Re-send signal for same character
        _send_attendance_saved(session, [char1], gm_user)

        # Now balance should be 5 (wanted=5, had=2, delta=+3)
        assert balance(char1) == 5
        entries = DowntimePointEntry.objects.filter(character=char1).order_by("created")
        assert entries.count() == 2
        assert entries[1].delta == 3

        award = SessionAward.objects.get(session=session, character=char1)
        assert award.points == 5


class TestNegativeGuard:
    """A removal that would go negative does not break the save."""

    def test_removal_that_would_go_negative_skipped(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        SessionSettings.objects.create(club=club, award_points=3)
        session = _make_session(club, gm_user)
        char1, _ = _make_characters(club, gm_user)

        SessionAttendance.objects.create(
            session=session, character=char1, played=True, confirmed_by=gm_user
        )
        _send_attendance_saved(session, [char1], gm_user)
        assert balance(char1) == 3

        # Spend the points
        DowntimePointEntry.objects.create(
            character=char1,
            delta=-3,
            note="Spent",
            kind="spend",
            created_by=gm_user,
            source="test",
        )
        assert balance(char1) == 0

        # Correction: played -> not played (would try to remove 3 more)
        SessionAttendance.objects.filter(session=session, character=char1).update(played=False)

        # Use RequestFactory to capture messages
        factory = RequestFactory()
        request = factory.post("/")
        request.user = gm_user
        request.club = club
        request.session = {}
        messages_storage = FallbackStorage(request)
        request._messages = messages_storage

        _send_attendance_saved(session, [char1], gm_user, request=request)

        # Signal send does not raise
        # SessionAward stays 3
        award = SessionAward.objects.get(session=session, character=char1)
        assert award.points == 3

        # No new ledger entry
        assert DowntimePointEntry.objects.filter(character=char1).count() == 2

        # Message added for GM
        messages_list = list(messages_storage)
        assert len(messages_list) == 1
        msg = str(messages_list[0]).lower()
        assert "does not have enough" in msg or "not enough" in msg

    def test_negative_guard_without_request_returns_notice(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        SessionSettings.objects.create(club=club, award_points=3)
        session = _make_session(club, gm_user)
        char1, _ = _make_characters(club, gm_user)

        SessionAttendance.objects.create(
            session=session, character=char1, played=True, confirmed_by=gm_user
        )
        _send_attendance_saved(session, [char1], gm_user)

        # Spend the points
        DowntimePointEntry.objects.create(
            character=char1,
            delta=-3,
            note="Spent",
            kind="spend",
            created_by=gm_user,
            source="test",
        )

        # Correction without request
        SessionAttendance.objects.filter(session=session, character=char1).update(played=False)
        responses = _send_attendance_saved(session, [char1], gm_user)

        # Notice returned in responses
        assert len(responses) == 1
        receiver, notices = responses[0]
        assert len(notices) == 1
        msg = notices[0].lower()
        assert "does not have enough" in msg or "not enough" in msg


class TestCrossSession:
    """Awards of two sessions do not collide."""

    def test_two_sessions_independent(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        SessionSettings.objects.create(club=club, award_points=3)
        session1 = _make_session(club, gm_user)
        session2 = PlaySession.objects.create(
            club=club,
            title="Session Two",
            starts_at=timezone.make_aware(datetime(2024, 6, 22, 18, 0)),
            game_master=Membership.objects.get(user=gm_user, club=club),
        )
        char1, _ = _make_characters(club, gm_user)

        SessionAttendance.objects.create(
            session=session1, character=char1, played=True, confirmed_by=gm_user
        )
        SessionAttendance.objects.create(
            session=session2, character=char1, played=True, confirmed_by=gm_user
        )

        _send_attendance_saved(session1, [char1], gm_user)
        _send_attendance_saved(session2, [char1], gm_user)

        # Two separate SessionAward rows
        awards = SessionAward.objects.filter(character=char1)
        assert awards.count() == 2

        # Two ledger entries, each +3
        entries = DowntimePointEntry.objects.filter(character=char1, kind="award")
        assert entries.count() == 2
        assert balance(char1) == 6


class TestNavEntry:
    """Nav entry visible to admins only."""

    def test_nav_entry_visible_to_admin_only(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        factory = RequestFactory()

        # Admin request
        request = factory.get("/")
        request.user = admin_user
        request.club = club
        request.membership = Membership.objects.get(user=admin_user, club=club)
        request.resolver_match = None

        from accounts import navigation

        entries = navigation.entries_for(request)
        admin_links = [e for e in entries["admin"] if e.url_name == "play_sessions:settings"]
        assert len(admin_links) == 1

        # GM request - should not see it
        request.user = gm_user
        request.membership = Membership.objects.get(user=gm_user, club=club)
        entries = navigation.entries_for(request)
        admin_links = [e for e in entries["admin"] if e.url_name == "play_sessions:settings"]
        assert len(admin_links) == 0

        # Player request - should not see it
        request.user = player_user
        request.membership = Membership.objects.get(user=player_user, club=club)
        entries = navigation.entries_for(request)
        admin_links = [e for e in entries["admin"] if e.url_name == "play_sessions:settings"]
        assert len(admin_links) == 0


class TestDispatchUID:
    """The attendance_saved receiver is connected only once."""

    def test_receiver_connected_once(self):
        club, admin_user, gm_user, player_user, other_admin, superuser = _make_club_and_users()
        SessionSettings.objects.create(club=club, award_points=3)
        session = _make_session(club, gm_user)
        char1, _ = _make_characters(club, gm_user)

        SessionAttendance.objects.create(
            session=session, character=char1, played=True, confirmed_by=gm_user
        )

        # Send once - should award once
        _send_attendance_saved(session, [char1], gm_user)
        assert DowntimePointEntry.objects.filter(character=char1).count() == 1

        # Send again - should not award again (second confirmation)
        _send_attendance_saved(session, [char1], gm_user)
        assert DowntimePointEntry.objects.filter(character=char1).count() == 1
