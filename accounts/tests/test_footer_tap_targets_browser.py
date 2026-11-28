"""Browser regression test: footer links are 44 px tap targets below 576 px.

Covers:
- Every .wm-site-footer a is at least 44 px tall at 390 px (phone).
- The two feedback links ("Report a bug", "Suggest a feature") do not touch
  at 390 px: an 8 px gap or separate rows.
- No sideways scroll at 390 px.
- At 1280 px footer links stay compact (< 30 px tall), i.e. desktop is unchanged.

Run with: uv run pytest -m browser accounts/tests/test_footer_tap_targets_browser.py
"""

import pytest
from django.core.management import call_command
from django.test import Client

from accounts.models import User

DEMO_CLUB_SLUG = "demo"
DEMO_PLAYER_EMAIL = "alice@example.com"


def _seed_demo():
    call_command("seed_demo", verbosity=0)


def _session_id(email):
    """Log in server-side and return the session cookie for Playwright."""
    client = Client()
    user = User.objects.get(email=email)
    client.force_login(user)
    return client.cookies["sessionid"].value


def _link_rects(page):
    """Return bounding rects for every footer link."""
    return page.evaluate(
        "() => Array.from(document.querySelectorAll('.wm-site-footer a')).map(a => {"
        "  const r = a.getBoundingClientRect();"
        "  return {text: (a.textContent || '').trim(), left: r.left, right: r.right,"
        "          top: r.top, bottom: r.bottom, height: r.height};"
        "})"
    )


def _no_sideways_scroll(page):
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


@pytest.mark.browser
@pytest.mark.django_db
@pytest.mark.parametrize("width", [390, 1280])
def test_footer_tap_targets(transactional_db, live_server, width):
    """Footer links are 44 px tall on phone and compact on desktop."""
    _seed_demo()

    from playwright.sync_api import sync_playwright

    session_id = _session_id(DEMO_PLAYER_EMAIL)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": "sessionid", "value": session_id, "url": live_server.url}])
        page = context.new_page()
        try:
            for path in ("/", f"/c/{DEMO_CLUB_SLUG}/"):
                page.goto(f"{live_server.url}{path}", wait_until="networkidle")
                rects = _link_rects(page)
                assert rects, f"no footer links found at {path}"

                for r in rects:
                    if width == 390:
                        assert r["height"] >= 44, (
                            f"footer link {r['text']!r} is {r['height']}px tall at {path}"
                        )
                    else:
                        assert r["height"] < 30, (
                            f"desktop footer link {r['text']!r} is {r['height']}px tall at {path}"
                        )

                if width == 390:
                    # No sideways scroll on the phone.
                    assert _no_sideways_scroll(page), f"sideways scroll at {path}"

                    # The two feedback links must not touch each other.
                    fb = [r for r in rects if r["text"] in ("Report a bug", "Suggest a feature")]
                    if len(fb) == 2:
                        a, b = sorted(fb, key=lambda r: r["left"])
                        same_row = abs(a["top"] - b["top"]) < 4
                        if same_row:
                            # a is left of b in DOM/flex order; the gap between them.
                            gap = b["left"] - a["right"]
                            assert gap >= 8, f"feedback links touch at {path}: gap {gap}px"
                        else:
                            # Separate rows: they cannot touch.
                            assert (
                                abs(a["bottom"] - b["top"]) >= 4 or abs(b["bottom"] - a["top"]) >= 4
                            )
        finally:
            browser.close()
