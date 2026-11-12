import pytest
from django.urls import reverse

from accounts import approvals
from accounts.models import Membership
from player_characters.models import Character, SelectedCharacter
from player_characters.selection import selected_character

pytestmark = pytest.mark.django_db


def _char(club, user, name):
    return Character.objects.create(
        club=club, owner=Membership.objects.get(user=user, club=club), name=name
    )


def _url(club):
    return reverse("characters:select", args=[club.slug])


def _req(rf, user, club):
    request = rf.get("/")
    request.user = user
    request.club = club
    request.membership = Membership.objects.filter(user=user, club=club).first()
    return request


@pytest.fixture
def two(club, player):
    return _char(club, player, "Aria"), _char(club, player, "Wren")


@pytest.mark.story("U24")
def test_select_saves_per_club(login, club, other_club, player, two):
    Membership.objects.create(user=player, club=other_club)
    b = _char(other_club, player, "Bram")
    _char(other_club, player, "Cade")
    client = login(player)
    assert client.post(_url(club), {"character": two[1].pk}).status_code == 302
    client.post(_url(other_club), {"character": b.pk})
    assert SelectedCharacter.objects.get(membership__club=club).character == two[1]
    assert SelectedCharacter.objects.get(membership__club=other_club).character == b


@pytest.mark.story("U24")
def test_other_players_character_refused(login, club, player, other_player, two):
    theirs = _char(club, other_player, "Borin")
    assert login(player).post(_url(club), {"character": theirs.pk}).status_code == 403
    assert not SelectedCharacter.objects.exists()


@pytest.mark.story("U24")
def test_foreign_club_character_404(login, club, other_club, player, two):
    Membership.objects.create(user=player, club=other_club)
    foreign = _char(other_club, player, "Fenn")
    assert login(player).post(_url(club), {"character": foreign.pk}).status_code == 404
    assert login(player).post(_url(club), {"character": "x"}).status_code == 404


@pytest.mark.story("U24")
def test_single_character_always_selected(rf, club, player, character, other_player):
    other = _char(club, other_player, "Borin")
    SelectedCharacter.objects.create(
        membership=Membership.objects.get(user=player, club=club), character=other
    )
    assert selected_character(_req(rf, player, club)) == character


@pytest.mark.story("U24")
def test_handover_fallback(rf, club, player, other_player, two):
    aria, wren = two
    membership = Membership.objects.get(user=player, club=club)
    SelectedCharacter.objects.create(membership=membership, character=wren)
    assert selected_character(_req(rf, player, club)) == wren
    wren.owner = Membership.objects.get(user=other_player, club=club)
    wren.save()
    assert selected_character(_req(rf, player, club)) == aria
    aria.owner = wren.owner
    aria.save()
    assert selected_character(_req(rf, player, club)) is None


@pytest.mark.story("U24")
@pytest.mark.parametrize("target", ["https://evil.example/", "//evil.example", "javascript:x"])
def test_unsafe_next_goes_home(login, club, player, two, target):
    r = login(player).post(_url(club), {"character": two[0].pk, "next": target})
    assert r.url == reverse("club_home", args=[club.slug])


@pytest.mark.story("U24")
def test_safe_next_and_get(login, club, player, two):
    client = login(player)
    nxt = f"/c/{club.slug}/characters/directory/"
    r = client.post(_url(club), {"character": two[0].pk, "next": nxt})
    assert r.url == nxt
    assert client.get(_url(club)).status_code == 405


@pytest.mark.story("U24")
def test_gm_and_superuser(login, club, game_master, site_admin):
    _char(club, game_master, "Gwen")
    assert b"Acting as Gwen" in login(game_master).get(f"/c/{club.slug}/characters/").content
    r = login(site_admin).get(f"/c/{club.slug}/characters/")
    assert b"No character" in r.content


@pytest.mark.story("U25")
def test_navbar_name_and_dropdown(login, club, player, character):
    html = login(player).get(f"/c/{club.slug}/characters/directory/").content.decode()
    assert "Player" in html and "Acting as Aria" in html and "<select" not in html


@pytest.mark.story("U25")
def test_navbar_dropdown_with_two(login, club, player, two):
    html = login(player).get(f"/c/{club.slug}/characters/directory/").content.decode()
    assert 'name="character"' in html and "Wren" in html


@pytest.mark.story("U25")
def test_navbar_no_character(login, club, player):
    assert b"No character" in login(player).get(f"/c/{club.slug}/characters/directory/").content


@pytest.mark.story("U25")
def test_selector_isolated_between_clubs(login, club, other_club, player, two):
    Membership.objects.create(user=player, club=other_club)
    _char(other_club, player, "Secretname")
    _char(other_club, player, "Othername")
    html = login(player).get(f"/c/{club.slug}/characters/directory/").content.decode()
    assert "Secretname" not in html and "Othername" not in html


@pytest.mark.story("U25")
def test_approvals_contract(rf, monkeypatch, club, player):
    monkeypatch.setattr(approvals, "_providers", [])
    approvals.register(lambda r: ("Batches", 2, "/x/"))
    approvals.register(lambda r: None)
    approvals.register(lambda r: ("Zero", 0, "/y/"))
    ctx = approvals.context_processor(_req(rf, player, club))
    assert ctx["approvals_total"] == 2
    assert [a.label for a in ctx["approvals"]] == ["Batches"]


@pytest.mark.story("U24")
def test_demo_gives_alice_two_characters(db):
    from django.core.management import call_command

    call_command("seed_demo")
    call_command("seed_demo")
    assert Character.objects.filter(owner__user__email="alice@example.com").count() == 2
