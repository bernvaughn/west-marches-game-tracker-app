"""Unit tests for the permission-check template tags in accounts_tags."""

import pytest
from django.template import Context, Template

pytestmark = [pytest.mark.django_db, pytest.mark.story("FOUNDATION")]


def _render(tmpl, **context):
    return Template(tmpl).render(Context(context))


def test_is_club_admin_tag(club, club_admin, game_master, player, site_admin):
    cases = {
        club_admin: True,
        site_admin: True,
        game_master: False,
        player: False,
    }
    for user, expected in cases.items():
        out = _render(
            "{% load accounts_tags %}{% is_club_admin user club %}", user=user, club=club
        )
        assert out.strip() == str(expected), f"is_club_admin({user})"


def test_is_game_master_tag(club, club_admin, game_master, player, site_admin):
    cases = {
        club_admin: False,
        site_admin: True,
        game_master: True,
        player: False,
    }
    for user, expected in cases.items():
        out = _render(
            "{% load accounts_tags %}{% is_game_master user club %}", user=user, club=club
        )
        assert out.strip() == str(expected), f"is_game_master({user})"


def test_is_club_member_tag(club, club_admin, game_master, player, site_admin):
    cases = {
        club_admin: True,
        site_admin: True,
        game_master: True,
        player: True,
    }
    for user, expected in cases.items():
        out = _render(
            "{% load accounts_tags %}{% is_club_member user club %}", user=user, club=club
        )
        assert out.strip() == str(expected), f"is_club_member({user})"


def test_can_view_inventory_filter(
    character, player, other_player, game_master, club_admin, site_admin
):
    cases = {
        player: True,
        game_master: True,
        club_admin: True,
        site_admin: True,
        other_player: False,
    }
    for user, expected in cases.items():
        out = _render(
            "{% load accounts_tags %}{{ user|can_view_inventory:character }}",
            user=user,
            character=character,
        )
        assert out.strip() == str(expected), f"can_view_inventory({user})"


def test_approvals_dropdown_shows_counts_by_type():
    approvals = [
        {"label": "Trades", "count": 1, "url": "/c/club/trades/"},
        {"label": "Map requests", "count": 2, "url": "/c/club/map/requests/"},
    ]
    html = _render(
        "{% include 'components/_approvals_dropdown.html' %}",
        approvals_total=3,
        approvals=approvals,
    )
    assert "approvals-menu" in html
    assert "approvals-total" in html
    assert "Trades" in html and "Map requests" in html
    assert '/c/club/trades/' in html and '/c/club/map/requests/' in html


def test_approvals_dropdown_hidden_when_zero():
    html = _render(
        "{% include 'components/_approvals_dropdown.html' %}",
        approvals_total=0,
        approvals=[],
    )
    assert html.strip() == ""
