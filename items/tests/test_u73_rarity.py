import pytest
from django.urls import reverse

from items import rarity
from items.models import Item

pytestmark = [pytest.mark.story("U73"), pytest.mark.django_db]

VALUE = {"value_pp": "", "value_gp": "", "value_sp": "", "value_cp": ""}
LABELS = {
    "common": "50–100 gp",
    "uncommon": "101–500 gp",
    "rare": "501–5,000 gp",
    "very_rare": "5,001–50,000 gp",
    "legendary": "50,001 gp and up",
}


def url(name, club, *args):
    return reverse(f"items:{name}", args=[club.slug, *args])


def data(**kw):
    return {"name": "Lantern", "description": "", "traits": "", "details": "", **VALUE, **kw}


@pytest.mark.parametrize("key,label", LABELS.items())
def test_range_label(key, label):
    assert rarity.range_label(key) == label


def test_save_edit_and_clear(login, club_admin, club):
    c = login(club_admin)
    assert c.post(url("create", club), data(rarity="rare")).status_code == 302
    lantern = Item.objects.get(club=club, name="Lantern")
    assert lantern.rarity == "rare"
    c.post(url("edit", club, lantern.pk), data(rarity="legendary"))
    lantern.refresh_from_db()
    assert lantern.rarity == "legendary"
    c.post(url("edit", club, lantern.pk), data(rarity=""))
    lantern.refresh_from_db()
    assert lantern.rarity == ""


def test_any_value_saves_for_any_rarity(login, club_admin, club):
    c = login(club_admin)
    c.post(url("create", club), data(rarity="legendary", value_cp="1"))
    assert Item.objects.get(name="Lantern").value_cp == 1
    c.post(url("create", club), data(name="Big", rarity="common", value_gp="10000"))
    assert Item.objects.get(name="Big").value_cp == 1_000_000


def test_invalid_rarity_refused(login, club_admin, club):
    r = login(club_admin).post(url("create", club), data(rarity="mythic"))
    assert r.status_code == 200
    assert not Item.objects.filter(name="Lantern").exists()


def test_form_page_shows_all_ranges(login, club_admin, club):
    body = login(club_admin).get(url("create", club)).content.decode()
    for label in LABELS.values():
        assert label in body
    assert "data-rarity-select" in body and "item_rarity.js" in body


def test_modal_shows_hint(login, club_admin, club):
    body = login(club_admin).get(url("create", club), HTTP_HX_REQUEST="true").content.decode()
    for label in LABELS.values():
        assert label in body
    assert "data-rarity-hint" in body and "item_rarity.js" in body


def test_detail_shows_rarity_only_when_set(login, player, club, item):
    c = login(player)
    assert "<dt>Rarity</dt>" not in c.get(url("detail", club, item.pk)).content.decode()
    item.rarity = "very_rare"
    item.save()
    body = c.get(url("detail", club, item.pk)).content.decode()
    assert "<dt>Rarity</dt><dd>Very rare</dd>" in body


def test_catalogue_column(login, player, club, item):
    c = login(player)
    body = c.get(url("index", club)).content.decode()
    assert "Rarity</th>" in body and "—</td>" in body
    item.rarity = "uncommon"
    item.save()
    assert "Uncommon</td>" in c.get(url("index", club)).content.decode()


def test_cross_club_rarity_not_shown(login, player, club, other_club):
    Item.objects.create(club=other_club, name="Foreign", rarity="legendary")
    body = login(player).get(url("index", club)).content.decode()
    assert "Legendary" not in body and "Foreign" not in body


def test_seed_demo_rarity_idempotent(club):
    from items import demo

    demo.seed(club)
    demo.seed(club)
    assert Item.objects.filter(club=club, name="Healing potion").count() == 1
    assert Item.objects.get(club=club, name="Healing potion").rarity == "common"
    assert Item.objects.get(club=club, name="Moonstone amulet").rarity == "uncommon"
