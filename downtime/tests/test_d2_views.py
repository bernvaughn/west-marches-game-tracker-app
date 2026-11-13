import pytest
from django.urls import reverse

from downtime import services
from downtime.models import DowntimeAction, DowntimeEntry, DowntimeEntryItem, DowntimeResult
from ledger import services as ledger

pytestmark = [pytest.mark.django_db, pytest.mark.story("D2")]


def url(name, club, *args):
    return reverse(f"downtime:{name}", args=[club.slug, *args])


def form_data(**over):
    data = {
        "name": "Fishing",
        "description": "Cast a line.",
        "cost": "2",
        "start_date": "",
        "end_date": "",
        "entries-TOTAL_FORMS": "1",
        "entries-INITIAL_FORMS": "0",
        "entries-MIN_NUM_FORMS": "0",
        "entries-MAX_NUM_FORMS": "1000",
        "entries-0-label": "Trout",
        "entries-0-weight": "3",
        "entries-0-order": "0",
        "entries-0-coins_pp": "",
        "entries-0-coins_gp": "1",
        "entries-0-coins_sp": "",
        "entries-0-coins_cp": "",
        "entries-0-items-TOTAL_FORMS": "1",
        "entries-0-items-INITIAL_FORMS": "0",
        "entries-0-items-MIN_NUM_FORMS": "0",
        "entries-0-items-MAX_NUM_FORMS": "1000",
        "entries-0-items-0-item": "",
        "entries-0-items-0-quantity": "1",
    }
    data.update(over)
    return data


# ---- admin ----


def test_admin_creates_action_with_entry_and_item(login, club, club_admin, item):
    data = form_data(**{"entries-0-items-0-item": str(item.pk)})
    r = login(club_admin).post(url("action_new", club), data)
    assert r.status_code == 302
    action = DowntimeAction.objects.get(name="Fishing")
    entry = action.entries.get()
    assert entry.weight == 3 and entry.coins == 100
    assert entry.items.get().item == item


def test_form_shows_chance_percent(login, club, club_admin, action, entries):
    body = login(club_admin).get(url("action_edit", club, action.pk)).content.decode()
    assert "75.0%" in body and "25.0%" in body
    assert "downtime_chances.js" in body


def test_admin_edits_and_deletes_entry(login, club, club_admin, action, entries):
    c = login(club_admin)
    data = form_data(
        name="Bakery",
        **{
            "entries-TOTAL_FORMS": "2",
            "entries-INITIAL_FORMS": "2",
            "entries-0-id": str(entries[0].pk),
            "entries-0-label": "Rolls",
            "entries-1-id": str(entries[1].pk),
            "entries-1-label": "Nothing",
            "entries-1-weight": "1",
            "entries-1-order": "1",
            "entries-1-DELETE": "on",
            "entries-1-items-TOTAL_FORMS": "0",
            "entries-1-items-INITIAL_FORMS": "0",
            "entries-0-items-0-item": "",
        },
    )
    r = c.post(url("action_edit", club, action.pk), data)
    assert r.status_code == 302, r.content.decode()[:3000]
    entries[0].refresh_from_db()
    assert entries[0].label == "Rolls"
    assert not DowntimeEntry.objects.filter(pk=entries[1].pk).exists()


def test_other_club_item_refused(login, club, club_admin, other_club):
    from items.models import Item

    foreign = Item.objects.create(club=other_club, name="Foreign")
    data = form_data(**{"entries-0-items-0-item": str(foreign.pk)})
    r = login(club_admin).post(url("action_new", club), data)
    assert r.status_code == 200
    assert not DowntimeAction.objects.filter(name="Fishing").exists()


def test_end_before_start_refused(login, club, club_admin):
    data = form_data(start_date="2026-05-02", end_date="2026-05-01")
    assert login(club_admin).post(url("action_new", club), data).status_code == 200


@pytest.mark.parametrize("name", ["actions", "action_new"])
def test_non_admins_blocked(login, club, player, game_master, name):
    for user in (player, game_master):
        assert login(user).get(url(name, club)).status_code in (302, 403)


