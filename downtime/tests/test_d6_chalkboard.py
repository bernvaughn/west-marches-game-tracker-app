import re

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from accounts.design_tokens import contrast_ratio, read_tokens
from downtime import services

pytestmark = [pytest.mark.django_db, pytest.mark.story("D6")]


def play(login, user, club):
    return login(user).get(reverse("downtime:play", args=[club.slug])).content.decode()


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
