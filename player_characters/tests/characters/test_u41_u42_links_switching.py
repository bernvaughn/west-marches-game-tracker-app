import pytest
from django.urls import reverse

from accounts.models import Membership
from player_characters.models import Character, SelectedCharacter

pytestmark = pytest.mark.django_db


def u(name, club, pk=None):
    kw = {"club_slug": club.slug}
    if pk is not None:
        kw["pk"] = pk
    return reverse(name, kwargs=kw)


def mk(club, user, name):
    return Character.objects.create(
        club=club, owner=Membership.objects.get(user=user, club=club), name=name
    )


@pytest.fixture
def two(club, player):
    return mk(club, player, "Aria"), mk(club, player, "Wren")


@pytest.mark.story("U41")
def test_mine_redirects_to_selected(login, club, player, two):
    aria, wren = two
    SelectedCharacter.objects.update_or_create(
        membership=Membership.objects.get(user=player, club=club), defaults={"character": wren}
    )
    r = login(player).get(u("characters:mine", club))
    assert r.url == u("characters:detail", club, wren.pk)


@pytest.mark.story("U41")
def test_mine_empty_state(login, club, player):
    r = login(player).get(u("characters:mine", club))
    assert r.status_code == 200
    assert b"Create a character" in r.content
    assert u("characters:create", club).encode() in r.content


@pytest.mark.story("U41")
def test_directory_name_and_player_only(login, club, player, other_player, two):
    mk(club, other_player, "Bram")
    html = login(player).get(u("characters:directory", club)).content.decode()
    assert "Aria" in html and "Bram" in html and "@" not in html.split("<main")[-1]
    assert u("characters:detail", club, two[0].pk) in html
    bram = Character.objects.get(name="Bram")
    assert u("characters:detail", club, bram.pk) not in html


@pytest.mark.story("U41")
def test_directory_gm_and_admin_see_all_links(login, club, player, game_master, club_admin, two):
    for who in (game_master, club_admin):
        html = login(who).get(u("characters:directory", club)).content.decode()
        assert u("characters:detail", club, two[0].pk) in html


@pytest.mark.story("U41")
def test_directory_cross_club_isolation(login, club, other_club, player, foreign_member, two):
    other_owner = Membership.objects.get(user=foreign_member, club=other_club)
    Character.objects.create(club=other_club, owner=other_owner, name="Zelda")
    html = login(player).get(u("characters:directory", club)).content.decode()
    assert "Zelda" not in html
    assert login(foreign_member).get(u("characters:directory", club)).status_code in (403, 404)


@pytest.mark.story("U41")
def test_index_gm_admin_only(login, club, player, game_master, club_admin):
    assert login(player).get(u("characters:index", club)).status_code == 403
    assert login(game_master).get(u("characters:index", club)).status_code == 200
    assert login(club_admin).get(u("characters:index", club)).status_code == 200


@pytest.mark.story("U41")
def test_nav_entries(login, club, player, game_master):
    p = login(player).get(u("characters:mine", club), follow=True).content.decode()
    assert "Character directory" in p and "All characters" not in p
    g = login(game_master).get(u("characters:directory", club)).content.decode()
    assert "All characters" in g and "Character directory" in g


def _switch(client, club, to, nxt):
    return client.post(u("characters:select", club), {"character": to.pk, "next": nxt})


@pytest.mark.story("U42")
def test_switch_same_page(login, club, player, two):
    aria, wren = two
    c = login(player)
    for name in ("characters:detail", "ledger:character_history", "characters:print_items"):
        r = _switch(c, club, wren, u(name, club, aria.pk))
        assert r.url == u(name, club, wren.pk), name


@pytest.mark.story("U42")
def test_switch_form_pages_go_to_sheet(login, club, player, two):
    aria, wren = two
    r = _switch(login(player), club, wren, u("characters:edit", club, aria.pk))
    assert r.url == u("characters:detail", club, wren.pk)


@pytest.mark.story("U42")
def test_switch_elsewhere_and_foreign_sheet_stay(login, club, player, other_player, two):
    aria, wren = two
    bram = mk(club, other_player, "Bram")
    c = login(player)
    nxt = u("characters:directory", club)
    assert _switch(c, club, wren, nxt).url == nxt
    nxt = u("characters:detail", club, bram.pk)
    assert _switch(c, club, wren, nxt).url == nxt


@pytest.mark.story("U42")
def test_switch_no_acting_message_and_unsafe_host(login, club, player, two):
    aria, wren = two
    c = login(player)
    r = _switch(c, club, wren, "https://evil.example/")
    assert r.url == reverse("club_home", args=[club.slug])
    r = _switch(c, club, aria, u("characters:detail", club, wren.pk))
    follow = c.get(r.url)
    assert not [m for m in follow.context["messages"] if "Acting as" in str(m)]
