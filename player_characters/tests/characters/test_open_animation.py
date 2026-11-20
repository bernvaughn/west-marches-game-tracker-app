"""Tests for the container opening animation (slice C).

Covers the result markup (live region, chest stage, reveal hooks) and the
static guards (reduced-motion CSS, no roll/fetch in the JS, base.html
includes).
"""

from pathlib import Path

import pytest
from django.urls import reverse

from items.models import Item
from items.tests.factories import add_slot, make_container
from ledger.services import Line, record

pytestmark = pytest.mark.django_db

STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static"


def open_url(club, character, item):
    return reverse(
        "characters:open_container",
        kwargs={"club_slug": club.slug, "pk": character.pk, "item_pk": item.pk},
    )


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


def award(character, item, quantity=1, actor=None):
    return record(character, "award", [Line(item=item, quantity=quantity)], actor=actor)


def fixed_container(club, name="Pack", item_name="Rope"):
    container = make_container(club, name=name)
    item = Item.objects.create(club=club, name=item_name, value_cp=1)
    add_slot(container, [(item, 1, 1, 1)], chance_pct=100)
    return container, item


def assert_no_raw_template_syntax(content):
    for token in ("{%", "%}", "{#", "#}", "{{", "}}"):
        assert token not in content, f"raw template syntax {token!r} in response"


# ---------------------------------------------------------------------------
# markup
# ---------------------------------------------------------------------------


def test_modal_result_has_live_region_chest_and_hooks(login, player, club, character, club_admin):
    container, rope = fixed_container(club)
    award(character, container, actor=club_admin)
    r = login(player).post(open_url(club, character, container), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    content = r.content.decode()
    assert 'role="status"' in content
    assert 'aria-live="polite"' in content
    assert "data-wm-live" in content
    assert 'class="wm-chest"' in content
    assert 'aria-hidden="true"' in content
    assert "data-wm-reveal" in content
    assert "data-wm-reveal-item" in content
    assert f"+1 {rope.name}" in content
    assert_no_raw_template_syntax(content)


def test_full_page_result_has_live_region_chest_and_hooks(
    login, player, club, character, club_admin
):
    container, rope = fixed_container(club)
    award(character, container, actor=club_admin)
    r = login(player).post(open_url(club, character, container))
    assert r.status_code == 200
    content = r.content.decode()
    assert 'role="status"' in content
    assert 'aria-live="polite"' in content
    assert "data-wm-live" in content
    assert 'class="wm-chest"' in content
    assert 'aria-hidden="true"' in content
    assert "data-wm-reveal" in content
    assert "data-wm-reveal-item" in content
    assert rope.name in content
    assert_no_raw_template_syntax(content)


# ---------------------------------------------------------------------------
# static guards
# ---------------------------------------------------------------------------


def test_static_files_exist():
    assert (STATIC_DIR / "css" / "areas" / "containers.css").is_file()
    assert (STATIC_DIR / "js" / "container_open.js").is_file()


def test_css_has_reduced_motion_block():
    css = (STATIC_DIR / "css" / "areas" / "containers.css").read_text()
    assert "prefers-reduced-motion: reduce" in css


def test_js_checks_reduced_motion_and_never_rolls():
    js = (STATIC_DIR / "js" / "container_open.js").read_text()
    assert "prefers-reduced-motion" in js
    assert "matchMedia" in js
    for token in ("fetch(", "XMLHttpRequest", "Math.random"):
        assert token not in js, f"JS must not roll or fetch: {token!r}"


def test_base_html_loads_both_includes():
    path = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "base.html"
    raw = path.read_text()
    assert "css/areas/containers.css" in raw
    assert "js/container_open.js" in raw
