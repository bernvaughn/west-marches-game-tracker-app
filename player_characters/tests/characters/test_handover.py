import pytest
from django.urls import reverse

from accounts.models import Membership
from ledger.models import LedgerEntry


def u(name, club, pk):
    return reverse(name, kwargs={"club_slug": club.slug, "pk": pk})


def mid(club, user):
    return Membership.objects.get(club=club, user=user).pk


@pytest.mark.story("U18")
@pytest.mark.parametrize("who", ["club_admin", "site_admin"])
def test_admin_hands_over(club, login, request, character, other_player, who, make_open_trade):
    trade = make_open_trade()
    before = LedgerEntry.objects.count()
    r = login(request.getfixturevalue(who)).post(
        u("characters:handover", club, character.pk),
        {"owner": mid(club, other_player)},
        follow=True,
    )
    character.refresh_from_db()
    assert character.owner.user == other_player
    assert LedgerEntry.objects.count() == before
    assert "now belongs to Other" in r.content.decode()
    trade.refresh_from_db()
    assert trade.sender == character


@pytest.mark.story("U18")
@pytest.mark.parametrize("who", ["game_master", "player"])
def test_others_403(club, login, request, character, other_player, who):
    c = login(request.getfixturevalue(who))
    url = u("characters:handover", club, character.pk)
    assert c.get(url).status_code == 403
    assert c.post(url, {"owner": mid(club, other_player)}).status_code == 403
    character.refresh_from_db()
    assert character.owner.user.email == "player@example.com"


@pytest.mark.story("U18")
def test_foreign_membership_rejected(
    club, other_club, login, club_admin, character, foreign_member
):
    r = login(club_admin).post(
        u("characters:handover", club, character.pk), {"owner": mid(other_club, foreign_member)}
    )
    assert r.status_code == 200
    character.refresh_from_db()
    assert character.owner.user.email == "player@example.com"


@pytest.mark.story("U18")
def test_other_club_character_404(login, club_admin, club, foreign_character):
    r = login(club_admin).get(u("characters:handover", club, foreign_character.pk))
    assert r.status_code == 404
