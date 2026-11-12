import re

import pytest
from django.urls import reverse

from player_characters.models import Trade

pytestmark = pytest.mark.django_db
S = Trade.Status


def directory(client, club):
    return client.get(reverse("characters:directory", args=[club.slug]))


def detail_url(club, t):
    return reverse("trades:detail", args=[club.slug, t.pk])


def propose_url(club, c):
    return reverse("trades:propose", args=[club.slug]) + f"?to={c.pk}"


@pytest.mark.story("U51")
def test_open_trades_show_both_directions(
    login, club, player, character, other_character, make_open_trade
):
    sent = make_open_trade(status=S.REQUESTED)
    got = make_open_trade(sender=other_character, receiver=character, status=S.ACCEPTED)
    body = directory(login(player), club).content.decode()
    assert detail_url(club, sent) in body
    assert detail_url(club, got) in body
    assert "Requested" in body and "Accepted" in body
    assert "Trades with Aria" in body or f"Trades with {character.name}" in body


@pytest.mark.story("U51")
@pytest.mark.parametrize("status", [S.COMPLETED, S.DECLINED, S.CANCELLED])
def test_finished_trades_hidden(
    login, club, player, character, other_character, make_open_trade, status
):
    t = make_open_trade(status=status)
    assert detail_url(club, t) not in directory(login(player), club).content.decode()


@pytest.mark.story("U51")
def test_propose_link_on_others_not_own(
    login, club, player, character, second_character, other_character
):
    client = login(player)
    body = directory(client, club).content.decode()
    assert propose_url(club, other_character) in body
    assert propose_url(club, character) not in body
    assert propose_url(club, second_character) not in body
    r = client.get(propose_url(club, other_character))
    assert r.status_code == 200
    assert r.context["to"] == other_character


@pytest.mark.story("U51")
def test_no_selected_character_no_column(login, club, game_master, other_character):
    body = directory(login(game_master), club).content.decode()
    assert "Trades with" not in body
    assert "?to=" not in body


@pytest.mark.story("U51")
def test_only_selected_characters_trades(
    login, club, player, character, second_character, other_character, make_open_trade
):
    from accounts.models import Membership
    from player_characters.models import SelectedCharacter

    SelectedCharacter.objects.update_or_create(
        membership=Membership.objects.get(user=player, club=club),
        defaults={"character": second_character},
    )
    mine = make_open_trade(sender=character)
    theirs = make_open_trade(sender=second_character)
    body = directory(login(player), club).content.decode()
    assert detail_url(club, theirs) in body
    assert detail_url(club, mine) not in body


@pytest.mark.story("U51")
def test_cross_club_isolation(
    login, club, player, character, other_character, foreign_character, other_club
):
    foreign_trade = Trade.objects.create(
        club=other_club, sender=foreign_character, receiver=foreign_character
    )
    client = login(player)
    body = directory(client, club).content.decode()
    assert "Fenn" not in body
    assert detail_url(club, foreign_trade) not in body
    assert client.get(propose_url(club, foreign_character)).status_code == 404


@pytest.mark.story("U51")
def test_query_count_flat(login, club, player, character, other_character, make_open_trade):
    from accounts.models import Membership
    from player_characters.models import Character

    client = login(player)
    make_open_trade()
    directory(client, club)
    owner = Membership.objects.get(user=player, club=club)
    for i in range(6):
        Character.objects.create(club=club, owner=owner, name=f"Extra{i}")
        make_open_trade(sender=other_character, receiver=character)
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as small:
        directory(client, club)
    for _ in range(5):
        make_open_trade(sender=other_character, receiver=character)
    with CaptureQueriesContext(connection) as big:
        directory(client, club)
    assert len(big) == len(small)


@pytest.mark.story("U53")
def test_directory_name_link_styles(login, club, player, character, other_character):
    body = directory(login(player), club).content.decode()
    own = reverse("characters:detail", args=[club.slug, character.pk])
    assert f'<a href="{own}">{character.name}</a>' in body
    assert f"<span>{other_character.name}</span>" in body
    assert not re.search(r"<a [^>]*wm-chip", body)
    assert (
        body.count(f'href="{reverse("characters:detail", args=[club.slug, other_character.pk])}"')
        == 0
    )
