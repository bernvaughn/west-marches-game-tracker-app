import datetime

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership
from downtime.forms import PointsForm
from map.visibility import pick_characters, resolve_view
from player_characters.context_processors import selection as selection_ctx
from player_characters.models import Character, SelectedCharacter
from player_characters.selection import own_characters, selected_character
from shops.views.browse import street_stalls

pytestmark = [pytest.mark.story("U144"), pytest.mark.django_db]


def _char(club, user, name, archived=False, dead=False):
    owner = Membership.objects.get(user=user, club=club)
    c = Character.objects.create(
        club=club,
        owner=owner,
        name=name,
    )
    if archived:
        c.archived_at = timezone.now()
        c.save()
    if dead:
        c.died_on = datetime.date.today()
        c.save()
    return c


def _req(rf, user, club):
    request = RequestFactory().get("/")
    request.user = user
    request.club = club
    request.membership = Membership.objects.filter(user=user, club=club).first()
    return request


# --- own_characters ---


def test_own_characters_excludes_archived_keeps_dead(rf, club, player):
    living = _char(club, player, "Living")
    dead = _char(club, player, "Dead", dead=True)
    archived = _char(club, player, "Archived", archived=True)
    qs = own_characters(_req(rf, player, club))
    assert living in qs
    assert dead in qs
    assert archived not in qs


# --- selected_character fallback ---


def test_selected_archived_falls_back_to_living(rf, club, player):
    first = _char(club, player, "First")
    second = _char(club, player, "Second")
    membership = Membership.objects.get(user=player, club=club)
    SelectedCharacter.objects.create(membership=membership, character=first)
    first.archived_at = timezone.now()
    first.save()
    assert selected_character(_req(rf, player, club)) == second


def test_selected_archived_falls_back_to_dead(rf, club, player):
    first = _char(club, player, "First", dead=True)
    second = _char(club, player, "Second", archived=True)
    membership = Membership.objects.get(user=player, club=club)
    SelectedCharacter.objects.create(membership=membership, character=second)
    assert selected_character(_req(rf, player, club)) == first


def test_selected_none_when_all_archived(rf, club, player):
    first = _char(club, player, "First", archived=True)
    membership = Membership.objects.get(user=player, club=club)
    SelectedCharacter.objects.create(membership=membership, character=first)
    assert selected_character(_req(rf, player, club)) is None


def test_selected_none_when_no_owned(rf, club, player):
    assert selected_character(_req(rf, player, club)) is None


# --- selection restores after unarchive ---


def test_selection_restores_after_unarchive(rf, club, player):
    first = _char(club, player, "First")
    second = _char(club, player, "Second")
    membership = Membership.objects.get(user=player, club=club)
    SelectedCharacter.objects.create(membership=membership, character=first)
    first.archived_at = timezone.now()
    first.save()
    assert selected_character(_req(rf, player, club)) == second
    first.archived_at = None
    first.save()
    assert selected_character(_req(rf, player, club)) == first


# --- top-bar picker context ---


def test_top_bar_picker_context_excludes_archived(rf, club, player):
    _char(club, player, "Living")
    _char(club, player, "Archived", archived=True)
    request = _req(rf, player, club)
    ctx = selection_ctx(request)
    names = {c.name for c in ctx["own_characters"]}
    assert "Living" in names
    assert "Archived" not in names


# --- street_stalls ---


def test_street_stalls_omits_archived(club, player, item):
    from ledger.services import Line, record
    from player_characters.models import JunkMark

    owner = Membership.objects.get(user=player, club=club)

    living = Character.objects.create(
        club=club,
        owner=owner,
        name="Living",
        shop_open=True,
    )
    record(living, "award", [Line(item=item, quantity=1)])
    JunkMark.objects.create(character=living, item=item, quantity=1)

    archived = Character.objects.create(
        club=club,
        owner=owner,
        name="Archived",
        shop_open=True,
        archived_at=timezone.now(),
    )
    record(archived, "award", [Line(item=item, quantity=1)])
    JunkMark.objects.create(character=archived, item=item, quantity=1)

    stalls = street_stalls(club)
    assert living in stalls
    assert archived not in stalls


# --- map pick_characters ---


def test_pick_characters_allows_any_omits_archived(rf, club, player, game_master):
    living = _char(club, player, "Living")
    archived = _char(club, player, "Archived", archived=True)
    ids = [living.pk, archived.pk]
    result = set(pick_characters(_req(rf, game_master, club), ids, allow_any=True))
    assert result == {living}


def test_pick_characters_own_omits_archived(rf, club, player):
    living = _char(club, player, "Living")
    archived = _char(club, player, "Archived", archived=True)
    ids = [living.pk, archived.pk]
    result = set(pick_characters(_req(rf, player, club), ids, allow_any=False))
    assert result == {living}


# --- resolve_view choices ---


def test_resolve_view_choices_omit_archived(rf, club, player):
    _char(club, player, "Living")
    _char(club, player, "Archived", archived=True)
    view = resolve_view(_req(rf, player, club), None)
    choice_names = {c.name for c in view["choices"]}
    assert "Living" in choice_names
    assert "Archived" not in choice_names


# --- downtime PointsForm ---


def test_points_form_queryset_excludes_archived(club, player):
    _char(club, player, "Living")
    _char(club, player, "Archived", archived=True)
    form = PointsForm(club=club)
    queryset = form.fields["characters"].queryset
    names = {c.name for c in queryset}
    assert "Living" in names
    assert "Archived" not in names


def test_points_form_post_rejects_archived(login, club, game_master, item):
    from downtime.models import DowntimePointEntry
    from ledger.services import Line, record
    from player_characters.models import JunkMark

    owner = Membership.objects.get(user=game_master, club=club)
    archived = Character.objects.create(
        club=club,
        owner=owner,
        name="Archived",
        shop_open=True,
        archived_at=timezone.now(),
    )
    record(archived, "award", [Line(item=item, quantity=1)])
    JunkMark.objects.create(character=archived, item=item, quantity=1)

    url = reverse("downtime:points_award", args=[club.slug])
    client = login(game_master)
    resp = client.post(
        url,
        {
            "characters": [archived.pk],
            "direction": "give",
            "points": 1,
            "note": "Test",
            "date": "2026-11-01",
        },
    )
    assert resp.status_code == 200
    assert DowntimePointEntry.objects.count() == 0


# --- id lookups still find archived ---


def test_character_objects_get_finds_archived(club, player):
    archived = _char(club, player, "Archived", archived=True)
    assert Character.objects.get(pk=archived.pk) == archived


def test_club_get_object_or_404_finds_archived(rf, club, player, game_master):
    from accounts.scoping import club_get_object_or_404

    archived = _char(club, player, "Archived", archived=True)
    request = _req(rf, game_master, club)
    found = club_get_object_or_404(request, Character, pk=archived.pk)
    assert found == archived


def test_character_detail_owner_still_finds_archived(login, club, player):
    archived = _char(club, player, "Archived", archived=True)
    url = reverse("characters:detail", args=[club.slug, archived.pk])
    resp = login(player).get(url)
    assert resp.status_code == 200
