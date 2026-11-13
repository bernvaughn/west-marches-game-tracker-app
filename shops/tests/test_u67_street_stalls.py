from datetime import date

import pytest
from django.core.management import call_command
from django.urls import reverse

from accounts.models import Club, Membership, User
from items.models import Item
from player_characters.models import Character, JunkMark
from shops.models import Rotation, Shop
from shops.views.browse import street_lots, street_stalls

pytestmark = [pytest.mark.django_db, pytest.mark.story("U67")]


def shop(pos, name=None):
    return Shop(name=name or f"S{pos}", street_position=pos)


def layout(lots):
    out = []
    for lot in lots:
        if lot["shop"]:
            out.append(lot["shop"].name)
        elif lot["stall"]:
            out.append("stall:" + lot["stall"])
        else:
            out.append(".")
    return out


def stalls(*names):
    return list(names)


# --- settings model ---------------------------------------------------------


def test_defaults(club):
    assert (club.street_min_gap, club.street_max_gap, club.street_stall_gap) == (0, 2, 1)


# --- placement --------------------------------------------------------------


def test_default_gaps_unchanged():
    assert layout(street_lots([shop(0), shop(9)])) == ["S0", ".", ".", "S9", ".", ".", ".", "."]


def test_min_raises_gaps():
    assert layout(street_lots([shop(0), shop(1)], min_gap=1))[:3] == ["S0", ".", "S1"]


def test_max_lowers_gaps():
    assert layout(street_lots([shop(0), shop(5)], max_gap=0))[:2] == ["S0", "S5"]


def test_leading_gap_is_min_of_position_and_max():
    assert layout(street_lots([shop(5)], max_gap=3))[:4] == [".", ".", ".", "S5"]
    assert layout(street_lots([shop(1)], min_gap=3, max_gap=3))[:2] == [".", "S1"]


def test_stall_gap_default_and_floor_at_min():
    assert layout(street_lots([shop(0)], stalls("A")))[:3] == ["S0", ".", "stall:A"]
    got = layout(street_lots([shop(0)], stalls("A"), min_gap=2, max_gap=3, stall_gap=0))
    assert got[:4] == ["S0", ".", ".", "stall:A"]


def test_stall_gap_beyond_max_wins():
    got = layout(street_lots([shop(0)], stalls("A"), max_gap=1, stall_gap=4))
    assert got[:6] == ["S0", ".", ".", ".", ".", "stall:A"]


def test_stalls_separated_by_min_and_padded():
    got = layout(street_lots([shop(0)], stalls("A", "B"), min_gap=1))
    assert got[:6] == ["S0", ".", "stall:A", ".", "stall:B", "."]
    assert len(got) == 8


def test_no_club_shops_stall_starts_at_zero():
    assert layout(street_lots([], stalls("A")))[0] == "stall:A"


# --- settings form ----------------------------------------------------------


def settings_url(club):
    return reverse("shops:street_settings", args=[club.slug])


def test_admin_saves_settings(login, club, club_admin):
    data = {"street_min_gap": 1, "street_max_gap": 4, "street_stall_gap": 3}
    resp = login(club_admin).post(settings_url(club), data)
    assert resp.status_code == 302
    club.refresh_from_db()
    assert (club.street_min_gap, club.street_max_gap, club.street_stall_gap) == (1, 4, 3)


def test_max_below_min_refused(login, club, club_admin):
    data = {"street_min_gap": 3, "street_max_gap": 1, "street_stall_gap": 1}
    resp = login(club_admin).post(settings_url(club), data)
    assert resp.status_code == 200
    assert "The maximum can&#x27;t be lower than the minimum." in resp.content.decode()
    club.refresh_from_db()
    assert club.street_min_gap == 0


def test_non_admin_cannot_change(login, club, player, game_master):
    data = {"street_min_gap": 1, "street_max_gap": 4, "street_stall_gap": 3}
    for user in (player, game_master):
        assert login(user).post(settings_url(club), data).status_code in (302, 403, 404)
    club.refresh_from_db()
    assert club.street_max_gap == 2


def test_manage_page_shows_form_to_admin(login, club, club_admin):
    body = login(club_admin).get(reverse("shops:manage_list", args=[club.slug])).content.decode()
    assert "Street settings" in body
    assert "street_min_gap" in body


