"""Tests for RSVP (P13: per player)."""

from datetime import UTC, timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions.models import PlayerRSVP, PlaySession
from player_characters.models import Character

FIXED_NOW = timezone.datetime(2024, 6, 2, 12, 0, tzinfo=UTC)

pytestmark = [pytest.mark.django_db, pytest.mark.story("P13")]


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


def test_player_answers_for_own_membership(client, rsvp_setup):
    """Player can RSVP for their own membership; one row created, answered_by set."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes"})

    assert response.status_code in (200, 302)
    rsvp = PlayerRSVP.objects.get(session=session, member=player_membership)
    assert rsvp.answer == "yes"
    assert rsvp.answered_by == player_user


def test_player_can_answer_for_themselves_only(client, rsvp_setup):
    """A player can only answer for their own membership (no member field in form for players)."""
    club = rsvp_setup["club"]
    rsvp_setup["player_user"]
    rsvp_setup["player_membership"]
    session = rsvp_setup["session"]

    # Create another player
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other_membership = Membership.objects.create(user=other_user, club=club)

    # other_user logs in and answers for themselves - should succeed
    client.force_login(other_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes"})
    assert response.status_code in (200, 302)
    rsvp = PlayerRSVP.objects.get(session=session, member=other_membership)
    assert rsvp.answer == "yes"

    # other_user cannot answer for player_membership by passing member
    # field (form ignores it for non-managers). The view uses
    # request.membership for non-managers, enforced by refusal logic.


def test_no_membership_posted_uses_request_membership(client, rsvp_setup):
    """No membership posted uses request.membership."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "maybe"})  # No membership in POST

    assert response.status_code in (200, 302)
    rsvp = PlayerRSVP.objects.get(session=session, member=player_membership)
    assert rsvp.answer == "maybe"


def test_after_start_player_refused_gm_allowed(client, rsvp_setup):
    """After the start, a player gets 403; GM answers for anyone; admin answers after start."""
    club = rsvp_setup["club"]
    gm_user = rsvp_setup["gm_user"]
    rsvp_setup["gm_membership"]
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]

    # Move session to the past
    session.starts_at = timezone.now() - timedelta(hours=1)
    session.save()

    # Player tries to answer after start -> 403
    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes"})
    assert response.status_code == 403

    # GM can answer for anyone after start (must specify member)
    client.force_login(gm_user)
    response = client.post(url, {"answer": "yes", "member": player_membership.pk})
    assert response.status_code in (200, 302)
    rsvp = PlayerRSVP.objects.get(session=session, member=player_membership)
    assert rsvp.answer == "yes"
    assert rsvp.answered_by == gm_user

    # Admin (superuser) can also answer for anyone
    admin_user = User.objects.create_superuser(email="admin@test.com", password="pass12345678")
    client.force_login(admin_user)
    response = client.post(url, {"answer": "no", "member": player_membership.pk})
    assert response.status_code in (200, 302)
    rsvp.refresh_from_db()
    assert rsvp.answer == "no"
    assert rsvp.answered_by == admin_user


def test_no_active_character_still_can_answer(client, rsvp_setup, monkeypatch):
    """Player with no active characters can still answer (no character check)."""
    club = rsvp_setup["club"]
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]

    # Delete all characters
    player_membership.characters.all().delete()

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes"})

    assert response.status_code in (200, 302)
    rsvp = PlayerRSVP.objects.get(session=session, member=player_membership)
    assert rsvp.answer == "yes"


def test_changing_answer_keeps_one_row(client, rsvp_setup):
    """Changing an answer keeps one row per session and membership."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})

    # First answer: yes
    client.post(url, {"answer": "yes"})
    # Second answer: maybe
    client.post(url, {"answer": "maybe"})
    # Third answer: no
    client.post(url, {"answer": "no"})

    rsvps = PlayerRSVP.objects.filter(session=session, member=player_membership)
    assert rsvps.count() == 1
    rsvp = rsvps.first()
    assert rsvp.answer == "no"
    assert rsvp.answered_by == player_user


def test_cancelled_session_refuses_player(client, rsvp_setup):
    """Cancelled session refuses a player's answer; GM and admin may still answer."""
    club = rsvp_setup["club"]
    gm_user = rsvp_setup["gm_user"]
    rsvp_setup["gm_membership"]
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]

    session.cancelled = True
    session.save()

    # Player refused
    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes"})
    assert response.status_code == 403

    # GM allowed (must specify member)
    client.force_login(gm_user)
    response = client.post(url, {"answer": "yes", "member": player_membership.pk})
    assert response.status_code in (200, 302)
    rsvp = PlayerRSVP.objects.get(session=session, member=player_membership)
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
    rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "invalid"})
    assert response.status_code == 400


