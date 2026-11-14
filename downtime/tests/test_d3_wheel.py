from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from downtime import services
from downtime.models import DowntimeEntry
from downtime.wheel import wheel_payload

pytestmark = [pytest.mark.django_db, pytest.mark.story("D3")]


def url(name, club, *args):
    return reverse(f"downtime:{name}", args=[club.slug, *args])


@pytest.fixture
def result(character, action, entries):
    services.award(character, 3)
    return services.spend(character, action, None)


def test_payload_matches_weights(result, entries):
    p = wheel_payload(result)
    assert p["chosen"] == [e.pk for e in entries].index(result.entry_id)
    assert sum(s["angle"] for s in p["slices"]) == pytest.approx(360)
    assert p["slices"][-1]["end"] == 360.0
    for s, e in zip(p["slices"], entries, strict=True):
        assert s["angle"] == pytest.approx(e.weight / 4 * 360)
    for a, b in zip(p["slices"], p["slices"][1:], strict=False):
        assert a["end"] == pytest.approx(b["start"])
    mid = (p["slices"][p["chosen"]]["start"] + p["slices"][p["chosen"]]["end"]) / 2
    assert (p["final_rotation"] + mid) % 360 == pytest.approx(0, abs=0.01) or (
        p["final_rotation"] + mid
    ) % 360 == pytest.approx(360, abs=0.01)


def test_single_entry_is_full_circle(character, action):
    DowntimeEntry.objects.create(action=action, label="Only", weight=2)
    services.award(character, 1)
    p = wheel_payload(services.spend(character, action, None))
    assert len(p["slices"]) == 1 and p["slices"][0]["angle"] == 360


def test_deleted_entry_gives_none_and_page_renders(login, club, player, result):
    result.entry.delete()
    result.refresh_from_db()
    assert wheel_payload(result) is None
    r = login(player).get(url("result", club, result.pk))
    assert r.status_code == 200 and b"data-downtime-wheel" not in r.content


def test_result_page_works_without_js(login, club, player, result):
    body = login(player).get(url("result", club, result.pk)).content.decode()
    assert result.entry.label in body
    assert "data-downtime-wheel" not in body and "downtime_wheel.js" not in body
    assert "hidden" not in body.split("data-wheel-result")[1].split(">")[0]


def test_htmx_spend_returns_modal(login, club, player, character, action, entries):
    services.award(character, 2)
    r = login(player).post(url("spend", club, action.pk), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert "<html" not in body and "data-downtime-wheel" in body and "modal-header" in body


def test_htmx_spend_without_points_redirects(login, club, player, character, action, entries):
    r = login(player).post(url("spend", club, action.pk), HTTP_HX_REQUEST="true")
    assert r["HX-Redirect"] == url("play", club)


def test_plain_spend_still_redirects(login, club, player, character, action, entries):
    services.award(character, 1)
    r = login(player).post(url("spend", club, action.pk))
    assert r.status_code == 302


def test_result_modal_cross_club_404(login, club, other_club, player, result):
    from accounts.models import Membership, User

    u = User.objects.create_user("y@example.com", password="pw", display_name="Y")
    Membership.objects.create(user=u, club=other_club)
    r = login(u).get(url("result", other_club, result.pk), HTTP_HX_REQUEST="true")
    assert r.status_code == 404


def test_reduced_motion_guards():
    base = Path(settings.BASE_DIR)
    assert "prefers-reduced-motion" in (base / "static/js/downtime_wheel.js").read_text()
    assert "prefers-reduced-motion" in (base / "static/css/areas/downtime.css").read_text()


def test_modal_spin_waits_until_shown():
    """A transition on a display:none modal never runs; the browser check proves the spin."""
    js = (Path(settings.BASE_DIR) / "static/js/downtime_wheel.js").read_text()
    assert "shown.bs.modal" in js
