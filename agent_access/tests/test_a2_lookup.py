import json

import pytest

from accounts.models import Membership
from items.models import Item
from ledger.coins import format_coins
from player_characters.models import Character

pytestmark = [pytest.mark.story("A2"), pytest.mark.django_db]


@pytest.fixture
def world(club, other_club, character, item, other_player, gm_connection, other_club_gm_connection):
    owner = Membership.objects.get(user=other_player, club=club)
    Character.objects.filter(pk=character.pk).update(name="Aria")
    Character.objects.create(club=club, owner=owner, name="Bram", description="SECRET NOTE")
    Character.objects.create(club=club, owner=owner, name="aragorn")
    Item.objects.create(
        club=club, name="Healing Potion", description="restores hp", details="HIDDEN DETAIL"
    )
    Item.objects.create(club=club, name="Cloak", traits="magical")
    Item.objects.create(club=club, name="Old Sword", retired=True, traits="magical")
    other_owner = Membership.objects.get(user=other_club_gm_connection[0].user, club=other_club)
    Character.objects.create(club=other_club, owner=other_owner, name="Zed")
    Item.objects.create(club=other_club, name="Rope", description="other club")
    Item.objects.create(club=other_club, name="Foreign Magic", traits="magical")
    return {"secret": gm_connection[1], "other": other_club_gm_connection[1]}


def sc(mcp, secret, tool, **args):
    status, result = mcp(secret, tool, **args)
    assert status == 200 and not result.get("isError")
    return result["structuredContent"]


def test_list_characters_all(mcp, world, character):
    rows = sc(mcp, world["secret"], "list_characters")["characters"]
    names = [r["name"] for r in rows]
    assert {"aragorn", "Aria", "Bram"} <= set(names)
    assert "Zed" not in names
    assert names == sorted(names, key=str.lower) or names == sorted(names)
    assert all(set(r) == {"id", "name", "owner_display_name"} for r in rows)
    assert rows[0]["owner_display_name"]


def test_list_characters_search(mcp, world):
    rows = sc(mcp, world["secret"], "list_characters", search="AR")["characters"]
    assert {r["name"] for r in rows} == {"Aria", "aragorn"}


def test_characters_cross_club(mcp, world):
    mine = sc(mcp, world["secret"], "list_characters")["characters"]
    assert "Zed" not in {r["name"] for r in mine}
    theirs = sc(mcp, world["other"], "list_characters")["characters"]
    assert [r["name"] for r in theirs] == ["Zed"]


def test_search_items_all(mcp, world, item):
    rows = sc(mcp, world["secret"], "search_items")["items"]
    names = {r["name"] for r in rows}
    assert "Old Sword" not in names and "Foreign Magic" not in names
    assert {"Healing Potion", "Cloak", item.name} <= names
    for r in rows:
        assert set(r) == {"id", "name", "description", "traits", "value_cp", "value"}
        assert r["value"] == format_coins(r["value_cp"])


def test_search_items_matches(mcp, world):
    s = world["secret"]
    assert [r["name"] for r in sc(mcp, s, "search_items", query="HP")["items"]] == [
        "Healing Potion"
    ]
    assert [r["name"] for r in sc(mcp, s, "search_items", query="MAGIC")["items"]] == ["Cloak"]
    assert [r["name"] for r in sc(mcp, s, "search_items", query="cloak")["items"]] == ["Cloak"]


def test_retired_never_listed(mcp, world):
    rows = sc(mcp, world["secret"], "search_items", query="Old Sword")["items"]
    assert rows == []


def test_limit_clamp(mcp, world, club):
    Item.objects.bulk_create([Item(club=club, name=f"Bulk {n}") for n in range(105)])
    s = world["secret"]
    assert len(sc(mcp, s, "search_items", limit=500)["items"]) == 100
    assert len(sc(mcp, s, "search_items", limit=0)["items"]) == 1
    assert len(sc(mcp, s, "search_items", limit=-5)["items"]) == 1
    assert len(sc(mcp, s, "search_items", limit=2)["items"]) == 2


def test_items_cross_club(mcp, world):
    mine = sc(mcp, world["secret"], "search_items", query="Rope")["items"]
    assert all(r["description"] != "other club" for r in mine)
    theirs = sc(mcp, world["other"], "search_items")["items"]
    assert {r["name"] for r in theirs} == {"Rope", "Foreign Magic"}
    assert not ({r["id"] for r in mine} & {r["id"] for r in theirs})


def test_no_leaks(mcp, world, game_master, other_player):
    s = world["secret"]
    dump = json.dumps(
        [
            sc(mcp, s, "list_characters"),
            sc(mcp, s, "search_items"),
        ]
    )
    assert game_master.email not in dump and other_player.email not in dump
    assert "SECRET NOTE" not in dump and "HIDDEN DETAIL" not in dump


def test_tools_listed(mcp_raw, world):
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    tools = {t["name"]: t for t in mcp_raw(world["secret"], body).json()["result"]["tools"]}
    for name in ("list_characters", "search_items"):
        assert tools[name]["description"]
