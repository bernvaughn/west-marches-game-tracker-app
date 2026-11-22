"""Tests for story U143: Died badge, dead-last sort, status filter, picker and print."""

import datetime

import pytest
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse

from player_characters.life import archive, mark_dead
from player_characters.models import Character
from player_characters.selection import selected_character
from player_characters.selector_context import all_characters_selector_context

pytestmark = [pytest.mark.story("U143"), pytest.mark.django_db]


def u(name, club, pk=None):
    kw = {"club_slug": club.slug}
    if pk is not None:
        kw["pk"] = pk
    return reverse(name, kwargs=kw)


def _membership(club, user):
    from accounts.models import Membership

    return Membership.objects.get(user=user, club=club)


def _request(user, club):
    request = RequestFactory().get("/")
    request.user = user
    request.club = club
    request.membership = _membership(club, user)
    return request


def _tbody(html):
    start = html.index("<tbody>")
    end = html.index("</tbody>", start)
    return html[start:end]


def _dead(character, by, died_on, note="Dragonfire"):
    mark_dead(character, by=by, died_on=datetime.date.fromisoformat(died_on), note=note)
    character.refresh_from_db()


# --- Sheet ---


@pytest.mark.story("U143")
def test_sheet_shows_died_badge_and_note(club, login, player, character):
    c = login(player)
    _dead(character, _membership(club, player), "2026-11-04", "Slain by the green dragon.")
    html = c.get(u("characters:detail", club, character.pk)).content.decode()
    assert "Died 4 Nov 2026" in html
    assert "Slain by the green dragon." in html


@pytest.mark.story("U143")
def test_sheet_shows_no_badge_for_living(club, login, player, character):
    html = login(player).get(u("characters:detail", club, character.pk)).content.decode()
    assert "Died" not in html


# --- Directory and index: badge and dead-last sort ---


@pytest.mark.story("U143")
def test_directory_shows_badge_and_sorts_dead_last(club, login, player):
    owner = _membership(club, player)
    Character.objects.create(club=club, owner=owner, name="Zora")
    dead = Character.objects.create(club=club, owner=owner, name="Aaron")
    _dead(dead, owner, "2026-10-01")
    html = login(player).get(u("characters:directory", club)).content.decode()
    assert "Died 1 Oct 2026" in html
    # Alpha order would put Aaron first; dead sorts after living.
    assert html.index("Zora") < html.index("Aaron")


@pytest.mark.story("U143")
def test_index_shows_badge_and_sorts_dead_last(club, login, club_admin):
    owner = _membership(club, club_admin)
    Character.objects.create(club=club, owner=owner, name="Zora")
    dead = Character.objects.create(club=club, owner=owner, name="Aaron")
    _dead(dead, owner, "2026-10-01")
    html = login(club_admin).get(u("characters:index", club)).content.decode()
    assert "Died 1 Oct 2026" in html
    assert html.index("Zora") < html.index("Aaron")


# --- Archived ---


@pytest.mark.story("U143")
def test_archived_absent_from_lists_but_reachable_by_url(club, login, player, club_admin):
    owner = _membership(club, player)
    archived = Character.objects.create(club=club, owner=owner, name="Vale")
    archive(archived, by=owner)
    # Archived characters should not appear in the directory table
    directory_html = login(player).get(u("characters:directory", club)).content.decode()
    # Check the table body only (where character rows appear)
    tbody = _tbody(directory_html)
    assert "Vale" not in tbody
    assert "Vale" not in login(club_admin).get(u("characters:index", club)).content.decode()
    # But they should still be reachable by direct URL
    r = login(player).get(u("characters:detail", club, archived.pk))
    assert r.status_code == 200
    assert "Vale" in r.content.decode()


# --- Filter ---


