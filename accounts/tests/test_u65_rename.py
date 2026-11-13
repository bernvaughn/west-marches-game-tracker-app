from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from agent_access.mcp.server import server
from map.xp import DEFAULT_XP_TABLE

pytestmark = [pytest.mark.django_db, pytest.mark.story("U65")]

NAME = "Downtime Market"
OLD = "West Marches"
TAGLINE = "Spend your loot between sessions."


def test_club_home_title_and_menu(login, club, player):
    body = login(player).get(reverse("club_home", args=[club.slug])).content.decode()
    assert NAME in body[: body.index("</title>")]
    assert f'id="site-menu-title">{NAME}<' in body
    assert OLD not in body


def test_login_page_name_and_tagline():
    body = Client().get(reverse("login")).content.decode()
    assert NAME in body and TAGLINE in body
    assert OLD not in body


def test_logged_out_and_password_pages(login, player):
    client = login(player)
    pages = [
        client.get(reverse("password_change")),
        client.get(reverse("password_change_done")),
        client.post(reverse("logout"), follow=True),
    ]
    for resp in pages:
        body = resp.content.decode()
        assert NAME in body and OLD not in body


def test_design_reference(login, site_admin):
    body = login(site_admin).get(reverse("site_design")).content.decode()
    assert f"Design system - {NAME}" in body
    assert OLD not in body


def test_one_setting_drives_templates(settings):
    settings.APP_NAME = "Test Name"
    body = Client().get(reverse("login")).content.decode()
    assert "Test Name" in body and NAME not in body


def test_mcp_instructions():
    assert NAME in server.instructions and OLD not in server.instructions


def test_oauth_names(client):
    assert NAME in settings.OAUTH2_PROVIDER["SCOPES"]["mcp"]
    assert NAME in settings.OAUTH2_PROVIDER["OAUTH2_PROTECTED_RESOURCE_NAME"]
    assert OLD not in str(settings.OAUTH2_PROVIDER)


def test_project_description_and_readme():
    base = Path(settings.BASE_DIR)
    desc = [
        ln
        for ln in (base / "pyproject.toml").read_text().splitlines()
        if ln.startswith("description")
    ]
    assert NAME in desc[0]
    assert NAME in (base / "README.md").read_text()


def test_xp_table_unchanged():
    assert DEFAULT_XP_TABLE == [
        ("1-2", 75, 225),
        ("3-4", 200, 400),
        ("5-6", 2825, 8475),
        ("7-8", 5000, 15000),
        ("9-10", 7500, 22500),
        ("11-12", 9000, 27000),
        ("13-14", 10000, 30000),
        ("15-16", 13750, 41250),
        ("17-18", 17500, 52000),
        ("19-20", 22500, 67500),
    ]


def test_no_template_names_app_west_marches():
    base = Path(settings.BASE_DIR)
    hits = [
        str(p)
        for p in base.rglob("templates/**/*.html")
        if ".venv" not in p.parts and OLD in p.read_text()
    ]
    assert hits == []
