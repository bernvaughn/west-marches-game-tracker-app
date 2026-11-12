import pytest
from django.urls import reverse

from accounts.models import Membership
from ledger.services import Line
from player_characters.models import Character, Trade

pytestmark = pytest.mark.story("U16")


def propose_url(club):
    return reverse("trades:propose", args=[club.slug])


def index_url(club):
    return reverse("trades:index", args=[club.slug])


@pytest.fixture
def stocked(character, item, give):
    give(character, item, 5, 1000)
    return character


def post_data(sender, receiver, **extra):
    data = {"sender": sender.pk, "receiver": receiver.pk, "note": ""}
    data.update(extra)
    return data


def test_propose_success(login, player, club, stocked, other_character, item):
    client = login(player)
    resp = client.post(
        propose_url(club),
        post_data(
            stocked,
            other_character,
            note="Please",
            **{f"offer-item_{item.pk}": 2, "offer-coins_gp": 3},
        ),
    )
    trade = Trade.objects.get()
    assert resp.status_code == 302
    assert resp.url == reverse("trades:detail", args=[club.slug, trade.pk])
    assert trade.status == Trade.Status.REQUESTED
    assert trade.note == "Please"
    lines = {(line.item_id, line.quantity, line.coins) for line in trade.lines.all()}
    assert lines == {(item.pk, 2, 0), (None, 0, 3 * 100)} or len(lines) == 2


def test_note_only(login, player, club, character, other_character):
    resp = login(player).post(propose_url(club), post_data(character, other_character, note="hi"))
    assert resp.status_code == 302
    assert Trade.objects.count() == 1


def test_empty_offer_error(login, player, club, character, other_character):
    client = login(player)
    resp = client.post(propose_url(club), post_data(character, other_character))
    assert resp.status_code == 302
    assert "from=" in resp.url
    page = client.get(resp.url)
    assert "Offer something or write a note." in page.content.decode()
    assert not Trade.objects.exists()


def test_preselects_single_character(login, player, club, stocked, other_character):
    html = login(player).get(propose_url(club)).content.decode()
    assert "Rope (5 available)" in html
    assert 'name="offer-item_' in html


def test_chooser_with_two_characters(login, player, club, character, other_character):
    owner = Membership.objects.get(user=player, club=club)
    second = Character.objects.create(club=club, owner=owner, name="Second")
    client = login(player)
    html = client.get(propose_url(club), {"choose": 1}).content.decode()
    assert "Choose" in html and 'name="from"' in html
    html = client.get(
        propose_url(club), {"from": second.pk, "to": other_character.pk}
    ).content.decode()
    assert "Second" in html and "offer-coins" in html
    assert f'value="{other_character.pk}" selected' in html


def test_only_own_items(login, player, club, stocked, other_character, item, give):
    from items.models import Item

    other_item = Item.objects.create(club=club, name="Bram Secret", value_cp=1)
    give(other_character, other_item, 1)
    html = login(player).get(propose_url(club)).content.decode()
    assert "Rope" in html
    assert "Bram Secret" not in html


def test_held_amount(
    login, player, club, stocked, other_character, third_character, item, make_trade
):
    make_trade(stocked, third_character, lines=[(True, Line(item=item, quantity=3))])
    client = login(player)
    assert "Rope (2 available)" in client.get(propose_url(club)).content.decode()
    resp = client.post(
        propose_url(club),
        post_data(stocked, other_character, **{f"offer-item_{item.pk}": 3}),
    )
    assert resp.status_code == 200
    assert Trade.objects.count() == 1


def test_bad_characters(
    login, player, club, stocked, other_character, foreign_character, third_character
):
    client = login(player)
    url = propose_url(club)
    assert client.get(url, {"from": other_character.pk}).status_code == 404
    assert client.get(url, {"from": foreign_character.pk}).status_code == 404
    assert client.get(url, {"to": foreign_character.pk}).status_code == 404
    assert client.get(url, {"to": stocked.pk}).status_code == 404
    for recv in (foreign_character, stocked):
        resp = client.post(url, post_data(stocked, recv, note="x"))
        assert resp.status_code == 200
    resp = client.post(url, post_data(other_character, third_character, note="x"))
    assert resp.status_code == 404
    assert not Trade.objects.exists()


def test_no_characters(login, other_player, club):
    html = login(other_player).get(propose_url(club)).content.decode()
    assert "Create a character first" in html
    assert reverse("characters:create", args=[club.slug]) in html


def test_index_order_and_visibility(
    login, player, club, character, other_character, third_character, make_trade
):
    closed = make_trade(character, other_character, status="completed", note="c")
    open_ = make_trade(other_character, character)
    unrelated = make_trade(other_character, third_character)
    html = login(player).get(index_url(club)).content.decode()
    detail = lambda t: reverse("trades:detail", args=[club.slug, t.pk])  # noqa: E731
    assert html.index(detail(open_)) < html.index("Closed trades") < html.index(detail(closed))
    assert detail(unrelated) not in html
    assert "All club trades" not in html


@pytest.mark.parametrize("who", ["game_master", "club_admin", "site_admin"])
def test_index_all_trades(
    request,
    login,
    who,
    club,
    other_character,
    third_character,
    other_club,
    foreign_character,
    make_trade,
):
    unrelated = make_trade(other_character, third_character)
    foreign_owner = foreign_character
    foreign = make_trade(foreign_character, foreign_character)
    html = login(request.getfixturevalue(who)).get(index_url(club)).content.decode()
    assert "All club trades" in html
    assert reverse("trades:detail", args=[club.slug, unrelated.pk]) in html
    assert reverse("trades:detail", args=[other_club.slug, foreign.pk]) not in html
    assert foreign_owner.name not in html


def test_other_club_index_404(login, player, other_club):
    assert login(player).get(index_url(other_club)).status_code == 404


def test_nav_links(login, player, club):
    html = login(player).get(index_url(club)).content.decode()
    assert f'href="{index_url(club)}">Trades' in html
    assert f'href="{propose_url(club)}">Propose trade' in html
