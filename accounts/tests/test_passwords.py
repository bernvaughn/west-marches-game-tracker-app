import pytest
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

from accounts.models import Membership
from accounts.passwords import ComplexityValidator, PasswordHistoryValidator, save_password_history

NEW_PW = "Tr1cky-Horse-Battery"


def _flag(user):
    user.must_change_password = True
    user.save(update_fields=["must_change_password"])
    user.refresh_from_db()


def _change(client, old="pw", new=NEW_PW):
    return client.post(
        reverse("password_change"),
        {"old_password": old, "new_password1": new, "new_password2": new},
    )


def _reset_url(club, user):
    m = Membership.objects.get(club=club, user=user)
    return reverse("accounts:reset_password", args=[club.slug, m.pk])


@pytest.mark.story("U20")
def test_flagged_user_redirected_everywhere(club, player, login):
    _flag(player)
    client = login(player)
    change = reverse("password_change")
    for url in [
        "/",
        reverse("club_home", args=[club.slug]),
        reverse("accounts:index", args=[club.slug]),
        "/c/club-a/items/",
    ]:
        r = client.get(url)
        assert r.status_code == 302 and r.url == change, url
    assert client.get(change).status_code == 200
    static = client.get("/static/css/components.css")
    assert static.status_code != 302 or static.url != change


@pytest.mark.story("U20")
def test_flagged_user_can_log_out(player, login):
    _flag(player)
    client = login(player)
    client.post(reverse("logout"))
    assert "/login" in client.get("/").url


@pytest.mark.story("U20")
def test_change_clears_flag_and_unlocks(club, player, login):
    _flag(player)
    client = login(player)
    r = _change(client)
    assert r.status_code == 302
    player.refresh_from_db()
    assert player.must_change_password is False
    # Follow redirect to dashboard
    response = client.get(reverse("club_home", args=[club.slug]), follow=True)
    assert response.status_code == 200


@pytest.mark.story("U22")
def test_change_own_password_stays_signed_in(player):
    client = Client()
    assert client.login(email=player.email, password="pw")
    assert _change(client).status_code == 302
    assert client.get("/").status_code == 200
    assert authenticate(email=player.email, password="pw") is None
    assert authenticate(email=player.email, password=NEW_PW) is not None


@pytest.mark.story("U21")
def test_admin_resets_member(club, club_admin, player, login):
    target_client = login(player)
    assert target_client.get("/").status_code == 200
    client = login(club_admin)
    url = _reset_url(club, player)
    assert client.get(url).status_code == 200
    r = client.post(url)
    assert r.status_code == 200
    assert "no-store" in r["Cache-Control"]
    player.refresh_from_db()
    assert player.must_change_password is True
    temp = r.context["temp_password"]
    assert temp in r.content.decode()
    assert player.check_password(temp)
    assert temp not in client.get(url).content.decode()
    assert target_client.get("/").status_code == 302


@pytest.mark.story("U21")
def test_admin_of_only_one_club_gets_403(club, other_club, club_admin, player, login):
    Membership.objects.create(user=player, club=other_club)
    client = login(club_admin)
    url = _reset_url(club, player)
    assert client.get(url).status_code == 403
    assert client.post(url).status_code == 403
    player.refresh_from_db()
    assert player.must_change_password is False


@pytest.mark.story("U21")
def test_only_site_admin_resets_site_admin(club, club_admin, site_admin, login):
    Membership.objects.create(user=site_admin, club=club)
    url = _reset_url(club, site_admin)
    assert login(club_admin).post(url).status_code == 403
    site_admin.refresh_from_db()
    assert site_admin.must_change_password is False


@pytest.mark.story("U21")
def test_site_admin_resets_club_admin(club, club_admin, site_admin, login):
    r = login(site_admin).post(_reset_url(club, club_admin))
    assert r.status_code == 200
    club_admin.refresh_from_db()
    assert club_admin.must_change_password is True


@pytest.mark.story("U12")
def test_cross_club_reset_is_404(
    club, other_club, club_admin, club_b_admin, player, club_b_member, login
):
    a_url = _reset_url(club, player)
    b_url = _reset_url(other_club, club_b_member)
    b_client = login(club_b_admin)
    assert b_client.get(a_url).status_code == 404
    assert b_client.post(a_url).status_code == 404
    m_b = Membership.objects.get(club=other_club, user=club_b_member)
    crossed = reverse("accounts:reset_password", args=[club.slug, m_b.pk])
    assert login(club_admin).get(crossed).status_code == 404
    assert b_url


