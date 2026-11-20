"""Tests for the starting gear reveal page.

The reveal shows the saved 'Starting equipment' ledger entry: the items one
by one, then the starting coins. It never rolls and never writes.
"""

from pathlib import Path

import pytest
from django.urls import reverse

from items.models import Item
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import Line, record

pytestmark = [pytest.mark.django_db]

STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static"


def reveal_url(club, character):
    return reverse(
        "characters:starting_reveal",
        kwargs={"club_slug": club.slug, "pk": character.pk},
    )


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


def grant_starting_equipment(character, actor, item_lines=None, coins_cp=0):
    """Create the single 'Starting equipment' award entry (no code path writes)."""
    lines = [Line(item=item, quantity=qty, coins=0) for item, qty in (item_lines or [])]
    if coins_cp:
        lines.append(Line(item=None, quantity=0, coins=coins_cp))
    return record(
        character,
        LedgerEntry.Kind.AWARD,
        lines,
        note="Starting equipment",
        actor=actor,
    )


def entry_counts(character):
    return {
        "entries": LedgerEntry.objects.filter(character=character).count(),
        "lines": LedgerLine.objects.filter(entry__character=character).count(),
        "claimed": character.starting_equipment_claimed,
    }


# ---------------------------------------------------------------------------
# owner GET
# ---------------------------------------------------------------------------


def test_owner_get_shows_items_and_coins(login, player, club, character, item):
    """The owner sees each granted item, the coins, the live region and the buttons."""
    sword = item
    sack = Item.objects.create(club=club, name="Sack", value_cp=50)
    grant_starting_equipment(character, player, item_lines=[(sword, 1), (sack, 2)], coins_cp=1500)

    client = login(player)
    response = client.get(reveal_url(club, character))
    assert response.status_code == 200

    content = response.content.decode()
    assert "+1 Rope" in content
    assert "+2 Sack" in content
    assert "+1 " + sword.name in content
    assert "data-wm-live" in content
    assert 'role="status"' in content
    assert 'aria-live="polite"' in content
    assert "data-wm-starting-reveal" in content
    assert "data-wm-reveal-item" in content
    assert "data-wm-coins-display" in content
    assert 'href="' + detail_url(club, character) + '"' in content
    assert "data-wm-skip" in content
    assert "data-wm-replay" in content
    assert "js/starting_coins_animation.js" in content
    assert "js/starting_reveal.js" in content


def test_owner_get_merges_duplicate_item_lines(login, player, club, character, item):
    """Two lines for the same item render merged, ordered by id."""
    grant_starting_equipment(character, player, item_lines=[(item, 1), (item, 3)], coins_cp=0)

    client = login(player)
    response = client.get(reveal_url(club, character))
    assert response.status_code == 200

    content = response.content.decode()
    assert "+4 " + item.name in content


def test_owner_get_items_only_renders_no_coins_block(login, player, club, character, item):
    """An items-only entry renders no coins block."""
    grant_starting_equipment(character, player, item_lines=[(item, 1)], coins_cp=0)

    client = login(player)
    response = client.get(reveal_url(club, character))
    assert response.status_code == 200

    content = response.content.decode()
    assert "+1 " + item.name in content
    assert "data-wm-coins" not in content


def test_owner_get_coins_only_renders_no_item_block(login, player, club, character):
    """A coins-only entry renders no item block and no stray rows."""
    grant_starting_equipment(character, player, item_lines=None, coins_cp=2500)

    client = login(player)
    response = client.get(reveal_url(club, character))
    assert response.status_code == 200

    content = response.content.decode()
    assert "data-wm-coins-display" in content
    assert "<ul data-wm-reveal>" in content
    assert "data-wm-reveal-item" not in content


# ---------------------------------------------------------------------------
# no writes
# ---------------------------------------------------------------------------


