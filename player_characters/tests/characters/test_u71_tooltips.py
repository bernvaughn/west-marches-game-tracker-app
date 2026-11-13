from html.parser import HTMLParser

import pytest

from player_characters.models import Character
from player_characters.tests.characters.test_sheet import u

EDIT = "Change this character's details: name, level, class, ability scores and more."
HISTORY = "See every change to this character's coins and items."
EXPECTED = {
    "Edit": EDIT,
    "Adjust": "Add or remove coins and items, for example loot from a session or a correction.",
    "Consume": "Mark items as lost or used up, based on what happened during the session.",
    "Transfer": "Move items or coins from this character to another of your characters.",
    "Hand over": "Give this character to another player.",
    "History": HISTORY,
    "Print item cards": "Print cards for all items, nine to a page, to bring to the table.",
    "Print sheet": "Print this character sheet in black and white.",
    "Full ledger": HISTORY,
}
ICONS = {
    "Mark as junk": "Set aside items to sell later, in shops or your own stall.",
    "Print card": "Print this one item's card, as a full page or in one spot of a card sheet.",
}
SWITCH = "List your junk in your own stall on the street for other players to buy."


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.els = []
        self._open = []
        self.label_for = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "label" and a.get("for"):
            self.label_for.add(a["for"])
        rec = [tag, a, ""]
        self.els.append(rec)
        self._open.append(rec)

    def handle_endtag(self, tag):
        if self._open and self._open[-1][0] == tag:
            self._open.pop()

    def handle_data(self, data):
        for r in self._open:
            r[2] += data


def parse(html):
    c = Collector()
    c.feed(html[html.index("<main") :])
    return c


@pytest.fixture
def page(club, login, player, game_master, club_admin, funded):
    # Owner (with a second character), GM and admin see different buttons; merge pages.
    Character.objects.create(club=club, owner=funded.owner, name="Second")
    merged = Collector()
    for who in (player, game_master, club_admin):
        c = parse(login(who).get(u("characters:detail", club, funded.pk)).content.decode())
        merged.els += c.els
        merged.label_for |= c.label_for
    return merged


@pytest.mark.story("U71")
def test_text_buttons_have_exact_tooltips_and_names(page):
    for label, text in EXPECTED.items():
        found = [e for e in page.els if e[0] in ("a", "button") and e[2].strip() == label]
        assert found, label
        for _, attrs, _ in found:
            assert "data-wm-tooltip" in attrs, label
            assert attrs.get("title") == text, label


@pytest.mark.story("U71")
def test_icon_buttons_keep_aria_label_and_long_tooltip(page):
    for label, text in ICONS.items():
        found = [e for e in page.els if e[1].get("aria-label") == label]
        assert found, label
        assert "data-wm-tooltip" in found[0][1]
        assert found[0][1]["title"] == text


@pytest.mark.story("U71")
def test_shop_switch_has_tooltip_and_label(page):
    wrap = [e for e in page.els if e[1].get("title") == SWITCH]
    assert wrap and "data-wm-tooltip" in wrap[0][1]
    assert "shop-open" in page.label_for


@pytest.mark.story("U71")
def test_no_adjust_rights_no_adjust_button(club, login, other_player, funded):
    html = login(other_player).get(u("characters:detail", club, funded.pk)).content.decode()
    assert EXPECTED["Adjust"] not in html and EXPECTED["Consume"] not in html
