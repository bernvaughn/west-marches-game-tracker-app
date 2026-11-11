import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.models import Membership, User
from ledger.services import Line, available_coins, available_items
from player_characters.models import Character

pytestmark = pytest.mark.story("U16")


def url(club, trade, name="detail"):
    return reverse(f"trades:{name}", args=[club.slug, trade.pk])


def msgs(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


@pytest.fixture
def trade(character, other_character, item, give, make_trade):
    give(character, item, 5, 1000)
    return make_trade(
        character,
        other_character,
        lines=[(True, Line(item=item, quantity=2)), (True, Line(coins=250))],
    )


def status(trade):
    trade.refresh_from_db()
    return trade.status


def test_receiver_accepts(login, club, trade, other_player):
    r = login(other_player).post(url(club, trade, "accept"))
    assert r.status_code == 302 and r.url == url(club, trade)
    assert status(trade) == "accepted"


def test_sender_cannot_accept(login, club, trade, player):
    r = login(player).post(url(club, trade, "accept"), follow=True)
    assert status(trade) == "requested"
    assert msgs(r)


def test_accept_limit(login, club, trade, other_player, character, third_character, make_trade):
    make_trade(character, third_character, status="accepted")
    r = login(other_player).post(url(club, trade, "accept"), follow=True)
    assert status(trade) == "requested"
    assert "already has another accepted trade" in r.content.decode()


@pytest.mark.parametrize("start", ["requested", "accepted"])
@pytest.mark.parametrize("action,who", [("decline", "other_player"), ("cancel", "player")])
def test_close_releases_holds(request, login, club, trade, character, item, start, action, who):
    trade.status = start
    trade.save()
    login(request.getfixturevalue(who)).post(url(club, trade, action))
    assert status(trade) == ("declined" if action == "decline" else "cancelled")
    assert available_coins(character) == 1000
    assert available_items(character)[item.pk] == 5


def test_wrong_side_cannot_close(login, club, trade, player, other_player):
    login(player).post(url(club, trade, "decline"))
    login(other_player).post(url(club, trade, "cancel"))
    assert status(trade) == "requested"


@pytest.mark.parametrize("closed", ["completed", "declined", "cancelled"])
@pytest.mark.parametrize(
    "action,who",
    [
        ("accept", "other_player"),
        ("decline", "other_player"),
        ("cancel", "player"),
    ],
)
def test_closed_rejected(request, login, club, trade, closed, action, who):
    trade.status = closed
    trade.save()
    r = login(request.getfixturevalue(who)).post(url(club, trade, action), follow=True)
    assert status(trade) == closed
    assert msgs(r)


@pytest.mark.parametrize("action", ["accept", "decline", "cancel"])
@pytest.mark.parametrize("who", ["game_master", "club_admin"])
def test_non_party_403(request, login, club, trade, action, who):
    r = login(request.getfixturevalue(who)).post(url(club, trade, action))
    assert r.status_code == 403
    assert status(trade) == "requested"


@pytest.mark.parametrize("action", ["accept", "decline", "cancel"])
def test_cannot_view_404(login, club, player, other_character, third_character, make_trade, action):
    t = make_trade(other_character, third_character)
    assert login(player).post(url(club, t, action)).status_code == 404
    assert status(t) == "requested"


@pytest.mark.parametrize("action", ["accept", "decline", "cancel"])
def test_other_club_404(login, club, trade, foreign_character, action):
    owner = foreign_character.owner.user
    assert login(owner).post(url(club, trade, action)).status_code == 404
    other = Character.objects.create(
        club=foreign_character.club, owner=foreign_character.owner, name="Y"
    )
    peer = User.objects.create_user("p2@example.com", password="pw", display_name="P2")
    m = Membership.objects.create(user=peer, club=foreign_character.club)
    other2 = Character.objects.create(club=foreign_character.club, owner=m, name="W")
    t = trade.__class__.objects.create(club=foreign_character.club, sender=other, receiver=other2)
    r = login(peer).post(reverse(f"trades:{action}", args=[club.slug, t.pk]))
    assert r.status_code == 404
    assert status(t) == "requested"


@pytest.mark.parametrize("action", ["accept", "decline", "cancel"])
def test_get_405(login, club, trade, other_player, action):
    assert login(other_player).get(url(club, trade, action)).status_code == 405
    assert status(trade) == "requested"


def actions_in(html, club, trade):
    return {n for n in ("accept", "decline", "cancel") if url(club, trade, n) in html}


@pytest.mark.parametrize(
    "who,state,expected",
    [
        ("other_player", "requested", {"accept", "decline"}),
        ("other_player", "accepted", {"decline"}),
        ("player", "requested", {"cancel"}),
        ("player", "accepted", {"cancel"}),
        ("game_master", "requested", set()),
        ("player", "completed", set()),
        ("other_player", "declined", set()),
        ("other_player", "cancelled", set()),
    ],
)
def test_buttons(request, login, club, trade, who, state, expected):
    trade.status = state
    trade.save()
    html = login(request.getfixturevalue(who)).get(url(club, trade)).content.decode()
    assert actions_in(html, club, trade) == expected
