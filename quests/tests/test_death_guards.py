"""Guards: a dead or archived character cannot turn in a quest."""

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership, User
from ledger import services as ledger_services
from ledger.models import LedgerEntry
from player_characters.models import Character
from quests import services
from quests.models import QuestCompletion

pytestmark = [pytest.mark.django_db]


def _url(name, *args):
    return reverse(f"quests:{name}", args=["club-a", *args])


def _make_character(club, name, *, died_on=None, archived_at=None):
    user = User.objects.create_user(f"{name.lower()}@example.com", password="pw", display_name=name)
    membership = Membership.objects.create(user=user, club=club)
    return Character.objects.create(
        club=club, owner=membership, name=name, died_on=died_on, archived_at=archived_at
    ), user


def test_dead_turn_in_refused(login, club, quest, character, item, give):
    dead, user = _make_character(club, "Dead", died_on=timezone.localdate())
    give(dead, item, 2)
    before_ledger = LedgerEntry.objects.count()
    before_completions = QuestCompletion.objects.count()
    before_items = ledger_services.item_quantities(dead)

    c = login(user)
    r = c.post(_url("turn_in", quest.pk), {"character": dead.pk}, follow=True)

    assert r.status_code == 200
    assert f"{dead.name} died on" in r.content.decode()
    assert QuestCompletion.objects.count() == before_completions
    assert LedgerEntry.objects.count() == before_ledger
    assert ledger_services.item_quantities(dead) == before_items


def test_archived_turn_in_refused(login, club, quest, character, item, give):
    archived, user = _make_character(club, "Archived", archived_at=timezone.now())
    give(archived, item, 2)
    before_ledger = LedgerEntry.objects.count()

    c = login(user)
    r = c.post(_url("turn_in", quest.pk), {"character": archived.pk}, follow=True)

    assert r.status_code == 200
    assert f"{archived.name} is archived" in r.content.decode()
    assert QuestCompletion.objects.count() == 0
    assert LedgerEntry.objects.count() == before_ledger


def test_turn_in_service_raises_character_blocked(quest, character, item, give):
    character.died_on = timezone.localdate()
    character.save(update_fields=["died_on"])
    give(character, item, 2)
    with pytest.raises(services.CharacterBlocked):
        services.turn_in(quest, character, character.owner.user)
    assert QuestCompletion.objects.count() == 0


def test_turn_in_detail_shows_reason(login, club, quest, character, item, give):
    dead, user = _make_character(club, "Dead", died_on=timezone.localdate())
    give(dead, item, 2)
    c = login(user)
    body = c.get(_url("detail", quest.pk)).content.decode()
    assert f"{dead.name} died on {dead.died_on.isoformat()}" in body


def test_living_character_still_turns_in(login, club, quest, character, item, give):
    give(character, item, 2)
    before = LedgerEntry.objects.count()
    c = login(character.owner.user)
    r = c.post(_url("turn_in", quest.pk))
    assert r.status_code == 302
    assert QuestCompletion.objects.count() == 1
    assert LedgerEntry.objects.count() == before + 2


def test_gm_adjust_items_for_dead_character_still_works(character, item):
    character.died_on = timezone.localdate()
    character.save(update_fields=["died_on"])
    before = ledger_services.item_quantities(character)
    ledger_services.record(
        character, "award", [ledger_services.Line(item=item, quantity=1)], note="gm adjustment"
    )
    assert ledger_services.item_quantities(character) == {
        **before,
        item.pk: before.get(item.pk, 0) + 1,
    }
