import datetime

import pytest
from django.urls import reverse

from accounts.models import Membership
from ledger.services import coin_balance
from player_characters.life import archive, mark_dead

pytestmark = pytest.mark.django_db


def adjust_url(club, character):
    return reverse("characters:adjust", kwargs={"club_slug": club.slug, "pk": character.pk})


def bulk_award_url(club):
    return reverse("characters:bulk_award", kwargs={"club_slug": club.slug})


def adjust_payload(cp="", note="why", date="2025-01-02", direction="give", kind=""):
    data = {
        "note": note,
        "date": date,
        "direction": direction,
        "coins_cp": cp,
        "items-TOTAL_FORMS": "3",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "3",
        "items-0-item": "",
        "items-0-quantity": "",
    }
    if kind:
        data["kind"] = kind
    return data


def membership_for(user, club):
    return Membership.objects.get(user=user, club=club)


# --- Adjust page ---


@pytest.mark.story("U144")
@pytest.mark.parametrize("who", ["game_master", "club_admin"])
def test_adjust_archived_shows_warning(request, login, club, character, item, who):
    user = request.getfixturevalue(who)
    archive(character, by=membership_for(user, club))
    r = login(user).get(adjust_url(club, character))
    assert r.status_code == 200
    assert "Archived character." in r.content.decode()
    assert "is archived" in r.content.decode()


@pytest.mark.story("U144")
@pytest.mark.parametrize("who", ["game_master", "club_admin"])
def test_adjust_archived_still_saves(request, login, club, character, item, who):
    user = request.getfixturevalue(who)
    archive(character, by=membership_for(user, club))
    c = login(user)
    r = c.post(
        adjust_url(club, character),
        adjust_payload(cp="100", direction="give"),
    )
    assert r.status_code == 302
    assert coin_balance(character) == 100


@pytest.mark.story("U144")
def test_adjust_living_no_warning(login, game_master, club, character):
    r = login(game_master).get(adjust_url(club, character))
    assert r.status_code == 200
    assert "Archived character." not in r.content.decode()


@pytest.mark.story("U144")
@pytest.mark.parametrize("who", ["game_master", "club_admin"])
def test_adjust_dead_no_archived_warning(request, login, club, character, item, who):
    user = request.getfixturevalue(who)
    mark_dead(character, by=membership_for(user, club), died_on=datetime.date(2025, 1, 1))
    r = login(user).get(adjust_url(club, character))
    assert r.status_code == 200
    assert "Archived character." not in r.content.decode()


@pytest.mark.story("U144")
@pytest.mark.parametrize("who", ["game_master", "club_admin"])
def test_adjust_dead_still_saves(request, login, club, character, item, who):
    user = request.getfixturevalue(who)
    mark_dead(character, by=membership_for(user, club), died_on=datetime.date(2025, 1, 1))
    c = login(user)
    r = c.post(
        adjust_url(club, character),
        adjust_payload(cp="100", direction="give"),
    )
    assert r.status_code == 302
    assert coin_balance(character) == 100


@pytest.mark.story("U144")
@pytest.mark.parametrize("who", ["game_master", "club_admin"])
def test_adjust_dead_and_archived_shows_warning(request, login, club, character, item, who):
    user = request.getfixturevalue(who)
    mark_dead(character, by=membership_for(user, club), died_on=datetime.date(2025, 1, 1))
    archive(character, by=membership_for(user, club))
    r = login(user).get(adjust_url(club, character))
    assert r.status_code == 200
    assert "Archived character." in r.content.decode()


# --- Bulk award ---


@pytest.mark.story("U144")
@pytest.mark.parametrize("who", ["game_master", "club_admin"])
def test_bulk_award_archived_label(request, login, club, character, second_character, who):
    user = request.getfixturevalue(who)
    archive(character, by=membership_for(user, club))
    c = login(user)
    r = c.get(bulk_award_url(club))
    assert r.status_code == 200
    content = r.content.decode()
    assert "(archived)" in content
    assert f'id="char-section-{character.pk}"' in content
    assert "Archived character." in content


@pytest.mark.story("U144")
@pytest.mark.parametrize("who", ["game_master", "club_admin"])
def test_bulk_award_archived_still_awards(request, login, club, character, second_character, who):
    user = request.getfixturevalue(who)
    archive(character, by=membership_for(user, club))
    c = login(user)
    payload = {
        "note": "Party loot",
        "date": "2025-01-15",
        "characters": [str(character.pk), str(second_character.pk)],
        f"coins_{character.pk}": "500",
        f"coins_{second_character.pk}": "300",
        f"items_{character.pk}-TOTAL_FORMS": "3",
        f"items_{character.pk}-INITIAL_FORMS": "0",
        f"items_{character.pk}-MIN_NUM_FORMS": "0",
        f"items_{character.pk}-MAX_NUM_FORMS": "3",
        f"items_{second_character.pk}-TOTAL_FORMS": "3",
        f"items_{second_character.pk}-INITIAL_FORMS": "0",
        f"items_{second_character.pk}-MIN_NUM_FORMS": "0",
        f"items_{second_character.pk}-MAX_NUM_FORMS": "3",
    }
    r = c.post(bulk_award_url(club), payload)
    assert r.status_code == 302
    assert coin_balance(character) == 500
    assert coin_balance(second_character) == 300
