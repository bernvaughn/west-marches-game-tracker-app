"""Admin editing theme for the play_sessions app.

Covers PlaySession, PlayerRSVP, AttendanceHint, SessionAttendance,
SessionAward and SessionSettings admins. AttendanceChangeAdmin is
read-only and left unchanged.

For each model: GET the changelist, add form and change form as a
superuser. Assert the configured FK widgets render in the change form
(admin-autocomplete for autocomplete_fields). POST a valid change for
PlaySession and assert it saves with the three inline formsets (management
form TOTAL_FORMS=0). Assert run_checks() raises no admin errors.

SessionAttendance.confirmed_by stays editable by design; only confirmed_at
is read-only as an auto-set stamp.
"""

from datetime import timedelta

import pytest
from django.contrib import admin
from django.core.checks import run_checks
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership
from play_sessions.models import (
    AttendanceHint,
    PlayerRSVP,
    PlaySession,
    SessionAttendance,
    SessionAward,
    SessionSettings,
)

pytestmark = pytest.mark.django_db

# (model, admin URL name, expected add-form status).
_ADMIN_MODELS = [
    (PlaySession, "playsession", 200),
    (PlayerRSVP, "playerrsvp", 200),
    (AttendanceHint, "attendancehint", 200),
    (SessionAttendance, "sessionattendance", 200),
    (SessionAward, "sessionaward", 200),
    (SessionSettings, "sessionsettings", 200),
]


def _instance(model_name, club, game_master, character, player):
    now = timezone.now()
    # game_master fixture returns a User; get the Membership for this club
    gm_membership = Membership.objects.get(user=game_master, club=club)
    # player fixture returns a User; get the Membership for this club
    player_membership = Membership.objects.get(user=player, club=club)

    if model_name == "playsession":
        return PlaySession.objects.create(
            club=club,
            title="Test Session",
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=1, hours=4),
            game_master=gm_membership,
            location="Test Location",
        )
    if model_name == "playerrsvp":
        session = PlaySession.objects.create(
            club=club,
            title="RSVP Session",
            starts_at=now + timedelta(days=1),
            game_master=gm_membership,
        )
        return PlayerRSVP.objects.create(
            session=session, member=player_membership, answer="yes", answered_by=player
        )
    if model_name == "attendancehint":
        session = PlaySession.objects.create(
            club=club,
            title="Hint Session",
            starts_at=now + timedelta(days=1),
            game_master=gm_membership,
        )
        return AttendanceHint.objects.create(session=session, character=character)
    if model_name == "sessionattendance":
        session = PlaySession.objects.create(
            club=club,
            title="Attendance Session",
            starts_at=now + timedelta(days=1),
            game_master=gm_membership,
        )
        return SessionAttendance.objects.create(
            session=session, character=character, played=True, confirmed_by=player
        )
    if model_name == "sessionaward":
        session = PlaySession.objects.create(
            club=club,
            title="Award Session",
            starts_at=now + timedelta(days=1),
            game_master=gm_membership,
        )
        return SessionAward.objects.create(session=session, character=character, points=5)
    if model_name == "sessionsettings":
        return SessionSettings.objects.create(club=club, award_points=10)
    raise ValueError(model_name)


@pytest.mark.parametrize("model,url_name,add_status", _ADMIN_MODELS)
def test_admin_pages(
    model,
    url_name,
    add_status,
    login,
    site_admin,
    club,
    game_master,
    character,
    player,
):
    """Changelist, add form and change form load for every play_sessions admin."""
    client = login(site_admin)
    instance = _instance(url_name, club, game_master, character, player)

    assert client.get(reverse(f"admin:play_sessions_{url_name}_changelist")).status_code == 200
    assert client.get(reverse(f"admin:play_sessions_{url_name}_add")).status_code == add_status
    assert (
        client.get(
            reverse(f"admin:play_sessions_{url_name}_change", args=[instance.pk])
        ).status_code
        == 200
    )