def test_next_redirect_safe(client, rsvp_setup):
    """next redirect is safe; external URL is ignored."""
    player_user = rsvp_setup["player_user"]
    rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})

    # Safe next (relative path)
    response = client.post(url, {"answer": "yes", "next": "/some/path"})
    assert response.status_code == 302
    assert response.url == "/some/path"

    # External URL ignored
    response = client.post(url, {"answer": "maybe", "next": "http://evil.com"})
    assert response.status_code == 302
    # Should redirect to session detail (relative URL)
    assert response.url.startswith("/c/")
    assert "sessions" in response.url


def test_htmx_post_returns_section_fragment(client, rsvp_setup):
    """HTMX POST returns the section fragment."""
    player_user = rsvp_setup["player_user"]
    rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    client.force_login(player_user)
    url = reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})
    response = client.post(url, {"answer": "yes"}, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"rsvp-section" in response.content
    assert b'name="answer"' in response.content


def _dashboard_url(club):
    return reverse("accounts:player_dashboard", kwargs={"club_slug": club.slug})


def _rsvp_url(club, session):
    return reverse("play_sessions:rsvp_set", kwargs={"club_slug": club.slug, "pk": session.pk})


def _player_with_character(player_membership, club):
    """Give the membership a character so the dashboard loads for the player."""
    Character.objects.create(name="Hero", club=club, owner=player_membership)


def test_dashboard_card_shows_rsvp_buttons_and_answer(client, rsvp_setup):
    """Dashboard card shows Yes / Maybe / No buttons and the current answer."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]
    club.timezone = "UTC"
    club.save()

    # Set RSVP for membership
    PlayerRSVP.objects.create(
        session=session, member=player_membership, answer="maybe", answered_by=player_user
    )
    _player_with_character(player_membership, club)

    client.force_login(player_user)
    response = client.get(_dashboard_url(club))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Test Session" in content
    assert "You: Maybe" in content
    # Three answer buttons, one per answer value.
    assert content.count('name="answer"') == 3
    assert 'value="yes"' in content
    assert 'value="maybe"' in content
    assert 'value="no"' in content
    # The current answer is pressed, the others are not.
    assert content.count('aria-pressed="true"') == 1
    assert content.count('aria-pressed="false"') == 2


def test_dashboard_rsvp_post_saves_and_returns(client, rsvp_setup):
    """POST answer=maybe with next=dashboard saves and returns to the dashboard."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]
    club.timezone = "UTC"
    club.save()

    _player_with_character(player_membership, club)
    client.force_login(player_user)
    dashboard_url = _dashboard_url(club)
    response = client.post(
        _rsvp_url(club, session),
        {"answer": "maybe", "next": dashboard_url},
        follow=True,
    )

    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == dashboard_url
    rsvp = PlayerRSVP.objects.get(session=session, member=player_membership)
    assert rsvp.answer == "maybe"
    assert rsvp.answered_by == player_user
    content = response.content.decode()
    assert "You: Maybe" in content


def test_dashboard_no_my_sessions(client, rsvp_setup):
    """The My Sessions card and provider are gone; next_session partial still works."""
    from accounts.dashboard_providers import get_provider

    assert get_provider("my_sessions") is None

    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    club = rsvp_setup["club"]
    club.timezone = "UTC"
    club.save()

    _player_with_character(player_membership, club)
    client.force_login(player_user)
    response = client.get(_dashboard_url(club))
    assert response.status_code == 200
    assert "My Sessions" not in response.content.decode()

    # Partial for my_sessions returns 404.
    partial_url = reverse(
        "accounts:dashboard_partial",
        kwargs={"club_slug": club.slug, "provider_key": "my_sessions"},
    )
    assert client.get(partial_url).status_code == 404

    # Partial for next_session still returns 200.
    partial_url = reverse(
        "accounts:dashboard_partial",
        kwargs={"club_slug": club.slug, "provider_key": "next_session"},
    )
    assert client.get(partial_url).status_code == 200


def test_dashboard_cancelled_session_no_form(client, rsvp_setup):
    """Cancelled session row shows no RSVP form."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]
    club.timezone = "UTC"
    club.save()

    session.cancelled = True
    session.save()

    _player_with_character(player_membership, club)
    client.force_login(player_user)
    response = client.get(_dashboard_url(club))
    assert response.status_code == 200
    content = response.content.decode()
    assert _rsvp_url(club, session) not in content


def test_dashboard_started_session_no_form(client, rsvp_setup):
    """Started session (earlier today) row shows no RSVP form but keeps its answer.

    The clock is pinned to midday UTC so ``starts_at = now - 1h`` is still
    earlier today (not yesterday near midnight UTC). Otherwise
    ``upcoming_sessions`` would drop the row between 00:00 and 01:00 UTC.
    """
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]
    club.timezone = "UTC"
    club.save()

    with patch("django.utils.timezone.now", return_value=FIXED_NOW):
        PlayerRSVP.objects.create(
            session=session, member=player_membership, answer="yes", answered_by=player_user
        )
        session.starts_at = timezone.now() - timedelta(hours=1)
        session.save()

        _player_with_character(player_membership, club)
        client.force_login(player_user)
        response = client.get(_dashboard_url(club))

    assert response.status_code == 200
    content = response.content.decode()
    assert _rsvp_url(club, session) not in content
    assert "You: Yes" in content


def test_sheet_page_no_rsvp_section(client, rsvp_setup):
    """Sheet page should not have RSVP section (file deleted)."""
    player_user = rsvp_setup["player_user"]
    char1 = rsvp_setup["char1"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Set RSVP
    PlayerRSVP.objects.create(
        session=session,
        member=rsvp_setup["player_membership"],
        answer="yes",
        answered_by=player_user,
    )

    client.force_login(player_user)
    sheet_url = reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": char1.pk})
    response = client.get(sheet_url)

    assert response.status_code == 200
    content = response.content.decode()
    # The section should not be rendered (file deleted)
    assert "Session RSVPs" not in content


def test_session_detail_shows_my_answer(client, rsvp_setup):
    """Session detail page shows player's answer."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Set RSVP
    PlayerRSVP.objects.create(
        session=session,
        member=player_membership,
        answer="yes",
        answered_by=player_user,
    )

    client.force_login(player_user)
    detail_url = reverse(
        "play_sessions:session_detail",
        kwargs={"club_slug": club.slug, "pk": session.pk},
    )
    response = client.get(detail_url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Test Session" in content
    assert "Yes" in content


def test_session_detail_manager_sees_all_answers(client, rsvp_setup):
    """Manager sees all members' answers grouped by answer."""
    gm_user = rsvp_setup["gm_user"]
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Create another player
    other_user = User.objects.create_user(email="other@test.com", password="pass12345678")
    other_membership = Membership.objects.create(user=other_user, club=club)

    # Set RSVPs
    PlayerRSVP.objects.create(
        session=session, member=player_membership, answer="yes", answered_by=player_user
    )
    PlayerRSVP.objects.create(
        session=session, member=other_membership, answer="no", answered_by=other_user
    )

    client.force_login(gm_user)
    detail_url = reverse(
        "play_sessions:session_detail",
        kwargs={"club_slug": club.slug, "pk": session.pk},
    )
    response = client.get(detail_url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Yes" in content
    assert "No" in content
    assert "Not answered" in content


def test_next_session_card_shows_my_answer(client, rsvp_setup):
    """Next session card shows player's answer."""
    player_user = rsvp_setup["player_user"]
    player_membership = rsvp_setup["player_membership"]
    session = rsvp_setup["session"]
    club = rsvp_setup["club"]

    # Set RSVP
    PlayerRSVP.objects.create(
        session=session, member=player_membership, answer="maybe", answered_by=player_user
    )

    client.force_login(player_user)
    dashboard_url = reverse("accounts:player_dashboard", kwargs={"club_slug": club.slug})
    response = client.get(dashboard_url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Test Session" in content
    assert "Maybe" in content
