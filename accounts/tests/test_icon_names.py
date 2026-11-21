"""Every icon name used in templates and Python must exist in the Bootstrap Icons sprite."""

import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders

SPRITE = "vendor/bootstrap-icons-1.11.3/bootstrap-icons.svg"
ICON_INCLUDE = re.compile(r'components/icon\.html"\s+with\s+[^%]*?\bname="([^"]+)"')
PY_ICON = re.compile(r'"icon"\s*:\s*"([^"]+)"')
BASE_DIRS = [Path("templates")]
BASE_DIRS += [p for p in Path().glob("*/templates") if p.is_dir()]


def _sprite_ids():
    path = finders.find(SPRITE)
    assert path, f"sprite not found: {SPRITE}"
    with open(path, encoding="utf-8") as fh:
        return set(re.findall(r'<symbol[^>]* id="([^"]+)"', fh.read()))


def _template_names():
    names = set()
    for base in BASE_DIRS:
        for html in base.rglob("*.html"):
            text = html.read_text(encoding="utf-8")
            for m in ICON_INCLUDE.finditer(text):
                names.add(m.group(1))
    return names


def _python_names():
    names = set()
    for py in [
        Path("accounts/dashboard_providers.py"),
        Path("player_characters/views/characters.py"),
    ]:
        if not py.exists():
            continue
        text = py.read_text(encoding="utf-8")
        for m in PY_ICON.finditer(text):
            names.add(m.group(1))
    return names


@pytest.mark.django_db
def test_all_icon_names_exist_in_sprite():
    """Fail when a template or Python literal names an icon the sprite lacks."""
    sprite = _sprite_ids()
    assert len(sprite) > 50, "sprite scan found no ids — regex may be broken"

    used = _template_names() | _python_names()
    assert len(used) > 50, "icon-name scan found no names — regex may be broken"

    missing = sorted(n for n in used if n not in sprite)
    assert not missing, f"Icon names missing from sprite: {missing}"
