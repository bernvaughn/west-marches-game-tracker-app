"""Tests for the recap feature (P10)."""

from datetime import UTC

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions import core
from play_sessions.models import PlaySession
from player_characters.models import Character

pytestmark = [pytest.mark.django_db, pytest.mark.story("P10")]


@pytest.fixture
def club_and_session():
    club = Club.objects.create(name="Recap Club", slug="recap-club", timezone="America/New_York")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    player_user = User.objects.create_user(email="player@test.com", password="pass12345678")
    admin_user = User.objects.create_user(email="admin@test.com", password="pass12345678")

    gm_membership = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    player_membership = Membership.objects.create(user=player_user, club=club)
    admin_membership = Membership.objects.create(user=admin_user, club=club, is_club_admin=True)

    character = Character.objects.create(name="Hero", club=club, owner=player_membership)
    gm_character = Character.objects.create(name="GM Hero", club=club, owner=gm_membership)

    session = PlaySession.objects.create(
        club=club,
        title="Test Session",
        starts_at=timezone.datetime(2024, 6, 15, 18, 0, tzinfo=UTC),
        game_master=gm_membership,
        recap="Session recap text here.",
        gm_notes="Secret GM notes here.",
    )
    return {
        "club": club,
        "gm_user": gm_user,
        "gm_membership": gm_membership,
        "gm_character": gm_character,
        "player_user": player_user,
        "player_membership": player_membership,
        "character": character,
        "admin_user": admin_user,
        "admin_membership": admin_membership,
        "session": session,
    }


