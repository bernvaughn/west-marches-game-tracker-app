"""Tests for play_sessions.timefmt (P17)."""

from datetime import UTC, datetime

import pytest
from django.template import Context, Template

from accounts.models import Club
from play_sessions.timefmt import (
    _short_zone_name,
    club_zone,
    format_session_time,
    timezone_choices,
    timezone_label,
    to_club_local,
)

pytestmark = [pytest.mark.django_db, pytest.mark.story("P17")]


@pytest.fixture
def ny_club():
    return Club.objects.create(name="NY Club", slug="ny-club", timezone="America/New_York")


@pytest.fixture
def utc_club():
    return Club.objects.create(name="UTC Club", slug="utc-club", timezone="UTC")


@pytest.fixture
def kathmandu_club():
    return Club.objects.create(
        name="Kathmandu Club", slug="kathmandu-club", timezone="Asia/Kathmandu"
    )


def test_format_session_time_winter_est(ny_club):
    """Winter date in America/New_York shows EST."""
    # Jan 15, 2024 19:00 local = Jan 16 00:00 UTC (EST, UTC-5)
    moment = datetime(2024, 1, 16, 0, 0, tzinfo=UTC)
    result = format_session_time(moment, ny_club)
    assert "7:00 PM EST" == result


def test_format_session_time_summer_edt(ny_club):
    """Summer date in America/New_York shows EDT."""
    # Jul 15, 2024 19:00 local = Jul 15 23:00 UTC (EDT, UTC-4)
    moment = datetime(2024, 7, 15, 23, 0, tzinfo=UTC)
    result = format_session_time(moment, ny_club)
    assert "7:00 PM EDT" == result


def test_format_session_time_utc(utc_club):
    """UTC zone shows UTC."""
    moment = datetime(2024, 6, 15, 19, 0, tzinfo=UTC)
    result = format_session_time(moment, utc_club)
    assert "7:00 PM UTC" == result


def test_format_session_time_offset_zone(kathmandu_club):
    """Offset-only zone (Asia/Kathmandu, UTC+5:45) falls back to UTC±H:MM."""
    # Kathmandu is UTC+5:45 year-round
    moment = datetime(2024, 1, 15, 13, 15, tzinfo=UTC)  # 19:00 local
    result = format_session_time(moment, kathmandu_club)
    assert "7:00 PM UTC+5:45" == result


def test_format_session_time_naive_input(ny_club):
    """Naive datetime is treated as UTC."""
    moment = datetime(2024, 1, 16, 0, 0)  # naive
    result = format_session_time(moment, ny_club)
    assert "7:00 PM EST" == result


def test_timezone_label_known_zones():
    """Friendly labels for curated zones."""
    labels = {
        "America/New_York": "Eastern Time (New York)",
        "America/Chicago": "Central Time (Chicago)",
        "America/Denver": "Mountain Time (Denver)",
        "America/Los_Angeles": "Pacific Time (Los Angeles)",
        "America/Toronto": "Eastern Time (Toronto)",
        "Europe/London": "Greenwich Mean Time (London)",
        "Europe/Paris": "Central European Time (Paris)",
        "Asia/Tokyo": "Japan Standard Time (Tokyo)",
        "Australia/Sydney": "Australian Eastern Time (Sydney)",
        "UTC": "Coordinated Universal Time (UTC)",
    }
    for iana, friendly in labels.items():
        label = timezone_label(iana)
        assert label.startswith(friendly)
        assert ", now " in label


def test_timezone_label_unknown_zone_fallback():
    """Unknown zone falls back to IANA name."""
    label = timezone_label("Mars/Olympus")
    assert label == "Mars/Olympus"


def test_timezone_choices_structure():
    """timezone_choices returns (iana, friendly_label) pairs."""
    choices = timezone_choices()
    assert isinstance(choices, list)
    assert len(choices) > 0
    # First few should be sorted IANA names
    for iana, label in choices[:5]:
        assert isinstance(iana, str)
        assert isinstance(label, str)
    # Known zones should have friendly labels
    ny_choices = [c for c in choices if c[0] == "America/New_York"]
    assert len(ny_choices) == 1
    assert "Eastern Time (New York)" in ny_choices[0][1]
    assert ", now " in ny_choices[0][1]


def test_timezone_choices_utc_label():
    """UTC choice has deterministic friendly label."""
    choices = timezone_choices()
    utc_choices = [c for c in choices if c[0] == "UTC"]
    assert len(utc_choices) == 1
    iana, label = utc_choices[0]
    assert iana == "UTC"
    assert label == "Coordinated Universal Time (UTC), now UTC"


def test_session_time_template_filter(ny_club):
    """Template filter session_time works."""
    moment = datetime(2024, 1, 16, 0, 0, tzinfo=UTC)  # 7 PM EST
    template = Template("{% load play_sessions_tags %}{{ moment|session_time:club }}")
    result = template.render(Context({"moment": moment, "club": ny_club}))
    assert result == "7:00 PM EST"


def test_club_zone_returns_zoneinfo(ny_club):
    """club_zone returns a ZoneInfo."""
    zone = club_zone(ny_club)
    assert zone.key == "America/New_York"


def test_to_club_local_converts(ny_club):
    """to_club_local converts UTC to club local time."""
    utc = datetime(2024, 1, 16, 0, 0, tzinfo=UTC)
    local = to_club_local(ny_club, utc)
    assert local.hour == 19  # 7 PM EST
    assert local.tzname() == "EST"


def test_short_zone_name_offset_fallback():
    """_short_zone_name falls back to UTC±H:MM for offset zones."""
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("Asia/Kathmandu")
    dt = datetime(2024, 1, 15, 19, 0, tzinfo=zone)
    name = _short_zone_name(dt)
    assert name == "UTC+5:45"


def test_format_session_time_preserves_date(ny_club):
    """The formatted time corresponds to the correct local date."""
    # March 9, 2024 19:00 EST = March 10 00:00 UTC (before DST)
    moment = datetime(2024, 3, 10, 0, 0, tzinfo=UTC)
    result = format_session_time(moment, ny_club)
    assert "7:00 PM EST" == result

    # March 10, 2024 19:00 EDT = March 10 23:00 UTC (after DST)
    moment = datetime(2024, 3, 10, 23, 0, tzinfo=UTC)
    result = format_session_time(moment, ny_club)
    assert "7:00 PM EDT" == result
