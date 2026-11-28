"""Tests for character selector top bar badges (coins, junk, DT)."""

import pytest
from django.urls import reverse

from downtime.models import DowntimePointEntry
from ledger.services import Line, record
from player_characters.models import JunkMark

pytestmark = pytest.mark.django_db


def _get_directory(client, club):
    return client.get(reverse("characters:directory", args=[club.slug]))


def test_selector_badges_show_coins_junk_dt(login, club, player, character, item):
    """Plain GET of directory page shows coins, Junk N, DT N badges for one character."""
    # Award coins and item
    record(character, "award", [Line(item=item, quantity=5), Line(coins=100)])
    # Mark 2 as junk
    JunkMark.objects.create(character=character, item=item, quantity=2)
    # Add 3 downtime points
    DowntimePointEntry.objects.create(character=character, delta=3, kind="award")

    resp = _get_directory(login(player), club)
    assert resp.status_code == 200
    body = resp.content.decode()

    # Should show coin total (from coin_summary, which returns e.g. "1 gp" for 100 cp)
    assert "1 gp" in body
    # Should show Junk badge
    assert "Junk 2" in body
    # Should show DT badge
    assert "DT 3" in body


def test_selector_badges_absent_when_zero(login, club, player, character):
    """No Junk or DT badge shows when values are zero."""
    resp = _get_directory(login(player), club)
    assert resp.status_code == 200
    body = resp.content.decode()

    assert "Junk" not in body
    assert "DT" not in body
    # Coin text may be empty string when zero


def test_selector_dropdown_still_renders_with_two_characters(
    login, club, player, character, second_character
):
    """Multi-character dropdown branch still renders (wm-character-dropdown)."""
    resp = _get_directory(login(player), club)
    assert resp.status_code == 200
    body = resp.content.decode()

    # The dropdown branch should render when more than one character
    assert "wm-character-dropdown" in body