def test_player_sees_recap_not_gm_notes(client, club_and_session):
    """Player sees recap on session page; gm_notes never in HTML."""
    player_user = club_and_session["player_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert b"Session recap text here." in response.content
    assert b"Secret GM notes here." not in response.content
    assert b"GM notes" not in response.content


def test_player_another_character_no_gm_notes(client, club_and_session):
    """Member who is only a player of another character sees no gm_notes."""
    player_user = club_and_session["player_user"]
    player_membership = club_and_session["player_membership"]
    club = club_and_session["club"]
    session = club_and_session["session"]

    Character.objects.create(name="Other Hero", club=club, owner=player_membership)

    client.force_login(player_user)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert b"Session recap text here." in response.content
    assert b"Secret GM notes here." not in response.content
    assert b"GM notes" not in response.content


def test_gm_sees_gm_notes_and_edit_link(client, club_and_session):
    """GM sees gm_notes and edit link on session page."""
    gm_user = club_and_session["gm_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    client.force_login(gm_user)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert b"Session recap text here." in response.content
    assert b"Secret GM notes here." in response.content
    assert b"GMs and admins only" in response.content
    assert b"Edit recap and notes" in response.content


def test_admin_sees_gm_notes_and_edit_link(client, club_and_session):
    """Club admin sees gm_notes and edit link."""
    admin_user = club_and_session["admin_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    client.force_login(admin_user)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert b"Secret GM notes here." in response.content
    assert b"Edit recap and notes" in response.content


def test_superuser_sees_gm_notes_and_edit_link(client, club_and_session):
    """Superuser sees gm_notes and edit link."""
    superuser = User.objects.create_superuser(email="super@test.com", password="pass12345678")
    session = club_and_session["session"]
    club = club_and_session["club"]

    client.force_login(superuser)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert b"Secret GM notes here." in response.content
    assert b"Edit recap and notes" in response.content


def test_player_get_recap_edit_403(client, club_and_session):
    """Player GET to recap_edit returns 403."""
    player_user = club_and_session["player_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:recap_edit", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)

    assert response.status_code == 403


def test_player_post_recap_edit_403_db_unchanged(client, club_and_session):
    """Player POST to recap_edit returns 403 and DB unchanged."""
    player_user = club_and_session["player_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:recap_edit", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"recap": "Hacked", "gm_notes": "Hacked notes"})

    assert response.status_code == 403
    session.refresh_from_db()
    assert session.recap == "Session recap text here."
    assert session.gm_notes == "Secret GM notes here."


def test_anonymous_recap_edit_redirects_to_login(client, club_and_session):
    """Anonymous user redirected to login."""
    session = club_and_session["session"]
    club = club_and_session["club"]

    url = reverse("play_sessions:recap_edit", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)

    assert response.status_code == 302
    assert "/accounts/login/" in response.url


def test_gm_post_saves_both_fields_and_redirects(client, club_and_session):
    """GM POST saves both fields and redirects to session detail."""
    gm_user = club_and_session["gm_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    client.force_login(gm_user)
    url = reverse("play_sessions:recap_edit", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"recap": "New recap", "gm_notes": "New GM notes"})

    assert response.status_code == 302
    assert "#section-recap" in response.url
    session.refresh_from_db()
    assert session.recap == "New recap"
    assert session.gm_notes == "New GM notes"


def test_admin_post_saves_both_fields(client, club_and_session):
    """Admin POST saves both fields."""
    admin_user = club_and_session["admin_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    client.force_login(admin_user)
    url = reverse("play_sessions:recap_edit", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"recap": "Admin recap", "gm_notes": "Admin GM notes"})

    assert response.status_code == 302
    session.refresh_from_db()
    assert session.recap == "Admin recap"
    assert session.gm_notes == "Admin GM notes"


def test_gm_edit_form_contains_gm_notes(client, club_and_session):
    """Edit form for GM contains gm_notes field."""
    gm_user = club_and_session["gm_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    client.force_login(gm_user)
    url = reverse("play_sessions:recap_edit", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert b"Secret GM notes here." in response.content
    assert b"Only game masters and club admins can see this" in response.content


def test_past_session_editable(client, club_and_session):
    """Past session is editable."""
    gm_user = club_and_session["gm_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    session.starts_at = timezone.now() - timezone.timedelta(days=1)
    session.save()

    client.force_login(gm_user)
    url = reverse("play_sessions:recap_edit", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"recap": "Past recap", "gm_notes": "Past notes"})

    assert response.status_code == 302
    session.refresh_from_db()
    assert session.recap == "Past recap"


def test_future_session_editable(client, club_and_session):
    """Future session is editable."""
    gm_user = club_and_session["gm_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    session.starts_at = timezone.now() + timezone.timedelta(days=10)
    session.save()

    client.force_login(gm_user)
    url = reverse("play_sessions:recap_edit", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"recap": "Future recap", "gm_notes": "Future notes"})

    assert response.status_code == 302
    session.refresh_from_db()
    assert session.recap == "Future recap"


def test_cancelled_session_editable(client, club_and_session):
    """Cancelled session is editable."""
    gm_user = club_and_session["gm_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    session.cancelled = True
    session.save()

    client.force_login(gm_user)
    url = reverse("play_sessions:recap_edit", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"recap": "Cancelled recap", "gm_notes": "Cancelled notes"})

    assert response.status_code == 302
    session.refresh_from_db()
    assert session.recap == "Cancelled recap"


def test_another_club_session_404_for_gm(client, club_and_session):
    """GM of a different club gets 404 for this session."""
    session = club_and_session["session"]

    other_club = Club.objects.create(name="Other Club", slug="other-club")
    other_gm_user = User.objects.create_user(email="othergm@test.com", password="pass12345678")
    Membership.objects.create(user=other_gm_user, club=other_club, is_game_master=True)

    client.force_login(other_gm_user)
    url = reverse(
        "play_sessions:recap_edit",
        kwargs={"club_slug": other_club.slug, "pk": session.pk},
    )
    response = client.get(url)

    assert response.status_code == 404


def test_html_in_recap_is_escaped(client, club_and_session):
    """HTML in recap is escaped (script tag)."""
    player_user = club_and_session["player_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    session.recap = '<script>alert("xss")</script>'
    session.save()

    client.force_login(player_user)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)

    # The script tag should be escaped, not rendered as HTML
    assert b"<script>" not in response.content
    # The content should be present but escaped (no raw script tag)
    # Check that the text content appears (escaped)
    assert b"xss" in response.content


def test_player_empty_recap_no_section(client, club_and_session):
    """Player with empty recap: no recap section rendered."""
    player_user = club_and_session["player_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    session.recap = ""
    session.save()

    client.force_login(player_user)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)

    assert response.status_code == 200
    # The recap section should not be rendered at all for players with empty recap
    assert b'id="section-recap"' not in response.content
    assert b"No recap yet" not in response.content


def test_gm_empty_recap_sees_no_recap_yet(client, club_and_session):
    """GM with empty recap sees 'No recap yet'."""
    gm_user = club_and_session["gm_user"]
    session = club_and_session["session"]
    club = club_and_session["club"]

    session.recap = ""
    session.save()

    client.force_login(gm_user)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert b"No recap yet." in response.content
    assert b"Edit recap and notes" in response.content


def test_hooks_recap_registered():
    """hooks_recap.register() registers the section."""
    original_sections = core._sections.copy()
    core._sections.clear()

    try:
        from play_sessions import hooks_recap

        hooks_recap.register()

        assert "recap" in core._sections
        section = core._sections["recap"]
        assert section["key"] == "recap"
        assert section["order"] == 80
        assert section["template"] == "play_sessions/_recap_section.html"
    finally:
        core._sections.clear()
        core._sections.update(original_sections)
