"""Tests for Value and Weight columns on the character sheet inventory (U165).

Covers: value and weight per row, stacked per-unit tooltips and totals, dash for
unlisted weight, one-pass computation (no query per row), print layout, and
that GM-only details are never exposed to players.
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import Membership
from items.models import Item
from ledger.services import Line, record
from player_characters.models import Character


def u(name, club, pk=None):
    kw = {"club_slug": club.slug}
    if pk is not None:
        kw["pk"] = pk
    return reverse(name, kwargs=kw)


def _character(club, player, name):
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(club=club, owner=owner, name=name)


def _award(character, item, quantity=1):
    record(character, "award", [Line(item=item, quantity=quantity)])


def test_value_and_weight_per_row(club, login, player):
    character = _character(club, player, "Aria")
    rope = Item.objects.create(club=club, name="Rope", value_cp=100, weight_hundredth_lb=500)
    _award(character, rope, quantity=3)

    html = login(player).get(u("characters:detail", club, character.pk)).content.decode()
    # 100 cp = 1 gp base value (non-stacked: base value shown, not multiplied)
    assert "1 gp" in html
    # 500 hundredths = 5.0 lb (non-stacked: weight is per item)
    assert "5.0 lb" in html


def test_stacked_shows_per_unit_tooltip_and_totals(club, login, player):
    character = _character(club, player, "Aria")
    arrows = Item.objects.create(
        club=club,
        name="Arrow",
        value_cp=100,
        value_units=20,  # 100 cp per 20 arrows -> 5 cp per arrow
        weight_hundredth_lb=40,  # 0.4 lb per arrow
        is_stacked=True,
        unit_name="arrow",
    )
    _award(character, arrows, quantity=40)

    html = login(player).get(u("characters:detail", club, character.pk)).content.decode()
    # Totals: 40 arrows x 5 cp = 200 cp = 2 gp ; 40 x 0.4 lb = 16.0 lb
    assert "2 gp" in html
    assert "16.0 lb" in html
    # Per-unit tooltip: 5 cp per arrow and 0.4 lb per arrow
    assert "5 cp per arrow" in html
    assert "0.4 lb per arrow" in html


def test_unlisted_weight_shows_dash(club, login, player):
    character = _character(club, player, "Aria")
    item = Item.objects.create(club=club, name="Potion", value_cp=50)  # no weight
    _award(character, item)

    html = login(player).get(u("characters:detail", club, character.pk)).content.decode()
    assert "5 sp" in html  # 50 cp
    assert "—" in html  # dash for no weight listed


def test_no_query_per_row(club, login, player):
    """Fetching the sheet must not issue one query per inventory row.

    Items are fetched with a single ``Item.objects.filter(pk__in=...)`` query,
    so the number of queries against ``items_item`` stays at one however many
    rows the sheet has.
    """

    def item_query_count(character):
        client = login(player)
        with CaptureQueriesContext(connection) as ctx:
            client.get(u("characters:detail", club, character.pk))
        return sum(1 for q in ctx.captured_queries if 'FROM "items_item"' in q["sql"])

    one_item = _character(club, player, "Solo")
    solo = Item.objects.create(club=club, name="Solo Item", value_cp=10, weight_hundredth_lb=100)
    _award(one_item, solo)

    many = _character(club, player, "Many")
    for name in ("Rope", "Torch", "Potion"):
        item = Item.objects.create(club=club, name=name, value_cp=10, weight_hundredth_lb=100)
        _award(many, item)

    assert item_query_count(one_item) == 1
    assert item_query_count(many) == 1


def test_gm_details_not_exposed_to_player(club, login, player):
    character = _character(club, player, "Aria")
    item = Item.objects.create(
        club=club,
        name="Blade",
        value_cp=300,
        weight_hundredth_lb=200,
        gm_details="It is bound to the wielder and cannot be sold.",
    )
    _award(character, item)

    html = login(player).get(u("characters:detail", club, character.pk)).content.decode()
    assert "3 gp" in html
    assert "2.0 lb" in html
    assert "bound to the wielder" not in html


def test_print_layout_includes_value_and_weight(club, login, player):
    character = _character(club, player, "Aria")
    item = Item.objects.create(club=club, name="Rope", value_cp=100, weight_hundredth_lb=500)
    _award(character, item)

    html = login(player).get(u("characters:detail", club, character.pk)).content.decode()
    # Both column headers are present in the sheet markup (print shows the same sheet).
    assert "wm-col-value" in html and "wm-col-weight" in html
    assert "Value" in html and "Weight" in html
