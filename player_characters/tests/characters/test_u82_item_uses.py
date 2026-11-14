import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from ledger.models import LedgerEntry
from ledger.services import Line, recent_changes, record
from player_characters.inventory import USE_CIRCLE_CAP

pytestmark = [pytest.mark.story("U82"), pytest.mark.django_db]

TIP = "Mark items as lost or used up, based on what happened during the session."


@pytest.fixture
def owned(character, item):
    record(character, "award", [Line(item=item, quantity=5)])
    return character


def consume_url(club, character, item):
    return reverse("characters:player_consume", args=[club.slug, character.pk, item.pk])


def sheet_url(club, character):
    return reverse("characters:detail", args=[club.slug, character.pk])


def print_all(club, character):
    return reverse("characters:print_items", args=[club.slug, character.pk])


def print_one(club, character, item, layout):
    return (
        reverse("characters:print_item", args=[club.slug, character.pk, item.pk])
        + f"?layout={layout}"
    )


def _give(character, item, n):
    record(character, "award", [Line(item=item, quantity=n)])


def _body(club, login, user, url):
    return login(user).get(url).content.decode()


# circles
def test_no_circles_for_single_item(club, login, player, character, item):
    _give(character, item, 1)
    body = _body(club, login, player, print_all(club, character))
    assert "wm-item-card-uses" not in body


def test_circles_match_quantity(club, login, player, owned, item):
    for url in (
        print_all(club, owned),
        print_one(club, owned, item, "full"),
        print_one(club, owned, item, "grid"),
    ):
        body = _body(club, login, player, url)
        assert body.count('class="wm-use-circle"') == 5
        assert "Used" in body and "+" not in body.split("wm-item-card-uses")[1].split("</div>")[0]


def test_circles_cap_with_overflow(club, login, player, character, item):
    _give(character, item, 35)
    body = _body(club, login, player, print_all(club, character))
    assert body.count('class="wm-use-circle"') == USE_CIRCLE_CAP
    assert "+5" in body


# wordmark
def test_wordmark_on_every_card(club, login, player, owned, item, second_item):
    _give(owned, second_item, 1)
    body = _body(club, login, player, print_all(club, owned))
    assert body.count('<article class="wm-item-card') == 2
    assert body.count('class="wm-item-card-brand wm-wordmark">✦ downtime market ✦<') == 2
    for layout in ("full", "grid"):
        assert "wm-wordmark" in _body(club, login, player, print_one(club, owned, item, layout))


# button
def test_owner_only_button(club, login, request, owned, item):
    url = consume_url(club, owned, item)
    assert url in _body(club, login, request.getfixturevalue("player"), sheet_url(club, owned))
    assert TIP in _body(club, login, request.getfixturevalue("player"), sheet_url(club, owned))
    for who in ("game_master", "club_admin"):
        assert url not in _body(club, login, request.getfixturevalue(who), sheet_url(club, owned))


@pytest.mark.parametrize("who", ["game_master", "club_admin", "other_player"])
def test_non_owner_forbidden(club, login, request, owned, item, who):
    c = login(request.getfixturevalue(who))
    assert c.get(consume_url(club, owned, item)).status_code == 403
    assert c.post(consume_url(club, owned, item), {"quantity": "1"}).status_code == 403
    assert LedgerEntry.objects.filter(kind="consumed").count() == 0


# modal
def test_modal_and_plain_page(club, login, player, owned, item):
    c = login(player)
    modal = c.get(consume_url(club, owned, item), HTTP_HX_REQUEST="true").content.decode()
    page = c.get(consume_url(club, owned, item)).content.decode()
    assert "Are you sure you want to consume" in modal and "<html" not in modal
    assert "Recent changes" in modal
    assert "<html" in page and "Are you sure you want to consume" in page


# ledger
def test_consume_writes_ledger_with_actor(club, login, player, owned, item):
    r = login(player).post(consume_url(club, owned, item), {"quantity": "2", "note": "Drank them"})
    assert r.status_code == 302
    entry = LedgerEntry.objects.get(kind="consumed")
    assert entry.created_by == player and entry.note == "Drank them"
    assert [(line.item, line.quantity) for line in entry.lines.all()] == [(item, -2)]


def test_blank_note_defaults(club, login, player, owned, item):
    r = login(player).post(
        consume_url(club, owned, item), {"quantity": "1"}, HTTP_HX_REQUEST="true"
    )
    assert r.status_code == 204 and "HX-Redirect" in r.headers
    assert LedgerEntry.objects.get(kind="consumed").note == "Consumed"


def test_over_quantity_refused(club, login, player, owned, item):
    r = login(player).post(consume_url(club, owned, item), {"quantity": "6"})
    assert r.status_code == 200
    assert LedgerEntry.objects.filter(kind="consumed").count() == 0


def test_items_in_open_trade_not_available(club, login, player, owned, item, make_open_trade):
    make_open_trade(sender=owned, items={item: 4})
    c = login(player)
    assert c.post(consume_url(club, owned, item), {"quantity": "2"}).status_code == 200
    assert LedgerEntry.objects.filter(kind="consumed").count() == 0
    assert c.post(consume_url(club, owned, item), {"quantity": "1"}).status_code == 302


def test_cross_club_is_404(club, login, player, owned, item, foreign_character, foreign_item):
    c = login(player)
    assert c.get(consume_url(club, foreign_character, item)).status_code == 404
    assert c.get(consume_url(club, owned, foreign_item)).status_code == 404


# recent changes
def _entry(character, kind, days_ago, actor=None, note="n"):
    return record(
        character,
        kind,
        [Line(coins=1)],
        note=note,
        date=timezone.localdate() - datetime.timedelta(days=days_ago),
        actor=actor,
    )


def test_recent_changes_rules(character, other_character, player, game_master):
    _entry(character, "consumed", 1, player)
    _entry(character, "adjustment", 0, game_master)
    _entry(character, "consumed", 40)
    _entry(character, "trade", 1)
    _entry(other_character, "consumed", 1)
    got = recent_changes(character)
    assert [e.kind for e in got] == ["adjustment", "consumed"]
    assert {e.created_by for e in got} == {player, game_master}


def test_recent_changes_limit(character):
    for _ in range(25):
        _entry(character, "consumed", 1)
    assert len(recent_changes(character)) == 20


def test_recent_list_on_all_forms(club, login, player, game_master, owned, item):
    _entry(owned, "adjustment", 0, game_master, note="Marker note")
    for user, url in (
        (game_master, reverse("characters:consume", args=[club.slug, owned.pk])),
        (game_master, reverse("characters:adjust", args=[club.slug, owned.pk])),
        (player, consume_url(club, owned, item)),
    ):
        body = _body(club, login, user, url)
        assert "Recent changes" in body and "Marker note" in body
