from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from downtime.models import DowntimeAction
from downtime.views import agenda as agenda_views
from downtime.views.agenda import AgendaItem, month_weeks
from quests.models import Quest
from shops.models import Rotation

pytestmark = [pytest.mark.story("U72"), pytest.mark.django_db]

HX = {"HTTP_HX_REQUEST": "true"}


def url(name, club, *args):
    return reverse(f"downtime:{name}", args=[club.slug, *args])


def bar(start, end, label="x"):
    return AgendaItem("quest", label, start, end, "/e/")


@pytest.fixture
def admin(login, club_admin):
    return login(club_admin)


@pytest.fixture
def stuff(club):
    return (
        Rotation.objects.create(
            club=club,
            name="Spring rotation",
            open_date=date(2030, 3, 5),
            close_date=date(2030, 3, 9),
        ),
        Quest.objects.create(
            club=club, name="Dragon hunt", start_date=date(2030, 3, 10), end_date=None
        ),
        DowntimeAction.objects.create(
            club=club, name="Bakery", start_date=None, end_date=date(2030, 3, 2)
        ),
    )


# month_weeks


def test_month_weeks_monday_start():
    weeks = month_weeks(2030, 3, [])
    assert weeks[0]["days"][0]["date"] == date(2030, 2, 25)
    assert weeks[0]["days"][0]["date"].weekday() == 0
    assert weeks[0]["days"][4]["in_month"] is True and weeks[0]["days"][0]["in_month"] is False


def test_month_weeks_clips_across_weeks():
    weeks = month_weeks(2030, 3, [bar(date(2030, 3, 6), date(2030, 3, 13))])
    segs = [(w["bars"][0] if w["bars"] else None) for w in weeks]
    first, second = segs[1], segs[2]
    assert segs[0] is None
    assert (first.col_start, first.span, first.continues_left, first.continues_right) == (
        3,
        5,
        False,
        True,
    )
    assert (second.col_start, second.span, second.continues_left, second.continues_right) == (
        1,
        3,
        True,
        False,
    )


def test_month_weeks_overlap_uses_lanes():
    weeks = month_weeks(
        2030,
        3,
        [
            bar(date(2030, 3, 5), date(2030, 3, 7), "a"),
            bar(date(2030, 3, 6), date(2030, 3, 8), "b"),
            bar(date(2030, 3, 9), date(2030, 3, 9), "c"),
        ],
    )
    bars = {b.label: b.lane for b in weeks[1]["bars"]}
    assert bars["a"] != bars["b"]
    assert bars["c"] == 0 and weeks[1]["lane_count"] == 2


def test_month_weeks_open_ended():
    weeks = month_weeks(2030, 3, [bar(None, None)])
    assert all(w["bars"][0].span == 7 for w in weeks)


# the page


def test_agenda_shows_items_in_range(admin, club, stuff):
    r = admin.get(url("agenda", club), {"month": "2030-03"})
    assert r.status_code == 200
    html = r.content.decode()
    for name in ("Spring rotation", "Dragon hunt", "Bakery"):
        assert name in html


def test_agenda_hides_items_outside_month(admin, club, stuff):
    html = admin.get(url("agenda", club), {"month": "2030-06"}).content.decode()
    assert "Spring rotation" not in html
    assert "Bakery" not in html
    assert "Dragon hunt" in html  # open-ended quest still runs
    assert "Nothing is scheduled" not in html


def test_agenda_bad_month_falls_back(admin, club):
    assert admin.get(url("agenda", club), {"month": "nope"}).status_code == 200


def test_agenda_empty_state(admin, club):
    assert (
        "Nothing is scheduled"
        in admin.get(url("agenda", club), {"month": "2030-03"}).content.decode()
    )


def test_agenda_htmx_returns_body_only(admin, club):
    r = admin.get(url("agenda", club), **HX)
    html = r.content.decode()
    assert 'id="agenda-body"' in html and "<html" not in html


def test_cross_club_never_shows(admin, club, other_club):
    Rotation.objects.create(club=other_club, name="Foreign rot", open_date=date(2030, 3, 1))
    Quest.objects.create(club=other_club, name="Foreign quest")
    foreign = DowntimeAction.objects.create(club=other_club, name="Foreign act")
    html = admin.get(url("agenda", club), {"month": "2030-03"}).content.decode()
    assert "Foreign" not in html
    assert admin.get(url("agenda_action_edit", club, foreign.pk)).status_code == 404


def test_access(club, club_admin, game_master, player, site_admin, login):
    u = url("agenda", club)
    assert login(club_admin).get(u).status_code == 200
    assert login(site_admin).get(u).status_code == 200
    assert login(game_master).get(u).status_code == 403
    assert login(player).get(u).status_code == 403
    assert Client().get(u).status_code == 302


