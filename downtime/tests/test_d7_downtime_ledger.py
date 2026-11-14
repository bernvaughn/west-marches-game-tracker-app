import pytest
from django.urls import reverse

from downtime import services
from ledger import services as ledger
from ledger.services import Line

pytestmark = [pytest.mark.django_db, pytest.mark.story("D7")]


@pytest.fixture
def spent(club, character, action, entries):
    services.award(character, 1)
    entries[1].delete()
    return services.spend(character, action, None)


def test_spend_links_ledger_entry(spent):
    assert spent.ledger_entry is not None
    assert spent.ledger_entry.downtime_result == spent


def test_empty_result_has_no_entry(club, character, action):
    from downtime.models import DowntimeEntry

    DowntimeEntry.objects.create(action=action, label="Nothing", weight=1)
    services.award(character, 1)
    assert services.spend(character, action, None).ledger_entry is None


def test_history_and_club_ledger_label_no_link(login, club, game_master, character, spent):
    link = reverse("downtime:result", args=[club.slug, spent.pk])
    for url in (
        reverse("ledger:character_history", args=[club.slug, character.pk]),
        reverse("ledger:index", args=[club.slug]),
    ):
        body = login(game_master).get(url).content.decode()
        assert f"Downtime: {spent.action.name}: {spent.entry.label} (" in body
        assert link not in body


def test_plain_award_has_no_link(login, club, game_master, character):
    ledger.record(character, "award", [Line(coins=5)], note="Treasure", actor=game_master)
    body = login(game_master).get(reverse("ledger:index", args=[club.slug])).content.decode()
    assert "Treasure" in body and "/downtime/" not in body.split("<tbody")[-1]


def test_downtime_filter(login, club, game_master, character, spent):
    ledger.record(character, "award", [Line(coins=5)], note="Treasure", actor=game_master)
    c = login(game_master)
    url = reverse("ledger:index", args=[club.slug])
    body = c.get(url + "?downtime=True").content.decode()
    assert f"Downtime: {spent.action.name}" in body and "Treasure" not in body
    assert "checked" in body
    assert "Treasure" in c.get(url).content.decode()
