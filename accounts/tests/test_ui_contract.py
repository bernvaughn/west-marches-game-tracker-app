"""U84 S1: flash message position and the one app-wide date format."""

import datetime

import pytest
from django.contrib.messages.storage.base import Message
from django.template import Context, Template
from django.urls import reverse

pytestmark = pytest.mark.story("U84")

HEADER_PAGE = (
    "{% load accounts_tags %}<main>{% flash_slot %}"
    '{% include "components/page_header.html" with title="Page" %}<p id="body">Body</p>'
    "{% endflash_slot %}</main>"
)
PLAIN_PAGE = (
    '{% load accounts_tags %}<main>{% flash_slot %}<p id="body">Body</p>{% endflash_slot %}</main>'
)


def _render(src, text="Saved it."):
    return Template(src).render(Context({"messages": [Message(25, text)]}))


def test_flash_renders_after_the_page_header_h1():
    html = _render(HEADER_PAGE)
    assert html.count("Saved it.") == 1
    assert html.index("<h1>") < html.index("Saved it.") < html.index('id="body"')


def test_flash_renders_at_top_of_main_without_a_page_header():
    html = _render(PLAIN_PAGE)
    assert html.count("Saved it.") == 1
    assert html.index("<main>") < html.index("Saved it.") < html.index('id="body"')


def test_page_header_outside_a_slot_shows_no_messages():
    html = Template('{% include "components/page_header.html" with title="Page" %}').render(
        Context({"messages": [Message(25, "Saved it.")]})
    )
    assert "Saved it." not in html


def test_two_headers_show_flash_once():
    src = HEADER_PAGE.replace(
        '<p id="body">', '{% include "components/page_header.html" with title="Two" %}<p id="body">'
    )
    assert _render(src).count("Saved it.") == 1


def test_flash_below_header_on_a_real_page(club, club_admin, login):
    client = login(club_admin)
    url = reverse("accounts:whitelist", kwargs={"club_slug": club.slug})
    client.post(url, {"email": club_admin.email, "display_name": "x"}, follow=True)
    resp = client.post(url, {"email": club_admin.email, "display_name": "x"}, follow=True)
    html = resp.content.decode()
    assert html.count("is already a member") == 1
    assert html.index("<h1>") < html.index("is already a member")


def test_date_format_is_13_nov_2026():
    assert (
        Template("{{ d|date }}").render(Context({"d": datetime.date(2026, 11, 13)}))
        == "13 Nov 2026"
    )
    dt = datetime.datetime(2026, 11, 13, 9, 5)
    assert (
        Template("{{ d|date:'DATETIME_FORMAT' }}").render(Context({"d": dt}))
        == "13 Nov 2026, 09:05"
    )
