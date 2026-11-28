import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from items.tests.factories import make_arrows, make_parchment, make_rope
from ledger.models import LedgerEntry
from ledger.services import Line, record
from player_characters.inventory import inventory_rows
from player_characters.item_cards import build_cards, too_many
from player_characters.notes import set_note

pytestmark = [
    pytest.mark.story("U127"),
    pytest.mark.story("U128"),
    pytest.mark.django_db,
]


def sheet_url(club, character):
    return reverse("characters:detail", args=[club.slug, character.pk])


def player_consume_url(club, character, item):
    return reverse("characters:player_consume", args=[club.slug, character.pk, item.pk])


def gm_consume_url(club, character):
    return reverse("characters:consume", args=[club.slug, character.pk])


def print_item_url(club, character, item, **q):
    base = reverse("characters:print_item", args=[club.slug, character.pk, item.pk])
    if q:
        base += "?" + "&".join(f"{k}={v}" for k, v in q.items())
    return base


def messages_of(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


def entries(character):
    return LedgerEntry.objects.filter(character=character).order_by("pk")


# --- unit helpers ----------------------------------------------------------


def test_build_cards_stacked_is_one_card(rope):
    cards = build_cards([(rope, 50)], "item")
    assert [(c.qty, len(c.use_circles), c.use_overflow) for c in cards] == [(50, 0, 0)]


def test_too_many_stacked_counts_one(rope, item):
    # 1000 units of a stacked item is still one card.
    assert not too_many([(rope, 1000)], "item")
    # a normal item with 91 units passes the cap.
    assert too_many([(item, 91)], "item")


# --- sheet / inventory display ---------------------------------------------


def test_sheet_shows_units_for_stacked_item(login, club, player, character, rope):
    record(character, "award", [Line(item=rope, quantity=40)])
    body = login(player).get(sheet_url(club, character)).content.decode()
    # Owned and Available cells show number and unit only (no item name)
    assert '<td class="num wm-col-optional">40 ft</td>' in body
    # Item name no longer appears in Owned/Available cells
    assert '<td class="num wm-col-optional">40 ft Rope</td>' not in body
    # normal style label never appears on the sheet
    assert "3 × " not in body


def test_sheet_shows_bare_number_for_normal_item(login, club, player, character, item, rope):
    record(character, "award", [Line(item=item, quantity=3)])
    record(character, "award", [Line(item=rope, quantity=40)])
    body = login(player).get(sheet_url(club, character)).content.decode()
    # Stacked item: Owned/Available cells show number and unit only
    assert '<td class="num wm-col-optional">40 ft</td>' in body
    assert '<td class="num wm-col-optional">40 ft Rope</td>' not in body
    # Normal item: bare number
    assert '<td class="num wm-col-optional">3</td>' in body
    assert "3 × " not in body


def test_sheet_shows_different_owned_available_and_zero(
    login, club, player, character, rope, parchment
):
    """Test that Owned and Available show number and unit only."""
    # Award 50 ft rope, then consume 10 so Owned=40, Available=40 (no holds)
    record(character, "award", [Line(item=rope, quantity=50)])
    record(character, "consumed", [Line(item=rope, quantity=-10)], note="Used some")
    # Award 25 sheet parchment
    record(character, "award", [Line(item=parchment, quantity=25)])
    body = login(player).get(sheet_url(club, character)).content.decode()
    # Both Owned and Available cells show number and unit only
    assert '<td class="num wm-col-optional">40 ft</td>' in body
    assert '<td class="num wm-col-optional">25 sheet</td>' in body
    # Item names not in Owned/Available cells (check cell content specifically)
    assert '<td class="num wm-col-optional">40 ft Rope</td>' not in body
    assert '<td class="num wm-col-optional">25 sheet Parchment</td>' not in body


@pytest.mark.story("U37")
def test_inventory_phone_markup(login, club, player, character, item, rope):
    """Pin the phone inventory markup: wm-col-optional on Owned/Available,
    wm-sheet-item-name flex wrapper, wm-sheet-owned-inline with quantity."""
    record(character, "award", [Line(item=item, quantity=2)])
    record(character, "award", [Line(item=rope, quantity=40)])

    body = login(player).get(sheet_url(club, character)).content.decode()

    # Owned and Available th have wm-col-optional
    assert '<th class="num wm-col-optional">Owned</th>' in body
    assert '<th class="num wm-col-optional">Available</th>' in body

    # Normal item: Owned td has wm-col-optional and shows bare number 2
    assert '<td class="num wm-col-optional">2</td>' in body
    # Stacked item: Owned td has wm-col-optional and shows number and unit only
    assert '<td class="num wm-col-optional">40 ft</td>' in body

    # wm-sheet-item-name wrapper exists
    assert 'class="wm-sheet-item-name"' in body

    # wm-sheet-owned-inline shows "&times; 2" for normal item (HTML entity)
    assert 'class="wm-sheet-owned-inline">&times; 2</small>' in body
    # wm-sheet-owned-inline shows "40 ft" for stacked item
    assert 'class="wm-sheet-owned-inline">40 ft</small>' in body

    # Actions cell still has no-print wm-row-actions-cell
    assert 'class="no-print wm-row-actions-cell"' in body


# --- item cards ------------------------------------------------------------


def test_print_card_stacked_one_card_held_pill_no_circles(login, club, player, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    body = login(player).get(print_item_url(club, character, rope, layout="grid")).content.decode()
    assert body.count('<article class="wm-item-card wm-pass"') == 1
    assert "50 ft Rope" in body
    assert "Held" in body
    assert "wm-use-circle" not in body
    pills = body.split('<ul class="wm-item-card-pills">')[1].split("</ul>")[0]
    assert "Qty" not in pills


def test_print_card_stacked_copies_item_does_not_multiply(login, club, player, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    choose = login(player).get(print_item_url(club, character, rope)).content.decode()
    # "One card per item" is not offered for a stacked item
    assert "copies=item" not in choose
    # copies=item is accepted but treated as type: still one card
    body = (
        login(player)
        .get(print_item_url(club, character, rope, layout="grid", copies="item"))
        .content.decode()
    )
    assert body.count('<article class="wm-item-card wm-pass"') == 1


def test_print_card_normal_unchanged(login, club, player, character, item):
    record(character, "award", [Line(item=item, quantity=5)])
    body = login(player).get(print_item_url(club, character, item, layout="grid")).content.decode()
    assert body.count('<article class="wm-item-card wm-pass"') == 1
    assert "Qty" in body
    assert "wm-use-circle" in body


# --- player consume --------------------------------------------------------


def test_player_consume_shows_units(login, club, player, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    c = login(player)
    r = c.get(player_consume_url(club, character, rope), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert "You have 50 ft Rope available." in body
    assert "Units (ft)" in body


def test_player_consume_units(login, club, player, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    c = login(player)
    r = c.post(player_consume_url(club, character, rope), {"quantity": 10, "note": "Used some"})
    assert r.status_code == 302
    assert "Consumed 10 ft Rope." in messages_of(r)
    e = entries(character).get(kind="consumed")
    assert e.lines.get(item=rope).quantity == -10
    body = c.get(sheet_url(club, character)).content.decode()
    # Owned/Available cells show number and unit only
    assert '<td class="num wm-col-optional">40 ft</td>' in body
    assert '<td class="num wm-col-optional">40 ft Rope</td>' not in body
    # Old full text should not appear in sheet (but may be in ledger)
    assert "50 ft Rope" not in body.split("Recent ledger entries")[0]


def test_player_consume_over_cap_refused(login, club, player, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    c = login(player)
    before = LedgerEntry.objects.count()
    r = c.post(player_consume_url(club, character, rope), {"quantity": 51, "note": "x"})
    assert r.status_code == 200
    assert "Only 50 ft Rope available to consume." in r.content.decode()
    assert LedgerEntry.objects.count() == before


def test_player_consume_zero_refused(login, club, player, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    c = login(player)
    before = LedgerEntry.objects.count()
    r = c.post(player_consume_url(club, character, rope), {"quantity": 0, "note": "x"})
    assert r.status_code == 200
    assert LedgerEntry.objects.count() == before


def test_player_consume_to_zero_removes_row(login, club, player, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    c = login(player)
    c.post(player_consume_url(club, character, rope), {"quantity": 50, "note": "all of it"})
    assert rope.pk not in {r.item.pk for r in inventory_rows(character)}
    e = entries(character).get(kind="consumed")
    assert e.lines.get(item=rope).quantity == -50


# --- U122 note hides and returns ------------------------------------------


def test_u122_note_hides_and_returns(login, club, player, game_master, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    set_note(character, rope, "Do not lose this.", player)
    c = login(player)
    c.post(player_consume_url(club, character, rope), {"quantity": 50, "note": "used it all"})
    # row and note hidden on the sheet
    body = c.get(sheet_url(club, character)).content.decode()
    assert "Do not lose this." not in body
    assert rope.pk not in {r.item.pk for r in inventory_rows(character)}
    # GM view shows nothing either
    gbody = login(game_master).get(sheet_url(club, character)).content.decode()
    assert "Do not lose this." not in gbody
    # award rope again: note is back with the same text
    record(character, "award", [Line(item=rope, quantity=5)])
    body = c.get(sheet_url(club, character)).content.decode()
    assert 'title="Do not lose this."' in body
    assert rope.pk in {r.item.pk for r in inventory_rows(character)}


# --- GM consume ------------------------------------------------------------


def test_gm_consume_page_shows_units(login, club, game_master, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    body = login(game_master).get(gm_consume_url(club, character)).content.decode()
    assert "50 ft Rope" in body


def test_gm_consume_units(login, club, game_master, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    c = login(game_master)
    r = c.post(
        gm_consume_url(club, character),
        {
            "note": "",
            "date": "2025-01-02",
            "coins_cp": "",
            "items-TOTAL_FORMS": "3",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "3",
            "items-0-item": rope.pk,
            "items-0-quantity": 20,
        },
    )
    assert r.status_code == 302
    e = entries(character).get(kind="consumed")
    assert e.lines.get(item=rope).quantity == -20
    body = c.get(sheet_url(club, character)).content.decode()
    # Owned/Available cells show number and unit only
    assert '<td class="num wm-col-optional">30 ft</td>' in body
    assert '<td class="num wm-col-optional">30 ft Rope</td>' not in body


def test_gm_consume_over_cap_refused(login, club, game_master, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    c = login(game_master)
    before = LedgerEntry.objects.count()
    r = c.post(
        gm_consume_url(club, character),
        {
            "note": "",
            "date": "2025-01-02",
            "coins_cp": "",
            "items-TOTAL_FORMS": "3",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "3",
            "items-0-item": rope.pk,
            "items-0-quantity": 60,
        },
    )
    assert r.status_code == 200
    assert "Only 50 ft Rope available to consume." in r.content.decode()
    assert LedgerEntry.objects.count() == before


def test_non_stacked_consume_message_unchanged(login, club, game_master, character, item):
    record(character, "award", [Line(item=item, quantity=5)])
    c = login(game_master)
    r = c.post(
        gm_consume_url(club, character),
        {
            "note": "",
            "date": "2025-01-02",
            "coins_cp": "",
            "items-TOTAL_FORMS": "3",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "3",
            "items-0-item": item.pk,
            "items-0-quantity": 2,
        },
    )
    assert r.status_code == 302
    e = entries(character).get(kind="consumed")
    assert e.lines.get(item=item).quantity == -2


# --- permissions -----------------------------------------------------------


@pytest.mark.parametrize("who", ["game_master", "club_admin", "site_admin"])
def test_gm_consume_page_allowed(request, login, club, character, rope, who):
    record(character, "award", [Line(item=rope, quantity=50)])
    assert (
        login(request.getfixturevalue(who)).get(gm_consume_url(club, character)).status_code == 200
    )


def test_player_consume_owner_ok(login, club, player, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    assert login(player).get(player_consume_url(club, character, rope)).status_code == 200


def test_player_consume_other_player_403(login, club, other_player, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    c = login(other_player)
    assert c.get(player_consume_url(club, character, rope)).status_code == 403
    assert (
        c.post(player_consume_url(club, character, rope), {"quantity": 1, "note": "x"}).status_code
        == 403
    )


def test_player_consume_anonymous_302(club, client, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    assert client.get(player_consume_url(club, character, rope)).status_code == 302


def test_gm_consume_player_403(login, club, player, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    assert login(player).get(gm_consume_url(club, character)).status_code == 403


def test_gm_consume_anonymous_302(club, client, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    assert client.get(gm_consume_url(club, character)).status_code == 302


def test_gm_consume_other_club_404(login, club, foreign_member, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    assert login(foreign_member).get(gm_consume_url(club, character)).status_code == 404


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def rope(club):
    return make_rope(club)


@pytest.fixture
def parchment(club):
    return make_parchment(club)


@pytest.fixture
def arrows(club):
    return make_arrows(club)