@pytest.mark.parametrize("model,url_name,add_status", _ADMIN_MODELS)
def test_admin_fk_widgets(
    model,
    url_name,
    add_status,
    login,
    site_admin,
    club,
    game_master,
    character,
    player,
):
    """Declared autocomplete FK widgets render on the change form."""
    client = login(site_admin)
    instance = _instance(url_name, club, game_master, character, player)
    model_admin = admin.site._registry[model]

    response = client.get(reverse(f"admin:play_sessions_{url_name}_change", args=[instance.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    for field in model_admin.autocomplete_fields:
        assert f'data-field-name="{field}"' in content
        assert "admin-autocomplete" in content


def test_playsession_change_form_fieldsets_and_inlines(
    login, site_admin, club, game_master, character, player
):
    """PlaySession change form renders the three fieldsets and three inlines."""
    gm_membership = Membership.objects.get(user=game_master, club=club)
    session = PlaySession.objects.create(
        club=club,
        title="Fieldset Session",
        starts_at=timezone.now() + timedelta(days=1),
        game_master=gm_membership,
    )
    client = login(site_admin)
    response = client.get(reverse("admin:play_sessions_playsession_change", args=[session.pk]))
    assert response.status_code == 200
    content = response.content.decode()

    # Fieldset titles
    assert "Main" in content
    assert "Schedule" in content
    assert "Notes" in content
    # Notes fieldset is collapsed
    assert "collapse" in content

    # Inline formset prefixes (related_name values)
    assert "player_rsvps" in content
    assert "attendance" in content
    assert "awards" in content


def test_playsession_admin_change_saves_with_inlines(
    login, site_admin, club, game_master, character, player
):
    """POSTing a valid PlaySession change with empty inline formsets saves."""
    gm_membership = Membership.objects.get(user=game_master, club=club)
    session = PlaySession.objects.create(
        club=club,
        title="Original Title",
        starts_at=timezone.now() + timedelta(days=1),
        game_master=gm_membership,
        location="Old Location",
        notes="Old notes",
    )
    client = login(site_admin)
    tomorrow = timezone.now() + timedelta(days=2)
    data = {
        "club": club.pk,
        "title": "Updated Title",
        "game_master": gm_membership.pk,
        "cancelled": False,
        "starts_at_0": tomorrow.strftime("%Y-%m-%d"),
        "starts_at_1": tomorrow.strftime("%H:%M:%S"),
        "ends_at_0": "",
        "ends_at_1": "",
        "location": "New Location",
        "notes": "New notes",
        "recap": "",
        "gm_notes": "",
        # Management form fields for the three inlines (extra=0, so TOTAL_FORMS=0)
        "player_rsvps-TOTAL_FORMS": "0",
        "player_rsvps-INITIAL_FORMS": "0",
        "player_rsvps-MIN_NUM_FORMS": "0",
        "player_rsvps-MAX_NUM_FORMS": "1000",
        "attendance-TOTAL_FORMS": "0",
        "attendance-INITIAL_FORMS": "0",
        "attendance-MIN_NUM_FORMS": "0",
        "attendance-MAX_NUM_FORMS": "1000",
        "awards-TOTAL_FORMS": "0",
        "awards-INITIAL_FORMS": "0",
        "awards-MIN_NUM_FORMS": "0",
        "awards-MAX_NUM_FORMS": "1000",
    }
    response = client.post(
        reverse("admin:play_sessions_playsession_change", args=[session.pk]), data
    )
    if response.status_code != 302:
        # Debug: print form errors
        if (
            hasattr(response, "context_data")
            and response.context_data
            and "adminform" in response.context_data
        ):
            form = response.context_data["adminform"].form
            print(f"Form errors: {form.errors}")
        elif hasattr(response, "context_data") and response.context_data:
            print(f"Context keys: {list(response.context_data.keys())}")
        else:
            # TemplateResponse needs to be rendered first
            if hasattr(response, "render"):
                response.render()
            if (
                hasattr(response, "context_data")
                and response.context_data
                and "adminform" in response.context_data
            ):
                form = response.context_data["adminform"].form
                print(f"Form errors after render: {form.errors}")
            else:
                print(f"Response status: {response.status_code}")
                print(response.content.decode()[:3000])
    assert response.status_code == 302
    session.refresh_from_db()
    assert session.title == "Updated Title"
    assert session.location == "New Location"
    assert session.notes == "New notes"


def test_admin_checks_have_no_errors():
    """django.core.checks.run_checks() reports no admin errors."""
    errors = [error for error in run_checks() if error.id.startswith("admin.")]
    assert not errors, [str(error) for error in errors]
