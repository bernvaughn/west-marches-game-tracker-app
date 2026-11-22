"""Guards: a dead or archived character cannot spend downtime points."""

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership, User
from downtime import services
from downtime.models import DowntimePointEntry, DowntimeResult
from player_characters.models import Character

pytestmark = [pytest.mark.django_db]


def url(club, action_pk):
    return reverse("downtime:spend", args=[club.slug, action_pk])


def _make_character(club, name, *, died_on=None, archived_at=None):
    user = User.objects.create_user(f"{name.lower()}@example.com", password="pw", display_name=name)
    membership = Membership.objects.create(user=user, club=club)
    return Character.objects.create(
        club=club, owner=membership, name=name, died_on=died_on, archived_at=archived_at
    ), user


def _fund(character, n=3):
    services.award(character, n, note="fund", by=character.owner.user)


def test_dead_spend_refused(login, club, player, character, action, entries):
    dead, user = _make_character(club, "Dead", died_on=timezone.localdate())
    _fund(dead)
    before_balance = services.balance(dead)
    before_entries = DowntimePointEntry.objects.filter(character=dead).count()
    before_results = DowntimeResult.objects.filter(character=dead).count()

    c = login(user)
    r = c.post(url(club, action.pk), follow=True)

    assert r.status_code == 200
    assert f"{dead.name} died on" in r.content.decode()
    assert services.balance(dead) == before_balance
    assert DowntimePointEntry.objects.filter(character=dead).count() == before_entries
    assert DowntimeResult.objects.filter(character=dead).count() == before_results


def test_archived_spend_refused(login, club, player, character, action, entries):
    archived, user = _make_character(club, "Archived", archived_at=timezone.now())
    _fund(archived)
    before_balance = services.balance(archived)

    c = login(user)
    r = c.post(url(club, action.pk), follow=True)

    assert r.status_code == 200
    assert f"{archived.name} is archived" in r.content.decode()
    assert services.balance(archived) == before_balance
    assert not DowntimeResult.objects.filter(character=archived).exists()


def test_spend_service_raises_character_blocked(character, action, entries, player):
    character.died_on = timezone.localdate()
    character.save(update_fields=["died_on"])
    _fund(character)
    with pytest.raises(services.CharacterBlocked):
        services.spend(character, action, character.owner.user)
    assert not DowntimeResult.objects.exists()


def test_award_to_dead_character_still_works(character, player):
    character.died_on = timezone.localdate()
    character.save(update_fields=["died_on"])
    services.award(character, 2, note="gm award", by=player)
    assert services.balance(character) == 2


def test_living_character_still_spends(login, club, player, character, action, entries):
    _fund(character)
    before = services.balance(character)
    c = login(player)
    r = c.post(url(club, action.pk))
    assert r.status_code == 302
    assert services.balance(character) == before - action.cost
    assert DowntimeResult.objects.filter(character=character).count() == 1


def test_play_page_shows_death_reason(login, club, player, character, action, entries):
    dead, user = _make_character(club, "Dead", died_on=timezone.localdate())
    _fund(dead)
    c = login(user)
    body = c.get(reverse("downtime:play", args=[club.slug])).content.decode()
    assert f"{dead.name} died on {dead.died_on.isoformat()}" in body
