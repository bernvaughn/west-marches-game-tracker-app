"""Smoke test: every page in the screenshot page list returns 200. No browser.
Browser tests: no OVERFLOW at 390px, no CLIPPED input.form-control at 390px.
"""

import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

import pytest
from django.core.management import call_command
from django.urls import get_resolver, resolve

from accounts.models import Membership, User
from scripts.screenshot_pages import (
    EXCLUDED,
    MODAL_ACTIONS,
    MODAL_SELECTORS,
    PAGES,
    ROLES,
    demo_objects,
    extra_fixtures,
)


@pytest.fixture
def demo(db):
    call_command("seed_demo", verbosity=0)
    extra_fixtures()
    return demo_objects()


def test_names_are_unique():
    names = [p.name for p in PAGES]
    assert len(names) == len(set(names))


def test_has_required_pages():
    names = {p.name for p in PAGES}
    assert {
        "shops-buy-modal",
        "map-tile-modal",
        "inbox-grant-modal",
        "topbar-menu-open",
        "shops-sell-junk-modal",
        "shops-sell-modal",
        "characters-junk-modal",
        "inbox-give-items-modal",
    } <= names


def _url_names(resolver=None, ns=""):
    """Every named non-admin URL pattern, as `namespace:name`."""
    resolver = resolver or get_resolver()
    out = set()
    for p in resolver.url_patterns:
        if hasattr(p, "url_patterns"):
            if p.namespace == "admin":
                continue
            out |= _url_names(p, f"{ns}{p.namespace}:" if p.namespace else ns)
        elif p.name:
            out.add(f"{ns}{p.name}")
    return out


def _covered(demo):
    names = set()
    for p in PAGES:
        for url in (p.url, p.modal_url):
            if url:
                names.add(resolve(urlsplit(url(demo)).path).view_name)
    return names


def test_every_get_url_is_covered_or_excluded(demo):
    missing = _url_names() - _covered(demo) - EXCLUDED.keys()
    assert not missing, f"Add to PAGES, or to EXCLUDED with a reason: {sorted(missing)}"


def test_excluded_is_clean(demo):
    names = _url_names()
    for name, reason in EXCLUDED.items():
        assert reason.strip() and "\n" not in reason, name
        assert name in names, f"stale EXCLUDED entry {name}"
    assert not EXCLUDED.keys() & _covered(demo)


def test_modal_actions_have_selectors():
    actions = {p.action for p in PAGES} - {None, "menu_open"}
    assert actions <= MODAL_ACTIONS
    assert set(MODAL_SELECTORS) <= actions


def test_extra_fixtures_idempotent(db):
    from downtime.models import DowntimePointRequest, DowntimeResult
    from player_characters.models import JunkMark, Trade

    call_command("seed_demo", verbosity=0)
    assert not User.objects.filter(email__in=["gm-only@example.com", "clubadmin@example.com"])
    extra_fixtures()
    counts = lambda: (  # noqa: E731
        User.objects.count(),
        Membership.objects.count(),
        JunkMark.objects.count(),
        DowntimePointRequest.objects.count(),
        DowntimeResult.objects.count(),
        Trade.objects.count(),
    )
    first = counts()
    extra_fixtures()
    assert counts() == first
    gm_only = Membership.objects.get(user__email="gm-only@example.com")
    assert gm_only.is_game_master and not gm_only.is_club_admin
    admin = Membership.objects.get(user__email="clubadmin@example.com")
    assert admin.is_club_admin and not admin.is_game_master


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
@pytest.mark.slow
def test_page_returns_200(client, demo, page):
    email = ROLES[page.role]
    if email:
        client.force_login(User.objects.get(email=email))
    # Follow redirect for players on club_home (they go to dashboard)
    # Pages that use club_home for players: club-home-*, topbar-menu-open
    follow = page.role in ("alice", "bob") and (
        page.name.startswith("club-home-") or page.name == "topbar-menu-open"
    )
    resp = client.get(page.url(demo), follow=follow)
    assert resp.status_code == 200
    if page.modal_url:
        resp = client.get(page.modal_url(demo), HTTP_HX_REQUEST="true")
        assert resp.status_code == 200


