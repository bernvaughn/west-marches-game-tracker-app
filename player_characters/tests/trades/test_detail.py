import pytest
from django.urls import reverse

from accounts.models import Membership, User
from ledger.services import Line

pytestmark = pytest.mark.story("U16")


@pytest.fixture
def trade(character, other_character, item, give, make_trade):
    give(character, item, 5, 1000)
    from items.models import Item

    extra = Item.objects.create(club=character.club, name="Secret Lamp", value_cp=1)
    give(character, extra, 1)
    return make_trade(
        character,
        other_character,
        lines=[(True, Line(item=item, quantity=2)), (False, Line(coins=250))],
        note="Hello\nthere",
    )


def url(club, trade, name="detail"):
    return reverse(f"trades:{name}", args=[club.slug, trade.pk])


@pytest.mark.parametrize(
    "who", ["player", "other_player", "game_master", "club_admin", "site_admin"]
)
def test_visible(request, login, club, trade, who):
    r = login(request.getfixturevalue(who)).get(url(club, trade))
    assert r.status_code == 200


def test_content_and_poll(login, club, trade, player):
    html = login(player).get(url(club, trade)).content.decode()
    assert "Rope" in html and "2 gp 5 sp" in html
    assert "Secret Lamp" not in html
    assert 'id="trade-live"' in html and "every 5s" in html
    assert "Hello<br>there" in html


def test_other_player_404(login, club, trade):
    u = User.objects.create_user("x@example.com", password="pw", display_name="X")
    Membership.objects.create(user=u, club=club)
    assert login(u).get(url(club, trade)).status_code == 404


def test_other_club_404(login, club, trade, foreign_character):
    u = foreign_character.owner.user
    assert login(u).get(url(club, trade)).status_code in (403, 404)


def test_cross_club_pk_404(
    login, club, other_club, foreign_character, give, make_trade, game_master
):
    u2 = User.objects.create_user("y@example.com", password="pw", display_name="Y")
    m = Membership.objects.create(user=u2, club=other_club)
    from player_characters.models import Character

    c2 = Character.objects.create(club=other_club, owner=m, name="Q")
    t = make_trade(foreign_character, c2)
    assert login(game_master).get(url(club, t)).status_code == 404


def test_routes_and_stubs(login, club, trade, player):
    c = login(player)
    assert reverse("trades:index", args=[club.slug])
    assert c.get(reverse("trades:propose", args=[club.slug])).status_code == 501
    assert c.get(url(club, trade, "edit_side")).status_code == 501
    for name in ("approve", "edit_side"):
        assert c.post(url(club, trade, name)).status_code == 501
        if name != "edit_side":
            assert c.get(url(club, trade, name)).status_code == 405