@pytest.mark.story("U143")
def test_admin_filter_living_dead_all(club, login, club_admin):
    owner = _membership(club, club_admin)
    Character.objects.create(club=club, owner=owner, name="Living One")
    dead = Character.objects.create(club=club, owner=owner, name="Dead One")
    _dead(dead, owner, "2026-10-01")

    admin = login(club_admin)
    all_html = admin.get(u("characters:directory", club) + "?status=all").content.decode()
    assert "Living One" in _tbody(all_html) and "Dead One" in _tbody(all_html)
    living_html = admin.get(u("characters:directory", club) + "?status=living").content.decode()
    assert "Living One" in _tbody(living_html) and "Dead One" not in _tbody(living_html)
    dead_html = admin.get(u("characters:directory", club) + "?status=dead").content.decode()
    assert "Dead One" in _tbody(dead_html) and "Living One" not in _tbody(dead_html)


@pytest.mark.story("U143")
def test_player_cannot_filter(club, login, player):
    owner = _membership(club, player)
    dead = Character.objects.create(club=club, owner=owner, name="Dead One")
    _dead(dead, owner, "2026-10-01")
    html = login(player).get(u("characters:directory", club) + "?status=dead").content.decode()
    assert "Dead One" in html
    assert 'name="status"' not in html


@pytest.mark.story("U143")
def test_index_admin_filter(club, login, club_admin):
    owner = _membership(club, club_admin)
    Character.objects.create(club=club, owner=owner, name="Living One")
    dead = Character.objects.create(club=club, owner=owner, name="Dead One")
    _dead(dead, owner, "2026-10-01")
    admin = login(club_admin)
    dead_html = admin.get(u("characters:index", club) + "?status=dead").content.decode()
    assert "Dead One" in _tbody(dead_html) and "Living One" not in _tbody(dead_html)


# --- Archive link ---


@pytest.mark.story("U143")
def test_archive_link_on_lists(club, login, player, club_admin):
    archived_url = reverse("characters:archived", args=[club.slug])
    player_html = login(player).get(u("characters:directory", club)).content.decode()
    assert archived_url in player_html
    admin_html = login(club_admin).get(u("characters:index", club)).content.decode()
    assert archived_url in admin_html


# --- Picker ---


@pytest.mark.story("U143")
def test_picker_context_orders_dead_last(club, player):
    owner = _membership(club, player)
    Character.objects.create(club=club, owner=owner, name="Zeb")
    aaron = Character.objects.create(club=club, owner=owner, name="Aaron")
    _dead(aaron, owner, "2026-10-01")
    pairs = all_characters_selector_context(_request(player, club))
    names = [c.name for c, _ in pairs]
    assert names == ["Zeb", "Aaron"]


@pytest.mark.story("U143")
def test_picker_dropdown_row_includes_died(club, player):
    owner = _membership(club, player)
    Character.objects.create(club=club, owner=owner, name="Zeb")
    aaron = Character.objects.create(club=club, owner=owner, name="Aaron")
    _dead(aaron, owner, "2026-10-01")
    request = _request(player, club)
    request.GET = {}
    html = render_to_string(
        "player_characters/characters/_selector.html",
        {"request": request, "club": club},
    )
    assert "Died 1 Oct 2026" in html
    assert f'data-character-pk="{aaron.pk}"' in html


@pytest.mark.story("U143")
def test_picker_single_character_shows_died(club, player):
    owner = _membership(club, player)
    aaron = Character.objects.create(club=club, owner=owner, name="Aaron")
    _dead(aaron, owner, "2026-10-01")
    request = _request(player, club)
    request.GET = {}
    html = render_to_string(
        "player_characters/characters/_selector.html",
        {"request": request, "club": club, "selected_character": selected_character(request)},
    )
    assert "Acting as Aaron" in html
    assert "Died 1 Oct 2026" in html


# --- Print ---


@pytest.mark.story("U143")
def test_print_items_includes_badge(club, login, player, funded):
    _dead(funded, _membership(club, player), "2026-11-04")
    html = login(player).get(u("characters:print_items", club, funded.pk)).content.decode()
    assert "Died 4 Nov 2026" in html
    assert "data-print-frame" in html


@pytest.mark.story("U143")
def test_sheet_header_carries_badge_in_print(club, login, player, character):
    _dead(character, _membership(club, player), "2026-11-04", "Note text")
    html = login(player).get(u("characters:detail", club, character.pk)).content.decode()
    assert "Died 4 Nov 2026" in html
    assert "Note text" in html
