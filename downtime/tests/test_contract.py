from datetime import date, timedelta

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from downtime import services
from downtime.models import (
    DowntimeAction,
    DowntimeEntryItem,
    DowntimePointEntry,
    DowntimePointRequest,
    DowntimeResult,
)
from ledger.models import AppendOnlyError

D = date(2026, 6, 15)
ONE = timedelta(days=1)


def _entry(character, delta=1):
    return DowntimePointEntry.objects.create(character=character, delta=delta, kind="award")


@pytest.mark.story("D1")
def test_models_scope_by_club(
    club, other_club, character, other_club_character, action, other_club_action, entry, item
):
    own_item = DowntimeEntryItem.objects.create(entry=entry, item=item)
    own_result = DowntimeResult.objects.create(character=character, action=action, entry=entry)
    own_point = _entry(character)
    other_point = _entry(other_club_character)
    other_result = DowntimeResult.objects.create(
        character=other_club_character, action=other_club_action
    )
    req = DowntimePointRequest.objects.create(club=club, requested_by=character.owner, points=2)
    other_req = DowntimePointRequest.objects.create(
        club=other_club, requested_by=other_club_character.owner, points=2
    )
    assert list(DowntimePointEntry.objects.for_club(club)) == [own_point]
    assert list(DowntimePointEntry.objects.for_club(other_club)) == [other_point]
    assert list(DowntimeAction.objects.for_club(club)) == [action]
    assert list(DowntimeEntryItem.objects.for_club(club)) == [own_item]
    assert not DowntimeEntryItem.objects.for_club(other_club).exists()
    assert not type(entry).objects.for_club(other_club).exists()
    assert list(DowntimeResult.objects.for_club(club)) == [own_result]
    assert list(DowntimeResult.objects.for_club(other_club)) == [other_result]
    assert list(DowntimePointRequest.objects.for_club(club)) == [req]
    assert list(DowntimePointRequest.objects.for_club(other_club)) == [other_req]


@pytest.mark.story("D1")
def test_entries_are_append_only(character):
    e = _entry(character)
    e.note = "x"
    with pytest.raises(AppendOnlyError):
        e.save()
    with pytest.raises(AppendOnlyError):
        e.delete()
    with pytest.raises(AppendOnlyError):
        DowntimePointEntry.objects.all().update(note="y")


@pytest.mark.story("D1")
def test_balance_sums(character):
    assert services.balance(character) == 0
    _entry(character, 5)
    _entry(character, -2)
    assert services.balance(character) == 3


@pytest.mark.story("D1")
def test_award_one_per_character(club, character, game_master, other_player):
    from player_characters.models import Character

    other = Character.objects.create(club=club, owner=character.owner, name="Bo")
    entries = services.award(
        [character, other], 2, note="n", by=game_master, source="result:1", club=club
    )
    assert len(entries) == 2
    assert services.balance(character) == services.balance(other) == 2
    e = entries[0]
    assert (e.kind, e.source, e.created_by, e.note) == ("award", "result:1", game_master, "n")
    assert services.award(character, 1)[0].delta == 1


@pytest.mark.story("D1")
def test_remove_to_zero_then_refused(character):
    services.award(character, 2)
    services.award(character, -2, kind="remove")
    assert services.balance(character) == 0
    with pytest.raises(services.InsufficientPoints):
        services.award(character, -1, kind="remove")
    assert DowntimePointEntry.objects.count() == 2


@pytest.mark.story("D1")
def test_negative_writes_nothing_for_any(club, character):
    from player_characters.models import Character

    rich = Character.objects.create(club=club, owner=character.owner, name="Rich")
    services.award(rich, 1)
    with pytest.raises(services.InsufficientPoints):
        services.award([rich, character], -1, kind="remove")
    assert services.balance(rich) == 1


@pytest.mark.story("D1")
def test_award_refuses_cross_club(club, other_club, character, other_club_character):
    with pytest.raises(services.DowntimeError):
        services.award([character, other_club_character], 1)
    with pytest.raises(services.DowntimeError):
        services.award(other_club_character, 1, club=club)
    assert not DowntimePointEntry.objects.exists()


@pytest.mark.story("D1")
def test_award_refuses_bad_input(character):
    with pytest.raises(services.DowntimeError):
        services.award(character, 0)
    with pytest.raises(services.DowntimeError):
        services.award(character, 1, kind="bogus")
    with pytest.raises(services.DowntimeError):
        services.award([], 1)


@pytest.mark.story("D2")
@pytest.mark.parametrize(
    "start,end,expected",
    [
        (D, None, "live"),
        (None, D, "live"),
        (D + ONE, None, "upcoming"),
        (None, D - ONE, "ended"),
        (None, None, "live"),
        (D - ONE, D + ONE, "live"),
        (D, D, "live"),
        (D - 10 * ONE, D - ONE, "ended"),
    ],
)
def test_live_on_matches_quest_rules(club, start, end, expected):
    a = DowntimeAction.objects.create(club=club, name="A", start_date=start, end_date=end)
    assert a.status_on(D) == expected
    assert (a in DowntimeAction.objects.live_on(D)) == (expected == "live")


@pytest.mark.story("D2")
def test_live_on_scopes_club(club, other_club, action, other_club_action):
    from django.utils import timezone

    live = DowntimeAction.objects.for_club(club).live_on(timezone.localdate())
    assert list(live) == [action]


@pytest.mark.story("D2")
def test_weight_check_constraint(action):
    from downtime.models import DowntimeEntry

    with pytest.raises(IntegrityError), transaction.atomic():
        DowntimeEntry.objects.create(action=action, label="x", weight=0)


@pytest.mark.story("D2")
def test_spend_not_implemented(character, action):
    with pytest.raises(NotImplementedError):
        services.spend(character, action, None)


@pytest.mark.story("D1")
def test_urls_importable():
    from downtime import urls

    assert isinstance(urls.urlpatterns, list)
    assert reverse  # url module loads through config.urls


@pytest.mark.story("D1")
def test_award_dedupes_characters(character):
    assert len(services.award([character, character], 1)) == 1
    assert services.balance(character) == 1
    with pytest.raises(services.InsufficientPoints):
        services.award([character, character], -2, kind="remove")
    services.award([character, character], -1, kind="remove")
    assert services.balance(character) == 0
