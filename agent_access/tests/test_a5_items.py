import pytest

from agent_access.models import ProposedItem
from items.models import Item

pytestmark = [pytest.mark.story("A5"), pytest.mark.django_db]

H = {"HTTP_HOST": "testserver"}


@pytest.fixture
def call(mcp_raw):
    def _call(secret, tool, **arguments):
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        result = mcp_raw(secret, body, headers=H).json()["result"]
        return result.get("isError", False), result

    return _call


def url(club, name, pk=None):
    from django.urls import reverse

    kw = {"club_slug": club.slug}
    if pk:
        kw["pk"] = pk
    return reverse(f"agent_access:{name}", kwargs=kw)


def make(club, **kw):
    kw.setdefault("name", "Gem")
    return ProposedItem.objects.create(club=club, **kw)


def test_propose_creates_pending(call, gm_connection, club):
    conn, secret = gm_connection
    before = Item.objects.count()
    err, res = call(secret, "propose_item", name=" Moon Gem ", value_cp=50)
    assert not err
    data = res["structuredContent"]
    p = ProposedItem.objects.get()
    assert data["created"] is True and data["status"] == "pending"
    assert data["proposed_item_id"] == p.pk
    assert p.connection == conn and p.name == "Moon Gem" and p.value_cp == 50
    assert Item.objects.count() == before
    assert data["review_url"] == f"http://testserver/c/{club.slug}/agent/proposed-items/{p.pk}/"


def test_duplicate_active_item_refused(call, gm_connection, item):
    _, secret = gm_connection
    err, res = call(secret, "propose_item", name="rope")
    assert err and f"item_id {item.pk}" in res["content"][0]["text"]
    assert not ProposedItem.objects.exists()
    item.retired = True
    item.save()
    err, _ = call(secret, "propose_item", name="rope")
    assert not err


def test_duplicate_pending_returned(call, gm_connection):
    _, secret = gm_connection
    _, a = call(secret, "propose_item", name="Gem")
    _, b = call(secret, "propose_item", name="GEM", description="x")
    assert b["structuredContent"]["created"] is False
    assert b["structuredContent"]["proposed_item_id"] == a["structuredContent"]["proposed_item_id"]
    assert ProposedItem.objects.count() == 1


@pytest.mark.parametrize(
    "args", [{"name": "  "}, {"name": "x" * 201}, {"name": "a", "value_cp": -1}]
)
def test_validation(call, gm_connection, args):
    err, _ = call(gm_connection[1], "propose_item", **args)
    assert err
    assert not ProposedItem.objects.exists()


def test_list_scoped_and_filtered(call, gm_connection, other_club_gm_connection, club, other_club):
    make(club, name="A")
    make(club, name="B", status="rejected")
    make(other_club, name="Z")
    _, res = call(gm_connection[1], "list_proposed_items")
    assert [p["name"] for p in res["structuredContent"]["proposed_items"]] == ["A"]
    _, res = call(gm_connection[1], "list_proposed_items", status="all")
    assert len(res["structuredContent"]["proposed_items"]) == 2
    _, res = call(gm_connection[1], "list_proposed_items", status="rejected")
    assert [p["name"] for p in res["structuredContent"]["proposed_items"]] == ["B"]
    err, _ = call(gm_connection[1], "list_proposed_items", status="bogus")
    assert err
    _, res = call(other_club_gm_connection[1], "list_proposed_items")
    assert [p["name"] for p in res["structuredContent"]["proposed_items"]] == ["Z"]


def test_pages_permissions(login, club, game_master, club_admin, player):
    p = make(club)
    for user in (game_master, club_admin):
        c = login(user)
        assert c.get(url(club, "proposed_items")).status_code == 200
        assert c.get(url(club, "proposed_item_detail", p.pk)).status_code == 200
    c = login(player)
    assert c.get(url(club, "proposed_items")).status_code == 403
    assert c.get(url(club, "proposed_item_detail", p.pk)).status_code == 403
    assert c.post(url(club, "proposed_item_approve", p.pk)).status_code == 403
    assert c.post(url(club, "proposed_item_reject", p.pk)).status_code == 403
    p.refresh_from_db()
    assert p.status == "pending" and not Item.objects.filter(name="Gem").exists()


def edited(**kw):
    data = {
        "name": "Moon Gem",
        "description": "d",
        "traits": "glows",
        "details": "x",
        "value_pp": "",
        "value_gp": "2",
        "value_sp": "",
        "value_cp": "5",
    }
    data.update(kw)
    return data


@pytest.mark.parametrize("who", ["game_master", "club_admin"])
def test_approve_creates_one_item(login, club, request, who):
    p = make(club)
    c = login(request.getfixturevalue(who))
    u = url(club, "proposed_item_approve", p.pk)
    assert c.post(u, edited()).status_code == 302
    assert c.post(u, edited()).status_code == 302
    p.refresh_from_db()
    item = Item.objects.get(name="Moon Gem")
    assert p.status == "approved" and p.approved_item == item
    assert (item.club, item.traits, item.value_cp) == (club, "glows", 205)


def test_approve_name_clash(login, club, game_master, item):
    p = make(club)
    r = login(game_master).post(url(club, "proposed_item_approve", p.pk), edited(name="rope"))
    assert r.status_code == 200
    assert Item.objects.count() == 1
    p.refresh_from_db()
    assert p.status == "pending"


def test_save_changes(login, club, game_master):
    p = make(club)
    r = login(game_master).post(url(club, "proposed_item_detail", p.pk), edited())
    assert r.status_code == 302
    p.refresh_from_db()
    assert (p.name, p.value_cp, p.status) == ("Moon Gem", 205, "pending")
    assert not Item.objects.exists()


def test_reject(login, club, game_master):
    p = make(club)
    c = login(game_master)
    assert c.post(url(club, "proposed_item_reject", p.pk)).status_code == 302
    p.refresh_from_db()
    assert p.status == "rejected"
    c.post(url(club, "proposed_item_approve", p.pk), edited())
    p.refresh_from_db()
    assert p.status == "rejected" and not Item.objects.exists()


def test_other_club_404(login, club, other_club, game_master):
    p = make(other_club)
    c = login(game_master)
    assert c.get(url(club, "proposed_item_detail", p.pk)).status_code == 404
    assert c.post(url(club, "proposed_item_approve", p.pk), edited()).status_code == 404
    assert c.post(url(club, "proposed_item_reject", p.pk)).status_code == 404
    assert b"Gem" not in c.get(url(club, "proposed_items")).content
    p.refresh_from_db()
    assert p.status == "pending" and not Item.objects.exists()


def test_escaped(login, club, game_master):
    p = make(club, name="<script>x</script>", description="<b>y</b>")
    c = login(game_master)
    for u in (url(club, "proposed_items"), url(club, "proposed_item_detail", p.pk)):
        body = c.get(u).content.decode()
        assert "<script>x" not in body and "&lt;script&gt;" in body
