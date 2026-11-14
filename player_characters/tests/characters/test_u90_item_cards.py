import datetime

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from items.models import Item
from ledger.services import Line, record
from player_characters.inventory import USE_CIRCLE_CAP
from player_characters.item_cards import CARD_CAP, build_cards, too_many

pytestmark = [pytest.mark.story("U90"), pytest.mark.django_db]

CARD = '<article class="wm-item-card wm-pass'


def all_url(club, ch, **q):
    base = reverse("characters:print_items", args=[club.slug, ch.pk])
    return base + ("?" + "&".join(f"{k}={v}" for k, v in q.items()) if q else "")


def one_url(club, ch, item, **q):
    base = reverse("characters:print_item", args=[club.slug, ch.pk, item.pk])
    return base + ("?" + "&".join(f"{k}={v}" for k, v in q.items()) if q else "")


def give(ch, item, n):
    record(ch, "award", [Line(item=item, quantity=n)])


def get(login, user, url):
    r = login(user).get(url)
    return r, r.content.decode()


# unit
def test_build_cards_type_and_item(item):
    t = build_cards([(item, 5), (item, 1), (item, 35)], "type")
    assert [c.qty for c in t] == [5, 1, 35]
    assert len(t[0].use_circles) == 5 and len(t[1].use_circles) == 0
    assert len(t[2].use_circles) == USE_CIRCLE_CAP and t[2].use_overflow == 5
    i = build_cards([(item, 3)], "item")
    assert [(c.qty, len(c.use_circles), c.use_overflow) for c in i] == [(1, 1, 0)] * 3


def test_too_many(item):
    assert not too_many([(item, CARD_CAP)], "item")
    assert too_many([(item, CARD_CAP), (item, 1)], "item")
    assert not too_many([(item, 500)], "type")


# layout
def test_card_layout(login, club, player, character):
    it = Item.objects.create(
        club=club,
        name="Flame Tongue",
        symbol="🔥",
        value_cp=100,
        rarity="rare",
        magic_type="weapon",
        description="Burns.",
        traits="Fire",
        details="Needs attunement",
    )
    give(character, it, 1)
    _, b = get(login, player, all_url(club, character))
    for s in (
        "✦ downtime market ✦",
        "wm-item-card-icon",
        "🔥",
        "wm-wordmark wm-item-card-name",
        "Rarity",
        "Value",
        "Qty",
        "Rare",
        "Weapon",
        "Description",
        "Traits",
        "Details",
        "wm-pass-rule",
    ):
        assert s in b, s
    assert f"printed {timezone.localdate():%Y-%m-%d}" in b
    assert "Maya" in b or character.name in b


def test_blank_pills_left_out(login, club, player, character, item):
    give(character, item, 1)
    _, b = get(login, player, all_url(club, character))
    assert "Rarity" not in b.split("wm-item-card-pills")[1].split("</ul>")[0]
    assert '<span class="wm-pill-label">Type</span>' not in b
    assert "wm-item-card-icon" not in b
    assert '<span class="wm-pill-label">Qty</span>' in b


def test_magic_pill_shown(login, club, player, character, item):
    item.magic_type = "wondrous"
    item.save()
    give(character, item, 1)
    _, b = get(login, player, all_url(club, character))
    assert "Wondrous item" in b


def test_circles_and_cap(login, club, player, character, item):
    give(character, item, 35)
    _, b = get(login, player, all_url(club, character))
    assert b.count('class="wm-use-circle"') == USE_CIRCLE_CAP and "+5" in b


# copies
def test_copies_type_is_default(login, club, player, funded):
    _, a = get(login, player, all_url(club, funded))
    _, b = get(login, player, all_url(club, funded, copies="type"))
    assert a.count(CARD) == b.count(CARD) == 1
    assert "<strong>Used</strong>" in b and b.count('class="wm-use-circle"') == 5


def test_copies_item(login, club, player, funded, character):
    other = Item.objects.create(club=club, name="Lamp", value_cp=5)
    give(character, other, 1)
    _, b = get(login, player, all_url(club, funded, copies="item"))
    assert b.count(CARD) == 6
    assert b.count('<span class="wm-pill-value">1</span>') == 6
    assert b.count('class="wm-use-circle"') == 6


