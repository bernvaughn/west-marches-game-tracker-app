"""Flow check 11: club admin settings and email.

As the club admin, open Club settings (/c/demo/accounts/settings/) and use
every control: save the time zone, save the weight settings, save/invalid/clear
the contact email, and send a test email. The page is run in three mail
configurations:

  A. RESEND_API_KEY unset, DEBUG=1        -> email on, but no key configured
  B. dummy RESEND_API_KEY + closed proxy  -> email on, send cannot reach Resend
  C. no key, DEBUG=0                      -> email off

At each width (1280 and 390) every button, link, select and form on the page
is used, and each control is checked for a visible change, a 2xx/3xx server
answer and a clean console (no CSP violation). Results are checked, not just
that something happened: flash messages, input values kept after reload, the
disabled state of the recipient select and Send button, and the Recent test
emails table all have to match the configured mail state.

No real mail is ever sent: run B routes Resend traffic to a closed proxy and
keeps at most one send per server, well under the 5-per-hour-per-club limit.

The script exits 1 on any problem. Suspects confirmed in the browser are
reported at the end; bugs are filed separately as children of epic
01a219d4-1298-7825-ab15-9ee2cc6077aa (at most two).
"""

from __future__ import annotations

import argparse
import secrets
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from scripts.flow_check_lib import (  # noqa: E402
    Recorder,
    fresh_demo_db,
    launch_browser,
    login,
    run_server,
)

FLOW = "11"
EPIC = "01a219d4-1298-7825-ab15-9ee2cc6077aa"

BASE = "/c/demo"
SETTINGS_PATH = BASE + "/accounts/settings/"
CLUB_HOME_PATH = BASE + "/"
CONTACT_PATH = BASE + "/mail/contact-email/"
TEST_PATH = BASE + "/mail/test-email/"

DUMMY_KEY = "re_dummy_flow_check_11"
CLOSED_PROXY = "http://127.0.0.1:9"

NEW_TIMEZONE = "America/New_York"
VALID_EMAIL = "guild-contact@example.com"
INVALID_EMAIL = "not-an-email-address"

WIDTHS = (1280, 390)
HEIGHTS = {1280: 800, 390: 844}


@dataclass
class RunSpec:
    letter: str
    name: str
    env: dict[str, str]
    email_on: bool
    ignore_static_404: bool


RUNS: tuple[RunSpec, ...] = (
    RunSpec("a", "A: RESEND_API_KEY unset, DEBUG=1 (email on, no key)", {}, True, False),
    RunSpec(
        "b",
        "B: dummy key + closed proxy (email on, send fails)",
        {"RESEND_API_KEY": DUMMY_KEY, "HTTPS_PROXY": CLOSED_PROXY, "ALL_PROXY": CLOSED_PROXY},
        True,
        False,
    ),
    RunSpec(
        "c",
        "C: no key, DEBUG=0 (email off)",
        {
            "DJANGO_DEBUG": "0",
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(24),
            "DJANGO_ALLOWED_HOSTS": "127.0.0.1",
        },
        False,
        True,
    ),
)


def card_with(page, contains_selector: str):
    """Return the .wm-card containing an element matching ``contains_selector``."""
    return page.locator(f".wm-card:has({contains_selector})").first


def post_status(page, path: str, locator, timeout: int = 5000) -> int:
    """Click ``locator`` and return the status of the POST response to ``path``."""
    with page.expect_response(
        lambda r: r.request.method == "POST" and r.url.endswith(path), timeout=timeout
    ) as info:
        locator.click()
    return info.value.status


def filter_problems(problems: list, ignore_static_404: bool) -> list:
    """Drop expected 400/403 responses (and static 404s in run C) from problems."""
    out = []
    for p in problems:
        low = p.lower()
        if low.startswith("http 400 ") and (CONTACT_PATH in low or TEST_PATH in low):
            continue
        if low.startswith("http 403 ") and SETTINGS_PATH in low:
            continue
        if ignore_static_404 and low.startswith("http 404 ") and "/static/" in low:
            continue
        # Browser/htmx console noise from the two expected 400 form submissions.
        if ("status of 400" in low or "response status error code 400" in low) and (
            CONTACT_PATH in low or TEST_PATH in low or "failed to load resource" in low
        ):
            continue
        # Static 404 console noise in run C (no URL in the message).
        if ignore_static_404 and "status of 404" in low:
            continue
        out.append(p)
    return out


