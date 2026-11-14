import datetime
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import Membership
from items.models import Item
from ledger import views
from ledger.services import Line, record
from player_characters.models import Character
from shops.models import Shop

pytestmark = [pytest.mark.story("U50"), pytest.mark.django_db]


def index(club):
    return reverse("ledger:index", args=[club.slug])


def hist(club, character):
    return reverse("ledger:character_history", args=[club.slug, character.pk])


def d(day):
    return datetime.date(2025, 1, day)


def text(response):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", response.content.decode()))


@pytest.fixture
def other_char(club, other_player):
    owner = Membership.objects.get(user=other_player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Borin")


@pytest.mark.parametrize("who", ["game_master", "club_admin", "site_admin"])
def test_privileged_see_all_newest_first(request, login, club, character, other_char, item, who):
    user = request.getfixturevalue(who)
    gm = request.getfixturevalue("game_master")
    record(character, "award", [Line(coins=100)], note="older", date=d(1), actor=gm)
    record(other_char, "award", [Line(item=item, quantity=2)], note="newest", date=d(9))
    r = login(user).get(index(club))
    assert r.status_code == 200
    t = text(r)
    assert t.index("newest") < t.index("older")
    for needle in (
        "9 Jan 2025",
        "Aria",
        "Borin",
        "Player",
        "Other",
        "Award",
        "Rope",
        "GM",
        "System",
    ):
        assert needle in t


def test_player_redirected_to_selected_history(login, player, club, character):
    r = login(player).get(index(club))
    assert r.status_code == 302 and r.url == hist(club, character)


def test_player_two_characters_goes_to_selected(login, player, club, character):
    owner = Membership.objects.get(user=player, club=club)
    Character.objects.create(club=club, owner=owner, name="Zed")
    r = login(player).get(index(club))
    assert r.status_code == 302 and r.url == hist(club, character)


def test_member_without_character_sees_empty_state(login, player, club):
    r = login(player).get(index(club))
    assert r.status_code == 200
    assert "You have no character in this club." in r.content.decode()


def setup_entries(club, character, other_char, item, gm):
    torch = Item.objects.create(club=club, name="Torch", value_cp=1)
    record(character, "award", [Line(coins=5)], note="e1", date=d(1), actor=gm)
    record(character, "purchase", [Line(item=item, quantity=1)], note="e2", date=d(5))
    record(other_char, "award", [Line(item=torch, quantity=1)], note="e3", date=d(9), actor=gm)
    return torch


def shown(response):
    t = text(response)
    return {n for n in ("e1", "e2", "e3") if n in t}


def test_each_filter(login, game_master, club, character, other_char, item, player):
    torch = setup_entries(club, character, other_char, item, game_master)
    c = login(game_master)
    url = index(club)
    assert shown(c.get(url, {"character": character.pk})) == {"e1", "e2"}
    owner = Membership.objects.get(user=player, club=club)
    assert shown(c.get(url, {"player": owner.pk})) == {"e1", "e2"}
    assert shown(c.get(url, {"kind": "purchase"})) == {"e2"}
    assert shown(c.get(url, {"item": torch.pk})) == {"e3"}
    assert shown(c.get(url, {"recorded_by": game_master.pk})) == {"e1", "e3"}
    assert shown(c.get(url, {"date_from": "2025-01-05"})) == {"e2", "e3"}
    assert shown(c.get(url, {"date_to": "2025-01-05"})) == {"e1", "e2"}


def test_filter_combinations(login, game_master, club, character, other_char, item):
    torch = setup_entries(club, character, other_char, item, game_master)
    c = login(game_master)
    r = c.get(index(club), {"character": character.pk, "kind": "award"})
    assert shown(r) == {"e1"}
    r = c.get(index(club), {"item": item.pk, "date_from": "2025-01-02", "date_to": "2025-01-08"})
    assert shown(r) == {"e2"}
    r = c.get(index(club), {"item": torch.pk, "date_to": "2025-01-08"})
    assert shown(r) == set()
    assert "No entries match these filters." in r.content.decode()


def test_invalid_values_ignored(login, game_master, club, character, other_char, item):
    setup_entries(club, character, other_char, item, game_master)
    r = login(game_master).get(
        index(club), {"character": "abc", "kind": "nope", "date_from": "xx", "item": "99999"}
    )
    assert r.status_code == 200 and shown(r) == {"e1", "e2", "e3"}


def test_paging_keeps_filters(monkeypatch, login, game_master, club, character, other_char):
    monkeypatch.setattr(views, "PAGE_SIZE", 2)
    for i in range(5):
        record(character, "award", [Line(coins=1)], note=f"mine{i}", date=d(i + 1))
    record(other_char, "award", [Line(coins=1)], note="zzother", date=d(20))
    c = login(game_master)
    r = c.get(index(club), {"character": character.pk})
    html = r.content.decode()
    nxt = re.search(r'href="([^"]*)">Next', html).group(1).replace("&amp;", "&")
    assert f"character={character.pk}" in nxt and "page=2" in nxt
    r2 = c.get(index(club) + nxt)
    assert "zzother" not in r2.content.decode() and "mine" in r2.content.decode()
    assert "ledger_page=2" in r2.content.decode()


def test_cross_club_isolation(login, game_master, club, other_club, character, item):
    foreign_owner = Membership.objects.create(
        user=game_master.__class__.objects.create_user("x@example.com", password="pw"),
        club=other_club,
    )
    foreign = Character.objects.create(club=other_club, owner=foreign_owner, name="Foreigner")
    foreign_item = Item.objects.create(club=other_club, name="Foreign Gem", value_cp=1)
    record(foreign, "award", [Line(item=foreign_item, quantity=1)], note="foreign-note")
    record(character, "award", [Line(coins=1)], note="local-note")
    c = login(game_master)
    t = text(c.get(index(club)))
    assert "foreign-note" not in t and "Foreigner" not in t and "local-note" in t
    for params in ({"character": foreign.pk}, {"item": foreign_item.pk}):
        r = c.get(index(club), params)
        assert r.status_code == 200 and "foreign-note" not in text(r)


def test_back_link(login, game_master, player, club, character):
    url = hist(club, character)
    qs = f"?from=ledger&character={character.pk}&kind=award&ledger_page=2&junk=<x>"
    html = login(game_master).get(url + qs).content.decode()
    assert "Back to club ledger" in html
    assert f"{index(club)}?character={character.pk}&amp;kind=award&amp;page=2" in html
    assert "junk" not in html.split("Back to club ledger")[0].split("<header")[-1]
    assert "Back to sheet" in login(player).get(url + "?from=ledger").content.decode()
    assert "Back to sheet" in login(game_master).get(url).content.decode()


def test_history_pager_keeps_from(monkeypatch, login, game_master, club, character):
    from ledger import views as v

    monkeypatch.setattr(v, "PAGE_SIZE", 1)
    record(character, "award", [Line(coins=1)], date=d(1))
    record(character, "award", [Line(coins=1)], date=d(2))
    html = (
        login(game_master).get(hist(club, character) + "?from=ledger&kind=award").content.decode()
    )
    nxt = re.search(r'href="([^"]*)">Next', html).group(1)
    assert "from=ledger" in nxt and "kind=award" in nxt and "page=2" in nxt


def test_query_count_flat(login, game_master, club, character, item):
    shop = Shop.objects.create(club=club, name="Smithy")
    record(character, "award", [Line(coins=100000)])
    c = login(game_master)

    def add(n):
        for _ in range(n):
            record(character, "purchase", [Line(item=item, quantity=1), Line(coins=-5)], shop=shop)

    def count():
        with CaptureQueriesContext(connection) as ctx:
            assert c.get(index(club)).status_code == 200
        return len(ctx)

    add(3)
    c.get(index(club))  # warm caches
    small = count()
    add(27)
    big = count()
    assert big == small, big


def test_source_links(login, game_master, club_admin, club, character, item):
    shop = Shop.objects.create(club=club, name="Smithy")
    record(character, "award", [Line(coins=100000)])
    record(character, "purchase", [Line(coins=-5)], shop=shop)
    r = login(game_master).get(index(club))
    assert reverse("shops:detail", args=[club.slug, shop.pk]) in r.content.decode()


def test_nav(login, player, game_master, club_admin, club, character):
    def menus(user):
        return login(user).get(reverse("club_home", args=[club.slug])).content.decode()

    assert "Club ledger" not in menus(player) and ">Ledger<" in re.sub(
        r"\s+", "", menus(player)
    ).replace(">\n", ">")
    for u in (game_master, club_admin):
        html = menus(u)
        assert "Club ledger" in html and ">Ledger<" not in re.sub(r"\s+", "", html)
