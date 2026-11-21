"""Tests for U137: warn before selling an item a live quest needs."""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from items.models import Item
from ledger.services import Line, record
from player_characters.junk import set_junk
from quests.models import Quest, QuestCompletion, QuestRequirement
from shops.models import Rotation

pytestmark = [pytest.mark.django_db, pytest.mark.story("U137")]


def _today():
    return timezone.localdate()


@pytest.fixture
def open_shop(club, shop):
    Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1)).shops.add(shop)
    return shop


def card(client, club, shop):
    b = client.get(reverse("shops:detail", args=[club.slug, shop.id])).content.decode()
    return b[b.index('id="your-inventory"') :]


def url(club, shop, item):
    return reverse("shops:sell_item", args=[club.slug, shop.id, item.id])


def post(client, club, shop, character, item, quantity, **extra):
    data = {"character": character.id, "quantity": quantity, **extra}
    return client.post(url(club, shop, item), data)


def make_quest(
    club,
    name,
    req_item,
    req_qty=1,
    start_date=None,
    end_date=None,
    max_completions=None,
    max_per_character=None,
):
    quest = Quest.objects.create(
        club=club,
        name=name,
        start_date=start_date,
        end_date=end_date,
        max_completions=max_completions,
        max_per_character=max_per_character,
    )
    QuestRequirement.objects.create(quest=quest, item=req_item, quantity=req_qty)
    return quest


@pytest.mark.story("U137")
def test_live_quest_shows_needed_for_in_inventory(login, player, club, open_shop, character, item):
    record(character, "award", [Line(item=item, quantity=3)])
    make_quest(
        club, "Pelts for the Tanner", item, req_qty=2, start_date=_today() - timedelta(days=7)
    )
    c = card(login(player), club, open_shop)
    assert "Needed for: Pelts for the Tanner" in c


@pytest.mark.story("U137")
def test_sell_confirm_shows_warning_and_still_sells(
    login, player, club, open_shop, character, item
):
    record(character, "award", [Line(item=item, quantity=3)])
    make_quest(
        club, "Pelts for the Tanner", item, req_qty=2, start_date=_today() - timedelta(days=7)
    )
    r = post(login(player), club, open_shop, character, item, 1)
    assert r.status_code == 200
    body = r.content.decode()
    assert f"Warning: {item.name} is needed for the quest Pelts for the Tanner." in body
    assert 'name="confirmed" value="1"' in body
    # Posting the confirm still sells.
    r2 = post(login(player), club, open_shop, character, item, 1, confirmed="1")
    assert r2.status_code == 302
    assert r2.url == reverse("shops:detail", args=[club.slug, open_shop.id])


@pytest.mark.story("U137")
def test_no_quest_shows_no_needed_for(login, player, club, open_shop, character, item):
    record(character, "award", [Line(item=item, quantity=3)])
    c = card(login(player), club, open_shop)
    assert "Needed for" not in c


@pytest.mark.story("U137")
def test_item_not_required_by_any_quest_shows_nothing(
    login, player, club, open_shop, character, item
):
    record(character, "award", [Line(item=item, quantity=3)])
    make_quest(
        club,
        "Pelts for the Tanner",
        Item.objects.create(club=club, name="Gem", value_cp=333),
        start_date=_today() - timedelta(days=7),
    )
    c = card(login(player), club, open_shop)
    assert "Needed for" not in c


@pytest.mark.story("U137")
def test_ended_upcoming_and_full_quests_show_nothing(
    login, player, club, open_shop, character, item, other_character
):
    record(character, "award", [Line(item=item, quantity=3)])
    make_quest(
        club,
        "Ended quest",
        item,
        start_date=_today() - timedelta(days=10),
        end_date=_today() - timedelta(days=1),
    )
    make_quest(club, "Upcoming quest", item, start_date=_today() + timedelta(days=1))
    full = make_quest(
        club, "Full quest", item, max_completions=1, start_date=_today() - timedelta(days=1)
    )
    QuestCompletion.objects.create(quest=full, character=other_character, date=_today())
    c = card(login(player), club, open_shop)
    assert "Needed for" not in c


@pytest.mark.story("U137")
def test_finished_by_character_hidden_not_by_other(
    login, player, club, open_shop, character, item, other_character
):
    record(character, "award", [Line(item=item, quantity=3)])
    finished = make_quest(
        club, "Limited quest", item, max_per_character=1, start_date=_today() - timedelta(days=1)
    )
    QuestCompletion.objects.create(quest=finished, character=character, date=_today())
    c = card(login(player), club, open_shop)
    assert "Needed for" not in c

    open_quest = make_quest(
        club, "Limited quest 2", item, max_per_character=1, start_date=_today() - timedelta(days=1)
    )
    QuestCompletion.objects.create(quest=open_quest, character=other_character, date=_today())
    c = card(login(player), club, open_shop)
    assert "Needed for: Limited quest 2" in c


@pytest.mark.story("U137")
def test_other_club_quest_hidden(login, player, club, open_shop, character, item, other_club):
    record(character, "award", [Line(item=item, quantity=3)])
    foreign = Item.objects.create(club=other_club, name="Foreign Rope", value_cp=100)
    make_quest(other_club, "Other club quest", foreign, start_date=_today() - timedelta(days=7))
    c = card(login(player), club, open_shop)
    assert "Needed for" not in c


@pytest.mark.story("U137")
def test_tag_returns_none_and_multiple_names(character, item):
    from quests.templatetags.quest_needs import quest_needs

    assert quest_needs(None) == {}
    make_quest(character.club, "Alpha quest", item, start_date=_today() - timedelta(days=7))
    make_quest(character.club, "Zulu quest", item, start_date=_today() - timedelta(days=7))
    assert quest_needs(character) == {item.pk: ["Alpha quest", "Zulu quest"]}


@pytest.mark.story("U137")
def test_sell_junk_modal_has_no_quest_warning(
    login, player, club, shop, character, item, always_open
):
    record(character, "award", [Line(item=item, quantity=3)])
    set_junk(character, item, 3, player)
    body = (
        login(player)
        .get(reverse("shops:sell_junk", args=[club.slug, shop.pk]), HTTP_HX_REQUEST="true")
        .content.decode()
    )
    assert "is needed for the quest" not in body