# ---- Browser guard-rail tests (run with pytest -m browser) ----

# Pages that are allowed to have OVERFLOW at 390px with a reason.
OVERFLOW_ALLOWLIST = {
    # Print pages are fixed by scaling (N-17), but the tool may still flag them
    "characters-print-items",
    "characters-print-item-full",
    "characters-print-item-grid",
    "characters-slips-print-aria",
    "characters-print-item-choose",
    "characters-print-items-per-item",
    "characters-print-item-grid-per-item",
}


# Pages that are allowed to have CLIPPED input.form-control at 390px with a reason.
CLIPPED_INPUT_ALLOWLIST = {
    "agent-batch-detail",
    "agent-proposed-item-detail",
}


def _run_screenshots_audit(pages_glob="*", extra_args=None):
    """Run screenshots.py --audit as a subprocess and return stdout."""
    ROOT = __file__.replace("test_screenshot_pages.py", "")
    cmd = [
        sys.executable, "-m", "uv", "run", "python", "scripts/screenshots.py",
        "--audit", "--out", tempfile.mkdtemp(prefix="audit-shots-"),
    ]
    if pages_glob != "*":
        cmd.extend(["--pages", pages_glob])
    if extra_args:
        cmd.extend(extra_args)
    
    env = {
        **__import__("os").environ,
        "PLAYWRIGHT_BROWSERS_PATH": "/tmp/vfy/pw",
        "LD_LIBRARY_PATH": "/tmp/vfy/libroot/usr/lib/x86_64-linux-gnu",
    }
    
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    return result.stdout, result.stderr, result.returncode


@pytest.mark.browser
def test_no_overflow_at_390px():
    """No page has horizontal overflow at 390px (B-01, B-04).
    
    Runs screenshots.py --audit and fails on any OVERFLOW line at 390px.
    """
    stdout, stderr, returncode = _run_screenshots_audit()
    
    # Parse OVERFLOW lines
    overflow_pages = []
    for line in stdout.splitlines():
        if line.startswith("OVERFLOW "):
            page_name = line.split("OVERFLOW ")[1].split("@")[0]
            if page_name not in OVERFLOW_ALLOWLIST:
                overflow_pages.append(page_name)
    
    assert not overflow_pages, f"OVERFLOW at 390px on pages: {', '.join(overflow_pages)}"


@pytest.mark.browser
def test_no_clipped_input_form_control_at_390px():
    """No page has CLIPPED input.form-control at 390px (B-45, B-41).
    
    Runs screenshots.py --audit and fails on any CLIPPED line naming input.form-control.
    """
    stdout, stderr, returncode = _run_screenshots_audit()
    
    # Parse CLIPPED lines that mention input.form-control
    clipped_pages = []
    for line in stdout.splitlines():
        if line.startswith("CLIPPED ") and "input.form-control" in line:
            page_name = line.split("CLIPPED ")[1].split("@")[0].split(" ")[0]
            if page_name not in CLIPPED_INPUT_ALLOWLIST:
                clipped_pages.append(page_name)
    
    msg = f"CLIPPED input.form-control at 390px on pages: {', '.join(clipped_pages)}"
    assert not clipped_pages, msg


@pytest.mark.browser
def test_agent_batch_detail_clipped_check():
    """Check the two open CLIPPED lines on agent-batch-detail and agent-proposed-item-detail.
    
    These are tracked in the audit as open checks. Fix them if they are real.
    """
    stdout, stderr, returncode = _run_screenshots_audit(
        pages_glob="agent-batch-detail,agent-proposed-item-detail"
    )
    
    # Check for any CLIPPED or OVERFLOW on these specific pages
    issues = []
    for line in stdout.splitlines():
        if line.startswith("CLIPPED ") or line.startswith("OVERFLOW "):
            if "agent-batch-detail" in line or "agent-proposed-item-detail" in line:
                issues.append(line)
    
    # If there are issues, they need to be fixed in the agent templates
    if issues:
        pytest.fail(f"Agent pages have CLIPPED/OVERFLOW issues: {'; '.join(issues)}")