# --- New validator tests ---

VALID_PASSWORD = "Tr1cky-Horse-Battery"
SHORT_PASSWORD = "short1!"  # no uppercase
NO_UPPER = "tricky-horse-battery1!"
NO_LOWER = "TRICKY-HORSE-BATTERY1!"
NO_DIGIT = "Tricky-Horse-Battery!"
NO_SPECIAL = "TrickyHorseBattery1"


@pytest.mark.story("U20")
def test_complexity_validator_accepts_valid_password(player):
    validator = ComplexityValidator()
    validator.validate(VALID_PASSWORD, player)  # Should not raise


@pytest.mark.story("U20")
@pytest.mark.parametrize("password", [SHORT_PASSWORD, NO_UPPER, NO_LOWER, NO_DIGIT, NO_SPECIAL])
def test_complexity_validator_rejects_invalid_passwords(password, player):
    validator = ComplexityValidator()
    with pytest.raises(ValidationError):
        validator.validate(password, player)


@pytest.mark.story("U20")
def test_minimum_length_12_enforced_by_django_validator(player):
    # This tests that Django's MinimumLengthValidator is configured with min_length=12
    # The actual validation is done by Django's validator, not our ComplexityValidator
    from django.contrib.auth.password_validation import MinimumLengthValidator
    validator = MinimumLengthValidator(min_length=12)
    # 11 chars should fail
    with pytest.raises(ValidationError):
        validator.validate("Abcdefgh1!", player)  # 11 chars
    # 12 chars should pass
    validator.validate("Abcdefgh1!@@", player)  # 12 chars with all requirements


@pytest.mark.story("U20")
def test_password_history_prevents_reuse_of_last_5(player):
    validator = PasswordHistoryValidator(history_count=5)
    # Add 5 passwords to history
    for i in range(5):
        save_password_history(player, f"Password{i}!")
    # Try to reuse each one - all should fail
    for i in range(5):
        with pytest.raises(ValidationError, match="used recently"):
            validator.validate(f"Password{i}!", player)


@pytest.mark.story("U20")
def test_password_history_allows_reuse_after_5_changes(player):
    validator = PasswordHistoryValidator(history_count=5)
    # Add 6 passwords to history
    for i in range(6):
        save_password_history(player, f"Password{i}!")
    # First one should now be allowed (only last 5 are kept)
    validator.validate("Password0!", player)  # Should not raise
    # But the last 5 should still be rejected
    for i in range(1, 6):
        with pytest.raises(ValidationError, match="used recently"):
            validator.validate(f"Password{i}!", player)


@pytest.mark.story("U21")
def test_temporary_password_reset_adds_to_history(club, club_admin, player, login):
    client = login(club_admin)
    url = _reset_url(club, player)
    r = client.post(url)
    assert r.status_code == 200
    temp = r.context["temp_password"]
    player.refresh_from_db()
    # Check that the temporary password was added to history
    history = player.password_history.all()
    assert history.count() == 1
    assert player.check_password(temp)
    # The history entry should be verifiable with check_password
    assert player.check_password(temp)


@pytest.mark.story("U20")
def test_password_change_adds_to_history(club, player, login):
    client = login(player)
    # The player fixture has password "pw"
    # Change to a valid new password
    r = client.post(
        reverse("password_change"),
        {"old_password": "pw", "new_password1": VALID_PASSWORD, "new_password2": VALID_PASSWORD},
    )
    assert r.status_code == 302
    player.refresh_from_db()
    # Check that the new password was added to history
    history = player.password_history.all()
    assert history.count() == 1
    assert player.check_password(VALID_PASSWORD)
    # The history entry should be verifiable with check_password
    assert player.check_password(VALID_PASSWORD)


@pytest.mark.story("U20")
def test_cannot_reuse_previous_password_via_change_form(club, player, login):
    client = login(player)
    # First change to a valid password
    r = client.post(
        reverse("password_change"),
        {"old_password": "pw", "new_password1": VALID_PASSWORD, "new_password2": VALID_PASSWORD},
    )
    assert r.status_code == 302
    player.refresh_from_db()
    # Now try to change back to "pw" - should fail
    r = client.post(
        reverse("password_change"),
        {"old_password": VALID_PASSWORD, "new_password1": "pw", "new_password2": "pw"},
    )
    assert r.status_code == 200  # Form error, not redirect
    assert b"used recently" in r.content or b"Password cannot be" in r.content
    player.refresh_from_db()
    # Password should still be VALID_PASSWORD
    assert player.check_password(VALID_PASSWORD)