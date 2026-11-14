from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from config import plans as plan_config

NOTE = "Built with CodeHerder"


@pytest.mark.story("U94")
@pytest.mark.django_db
@pytest.mark.parametrize("name", ["about", "plans"])
def test_pages_public(name):
    assert Client().get(reverse(name)).status_code == 200


@pytest.mark.story("U94")
@pytest.mark.django_db
def test_plans_come_from_module(monkeypatch):
    monkeypatch.setattr(
        plan_config,
        "PLANS",
        [
            {
                "key": "x",
                "name": "Sentinel Plan",
                "price": "P",
                "summary": "S",
                "limits": [("L", "V")],
            }
        ],
    )
    assert "Sentinel Plan" in Client().get(reverse("plans")).content.decode()


@pytest.mark.story("U94")
@pytest.mark.django_db
def test_default_plans_marked_tbd():
    body = Client().get(reverse("plans")).content.decode()
    assert "To be decided" in body
    assert [p["key"] for p in plan_config.PLANS] == ["free", "subscription"]
    for p in plan_config.PLANS:
        assert p["name"] in body


@pytest.mark.story("U94")
@pytest.mark.django_db
def test_login_links_to_pages():
    body = Client().get(reverse("login")).content.decode()
    assert reverse("about") in body and reverse("plans") in body


@pytest.mark.story("U94")
def test_no_payment_code():
    root = Path(settings.BASE_DIR)
    for rel in [
        "config/plans.py",
        "accounts/views/public.py",
        "templates/public/about.html",
        "templates/public/plans.html",
    ]:
        text = (root / rel).read_text().lower()
        for bad in ("stripe", "paypal", "checkout", "<form", "card number"):
            assert bad not in text, (rel, bad)
    assert not [a for a in settings.INSTALLED_APPS if "stripe" in a or "paypal" in a]


@pytest.mark.story("U95")
@pytest.mark.django_db
@pytest.mark.parametrize("name", ["about", "plans", "login", "logout"])
def test_footer_on_public_pages(name, player, login):
    if name == "logout":
        body = login(player).post(reverse("logout"), follow=True).content.decode()
    else:
        body = Client().get(reverse(name)).content.decode()
    assert NOTE in body
    assert "<a" not in body.split(NOTE)[0].rsplit("<p", 1)[1]


@pytest.mark.story("U95")
def test_footer_absent_on_club_pages(club, player, login):
    c = login(player)
    for url in (reverse("club_home", args=[club.slug]), reverse("items:index", args=[club.slug])):
        r = c.get(url)
        assert r.status_code == 200
        assert NOTE not in r.content.decode()


@pytest.mark.story("U94")
def test_pages_show_no_club_data(club, other_club, player, login):
    c = login(player)
    for name in ("about", "plans"):
        main = c.get(reverse(name)).content.decode().split("<main", 1)[1].split("</main>")[0]
        assert club.name not in main and other_club.name not in main
