import pytest
from django.urls import reverse

from ledger.models import LedgerEntry
from ledger.services import available_coins, coin_balance, item_quantities

pytestmark = [pytest.mark.django_db, pytest.mark.story("U15")]


def url(club, character):
    return reverse("characters:transfer", kwargs={"club_slug": club.slug, "pk": character.pk})


def payload(dest, item=None, qty="", cp="", note="", **extra):
    return {
        "destination": dest.pk,
        "note": note,
        "coins_cp": cp,
        "items-TOTAL_FORMS": "3",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "3",
        "items-0-item": item.pk if item else "",
        "items-0-quantity": qty,
        **extra,
    }


def count():
    return LedgerEntry.objects.count()


def test_owner_moves_coins_and_items(login, player, club, funded, second_character, item):
    before = count()
    r = login(player).post(
        url(club, funded), payload(second_character, item, 2, cp=300, note="for the dungeon")
    )
    assert r.status_code == 302
    assert count() == before + 2
    out = LedgerEntry.objects.filter(character=funded, kind="transfer").get()
    inn = LedgerEntry.objects.filter(character=second_character, kind="transfer").get()
    assert out.note == "Transferred to Brannoc: for the dungeon"
    assert inn.note == f"Transferred from {funded.name}: for the dungeon"
    assert out.created_by == player and inn.created_by == player
    assert coin_balance(funded) == 700 and coin_balance(second_character) == 300
    assert item_quantities(funded)[item.pk] == 3
    assert item_quantities(second_character)[item.pk] == 2


def test_default_note(login, player, club, funded, second_character):
    login(player).post(url(club, funded), payload(second_character, cp=10))
    assert LedgerEntry.objects.get(character=funded, kind="transfer").note == (
        "Transferred to Brannoc"
    )


def test_get_with_one_character(login, player, club, character):
    r = login(player).get(url(club, character))
    assert r.status_code == 200
    assert "no other character" in r.content.decode()


def test_get_lists_form(login, player, club, funded, second_character):
    r = login(player).get(url(club, funded))
    assert r.status_code == 200
    assert "Move loot" in r.content.decode()


@pytest.mark.parametrize("who", ["game_master", "club_admin", "site_admin", "other_player"])
def test_non_owner_forbidden(request, login, club, funded, second_character, who):
    user = request.getfixturevalue(who)
    c = login(user)
    before = count()
    assert c.get(url(club, funded)).status_code == 403
    assert c.post(url(club, funded), payload(second_character, cp=10)).status_code == 403
    assert count() == before


def test_destination_of_other_player_refused(login, player, club, funded, other_character):
    before = count()
    r = login(player).post(url(club, funded), payload(other_character, cp=10))
    assert r.status_code == 200
    assert count() == before


def test_destination_self_refused(login, player, club, funded, second_character):
    before = count()
    r = login(player).post(url(club, funded), payload(funded, cp=10))
    assert r.status_code == 200
    assert count() == before


def test_cross_club_destination_refused(
    login, player, club, funded, second_character, foreign_character
):
    before = count()
    r = login(player).post(url(club, funded), payload(foreign_character, cp=10))
    assert r.status_code == 200
    assert count() == before


def test_cross_club_url_is_404(login, player, club, foreign_character, second_character):
    r = login(player).post(url(club, foreign_character), payload(second_character, cp=10))
    assert r.status_code == 404


def test_fully_held_item_not_offered_or_moved(
    login, player, club, funded, second_character, item, make_open_trade
):
    make_open_trade(sender=funded, receiver=second_character, items={item: 5})
    c = login(player)
    r = c.get(url(club, funded))
    assert item.name not in r.content.decode().split("<form")[0]
    before = count()
    r = c.post(url(club, funded), payload(second_character, item, 1))
    assert r.status_code == 200
    assert count() == before


def test_partially_held_item_limited(
    login, player, club, funded, second_character, item, make_open_trade
):
    make_open_trade(sender=funded, receiver=second_character, items={item: 3})
    before = count()
    c = login(player)
    assert c.post(url(club, funded), payload(second_character, item, 3)).status_code == 200
    assert count() == before
    assert c.post(url(club, funded), payload(second_character, item, 2)).status_code == 302


def test_held_coins_cannot_move(login, player, club, funded, second_character, make_open_trade):
    make_open_trade(sender=funded, receiver=second_character, coins=900)
    assert available_coins(funded) == 100
    before = count()
    r = login(player).post(url(club, funded), payload(second_character, cp=200))
    assert r.status_code == 200
    assert count() == before


def test_insufficient_funds_writes_nothing(login, player, club, funded, second_character):
    before = count()
    r = login(player).post(url(club, funded), payload(second_character, cp=5000))
    assert r.status_code == 200
    assert count() == before


def test_empty_submission(login, player, club, funded, second_character):
    before = count()
    r = login(player).post(url(club, funded), payload(second_character))
    assert r.status_code == 200
    assert "at least one" in r.content.decode()
    assert count() == before


def test_both_or_neither(monkeypatch, login, player, club, funded, second_character):
    real = LedgerEntry.objects.create
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real(*a, **kw)

    monkeypatch.setattr(LedgerEntry.objects, "create", flaky)
    before = count()
    c = login(player)
    c.raise_request_exception = False
    r = c.post(url(club, funded), payload(second_character, cp=100))
    assert r.status_code == 500
    assert count() == before
