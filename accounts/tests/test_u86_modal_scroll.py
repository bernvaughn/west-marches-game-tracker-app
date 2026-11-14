from datetime import date

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from accounts.models import Membership, Message
from downtime.models import DowntimeAction
from quests.models import Quest
from shops.models import Rotation, Shop

pytestmark = [pytest.mark.story("U86"), pytest.mark.django_db]

HX = {"HTTP_HX_REQUEST": "true"}


def pos(body, *needles):
    idx = [body.index(n) for n in needles]
    assert idx == sorted(idx), needles


def test_dialog_is_scrollable(login, player, club):
    body = login(player).get(reverse("club_home", args=[club.slug])).content.decode()
    assert "modal-dialog-scrollable" in body


def test_css_makes_form_a_flex_column():
    css = open(finders.find("css/components.css")).read()
    rule = css.split(".modal-content > form {")[1].split("}")[0]
    assert "display: flex" in rule and "min-height: 0" in rule
    assert "overflow-y: auto" in css.split(".modal-content > form > .modal-body {")[1].split("}")[0]


def test_design_reference_tall_sample(login, site_admin):
    body = login(site_admin).get(reverse("site_design")).content.decode()
    assert "Tall modals scroll the body" in body
    tall = body.split('data-testid="modal-tall-sample"')[1]
    pos(tall, "<form", "modal-header", "modal-body", "modal-footer", "Save")


def _tall(club):
    quest = Quest.objects.create(club=club, name="Pelts for the Tanner")
    rot = Rotation.objects.create(
        club=club, name="Spring", open_date=date(2030, 3, 5), close_date=date(2030, 3, 9)
    )
    act = DowntimeAction.objects.create(club=club, name="Bakery", start_date=date(2030, 3, 1))
    shop = Shop.objects.create(club=club, name="Lantern")
    return {
        "quest edit": reverse("quests:edit", args=[club.slug, quest.pk]),
        "quest create": reverse("quests:create", args=[club.slug]),
        "rotation": reverse("shops:rotation_edit", args=[club.slug, rot.pk]),
        "action": reverse("downtime:agenda_action_edit", args=[club.slug, act.pk]),
        "sell junk": reverse("shops:sell_junk", args=[club.slug, shop.pk]),
    }


@pytest.mark.parametrize("key", ["quest edit", "quest create", "rotation", "action"])
def test_admin_modals_use_frame_and_keep_plain_page(login, club_admin, club, key):
    url = _tall(club)[key]
    c = login(club_admin)
    body = c.get(url, **HX).content.decode()
    pos(body, "<form", "modal-header", "modal-body", "modal-footer", "submit")
    assert "<html" not in body
    page = c.get(url)
    assert page.status_code == 200 and "<html" in page.content.decode()


def test_sell_junk_modal_uses_frame(login, player, character, club):
    shop = Shop.objects.create(club=club, name="Lantern")
    rot = Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1))
    rot.shops.add(shop)
    url = reverse("shops:sell_junk", args=[club.slug, shop.pk])
    body = login(player).get(url, **HX).content.decode()
    pos(body, "modal-header", "modal-body", "modal-footer")
    assert "<form" in body


def test_give_modal_uses_frame(login, club_admin, club, character, player):
    msg = Message.objects.create(
        club=club,
        sender=Membership.objects.get(user=player, club=club),
        character=character,
        body="Please",
    )
    url = reverse("accounts:message_give_coins", args=[club.slug, msg.pk])
    c = login(club_admin)
    body = c.get(url, **HX).content.decode()
    pos(body, "<form", "modal-header", "modal-body", "modal-footer", "submit")
    assert "<html" in c.get(url).content.decode()
