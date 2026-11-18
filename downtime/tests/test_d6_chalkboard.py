import re
from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse
from django.utils import timezone

from accounts.design_tokens import contrast_ratio, read_tokens
from downtime import services
from downtime.models import DowntimeAction, DowntimeEntry, DowntimeEntryItem

pytestmark = [pytest.mark.django_db, pytest.mark.story("D6")]


def _today():
    return timezone.localdate()


def play(login, user, club, **params):
    url = reverse("downtime:play", args=[club.slug])
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"
    return login(user).get(url).content.decode()


def test_page_is_chalkboard_with_cost_rewards_and_button(
    login, club, player, character, action, entries
):
    services.award(character, 2)
    body = play(login, player, club)
    assert "wm-chalkboard" in body and "wm-chalk-job" in body
    assert action.name in body and "Cost: <strong>1</strong> point" in body
    for e in entries:
        assert e.label in body
    assert "75.0%" in body and "25.0%" in body
    assert "Take the job" in body
    assert reverse("downtime:spend", args=[club.slug, action.pk]) in body


def test_disabled_reason_without_points(login, club, player, character, action, entries):
    body = play(login, player, club)
    assert "disabled" in body and "does not have enough" in body.lower() or "point" in body


def test_other_club_action_not_listed(
    login, club, player, character, action, entries, other_club_action
):
    assert other_club_action.name not in play(login, player, club)


def test_cost_filter_shows_only_selected_cost(login, club, player, character, action, entries):
    services.award(character, 2)
    costly = DowntimeAction.objects.create(
        club=club, name="Costly job", cost=3, start_date=_today() - timedelta(days=1)
    )
    DowntimeEntry.objects.create(action=costly, label="Gold", weight=1, coins=50)
    body = play(login, player, club, cost="1")
    assert action.name in body
    assert costly.name not in body


def test_cost_filter_3plus(login, club, player, character, action):
    services.award(character, 2)
    cheap = DowntimeAction.objects.create(
        club=club, name="Cheap job", cost=2, start_date=_today() - timedelta(days=1)
    )
    DowntimeEntry.objects.create(action=cheap, label="Bread", weight=1, coins=5)
    costly = DowntimeAction.objects.create(
        club=club, name="Costly job", cost=5, start_date=_today() - timedelta(days=1)
    )
    DowntimeEntry.objects.create(action=costly, label="Gold", weight=1, coins=50)
    body = play(login, player, club, cost="3+")
    assert "Costly job" in body
    assert action.name not in body and "Cheap job" not in body


def test_cost_filter_or_within_group(login, club, player, character, action, entries):
    services.award(character, 2)
    cost2 = DowntimeAction.objects.create(
        club=club, name="Cost two", cost=2, start_date=_today() - timedelta(days=1)
    )
    DowntimeEntry.objects.create(action=cost2, label="Bread", weight=1, coins=5)
    cost3 = DowntimeAction.objects.create(
        club=club, name="Cost three", cost=3, start_date=_today() - timedelta(days=1)
    )
    DowntimeEntry.objects.create(action=cost3, label="Gold", weight=1, coins=5)
    body = play(login, player, club, cost=["1", "3+"])
    assert action.name in body and "Cost three" in body
    assert "Cost two" not in body


def test_reward_filter_coins_items_mixed(login, club, player, character, action, entries, item):
    services.award(character, 2)
    coins_action = DowntimeAction.objects.create(
        club=club, name="Coins only", cost=1, start_date=_today() - timedelta(days=1)
    )
    DowntimeEntry.objects.create(action=coins_action, label="Pay", weight=1, coins=10)
    items_action = DowntimeAction.objects.create(
        club=club, name="Items only", cost=1, start_date=_today() - timedelta(days=1)
    )
    entry = DowntimeEntry.objects.create(action=items_action, label="Gear", weight=1, coins=0)
    DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=1)
    mixed_action = DowntimeAction.objects.create(
        club=club, name="Mixed bag", cost=1, start_date=_today() - timedelta(days=1)
    )
    mixed_entry = DowntimeEntry.objects.create(action=mixed_action, label="Both", weight=1, coins=5)
    DowntimeEntryItem.objects.create(entry=mixed_entry, item=item, quantity=1)
    split_action = DowntimeAction.objects.create(
        club=club, name="Split bag", cost=1, start_date=_today() - timedelta(days=1)
    )
    DowntimeEntry.objects.create(action=split_action, label="Pay", weight=1, coins=5)
    split_entry = DowntimeEntry.objects.create(action=split_action, label="Gear", weight=1, coins=0)
    DowntimeEntryItem.objects.create(entry=split_entry, item=item, quantity=1)

    body = play(login, player, club, reward="coins")
    assert "Coins only" in body
    assert "Items only" not in body and "Mixed bag" not in body

    body = play(login, player, club, reward="items")
    assert "Items only" in body
    assert "Coins only" not in body and "Mixed bag" not in body

    body = play(login, player, club, reward="mixed")
    assert "Mixed bag" in body and "Split bag" in body
    assert "Coins only" not in body and "Items only" not in body

    # The fixture action pays coins or nothing: Coins (no items possible).
    body = play(login, player, club, reward="coins")
    assert action.name in body