def test_sheets_continue(login, club, player, character, item):
    give(character, item, 10)
    _, b = get(login, player, all_url(club, character, copies="item"))
    assert b.count('<section class="wm-card-sheet">') == 2
    assert b.split('<section class="wm-card-sheet">')[1].count(CARD) == 9


def test_cap_message(login, club, player, character, item):
    give(character, item, CARD_CAP + 1)
    r, b = get(login, player, all_url(club, character, copies="item"))
    assert r.status_code == 200 and "more than 90 cards" in b and CARD not in b
    give(character, item, 0) if False else None
    _, ok = get(login, player, all_url(club, character, copies="type"))
    assert ok.count(CARD) == 1


def test_cap_exactly_ok(login, club, player, character, item):
    give(character, item, CARD_CAP)
    _, b = get(login, player, all_url(club, character, copies="item"))
    assert b.count(CARD) == 90 and b.count('<section class="wm-card-sheet">') == 10


def test_bad_copies(login, club, player, funded, item):
    c = login(player)
    assert c.get(all_url(club, funded, copies="x")).status_code == 400
    assert c.get(one_url(club, funded, item, layout="grid", copies="x")).status_code == 400


# single item
def test_single_item_grid_item(login, club, player, character, item):
    give(character, item, 11)
    _, b = get(login, player, one_url(club, character, item, layout="grid", copies="item"))
    assert b.count(CARD) == 11 and b.count('<section class="wm-card-sheet">') == 2
    assert b.count("wm-card-cell") == 7


def test_single_item_full_item(login, club, player, funded, item):
    _, b = get(login, player, one_url(club, funded, item, layout="full", copies="item"))
    assert b.count('<div class="wm-card-page">') == 5 and "wm-item-card--full" in b


def test_single_item_type_unchanged(login, club, player, funded, item):
    _, g = get(login, player, one_url(club, funded, item, layout="grid"))
    assert g.count(CARD) == 1 and g.count("wm-card-cell") == 8
    _, f = get(login, player, one_url(club, funded, item, layout="full", copies="type"))
    assert f.count('<div class="wm-card-page">') == 1


def test_single_item_cap(login, club, player, character, item):
    give(character, item, 91)
    _, b = get(login, player, one_url(club, character, item, layout="grid", copies="item"))
    assert "more than 90 cards" in b and CARD not in b


def test_chooser_groups(login, club, player, funded, character, item):
    _, b = get(login, player, one_url(club, funded, item))
    assert "One card per item type" in b and "copies=item" in b and "copies=type" in b
    other = Item.objects.create(club=club, name="Lamp", value_cp=5)
    give(character, other, 1)
    _, b = get(login, player, one_url(club, character, other))
    assert "copies=item" not in b and "copies=type" in b


def test_sheet_dropdown_groups(login, club, player, funded):
    _, b = get(login, player, reverse("characters:detail", args=[club.slug, funded.pk]))
    assert "One card per item type" in b and "copies=item" in b


# footer
def test_footer_owner(login, club, player, funded):
    _, b = get(login, player, all_url(club, funded))
    assert f"{funded.name} · printed {timezone.localdate():%Y-%m-%d}" in b


def test_footer_loot_without_owner(item):
    card = build_cards([(item, 1)])[0]
    html = render_to_string(
        "player_characters/characters/_item_card.html",
        {"card": card, "owner": None, "printed_on": datetime.date(2026, 1, 2)},
    )
    assert "Loot · printed 2026-01-02" in html


# isolation
def test_cross_club_copies_item(
    login, club, other_club, player, foreign_member, foreign_character, funded, item
):
    c = login(player)
    assert c.get(all_url(club, foreign_character, copies="item")).status_code == 404
    assert c.get(all_url(other_club, foreign_character, copies="item")).status_code == 404
    assert (
        c.get(one_url(club, foreign_character, item, layout="grid", copies="item")).status_code
        == 404
    )