def test_non_admin_cannot_edit(login, club, player, action):
    assert login(player).get(url("action_edit", club, action.pk)).status_code in (302, 403)


def test_admin_isolation(login, club, club_admin, action, other_club_action):
    c = login(club_admin)
    body = c.get(url("actions", club)).content.decode()
    assert action.name in body and "Other" not in body
    assert c.get(url("action_edit", club, other_club_action.pk)).status_code == 404


# ---- player ----


def test_player_page_lists_live_actions_only(
    login,
    club,
    player,
    character,
    action,
    entries,
    upcoming_action,
    ended_action,
    other_club_action,
):
    DowntimeEntry.objects.create(action=upcoming_action, label="x")
    DowntimeEntry.objects.create(action=ended_action, label="x")
    DowntimeEntry.objects.create(action=other_club_action, label="x")
    empty = DowntimeAction.objects.create(club=club, name="Empty one")
    body = login(player).get(url("play", club)).content.decode()
    assert "Work at a bakery" in body and "75.0%" in body
    for hidden in ("Upcoming", "Ended", "Other", empty.name):
        assert hidden not in body


def test_spend_redirects_to_result_and_lowers_balance(
    login, club, player, character, action, entries
):
    services.award(character, 3)
    c = login(player)
    r = c.post(url("spend", club, action.pk))
    res = DowntimeResult.objects.get()
    assert r.status_code == 302 and r.url == url("result", club, res.pk)
    assert services.balance(character) == 2
    body = c.get(r.url).content.decode()
    assert res.entry.label in body
    assert ledger.coin_balance(character) in (0, 10)


def test_spend_without_points_shows_error(login, club, player, character, action, entries):
    r = login(player).post(url("spend", club, action.pk), follow=True)
    assert "enough downtime points" in r.content.decode()
    assert not DowntimeResult.objects.exists()


def test_spend_get_refused(login, club, player, character, action, entries):
    assert login(player).get(url("spend", club, action.pk)).status_code == 405


def test_other_players_result_404(login, club, player, other_player, character, action, entries):
    services.award(character, 1)
    login(player).post(url("spend", club, action.pk))
    res = DowntimeResult.objects.get()
    assert login(other_player).get(url("result", club, res.pk)).status_code == 404


def test_cross_club_isolation(
    login, club, other_club, player, character, other_club_action, other_club_character
):
    DowntimeEntry.objects.create(action=other_club_action, label="x")
    services.award(character, 1)
    c = login(player)
    assert c.post(url("spend", club, other_club_action.pk)).status_code == 404
    res = DowntimeResult.objects.create(character=other_club_character, action=other_club_action)
    assert c.get(url("result", club, res.pk)).status_code == 404


def test_result_lists_items(login, club, player, character, action, entries, item):
    DowntimeEntryItem.objects.create(entry=entries[0], item=item, quantity=1)
    DowntimeEntry.objects.filter(pk=entries[1].pk).delete()
    services.award(character, 1)
    c = login(player)
    r = c.post(url("spend", club, action.pk))
    assert "Rope" in c.get(r.url).content.decode()


# ---- navigation ----


def test_admin_nav_entry_only_for_admins(login, club, player, club_admin):
    link = f'href="{url("actions", club)}"'
    home = reverse("club_home", args=[club.slug])
    assert link not in login(player).get(home).content.decode()
    assert link in login(club_admin).get(home).content.decode()


def test_shortcut_before_trades(login, club, player):
    body = login(player).get(reverse("club_home", args=[club.slug])).content.decode()
    bar = body[body.index('<nav class="site-header') :]
    bar = bar[: bar.index("</nav>")]
    assert bar.index('aria-label="Downtime"') < bar.index('aria-label="Trades"')
    assert bar.index('aria-label="Quests"') < bar.index('aria-label="Downtime"')


def test_topbar_css_has_six_ranks():
    from pathlib import Path

    css = Path("static/css/components.css").read_text()
    for i in range(1, 7):
        assert f".wm-shortcut-rank-{i}" in css
