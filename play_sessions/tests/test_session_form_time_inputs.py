"""Time inputs on the session form get form-control like the date input.

Before the fix, `start_time` and `end_time` render without `form-control`:
the label sits beside the input and the input is 28 px high. After the fix
`"time"` is in `TEXT_TYPES` in `config/form_renderer.py`, so time inputs get
`form-control form-control-sm` just like the date input. New and edit forms
share `play_sessions/session_form.html`, so both change together.
"""

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from accounts.models import Club, Membership, User
from play_sessions.models import PlaySession

pytestmark = [pytest.mark.django_db, pytest.mark.story("P1")]


def _make_gm_client(client, club):
    user = User.objects.create_user(email="gm@test.com", password="pass12345678")
    Membership.objects.create(user=user, club=club, is_game_master=True)
    client.force_login(user)
    return user


def _input_classes(content, name):
    """Return the class list of the input with this name, or None if missing."""
    soup = BeautifulSoup(content, "html.parser")
    inp = soup.find("input", {"name": name})
    return inp.get("class", []) if inp else None


@pytest.mark.parametrize("page", ["create", "edit"])
def test_time_inputs_carry_form_control(client, page):
    club = Club.objects.create(name="Test Club", slug="test-club", timezone="America/New_York")
    _make_gm_client(client, club)

    if page == "create":
        url = reverse("play_sessions:session_create", kwargs={"club_slug": club.slug})
    else:
        gm_membership = Membership.objects.get(user__email="gm@test.com", club=club)
        session = PlaySession.objects.create(
            club=club,
            title="Old session",
            starts_at=timezone.now(),
            ends_at=timezone.now(),
            game_master=gm_membership,
        )
        url = reverse(
            "play_sessions:session_edit", kwargs={"club_slug": club.slug, "pk": session.pk}
        )

    response = client.get(url)
    assert response.status_code == 200, f"{page} should load for a GM"

    classes = {
        name: _input_classes(response.content.decode(), name)
        for name in ("date", "start_time", "end_time")
    }
    for name in ("date", "start_time", "end_time"):
        assert "form-control" in classes[name], (
            f"{name} on {page} lacks form-control; got {classes[name]}"
        )


# ---------------------------------------------------------------------------
# Browser test
# ---------------------------------------------------------------------------

DEMO_CLUB_SLUG = "demo"
DEMO_GM_EMAIL = "gm@example.com"


def _seed_demo():
    from django.core.management import call_command

    call_command("seed_demo", verbosity=0)


def _session_id(user):
    """Log in server-side and return the session cookie for Playwright."""
    from django.test import Client

    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def _time_input_metrics(page):
    """Return per-input metrics for start_time and end_time."""
    return page.evaluate(
        """() => {
        const out = {};
        for (const name of ['start_time', 'end_time']) {
            const input = document.querySelector(`input[name="${name}"]`);
            const label = input
              ? document.querySelector(`label[for="${input.id}"]`)
              : null;
            out[name] = {
                present: !!input,
                height: input ? input.getBoundingClientRect().height : 0,
                width: input ? input.getBoundingClientRect().width : 0,
                labelAbove: label && input
                  ? label.getBoundingClientRect().bottom <= input.getBoundingClientRect().top
                  : false,
            };
        }
        out.page = {
            scrollWidth: document.documentElement.scrollWidth,
            innerWidth: window.innerWidth,
        };
        return out;
      }"""
    )


@pytest.mark.browser
@pytest.mark.parametrize("width", [390, 1280])
@pytest.mark.parametrize("form_page", ["new", "edit"])
def test_time_inputs_match_other_fields_on_phone_and_desktop(
    transactional_db, live_server, width, form_page
):
    """At 390 px time inputs have the label above and are >= 44 px high, no
    sideways scroll. At 1280 px they stay short (<= 12rem)."""
    from playwright.sync_api import sync_playwright

    from accounts.models import User

    _seed_demo()
    user = User.objects.get(email=DEMO_GM_EMAIL)
    session_id = _session_id(user)

    edit_pk = None
    if form_page == "edit":
        club = Club.objects.get(slug=DEMO_CLUB_SLUG)
        gm_membership = Membership.objects.get(user=user, club=club)
        session = PlaySession.objects.create(
            club=club,
            title="Browser edit session",
            starts_at=timezone.now(),
            ends_at=timezone.now(),
            game_master=gm_membership,
        )
        edit_pk = session.pk

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 800})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        browser_page = context.new_page()
        try:
            path = (
                f"/c/{DEMO_CLUB_SLUG}/sessions/new/"
                if form_page == "new"
                else f"/c/{DEMO_CLUB_SLUG}/sessions/{edit_pk}/edit/"
            )
            browser_page.goto(f"{live_server.url}{path}")
            browser_page.wait_for_load_state("networkidle")

            metrics = _time_input_metrics(browser_page)
            for name in ("start_time", "end_time"):
                m = metrics[name]
                assert m["present"], f"{name} input missing on {form_page} at {width} px"
                if width == 390:
                    assert m["labelAbove"], f"{name} label not above input on {form_page} at 390 px"
                    assert m["height"] >= 44, (
                        f"{name} input {m['height']} px high on {form_page} at 390 px"
                    )
                else:
                    assert m["width"] <= 192, (
                        f"{name} input {m['width']} px wide on {form_page} at 1280 px"
                    )
            assert metrics["page"]["scrollWidth"] <= metrics["page"]["innerWidth"], (
                f"sideways scroll on {form_page} at {width} px"
            )
        finally:
            browser.close()