def test_menu_shows_agenda_for_admins_only(club, club_admin, player, login):
    home = reverse("accounts:index", args=[club.slug])
    assert url("agenda", club) in login(club_admin).get(home).content.decode()
    assert url("agenda", club) not in login(player).get(home).content.decode()


# action create and edit


def form_data(**kw):
    return {
        "name": "Fish",
        "description": "",
        "cost": 1,
        "start_date": "2030-03-04",
        "end_date": "2030-03-08",
        **kw,
    }


def test_action_plain_post_saves_and_redirects(admin, club):
    r = admin.post(url("agenda_action_create", club), form_data())
    assert r.status_code == 302 and r["Location"].endswith("?month=2030-03")
    assert DowntimeAction.objects.get(club=club).name == "Fish"


def test_action_htmx_post_triggers_refresh(admin, club):
    r = admin.post(url("agenda_action_create", club), form_data(), **HX)
    assert r.status_code == 204
    assert "agendaChanged" in r["HX-Trigger"] and "appModalClose" in r["HX-Trigger"]


def test_action_invalid_htmx_rerenders_fragment(admin, club):
    r = admin.post(url("agenda_action_create", club), form_data(end_date="2030-03-01"), **HX)
    html = r.content.decode()
    assert r.status_code == 200 and "<html" not in html and "must not be before" in html
    assert not DowntimeAction.objects.exists()


def test_action_date_prefill_and_bad_date(admin, club):
    r = admin.get(url("agenda_action_create", club), {"date": "2030-03-04"}, **HX)
    assert 'value="2030-03-04"' in r.content.decode()
    assert admin.get(url("agenda_action_create", club), {"date": "junk"}, **HX).status_code == 200


def test_action_edit_moves_dates(admin, club, stuff):
    act = stuff[2]
    r = admin.post(url("agenda_action_edit", club, act.pk), form_data(name="Bakery"), **HX)
    assert r.status_code == 204
    act.refresh_from_db()
    assert act.start_date == date(2030, 3, 4)


def test_full_edit_link_absent_without_d2(admin, club, stuff, monkeypatch):
    monkeypatch.setattr(
        agenda_views,
        "reverse",
        lambda *a, **k: (
            (_ for _ in ()).throw(agenda_views.NoReverseMatch())
            if a[0] == "downtime:action_edit"
            else reverse(*a, **k)
        ),
    )
    r = admin.get(url("agenda_action_edit", club, stuff[2].pk), **HX)
    assert r.status_code == 200 and "Open full editor" not in r.content.decode()


def test_add_chooser_carries_date(admin, club):
    html = admin.get(url("agenda_add", club), {"date": "2030-03-04"}, **HX).content.decode()
    assert "<html" not in html and html.count("date=2030-03-04") >= 3


# modal branches on rotation and quest views


def test_rotation_modal_and_prefill(admin, club):
    u = reverse("shops:rotation_create", args=[club.slug])
    r = admin.get(u, {"date": "2030-03-04"}, **HX)
    assert "<html" not in r.content.decode() and 'value="2030-03-04"' in r.content.decode()
    r = admin.post(u, {"name": "R", "open_date": "2030-03-04", "close_date": ""}, **HX)
    assert r.status_code == 204 and "agendaChanged" in r["HX-Trigger"]
    assert Rotation.objects.filter(club=club, name="R").exists()


def test_rotation_edit_modal(admin, club, stuff):
    u = reverse("shops:rotation_edit", args=[club.slug, stuff[0].pk])
    assert "<html" not in admin.get(u, **HX).content.decode()
    assert "<html" in admin.get(u).content.decode()


def test_quest_modal_and_prefill(admin, club, item):
    u = reverse("quests:create", args=[club.slug])
    r = admin.get(u, {"date": "2030-03-04"}, **HX)
    html = r.content.decode()
    assert "<html" not in html and 'value="2030-03-04"' in html and "req-TOTAL_FORMS" in html
    data = {
        "name": "Q",
        "description": "d",
        "start_date": "2030-03-04",
        "req-TOTAL_FORMS": 1,
        "req-INITIAL_FORMS": 0,
        "rew-TOTAL_FORMS": 1,
        "req-0-item": item.pk,
        "req-0-quantity": 1,
        "rew-0-coins_gp": 5,
        "rew-0-quantity": 0,
        "rew-INITIAL_FORMS": 0,
    }
    r = admin.post(u, data, **HX)
    assert r.status_code == 204, r.content.decode()[-1500:]
    assert "agendaChanged" in r["HX-Trigger"]
    assert Quest.objects.filter(club=club, name="Q").exists()
