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
def test_trade_uses_selected_and_ignores_override(login, club, player, two):
    aria, wren = two
    url = reverse("trades:propose", args=[club.slug])
    c = login(player)
    assert c.get(url).context["sender"] == wren
    assert c.get(url, {"from": aria.pk}).context["sender"] == wren
    assert c.get(url, {"choose": 1}).context["sender"] == wren
    assert _stored(player, club) == wren


def test_trade_no_character(login, club, other_player):
    url = reverse("trades:propose", args=[club.slug])
    assert NONE in login(other_player).get(url).content.decode()


def test_trade_isolation(login, club, other_club, player, two):
    aria, wren = two
    Membership.objects.create(user=player, club=other_club)
    foreign = _mk(other_club, player, "Far")
    r = login(player).get(reverse("trades:propose", args=[club.slug]), {"from": foreign.pk})
    assert r.context["sender"] == wren


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
def test_quest_uses_selected_only(login, club, player, two):
    aria, wren = two
    q = Quest.objects.create(club=club, name="Q")
    q.refresh_from_db()
    url = reverse("quests:detail", args=[club.slug, q.pk])
    r = login(player).get(url)
    assert r.status_code == 200
    assert r.context["character"] == wren
    assert "Turn in as Wren" in r.content.decode()
    assert "Aria" not in r.content.decode().split('id="turn-in"')[1]


def test_quest_no_character(login, club, other_player):
    q = Quest.objects.create(club=club, name="Q")
    r = login(other_player).get(reverse("quests:detail", args=[club.slug, q.pk]))
    assert r.status_code == 200
    assert NONE in r.content.decode()


# --- message
def test_message_uses_selected_and_ignores_posted(login, club, player, two):
    from accounts.models import Message

    aria, wren = two
    url = reverse("accounts:message_new", args=[club.slug])
    c = login(player)
    assert "Send as Wren" in c.get(url).content.decode()
    assert c.post(url, {"body": "hi", "character": aria.pk}).status_code == 302
    assert Message.objects.get().character == wren
    assert _stored(player, club) == wren


def test_message_no_character(login, club, other_player):
    from accounts.models import Message

    url = reverse("accounts:message_new", args=[club.slug])
    assert NONE in login(other_player).get(url).content.decode()
    assert login(other_player).post(url, {"body": "hi"}).status_code == 200
    assert Message.objects.count() == 0


def test_message_isolation(login, club, other_club, player, two):
    from accounts.models import Message

    aria, wren = two
    Membership.objects.create(user=player, club=other_club)
    foreign = _mk(other_club, player, "Far")
    url = reverse("accounts:message_new", args=[club.slug])
    assert login(player).post(url, {"body": "x", "character": foreign.pk}).status_code == 302
    assert Message.objects.get().character == wren


@pytest.mark.story("U27")
def test_u27_trade_propose_has_no_sender_field(login, club, player, two):
    html = login(player).get(reverse("trades:propose", args=[club.slug])).content.decode()
    assert 'name="sender"' not in html and 'name="from"' not in html
    assert "Propose trade as Wren" in html


@pytest.mark.story("U27")
def test_u27_quest_no_character_input_and_no_form(login, club, player, other_player, two):
    q = Quest.objects.create(club=club, name="Q")
    url = reverse("quests:detail", args=[club.slug, q.pk])
    assert 'name="character"' not in login(player).get(url).content.decode().split("<h1")[1]
    html = login(other_player).get(url).content.decode()
    assert NONE in html and "Turn in as" not in html


@pytest.mark.story("U27")
def test_u27_move_items_keeps_destination_picker(login, club, player, two, other_player):
    _mk(club, other_player, "Theirs")
    aria, wren = two
    html = (
        login(player)
        .get(reverse("characters:transfer", args=[club.slug, wren.pk]))
        .content.decode()
    )
    assert 'name="destination"' in html