# --- street page ------------------------------------------------------------


def open_stall(club, owner_user, name, item, quantity=1, is_open=True):
    owner = Membership.objects.get(user=owner_user, club=club)
    c = Character.objects.create(club=club, owner=owner, name=name, shop_open=is_open)
    from ledger.services import Line, record

    record(c, "award", [Line(item=item, quantity=quantity)])
    JunkMark.objects.create(character=c, item=item, quantity=quantity)
    return c


def street(login, user, club):
    return login(user).get(reverse("shops:index", args=[club.slug])).content.decode()


def test_stalls_ordered_by_name_then_id(club, player, item):
    c = open_stall(club, player, "cara", item)
    a = open_stall(club, player, "Aria", item)
    b = open_stall(club, player, "borin", item)
    assert street_stalls(club) == [a, b, c]


def test_stall_hidden_when_off_or_nothing_listed(club, player, item):
    open_stall(club, player, "Off", item, is_open=False)
    c = open_stall(club, player, "Empty", item)
    JunkMark.objects.filter(character=c).delete()
    assert street_stalls(club) == []


def test_stall_sign_link_and_image(login, club, player, item):
    c = open_stall(club, player, "Aria", item)
    body = street(login, player, club)
    assert "Aria&#x27;s stall" in body or "Aria's stall" in body
    assert reverse("shops:player_shop", args=[club.slug, c.pk]) in body
    assert "player_stall.svg" in body
    assert "wm-street-lot--stall" in body
    # inside the screen-reader list of shop links
    assert body.index('aria-label="Shops"') < body.index("wm-street-lot--stall")


def test_stall_only_club_shows_street(login, club, player, item):
    open_stall(club, player, "Aria", item)
    body = street(login, player, club)
    assert "No shops are open today." not in body


def test_other_clubs_stall_not_shown(login, club, other_club, player, item):
    other_user = User.objects.create_user("x@example.com", password="pw", display_name="X")
    Membership.objects.create(user=other_user, club=other_club)
    other_item = Item.objects.create(club=other_club, name="Rope", value_cp=100)
    open_stall(other_club, other_user, "Zed", other_item)
    assert street_stalls(club) == []
    assert "Zed" not in street(login, player, club)


def test_street_same_on_every_load(login, club, player, item):
    open_stall(club, player, "Aria", item)
    rotation = Rotation.objects.create(club=club, name="R", open_date=date(2000, 1, 1))
    rotation.shops.add(Shop.objects.create(club=club, name="Inn", street_position=2))
    client = login(player)
    url = reverse("shops:index", args=[club.slug])
    first = client.get(url).content.decode()
    second = client.get(url).content.decode()

    def strip(html):
        return html[
            html.index('<ul class="wm-street"') : html.index("</ul>", html.index("wm-street"))
        ]

    assert strip(first) == strip(second)


def test_street_uses_club_settings(login, club, player, item):
    club.street_stall_gap = 3
    club.save()
    open_stall(club, player, "Aria", item)
    rotation = Rotation.objects.create(club=club, name="R", open_date=date(2000, 1, 1))
    rotation.shops.add(Shop.objects.create(club=club, name="Inn", street_position=0))
    body = street(login, player, club)
    between = body[body.index("Inn") : body.index("wm-street-lot--stall")]
    assert between.count("wm-street-lot--filler") == 3


# --- stall page banner ------------------------------------------------------


def test_banner_is_stall_look(login, club, player, other_player, item):
    c = open_stall(club, player, "Aria", item)
    url = reverse("shops:player_shop", args=[club.slug, c.pk])
    body = login(other_player).get(url).content.decode()
    assert "Aria&#x27;s stall" in body or "Aria's stall" in body
    assert "player_stall.svg" in body
    assert "wm-shop-silhouette" not in body
    assert "wm-shop-keeper-name" not in body


# --- demo -------------------------------------------------------------------


def test_seed_demo_twice_has_borin_stall_not_aria():
    call_command("seed_demo")
    call_command("seed_demo")
    club = Club.objects.get(characters__name="Borin Stonefist")
    names = [c.name for c in street_stalls(club)]
    assert names == ["Borin Stonefist"]
