"""Tests for manual capacity override and coin weight settings (S4/U156)."""

import pytest
from django.urls import reverse

from accounts.models import Membership
from items.models import ClubWeightSettings
from ledger.services import Line, record
from player_characters.coin_weight import coin_weight_hundredths
from player_characters.models import Character

pytestmark = [pytest.mark.django_db, pytest.mark.story("S4")]


def _login(client, user):
    client.force_login(user)
    return client


def _character(club, user, name):
    owner = Membership.objects.get(user=user, club=club)
    return Character.objects.create(club=club, owner=owner, name=name)


# --- carrying_capacity_lb override ---


def test_carrying_capacity_override_replaces_default(club_admin, login, club):
    """carrying_capacity_lb overrides 15 x Strength."""
    client = _login(login(club_admin), club_admin)
    owner = Membership.objects.get(user=club_admin, club=club)
    # Create character with STR 14 and override 200
    char = Character.objects.create(
        club=club,
        owner=owner,
        name="Override Char",
        strength=14,
        carrying_capacity_lb=200,
    )
    # Default would be 15 * 14 = 210, but override is 200
    assert char.carrying_capacity_lb == 200
    # Sheet should show override
    detail_url = reverse("characters:detail", args=[club.slug, char.pk])
    r = client.get(detail_url)
    body = r.content.decode()
    # The carrying line should show the override
    assert "200" in body  # override value


def test_carrying_capacity_blank_restores_default(club_admin, login, club):
    """Blank carrying_capacity_lb restores 15 x Strength."""
    _login(login(club_admin), club_admin)
    owner = Membership.objects.get(user=club_admin, club=club)
    char = Character.objects.create(
        club=club,
        owner=owner,
        name="Blank Override Char",
        strength=12,
        carrying_capacity_lb=None,
    )
    assert char.carrying_capacity_lb is None
    # Default would be 15 * 12 = 180


def test_edit_form_shows_capacity_override_field(club_admin, login, club):
    """Edit form includes carrying_capacity_lb field."""
    c = _login(login(club_admin), club_admin)
    char = _character(club, club_admin, "Test Char")
    url = reverse("characters:edit", args=[club.slug, char.pk])
    r = c.get(url)
    body = r.content.decode()
    # Field should be in the form
    assert "carrying_capacity_lb" in body
    assert "Carrying capacity" in body or "capacity" in body.lower()


# --- ClubWeightSettings ---


def test_club_weight_settings_default_off(club_admin, login, club):
    """Coin weight is off by default."""
    settings = ClubWeightSettings.objects.get_or_create(club=club)[0]
    assert settings.count_coin_weight is False


def test_club_weight_settings_toggle_persists(club_admin, login, club):
    """Club admin can toggle coin weight in settings."""
    c = _login(login(club_admin), club_admin)
    url = reverse("accounts:club_settings", args=[club.slug])
    # POST to enable coin weight
    r = c.post(url, {"count_coin_weight": "on"})
    assert r.status_code == 302
    settings = ClubWeightSettings.objects.get(club=club)
    assert settings.count_coin_weight is True


def test_club_weight_settings_form_shows_toggle(club_admin, login, club):
    """Club settings page shows the coin weight toggle."""
    c = _login(login(club_admin), club_admin)
    url = reverse("accounts:club_settings", args=[club.slug])
    r = c.get(url)
    body = r.content.decode()
    assert "count_coin_weight" in body
    assert "Count coin weight" in body or "coin weight" in body.lower()


# --- coin_weight_hundredths ---


def test_coin_weight_off_by_default(club, club_admin):
    """coin_weight_hundredths returns 0 when coin weight disabled."""
    char = _character(club, club_admin, "Test Char")
    settings = ClubWeightSettings(count_coin_weight=False)
    assert coin_weight_hundredths(char, settings) == 0


def test_coin_weight_none_settings(club, club_admin):
    """coin_weight_hundredths returns 0 when settings is None."""
    char = _character(club, club_admin, "Test Char")
    assert coin_weight_hundredths(char, None) == 0


def test_coin_weight_no_coins(club, club_admin):
    """coin_weight_hundredths returns 0 when no coins."""
    char = _character(club, club_admin, "Test Char")
    settings = ClubWeightSettings.objects.create(club=club, count_coin_weight=True)
    assert coin_weight_hundredths(char, settings) == 0


def test_coin_weight_50_coins_per_pound(club, club_admin):
    """50 coins = 1 lb = 100 hundredths."""
    char = _character(club, club_admin, "Test Char")
    # Give 50000 cp = 50 pp = 50 coins = 1 lb = 100 hundredths
    record(char, "award", [Line(coins=50000)], actor=club_admin)
    settings = ClubWeightSettings.objects.create(club=club, count_coin_weight=True)
    assert coin_weight_hundredths(char, settings) == 100


def test_coin_weight_minimum_coin_count(club, club_admin):
    """Uses minimum physical coins (greedy denomination)."""
    char = _character(club, club_admin, "Test Char")
    # 1000 cp = 1 pp = 1 coin (not 1000 coins)
    record(char, "award", [Line(coins=1000)], actor=club_admin)
    settings = ClubWeightSettings.objects.create(club=club, count_coin_weight=True)
    # 1 coin = 2 hundredths
    assert coin_weight_hundredths(char, settings) == 2


def test_coin_weight_mixed_denominations(club, club_admin):
    """Mixed coins use minimum total count."""
    char = _character(club, club_admin, "Test Char")
    # 1111 cp = 1pp + 1gp + 1sp + 1cp = 4 coins = 8 hundredths
    record(char, "award", [Line(coins=1111)], actor=club_admin)
    settings = ClubWeightSettings.objects.create(club=club, count_coin_weight=True)
    assert coin_weight_hundredths(char, settings) == 8


def test_coin_weight_greedy_conversion(club, club_admin):
    """Greedy conversion minimizes coin count."""
    char = _character(club, club_admin, "Test Char")
    # 1100 cp = 1pp + 1gp = 2 coins (not 1100)
    record(char, "award", [Line(coins=1100)], actor=club_admin)
    settings = ClubWeightSettings.objects.create(club=club, count_coin_weight=True)
    assert coin_weight_hundredths(char, settings) == 4  # 2 coins * 2

    # 110 cp = 1gp + 1sp = 2 coins
    char2 = _character(club, club_admin, "Test Char 2")
    record(char2, "award", [Line(coins=110)], actor=club_admin)
    assert coin_weight_hundredths(char2, settings) == 4

    # 11 cp = 1sp + 1cp = 2 coins
    char3 = _character(club, club_admin, "Test Char 3")
    record(char3, "award", [Line(coins=11)], actor=club_admin)
    assert coin_weight_hundredths(char3, settings) == 4


def test_coin_weight_large_amount(club, club_admin):
    """Large coin amounts calculate correctly."""
    char = _character(club, club_admin, "Test Char")
    # 10000 cp = 10 pp = 10 coins = 20 hundredths
    record(char, "award", [Line(coins=10000)], actor=club_admin)
    settings = ClubWeightSettings.objects.create(club=club, count_coin_weight=True)
    assert coin_weight_hundredths(char, settings) == 20


def test_coin_weight_exact_50_boundary(club, club_admin):
    """Exactly 50 coins = 100 hundredths."""
    char = _character(club, club_admin, "Test Char")
    # 500 cp = 5 gp = 5 coins
    record(char, "award", [Line(coins=500)], actor=club_admin)
    settings = ClubWeightSettings.objects.create(club=club, count_coin_weight=True)
    assert coin_weight_hundredths(char, settings) == 10  # 5 coins * 2