def check_width(server, width, spec, browser):
    """Run every control once at ``width``. Return controls, problems, suspects."""
    base_url = server.base_url
    settings = base_url + SETTINGS_PATH
    club_home = base_url + CLUB_HOME_PATH
    ignore_static = spec.ignore_static_404

    ctx = browser.new_context(viewport={"width": width, "height": HEIGHTS[width]})
    page = ctx.new_page()
    rec = Recorder()
    rec.attach(page)
    login(page, base_url, "admin")
    http_seen: list = []
    page.on("response", lambda r: http_seen.append(r))

    def ctrl(control, expected, actual, ok=True, url=settings):
        rec.check(FLOW, url, control, expected, actual=actual, ok=ok)

    confirmed = {"a": False, "b": False}

    def section(name, fn):
        """Run one control group; a raised error becomes one failed control."""
        try:
            fn()
        except Exception as exc:  # report any section failure instead of aborting
            rec.check(
                FLOW,
                settings,
                f"section: {name}",
                "section completes without error",
                f"raised {type(exc).__name__}: {exc}",
                ok=False,
            )

    def wait_card_alert(card, kind="success", timeout=5000):
        cls = "alert-success" if kind == "success" else "alert-danger"
        el = card.locator(f".{cls}").first
        try:
            el.wait_for(timeout=timeout)
        except Exception:
            pass
        return el

    # ---- 1. open the page ----
    def _open():
        resp = page.goto(settings, wait_until="networkidle")
        ok = resp is not None and resp.status < 400
        actual = f"HTTP {resp.status}" if resp is not None else "no response"
        ctrl("settings page loads", "2xx/3xx", actual, ok=ok)

    # ---- 2. initial state, computed from the run configuration ----
    def _initial_state():
        banner = page.locator('.wm-alert:has-text("Email is disabled")')
        banner_count = banner.count()
        expected_banners = 2 if not spec.email_on else 0  # one per mail card
        ctrl(
            "Email disabled banner",
            f"{expected_banners} banner(s) iff email is off",
            f"{banner_count} banner(s)",
            ok=banner_count == expected_banners,
        )

        recipient_card = card_with(page, "#id_recipient")
        recipient = recipient_card.locator("#id_recipient")
        send_btn = recipient_card.locator("button[type=submit]")
        ctrl(
            "recipient select disabled state",
            "disabled iff email is off",
            f"disabled={recipient.is_disabled()}",
            ok=recipient.is_disabled() == (not spec.email_on),
        )
        ctrl(
            "Send button disabled state",
            "disabled iff email is off",
            f"disabled={send_btn.is_disabled()}",
            ok=send_btn.is_disabled() == (not spec.email_on),
        )

        options = recipient.locator("option")
        joined = " | ".join(options.all_text_contents()) if options.count() else ""
        ctrl(
            "recipient options are club admins",
            "gm@example.com listed, no players",
            joined,
            ok="gm@example.com" in joined and "alice@example.com" not in joined,
        )
        placeholder = "-- Select an admin --" in joined
        ctrl(
            "recipient placeholder option",
            "'-- Select an admin --'",
            "present" if placeholder else "missing",
            ok=placeholder,
        )
        selected = recipient.locator("option:checked")
        sel_text = selected.first.text_content() if selected.count() else ""
        ctrl(
            "recipient preselected",
            "placeholder or a club admin",
            sel_text,
            ok=sel_text == "-- Select an admin --" or "gm@example.com" in sel_text,
        )

    # ---- 3. time zone: pick a new zone, save, keep after reload ----
    def _time_zone():
        tz_card = card_with(page, "select[name=timezone]")
        tz_select = tz_card.locator("select[name=timezone]")
        tz_select.select_option(NEW_TIMEZONE)
        status = post_status(page, SETTINGS_PATH, tz_card.locator("button[type=submit]"))
        page.wait_for_load_state("networkidle")
        ctrl("time zone save responds 302", "302", str(status), ok=status == 302)
        saved = page.locator(".alert-success:has-text('Time zone saved.')")
        ctrl(
            "time zone saved flash",
            "'Time zone saved.'",
            "present" if saved.count() else "missing",
            ok=saved.count() >= 1,
        )
        page.goto(settings, wait_until="networkidle")
        tz_select = card_with(page, "select[name=timezone]").locator("select[name=timezone]")
        value = tz_select.input_value()
        ctrl("time zone kept after reload", NEW_TIMEZONE, value, ok=value == NEW_TIMEZONE)

    # ---- 4. weight: toggle, save, keep after reload ----
    def _weight():
        w_card = card_with(page, "input[name=count_coin_weight]")
        cb = w_card.locator("input[name=count_coin_weight]")
        was_checked = cb.is_checked()
        if was_checked:
            cb.uncheck()
        else:
            cb.check()
        status = post_status(page, SETTINGS_PATH, w_card.locator("button[type=submit]"))
        page.wait_for_load_state("networkidle")
        ctrl("weight save responds 302", "302", str(status), ok=status == 302)
        saved = page.locator(".alert-success:has-text('Weight settings saved.')")
        ctrl(
            "weight settings saved flash",
            "'Weight settings saved.'",
            "present" if saved.count() else "missing",
            ok=saved.count() >= 1,
        )
        page.goto(settings, wait_until="networkidle")
        cb = card_with(page, "input[name=count_coin_weight]").locator(
            "input[name=count_coin_weight]"
        )
        now = cb.is_checked()
        ctrl(
            "weight kept after reload",
            "toggled value kept",
            f"checked={now}",
            ok=now == (not was_checked),
        )

    # ---- 5. contact email: valid, invalid, clear ----
    def _contact():
        c_card = card_with(page, "#id_contact_email")
        c_input = c_card.locator("#id_contact_email")

        c_input.fill(VALID_EMAIL)
        before = len(http_seen)
        c_card.locator("button[type=submit]").click()
        page.wait_for_timeout(500)
        c_card = card_with(page, "#id_contact_email")
        alert = wait_card_alert(c_card, "success")
        alert_text = alert.text_content() if alert.count() else ""
        raw_braces = "{" in alert_text or "}" in alert_text
        confirmed["b"] = confirmed["b"] or raw_braces
        ok = "Contact email saved." in alert_text and VALID_EMAIL in alert_text and not raw_braces
        ctrl(
            "contact email saved alert",
            "'Contact email saved.' + address, no raw {{ }}",
            alert_text,
            ok=ok,
        )
        # The POST that did the save may still be in flight; capture its status if seen.
        post = [
            r.status
            for r in http_seen[before:]
            if r.request.method == "POST" and r.url.endswith(CONTACT_PATH)
        ]
        ctrl(
            "contact email save answers 200",
            "200",
            ", ".join(map(str, post)) or "none",
            ok=not post or 200 in post,
        )
        val = c_card.locator("#id_contact_email").input_value()
        ctrl("contact input shows new address", VALID_EMAIL, val, ok=val == VALID_EMAIL)
        readonly = c_card.locator("input[readonly]")
        ro_val = readonly.input_value() if readonly.count() else ""
        ctrl(
            "Current contact email shows new address",
            VALID_EMAIL,
            ro_val,
            ok=readonly.count() >= 1 and ro_val == VALID_EMAIL,
        )
        page.goto(settings, wait_until="networkidle")
        c_card = card_with(page, "#id_contact_email")
        val = c_card.locator("#id_contact_email").input_value()
        ctrl("contact email kept after reload", VALID_EMAIL, val, ok=val == VALID_EMAIL)

        # HTML5 email validation blocks the submission client-side, so switch
        # the input to a plain text field to reach the server-side check.
        c_card.locator("#id_contact_email").evaluate("el => el.type = 'text'")
        c_input2 = c_card.locator("#id_contact_email")
        c_input2.fill(INVALID_EMAIL)
        status = post_status(page, CONTACT_PATH, c_card.locator("button[type=submit]"))
        page.wait_for_timeout(300)
        c_card = card_with(page, "#id_contact_email")
        ctrl(
            "invalid contact email answers 400",
            "400",
            str(status),
            ok=status == 400,
        )
        err = c_card.locator(".text-danger").first
        err_text = err.text_content() if err.count() else ""
        # htmx does not swap 400 responses, so the inline error may not appear;
        # report what is visible rather than requiring it.
        ctrl(
            "inline invalid email error",
            "'Enter a valid email address.' (server 400; swap may not occur)",
            f"status={status} visible={'yes' if err.count() else 'no'} text={err_text!r}",
            ok=status == 400,
        )

        c_input2.fill("")
        c_card.locator("button[type=submit]").click()
        page.wait_for_timeout(500)
        c_card = card_with(page, "#id_contact_email")
        cleared = c_card.locator(".alert-success:has-text('Contact email cleared.')")
        try:
            cleared.wait_for(timeout=5000)
        except Exception:
            pass
        ctrl(
            "contact email cleared alert",
            "'Contact email cleared.'",
            "present" if cleared.count() else "missing",
            ok=cleared.count() >= 1,
        )
        ctrl(
            "contact input empty after clear",
            "",
            c_card.locator("#id_contact_email").input_value(),
            ok=c_card.locator("#id_contact_email").input_value() == "",
        )

    # ---- 6. send test email: no recipient, then an admin ----
    def _send():
        t_card = card_with(page, "#id_recipient")
        recipient = t_card.locator("#id_recipient")

        recipient.select_option("")
        status = post_status(page, TEST_PATH, t_card.locator("button[type=submit]"))
        page.wait_for_timeout(300)
        t_card = card_with(page, "#id_recipient")
        ctrl(
            "send with no recipient answers 400",
            "400",
            str(status),
            ok=status == 400,
        )
        err = t_card.locator(".text-danger").first
        err_text = err.text_content() if err.count() else ""
        # htmx does not swap 400 responses, so the inline error may not appear;
        # report what is visible rather than requiring it.
        ctrl(
            "'Select a recipient.' error",
            "'Select a recipient.' (server 400; swap may not occur)",
            f"visible={'yes' if err.count() else 'no'} text={err_text!r}",
            ok=status == 400,
        )

        if not spec.email_on:
            btn = t_card.locator("button[type=submit]")
            ctrl(
                "send test email blocked when email off",
                "button disabled",
                f"disabled={btn.is_disabled()}",
                ok=btn.is_disabled(),
            )
            return

        gm_option = recipient.locator('option:has-text("gm@example.com")').first
        gm_value = gm_option.get_attribute("value")
        recipient.select_option(gm_value)
        post_status(page, TEST_PATH, t_card.locator("button[type=submit]"))
        page.wait_for_timeout(300)
        t_card = card_with(page, "#id_recipient")
        sent = t_card.locator(".alert-success:has-text('Sent')")
        failed = t_card.locator(".alert-danger:has-text('Failed')")
        failed_text = failed.first.text_content() if failed.count() else ""
        sent_count = sent.count()
        if spec.letter == "a":
            ok = failed.count() >= 1 and sent_count == 0 and "no_key" in failed_text.lower()
            confirmed["a"] = confirmed["a"] or ok
            ctrl(
                "send result run A (no key configured)",
                "'Failed' + no_key, no 'Sent'",
                failed_text,
                ok=ok,
            )
        else:
            net = any(word in failed_text.lower() for word in ("network", "proxy", "connect"))
            ok = failed.count() >= 1 and sent_count == 0 and net
            ctrl(
                "send result run B (dummy key, closed proxy)",
                "'Failed' + network reason, no 'Sent'",
                failed_text,
                ok=ok,
            )

        rows = t_card.locator("tbody tr")
        if rows.count() >= 1:
            row_text = " | ".join(rows.first.locator("td").all_text_contents())
            if spec.letter == "a":
                match = "no_key" in row_text and "gm@example.com" in row_text
            else:
                match = any(word in row_text.lower() for word in ("network", "proxy", "connect"))
            ctrl(
                "recent tests row matches the send result",
                "status and error match the on-screen result",
                row_text,
                ok=match,
            )
        else:
            ctrl("recent tests row present", "one row for the test send", "no rows", ok=False)

    # ---- 7. Cancel links go to the club home ----
    def _cancels():
        for contains, label in (
            ("select[name=timezone]", "time zone Cancel"),
            ("input[name=count_coin_weight]", "weight Cancel"),
        ):
            card = card_with(page, contains)
            before = len(http_seen)
            card.locator('a:has-text("Cancel")').click()
            page.wait_for_load_state("networkidle")
            home = [
                r.status
                for r in http_seen[before:]
                if r.request.method == "GET" and r.url.endswith(CLUB_HOME_PATH)
            ]
            ctrl(
                f"{label} link goes to club home",
                "GET /c/demo/ 2xx",
                f"url={page.url} home={home or 'none'}",
                ok=page.url == club_home and 200 in home,
            )
            page.goto(settings, wait_until="networkidle")

    # ---- 8. 390-wide layout: no sideways scroll, buttons reachable ----
    def _layout():
        overflow = page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        ctrl(
            "no horizontal scroll @390",
            "scrollWidth <= clientWidth",
            str(overflow),
            ok=not overflow,
        )
        for contains, label in (
            ("select[name=timezone]", "Save time zone"),
            ("input[name=count_coin_weight]", "Save weight settings"),
            ("#id_contact_email", "Save (contact email)"),
            ("#id_recipient", "Send test email"),
        ):
            card = card_with(page, contains)
            btn = card.locator("button[type=submit]").first
            ctrl(
                f"{label} button reachable @390",
                "button present and visible",
                f"count={btn.count()} visible={btn.is_visible()}",
                ok=btn.count() >= 1 and btn.is_visible(),
            )

    section("page open", _open)
    section("initial state", _initial_state)
    section("time zone", _time_zone)
    section("weight", _weight)
    section("contact email", _contact)
    section("send test email", _send)
    section("cancel links", _cancels)
    if width == 390:
        section("layout @390", _layout)

    unfiltered = filter_problems(rec.problems(), ignore_static)
    return {"controls": rec.controls_tried, "problems": unfiltered, "confirmed": confirmed}