def test_get_does_not_change_ledger_or_inventory(login, player, club, character, item):
    """GET and a reload change nothing: no new entry, no new lines, claimed flag untouched."""
    grant_starting_equipment(character, player, item_lines=[(item, 1)], coins_cp=1000)
    before = entry_counts(character)

    client = login(player)
    client.get(reveal_url(club, character))
    client.get(reveal_url(club, character))  # reload
    assert entry_counts(character) == before


# ---------------------------------------------------------------------------
# permissions
# ---------------------------------------------------------------------------


def test_another_player_gets_403(login, player, other_player, club, character, item):
    grant_starting_equipment(character, player, item_lines=[(item, 1)], coins_cp=1000)

    client = login(other_player)
    response = client.get(reveal_url(club, character))
    assert response.status_code == 403


def test_cross_club_member_gets_404(login, club, other_player, foreign_character):
    """A member of another club cannot see another club's character reveal (404)."""
    foreign_item = Item.objects.create(
        club=foreign_character.club, name="Foreign Rope", value_cp=10
    )
    grant_starting_equipment(
        foreign_character,
        foreign_character.owner.user,
        item_lines=[(foreign_item, 1)],
        coins_cp=1000,
    )

    client = login(other_player)
    response = client.get(
        reverse(
            "characters:starting_reveal",
            kwargs={"club_slug": club.slug, "pk": foreign_character.pk},
        )
    )
    assert response.status_code == 404


def test_anonymous_get_redirects_to_login(client, club, character, item):
    grant_starting_equipment(character, character.owner.user, item_lines=[(item, 1)], coins_cp=1000)

    response = client.get(reveal_url(club, character))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


# ---------------------------------------------------------------------------
# no saved grant
# ---------------------------------------------------------------------------


def test_no_entry_redirects_to_sheet(login, player, club, character):
    """No 'Starting equipment' entry: nothing to reveal, go to the sheet."""
    client = login(player)
    response = client.get(reveal_url(club, character))
    assert response.status_code == 302
    assert response.url == detail_url(club, character)


# ---------------------------------------------------------------------------
# only the starting equipment entry is shown
# ---------------------------------------------------------------------------


def test_later_adjustment_entry_does_not_appear(login, player, club, character, item):
    """A later adjustment entry stays out of the reveal."""
    grant_starting_equipment(character, player, item_lines=[(item, 1)], coins_cp=1000)
    from items.models import Item as _Item

    potion = _Item.objects.create(club=club, name="Potion of Healing", value_cp=100)
    record(character, LedgerEntry.Kind.ADJUSTMENT, [Line(item=potion, quantity=5)], actor=player)

    client = login(player)
    response = client.get(reveal_url(club, character))
    assert response.status_code == 200

    content = response.content.decode()
    assert "+1 " + item.name in content
    assert "Potion of Healing" not in content


# ---------------------------------------------------------------------------
# redirects from both grant paths
# ---------------------------------------------------------------------------


def test_redirects_have_shape(club, character):
    reveal = reveal_url(club, character)
    detail = detail_url(club, character)
    assert reveal != detail
    assert reveal.endswith("/starting-equipment/reveal/")


# ---------------------------------------------------------------------------
# static guards
# ---------------------------------------------------------------------------


def test_css_has_reduced_motion_block():
    css = (STATIC_DIR / "css" / "areas" / "containers.css").read_text()
    assert "prefers-reduced-motion: reduce" in css
    assert "[data-wm-starting-reveal]" in css


def test_js_never_rolls_or_fetches():
    js = (STATIC_DIR / "js" / "starting_reveal.js").read_text()
    for token in ("fetch(", "XMLHttpRequest", "Math.random"):
        assert token not in js, f"JS must not roll or fetch: {token!r}"


def test_js_exposes_coin_animation_callables():
    js = (STATIC_DIR / "js" / "starting_coins_animation.js").read_text()
    assert "window.wmAnimateCoins" in js
    assert "window.wmFormatCoins" in js
