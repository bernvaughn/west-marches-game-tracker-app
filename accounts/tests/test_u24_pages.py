"""U24: pages default the character field to the selected character."""

import pytest
from django.urls import reverse

from accounts.models import Membership
from player_characters.models import Character, SelectedCharacter
from quests.models import Quest

pytestmark = [pytest.mark.django_db, pytest.mark.story("U24")]

NONE = "You have no character in this club."


def _mk(club, user, name):
    return Character.objects.create(
        club=club, owner=Membership.objects.get(user=user, club=club), name=name
    )


@pytest.fixture
def two(club, player, character):
    second = _mk(club, player, "Wren")
    m = Membership.objects.get(user=player, club=club)
    SelectedCharacter.objects.create(membership=m, character=second)
    return character, second


def _stored(player, club):
    return SelectedCharacter.objects.get(
        membership=Membership.objects.get(user=player, club=club)
    ).character


# --- trade propose
def test_trade_default_and_change(login, club, player, two):
    aria, wren = two
    url = reverse("trades:propose", args=[club.slug])
    c = login(player)
    assert c.get(url).context["sender"] == wren
    assert c.get(url, {"from": aria.pk}).context["sender"] == aria
    r = c.get(url, {"choose": 1})
    assert r.context["sender"] is None
    assert f'value="{wren.pk}" selected' in r.content.decode()
    assert _stored(player, club) == wren


def test_trade_no_character(login, club, other_player):
    url = reverse("trades:propose", args=[club.slug])
    assert NONE in login(other_player).get(url).content.decode()


def test_trade_isolation(login, club, other_club, player, two):
    Membership.objects.create(user=player, club=other_club)
    foreign = _mk(other_club, player, "Far")
    r = login(player).get(reverse("trades:propose", args=[club.slug]), {"from": foreign.pk})
    assert r.status_code == 404


# --- move items
def test_transfer_start(login, club, other_club, player, two, other_player):
    aria, wren = two
    url = reverse("characters:transfer_start", args=[club.slug])
    c = login(player)
    assert c.get(url).url == reverse("characters:transfer", args=[club.slug, wren.pk])
    assert c.get(url, {"from": aria.pk}).url == reverse(
        "characters:transfer", args=[club.slug, aria.pk]
    )
    assert _stored(player, club) == wren
    theirs = _mk(club, other_player, "Theirs")
    assert c.get(url, {"from": theirs.pk}).status_code == 404
    assert c.get(url, {"from": "x"}).status_code == 404


def test_transfer_start_no_character(login, club, other_player):
    url = reverse("characters:transfer_start", args=[club.slug])
    assert NONE in login(other_player).get(url).content.decode()


def test_transfer_start_cross_club(login, club, other_club, player, two):
    Membership.objects.create(user=player, club=other_club)
    foreign = _mk(other_club, player, "Far")
    url = reverse("characters:transfer_start", args=[club.slug])
    assert login(player).get(url, {"from": foreign.pk}).status_code == 404


# --- quests
def test_quest_selected_first(login, club, player, two):
    aria, wren = two
    q = Quest.objects.create(club=club, name="Q")
    q.refresh_from_db()
    url = reverse("quests:detail", args=[club.slug, q.pk])
    r = login(player).get(url)
    assert r.status_code == 200
    assert [x["character"] for x in r.context["rows"]] == [wren, aria]
    assert r.context["rows"][0]["selected"]
    assert "(acting as)" in r.content.decode()


def test_quest_no_character(login, club, other_player):
    q = Quest.objects.create(club=club, name="Q")
    r = login(other_player).get(reverse("quests:detail", args=[club.slug, q.pk]))
    assert r.status_code == 200
    assert NONE in r.content.decode()


# --- message
def test_message_default_and_other(login, club, player, two):
    aria, wren = two
    url = reverse("accounts:message_new", args=[club.slug])
    c = login(player)
    assert c.get(url).context["form"].initial["character"] == wren
    r = c.post(url, {"body": "hi", "character": aria.pk})
    assert r.status_code == 302
    assert _stored(player, club) == wren
    assert c.post(url, {"body": "no char"}).status_code == 302


def test_message_no_character(login, club, other_player):
    url = reverse("accounts:message_new", args=[club.slug])
    assert NONE in login(other_player).get(url).content.decode()
    assert login(other_player).post(url, {"body": "hi"}).status_code == 302


def test_message_isolation(login, club, other_club, player, two):
    Membership.objects.create(user=player, club=other_club)
    foreign = _mk(other_club, player, "Far")
    url = reverse("accounts:message_new", args=[club.slug])
    assert login(player).post(url, {"body": "x", "character": foreign.pk}).status_code == 200
