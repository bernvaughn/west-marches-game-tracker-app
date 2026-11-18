import pytest
from django.urls import reverse

from accounts.models import User
from items.models import Item
from player_characters.models import Character, JunkMark
from shops.models import Shop
from shops.services import set_street_order

pytestmark = [pytest.mark.django_db, pytest.mark.story("S12")]


def u(club):
    return reverse("shops:street_editor", kwargs={"club_slug": club.slug})


@pytest.fixture
def admin_client(club_admin, login):
    return login(club_admin)


@pytest.fixture
def other_club_admin(other_club):
    user = User.objects.create_user("other-admin@example.com", password="pw", display_name="Other Admin")
    from accounts.models import Membership

    Membership.objects.create(user=user, club=other_club, is_club_admin=True)
    return user


@pytest.fixture
def street_shops(club):
    a = Shop.objects.create(club=club, name="Alpha", street_position=0)
    b = Shop.objects.create(club=club, name="Bravo", street_position=1, symbol="⚓")
    c = Shop.objects.create(club=club, name="Charlie", street_position=2)
    return a, b, c


@pytest.fixture
def stall(club, other_player, item):
    owner = club.memberships.get(user=other_player)
    character = Character.objects.create(club=club, owner=owner, name="Stallkeeper")
    character.shop_open = True
    character.save()
    from ledger.services import Line, record

    record(character, "award", [Line(item=item, quantity=1)])
    JunkMark.objects.create(character=character, item=item, quantity=1)
    return character


# --- GET --------------------------------------------------------------------


def test_get_renders_8xn_grid(admin_client, club, street_shops, stall):
    page = admin_client.get(u(club))
    assert page.status_code == 200
    lots = page.context["lots"]
    assert len(lots) > 0 and len(lots) % 8 == 0
    present = [lot["shop"] for lot in lots if lot["shop"]]
    assert set(present) == set(street_shops)
    assert any(lot["stall"] and lot["stall"].pk == stall.pk for lot in lots)


def test_get_shows_shop_stall_and_filler(admin_client, club, street_shops, stall):
    page = admin_client.get(u(club))
    html = page.content.decode()
    lots = page.context["lots"]
    for shop in street_shops:
        assert shop.name in html
    assert street_shops[1].symbol in html
    assert f"{stall.name}'s stall" in html
    filler = [lot for lot in lots if not lot["shop"] and not lot["stall"]]
    assert len(filler) > 0
    assert html.count('class="wm-building"') == len(lots)


# --- POST -------------------------------------------------------------------


def test_post_reorders_shops_and_writes_positions(admin_client, club, street_shops):
    a, b, c = street_shops
    r = admin_client.post(u(club), {"shop_order": [str(c.pk), str(a.pk), str(b.pk)]})
    assert r.status_code == 302
    assert r["Location"].endswith(u(club))
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert (a.street_position, b.street_position, c.street_position) == (1, 2, 0)


def test_post_redirects_with_success_message(admin_client, club, street_shops):
    a, b, c = street_shops
    admin_client.post(u(club), {"shop_order": [str(c.pk), str(a.pk), str(b.pk)]})
    assert "Street order saved" in admin_client.get(u(club)).content.decode()


def test_post_saves_in_visual_order(admin_client, club, street_shops):
    a, b, c = street_shops
    admin_client.post(u(club), {"shop_order": [str(c.pk), str(a.pk), str(b.pk)]})
    ordered = [lot["shop"] for lot in admin_client.get(u(club)).context["lots"] if lot["shop"]]
    assert [s.pk for s in ordered] == [c.pk, a.pk, b.pk]


def test_post_ignores_unknown_shop_ids(admin_client, club, street_shops, other_shop):
    a, b, c = street_shops
    admin_client.post(u(club), {"shop_order": [str(c.pk), str(a.pk), str(other_shop.pk), str(b.pk)]})
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert (a.street_position, b.street_position, c.street_position) == (1, 2, 0)
    other_shop.refresh_from_db()
    assert other_shop.street_position == 0


def test_post_touches_current_club_only(admin_client, club, other_club, street_shops):
    foreign = Shop.objects.create(club=other_club, name="Foreign", street_position=0)
    admin_client.post(u(club), {"shop_order": [str(s.pk) for s in street_shops] + [str(foreign.pk)]})
    foreign.refresh_from_db()
    assert foreign.street_position == 0


# --- stalls -----------------------------------------------------------------


def test_stall_displayed_but_not_reorderable(admin_client, club, street_shops, stall):
    page = admin_client.get(u(club))
    stalls = [lot for lot in page.context["lots"] if lot["stall"]]
    assert len(stalls) == 1
    assert stalls[0]["shop"] is None
    admin_client.post(u(club), {"shop_order": [str(s.pk) for s in street_shops]})
    stall.refresh_from_db()
    assert stall.shop_open
    assert JunkMark.objects.filter(character=stall).exists()


# --- permissions ------------------------------------------------------------


@pytest.mark.parametrize("role", ["player", "game_master"])
def test_non_admins_403(role, request, club, login):
    user = request.getfixturevalue(role)
    assert login(user).get(u(club)).status_code == 403
    assert login(user).post(u(club), {"shop_order": []}).status_code == 403


def test_site_admin_ok(site_admin, login, club):
    assert login(site_admin).get(u(club)).status_code == 200


def test_other_club_admin_403(other_club_admin, club, login):
    # Non-members of the club get 404 from club middleware; admins of other clubs are not members here.
    assert login(other_club_admin).get(u(club)).status_code in (403, 404)


# --- service ----------------------------------------------------------------


def test_set_street_order_writes_sequential_positions(club, street_shops):
    a, b, c = street_shops
    set_street_order(club, [c.pk, a.pk, b.pk])
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert (a.street_position, b.street_position, c.street_position) == (1, 2, 0)


def test_set_street_order_is_club_scoped(club, other_club, street_shops):
    foreign = Shop.objects.create(club=other_club, name="Foreign", street_position=0)
    set_street_order(club, [foreign.pk, street_shops[0].pk])
    foreign.refresh_from_db()
    assert foreign.street_position == 0