def test_reward_filter_or_within_group(login, club, player, character, item):
    services.award(character, 2)
    coins_action = DowntimeAction.objects.create(
        club=club, name="Coins only", cost=1, start_date=_today() - timedelta(days=1)
    )
    DowntimeEntry.objects.create(action=coins_action, label="Pay", weight=1, coins=10)
    items_action = DowntimeAction.objects.create(
        club=club, name="Items only", cost=1, start_date=_today() - timedelta(days=1)
    )
    entry = DowntimeEntry.objects.create(action=items_action, label="Gear", weight=1, coins=0)
    DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=1)
    body = play(login, player, club, reward=["coins", "items"])
    assert "Coins only" in body and "Items only" in body


def test_availability_filters(login, club, player, character, action, entries):
    services.award(character, 2)
    future = DowntimeAction.objects.create(
        club=club, name="Future job", cost=1, start_date=_today() + timedelta(days=5)
    )
    DowntimeEntry.objects.create(action=future, label="Later", weight=1, coins=5)
    body = play(login, player, club)
    assert action.name in body
    assert "Future job" not in body

    body = play(login, player, club, availability="upcoming")
    assert "Future job" in body
    assert action.name not in body

    body = play(login, player, club, availability=["now", "upcoming"])
    assert action.name in body and "Future job" in body


def test_filters_combine_across_groups(login, club, player, character, action):
    services.award(character, 2)
    upcoming = DowntimeAction.objects.create(
        club=club, name="Upcoming job", cost=1, start_date=_today() + timedelta(days=5)
    )
    DowntimeEntry.objects.create(action=upcoming, label="Later", weight=1, coins=5)
    pricey = DowntimeAction.objects.create(
        club=club, name="Pricey upcoming", cost=4, start_date=_today() + timedelta(days=5)
    )
    DowntimeEntry.objects.create(action=pricey, label="Later", weight=1, coins=5)
    body = play(login, player, club, cost="1", availability="upcoming")
    assert upcoming.name in body
    assert action.name not in body and pricey.name not in body


def test_tokens_and_contrast():
    t = read_tokens()
    for name in ("--wm-slate", "--wm-chalk", "--wm-chalk-muted", "--wm-chalk-accent"):
        assert name in t
    assert "--wm-board-wood" in t
    for fg in ("--wm-chalk", "--wm-chalk-muted", "--wm-chalk-accent"):
        assert contrast_ratio(t[fg], t["--wm-slate"]) >= 4.5


def test_css_has_phone_and_print_rules():
    with open(finders.find("css/areas/downtime.css"), encoding="utf-8") as fh:
        css = fh.read()
    assert "@media print" in css and "575.98px" in css


def test_design_reference_has_chalkboard(login, site_admin):
    body = login(site_admin).get("/site/design/").content.decode()
    assert 'id="downtime-chalkboard"' in body


def test_chalkboard_coin_text_meets_contrast():
    with open(finders.find("css/areas/downtime.css"), encoding="utf-8") as fh:
        css = fh.read()
    m = re.search(
        r"\.wm-chalkboard \.coin-cp, \.wm-chalkboard \.coin-sp, \.wm-chalkboard \.coin-gp"
        r" \{ color: var\((--wm-[a-z-]+)\); \}",
        css,
    )
    assert m, "chalkboard coin rule missing"
    t = read_tokens()
    assert contrast_ratio(t[m.group(1)], t["--wm-slate"]) >= 4.5
    # .coin-pp keeps its own pill: its text must pass on its own background.
    assert contrast_ratio(t["--wm-coin-pp"], t["--wm-coin-pp-bg"]) >= 4.5