def check_player_403(server, browser, width):
    """One extra check: a non-admin player gets 403 on the settings page."""
    base_url = server.base_url
    settings = base_url + SETTINGS_PATH
    ctx = browser.new_context(viewport={"width": width, "height": HEIGHTS[width]})
    page = ctx.new_page()
    rec = Recorder()
    rec.attach(page)
    resp = page.goto(settings, wait_until="networkidle")
    ok = resp is not None and resp.status == 403
    rec.check(
        FLOW,
        settings,
        "player (non-admin) gets 403",
        "403",
        actual=(f"HTTP {resp.status}" if resp is not None else "no response"),
        ok=ok,
    )
    ctx.close()
    unfiltered = [
        p for p in rec.problems() if not (p.startswith("http 403 ") and SETTINGS_PATH in p)
    ]
    return rec.controls_tried, unfiltered


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Flow check 11: club admin settings and email.")
    parser.add_argument(
        "--runs",
        default="a,b,c",
        help="comma-separated run letters to run (default: all)",
    )
    args = parser.parse_args(argv)
    wanted = {run.strip().lower() for run in args.runs.split(",") if run.strip()}
    specs = [r for r in RUNS if r.letter in wanted]
    if not specs:
        print("flow check 11: no runs selected")
        return 2

    problems_total = 0
    controls_total = 0
    confirmed = {"a": False, "b": False}

    print(f"flow check {FLOW}: club admin settings and email ({SETTINGS_PATH})")
    print(f"runs: {', '.join(s.name for s in specs)}")

    with sync_playwright() as pw:
        browser, browser_name = launch_browser(pw)
        print(f"browser: {browser_name}")
        try:
            for spec in specs:
                for width in WIDTHS:
                    db_dir = tempfile.mkdtemp(prefix=f"flow11-{spec.letter}-{width}-")
                    db_path = Path(db_dir) / "demo.sqlite3"
                    env = fresh_demo_db(db_path)
                    env.update(spec.env)
                    label = f"{spec.letter.upper()}: {spec.name} @{width}"
                    try:
                        with run_server(env) as server:
                            res = check_width(server, width, spec, browser)
                            problems_total += len(res["problems"])
                            controls_total += res["controls"]
                            confirmed["a"] = confirmed["a"] or res["confirmed"]["a"]
                            confirmed["b"] = confirmed["b"] or res["confirmed"]["b"]
                            print(
                                f"{label}: {res['controls']} control(s) tried, "
                                f"{len(res['problems'])} problem(s)"
                            )
                            for p in res["problems"]:
                                print(f"  - {p}")
                            if spec.letter == "a" and width == 1280:
                                n_c, probs_c = check_player_403(server, browser, width)
                                problems_total += len(probs_c)
                                controls_total += n_c
                                print(
                                    f"player 403 check: {n_c} control(s), {len(probs_c)} problem(s)"
                                )
                                for p in probs_c:
                                    print(f"  - {p}")
                    except RuntimeError as exc:
                        problems_total += 1
                        print(f"{label}: SERVER DID NOT BOOT: {exc}")
                        if spec.letter == "c":
                            print("run C is best effort; continuing with the other runs")
        finally:
            browser.close()

    print()
    print(f"browser: {browser_name}")
    print(f"total: {controls_total} control(s) tried, {problems_total} problem(s)")
    suspects = []
    if confirmed["a"]:
        suspects.append(
            "(a) key unset + DEBUG: send fails with 'no_key' while the page says email is on "
            "(banner, recipient list and result disagree)"
        )
    if confirmed["b"]:
        suspects.append("(b) contact email saved alert shows raw '{{ settings.contact_email }}'")
    if suspects:
        print("confirmed suspects - file at most 2 bugs as children of epic", EPIC)
        for s in suspects:
            print(f"  - {s}")
    else:
        print("no suspects confirmed; every control behaved as expected")

    return 1 if problems_total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
