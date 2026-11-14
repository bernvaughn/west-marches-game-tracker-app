import pytest
from django.urls import reverse

from downtime import services
from downtime.models import DowntimeResult
from ledger.models import LedgerEntry

pytestmark = pytest.mark.django_db


@pytest.mark.story("D8")
def test_reward_entries_render_in_blocks(login, club, club_admin, action, entries):
    body = (
        login(club_admin)
        .get(reverse("downtime:action_edit", args=[club.slug, action.pk]))
        .content.decode()
    )
    assert body.count('class="wm-reward-entry"') >= len(entries)
    block = body.split('class="wm-reward-entry"')[1]
    assert "entries-0-label" in block and "entries-0-weight" in block
    assert "data-chance" in block and "entries-0-DELETE" in block and "entries-0-coins" in block
    assert block.index("entries-0-DELETE") < block.index("wm-reward-entry-body")


@pytest.mark.story("D9")
def test_note_plain_text_and_result_page_no_draw(
    login, club, game_master, character, action, entries
):
    services.award(character, 1)
    res = services.spend(character, action, None)
    c = login(game_master)
    n = (DowntimeResult.objects.count(), LedgerEntry.objects.count())
    body = c.get(reverse("ledger:index", args=[club.slug])).content.decode()
    assert f"Downtime: {action.name}: {res.entry.label} (" in body
    assert reverse("downtime:result", args=[club.slug, res.pk]) not in body
    page = c.get(reverse("downtime:result", args=[club.slug, res.pk])).content.decode()
    assert res.entry.label in page and "data-downtime-wheel" not in page
    assert n == (DowntimeResult.objects.count(), LedgerEntry.objects.count())


@pytest.mark.story("D10")
def test_rewards_table(login, club, player, character, action, entries):
    body = login(player).get(reverse("downtime:play", args=[club.slug])).content.decode()
    for h in ("Outcome", "Reward", "Chance"):
        assert f'<th scope="col">{h}</th>' in body
    assert "<table" in body and "wm-chalkboard" in body
