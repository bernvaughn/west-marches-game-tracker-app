import pytest
from datetime import datetime
from django.template import TemplateDoesNotExist
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions import core
from play_sessions.models import PlaySession
from player_characters.models import Character


pytestmark = [pytest.mark.django_db, pytest.mark.story("P1")]


@pytest.fixture
def club_and_session():
    club = Club.objects.create(name="Detail Club", slug="detail-club", timezone="America/New_York")
    membership = Membership.objects.create(
        user=User.objects.create_user(email="gm@test.com", password="pass12345678"),
        club=club,
        is_game_master=True,
    )
    character = Character.objects.create(name="Hero", club=club, owner=membership)
    session = PlaySession.objects.create(
        club=club,
        title="Test Session",
        starts_at=timezone.datetime(2024, 6, 15, 18, 0, tzinfo=timezone.utc),
        game_master=membership,
        location="The Tavern",
        notes="Bring dice.",
    )
    return club, membership, character, session


def test_detail_200_for_member(client, club_and_session):
    club, membership, character, session = club_and_session
    user = membership.user
    client.force_login(user)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    assert response.status_code == 200
    assert b"Test Session" in response.content
    assert b"The Tavern" in response.content


def test_detail_404_for_another_club(client, club_and_session):
    club, membership, character, session = club_and_session
    # Create another club and user
    other_club = Club.objects.create(name="Other Club", slug="other-club")
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    Membership.objects.create(user=other_user, club=other_club)
    client.force_login(other_user)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": other_club.slug, "pk": session.pk})
    response = client.get(url)
    assert response.status_code == 404


def test_detail_login_redirect(client, club_and_session):
    club, membership, character, session = club_and_session
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


def test_detail_sections_render_in_order(client, club_and_session, monkeypatch, tmp_path):
    club, membership, character, session = club_and_session
    user = membership.user
    client.force_login(user)

    # Create temporary template directory
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "section_a.html").write_text("Section A content")
    (template_dir / "section_b.html").write_text("Section B content")

    # Add to TEMPLATES DIRS
    from django.conf import settings

    original_dirs = settings.TEMPLATES[0]["DIRS"]
    settings.TEMPLATES[0]["DIRS"] = [*original_dirs, str(template_dir)]

    # Swap core._sections
    original_sections = core._sections.copy()
    core._sections.clear()
    core.register_session_section("b_section", 20, "section_b.html", lambda r, s: {})
    core.register_section_a = core.register_session_section("a_section", 10, "section_a.html", lambda r, s: {})

    try:
        url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # A should appear before B
        a_pos = content.index("Section A content")
        b_pos = content.index("Section B content")
        assert a_pos < b_pos
    finally:
        core._sections.clear()
        core._sections.update(original_sections)
        settings.TEMPLATES[0]["DIRS"] = original_dirs


def test_detail_visible_fn_false_hides_section(client, club_and_session, monkeypatch, tmp_path):
    club, membership, character, session = club_and_session
    user = membership.user
    client.force_login(user)

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "hidden_section.html").write_text("Hidden content")

    from django.conf import settings

    original_dirs = settings.TEMPLATES[0]["DIRS"]
    settings.TEMPLATES[0]["DIRS"] = [*original_dirs, str(template_dir)]

    original_sections = core._sections.copy()
    core._sections.clear()
    core.register_session_section(
        "hidden",
        10,
        "hidden_section.html",
        lambda r, s: {},
        visible_fn=lambda r, s: False,
    )

    try:
        url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
        response = client.get(url)
        assert b"Hidden content" not in response.content
    finally:
        core._sections.clear()
        core._sections.update(original_sections)
        settings.TEMPLATES[0]["DIRS"] = original_dirs


def test_detail_time_shows_in_club_zone_across_dst(client):
    # Club in America/New_York
    club = Club.objects.create(name="DST Club", slug="dst-club", timezone="America/New_York")
    membership = Membership.objects.create(
        user=User.objects.create_user(email="gm@test.com", password="pass12345678"),
        club=club,
        is_game_master=True,
    )
    client.force_login(membership.user)

    # Session before DST (EST, UTC-5): March 9, 2024 19:00 local = March 10 00:00 UTC
    session_before = PlaySession.objects.create(
        club=club,
        title="Before DST",
        starts_at=timezone.datetime(2024, 3, 10, 0, 0, tzinfo=timezone.utc),
        game_master=membership,
    )

    # Session after DST (EDT, UTC-4): March 10, 2024 19:00 local = March 10 23:00 UTC
    session_after = PlaySession.objects.create(
        club=club,
        title="After DST",
        starts_at=timezone.datetime(2024, 3, 10, 23, 0, tzinfo=timezone.utc),
        game_master=membership,
    )

    url_before = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session_before.pk})
    response_before = client.get(url_before)
    content_before = response_before.content.decode()
    assert "7:00 PM" in content_before or "19:00" in content_before
    assert "EDT" not in content_before  # Should be EST or just the zone abbreviation

    url_after = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session_after.pk})
    response_after = client.get(url_after)
    content_after = response_after.content.decode()
    assert "7:00 PM" in content_after or "19:00" in content_after


def test_detail_cancelled_badge_shows(client, club_and_session):
    club, membership, character, session = club_and_session
    session.cancelled = True
    session.save()
    user = membership.user
    client.force_login(user)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    assert b"Cancelled" in response.content
    assert b"danger" in response.content  # badge status


def test_detail_gm_notes_never_in_shell_for_player(client):
    club = Club.objects.create(name="GM Notes Club", slug="gm-notes")
    gm_user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    player_user = User.objects.create_user(email="player@test.com", password="pass12345678")
    gm_membership = Membership.objects.create(user=gm_user, club=club, is_game_master=True)
    player_membership = Membership.objects.create(user=player_user, club=club)

    session = PlaySession.objects.create(
        club=club,
        title="GM Notes Test",
        starts_at=timezone.now(),
        game_master=gm_membership,
        gm_notes="Secret GM notes here",
    )

    client.force_login(player_user)
    url = reverse("play_sessions:session_detail", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.get(url)
    assert b"Secret GM notes here" not in response.content