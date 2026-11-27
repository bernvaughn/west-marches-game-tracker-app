"""Tests for contact email (E10)."""

import pytest
from django.urls import reverse

from accounts.models import Club
from mail.models import ClubMailSettings

pytestmark = [pytest.mark.django_db, pytest.mark.story("E10")]


def _login(client, user):
    client.force_login(user)
    return client


def test_contact_email_get_requires_club_admin(club_admin, player, login, club):
    """Only club admins can access the contact email view."""
    url = reverse("mail:contact_email", args=[club.slug])

    # Club admin - should work
    c = _login(login(club_admin), club_admin)
    r = c.get(url)
    assert r.status_code == 200

    # Player - should get 403
    c = _login(login(player), player)
    r = c.get(url)
    assert r.status_code == 403


def test_contact_email_get_shows_current_value(club_admin, login, club):
    """GET shows the currently saved contact email."""
    ClubMailSettings.objects.create(club=club, contact_email="contact@club.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:contact_email", args=[club.slug])
    r = c.get(url)
    assert r.status_code == 200
    body = r.content.decode()
    assert "contact@club.com" in body


def test_contact_email_post_shows_saved_confirmation(club_admin, login, club):
    """POST save shows a saved confirmation and updates the DB."""
    c = _login(login(club_admin), club_admin)
    url = reverse("mail:contact_email", args=[club.slug])
    r = c.post(url, {"contact_email": "contact@club.com"})
    assert r.status_code == 200
    body = r.content.decode()
    assert "Contact email saved" in body
    assert "{{" not in body, "template variable was not expanded in the alert text"
    assert "The contact email is now contact@club.com." in body

    settings = ClubMailSettings.objects.get(club=club)
    assert settings.contact_email == "contact@club.com"


def test_contact_email_post_blank_shows_cleared_confirmation(club_admin, login, club):
    """POST blank shows a cleared confirmation and clears the DB."""
    ClubMailSettings.objects.create(club=club, contact_email="old@club.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:contact_email", args=[club.slug])
    r = c.post(url, {"contact_email": ""})
    assert r.status_code == 200
    body = r.content.decode()
    assert "Contact email cleared" in body

    settings = ClubMailSettings.objects.get(club=club)
    assert settings.contact_email == ""


def test_contact_email_card_labels_db_table(club_admin, login, club):
    """Card labels ClubMailSettings as the database table."""
    ClubMailSettings.objects.create(club=club, contact_email="contact@club.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:contact_email", args=[club.slug])
    r = c.get(url)
    assert r.status_code == 200
    body = r.content.decode()
    assert "ClubMailSettings" in body
    assert "contact_email" in body


def test_contact_email_post_valid_email(club_admin, login, club):
    """Club admin can set a valid contact email."""
    c = _login(login(club_admin), club_admin)
    url = reverse("mail:contact_email", args=[club.slug])
    r = c.post(url, {"contact_email": "contact@club.com"})
    assert r.status_code == 200

    settings = ClubMailSettings.objects.get(club=club)
    assert settings.contact_email == "contact@club.com"


def test_contact_email_post_blank_clears(club_admin, login, club):
    """Club admin can clear the contact email by submitting blank."""
    # First set an email
    ClubMailSettings.objects.create(club=club, contact_email="old@club.com")

    c = _login(login(club_admin), club_admin)
    url = reverse("mail:contact_email", args=[club.slug])
    r = c.post(url, {"contact_email": ""})
    assert r.status_code == 200

    settings = ClubMailSettings.objects.get(club=club)
    assert settings.contact_email == ""


def test_contact_email_post_invalid_email_rejected(club_admin, login, club):
    """Invalid email address is rejected."""
    c = _login(login(club_admin), club_admin)
    url = reverse("mail:contact_email", args=[club.slug])
    r = c.post(url, {"contact_email": "not-an-email"})
    assert r.status_code == 400
    assert "valid email" in r.content.decode()

    settings = ClubMailSettings.objects.get(club=club)
    assert settings.contact_email == ""


def test_contact_email_htmx_returns_partial(club_admin, login, club):
    """HTMX requests return the card partial."""
    c = _login(login(club_admin), club_admin)
    url = reverse("mail:contact_email", args=[club.slug])
    r = c.post(url, {"contact_email": "contact@club.com"}, HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Contact email" in body
    assert "contact@club.com" in body


def test_new_club_form_sets_contact_email(site_admin, login):
    """Site admin can set contact email when creating a new club."""
    c = _login(login(site_admin), site_admin)
    url = reverse("site_club_new")
    r = c.post(
        url,
        {
            "name": "Test Club",
            "slug": "",
            "admin_email": "admin@test.com",
            "admin_display_name": "Admin",
            "timezone": "UTC",
            "contact_email": "club@test.com",
        },
    )
    assert r.status_code == 200
    club = Club.objects.get(slug="test-club")
    settings = ClubMailSettings.objects.get(club=club)
    assert settings.contact_email == "club@test.com"


def test_new_club_form_contact_email_optional(site_admin, login):
    """Contact email is optional on new club form."""
    c = _login(login(site_admin), site_admin)
    url = reverse("site_club_new")
    r = c.post(
        url,
        {
            "name": "Test Club 2",
            "slug": "",
            "admin_email": "admin2@test.com",
            "admin_display_name": "Admin",
            "timezone": "UTC",
            "contact_email": "",
        },
    )
    assert r.status_code == 200
    club = Club.objects.get(slug="test-club-2")
    settings = ClubMailSettings.objects.get(club=club)
    assert settings.contact_email == ""


def test_contact_email_not_shown_on_player_page(club_admin, player, login, club):
    """Contact email is never shown on player-facing pages."""
    c = _login(login(player), player)
    # Try a player page - club home
    from django.urls import reverse

    url = reverse("club_home", args=[club.slug])
    r = c.get(url, follow=True)
    body = r.content.decode()
    assert "Contact email" not in body
    assert "contact@club.com" not in body


def test_contact_email_not_shown_on_character_page(club_admin, player, login, club, character):
    """Contact email is never shown on character pages."""
    c = _login(login(player), player)
    url = reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.id})
    r = c.get(url)
    body = r.content.decode()
    assert "Contact email" not in body
    assert "contact@club.com" not in body


def test_contact_email_used_as_reply_to(club_admin, login, club, settings):
    """Contact email is used as reply-to on queued emails."""
    settings.MAIL_ENABLED = True
    ClubMailSettings.objects.create(club=club, contact_email="reply@club.com")

    from mail.service import queue_email

    result = queue_email(
        kind="welcome",
        to="player@test.com",
        club=club,
        subject="Test",
        text="Hello",
    )
    assert result.status == "queued"
    assert result.message.payload.reply_to == "reply@club.com"
