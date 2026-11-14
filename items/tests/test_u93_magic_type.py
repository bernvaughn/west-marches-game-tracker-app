import pytest
from django.core.management import call_command
from django.urls import reverse

from items.forms import ItemForm
from items.magic_types import NONE_LABEL, MagicType
from items.models import Item

pytestmark = [pytest.mark.story("U93"), pytest.mark.django_db]

VALUE = {"value_pp": "", "value_gp": "", "value_sp": "", "value_cp": ""}


def url(name, club, *args):
    return reverse(f"items:{name}", args=[club.slug, *args])


def data(**kw):
    return {"name": "Lantern", "description": "", "traits": "", "details": "", **VALUE, **kw}


def test_choices():
    assert [(m.value, m.label) for m in MagicType] == [
        ("armor", "Armor"),
        ("potion", "Potion"),
        ("ring", "Ring"),
        ("rod", "Rod"),
        ("scroll", "Scroll"),
        ("staff", "Staff"),
        ("wand", "Wand"),
        ("weapon", "Weapon"),
        ("wondrous", "Wondrous item"),
    ]
    assert Item._meta.get_field("magic_type").blank is True


def test_form_choices_none_first(club):
    form = ItemForm(club=club)
    assert form.fields["magic_type"].choices[0] == ("", NONE_LABEL)


def test_form_saves_edits_and_clears(login, club_admin, club):
    c = login(club_admin)
    assert c.post(url("create", club), data(magic_type="wand")).status_code == 302
    item = Item.objects.get(club=club, name="Lantern")
    assert item.magic_type == "wand"
    c.post(url("edit", club, item.pk), data(magic_type=""))
    item.refresh_from_db()
    assert item.magic_type == ""


def test_invalid_refused(club):
    form = ItemForm(data=data(magic_type="gizmo"), club=club)
    assert not form.is_valid() and "magic_type" in form.errors


def test_form_pages_show_select(login, club_admin, club):
    c = login(club_admin)
    assert "None (non-magical)" in c.get(url("create", club)).content.decode()
    assert (
        "None (non-magical)" in c.get(url("create", club), HTTP_HX_REQUEST="true").content.decode()
    )


def test_detail_pill(login, player, club):
    a = Item.objects.create(club=club, name="Zap", magic_type="wondrous")
    b = Item.objects.create(club=club, name="Plain")
    c = login(player)
    assert "Wondrous item" in c.get(url("detail", club, a.pk)).content.decode()
    assert "Magic item type" not in c.get(url("detail", club, b.pk)).content.decode()


def test_catalogue_filter(login, player, club):
    Item.objects.create(club=club, name="Elixir", magic_type="potion")
    Item.objects.create(club=club, name="Blade", magic_type="weapon")
    Item.objects.create(club=club, name="Spoon")
    c = login(player)
    body = c.get(url("index", club) + "?magic_type=potion").content.decode()
    assert "Elixir" in body and "Blade" not in body and "Spoon" not in body
    body = c.get(url("index", club) + "?magic_type=none").content.decode()
    assert "Spoon" in body and "Elixir" not in body
    body = c.get(url("index", club) + "?magic_type=bogus").content.decode()
    assert "Elixir" in body and "Blade" in body and "Spoon" in body
    assert "Weapon" in body  # column text


def test_filter_keeps_retired(login, club_admin, club):
    Item.objects.create(club=club, name="Old", magic_type="ring", retired=True)
    c = login(club_admin)
    body = c.get(url("index", club) + "?retired=1&magic_type=ring").content.decode()
    assert "Old" in body and 'name="retired"' in body


def test_cross_club_isolation(login, player, club, other_club):
    foreign = Item.objects.create(club=other_club, name="Foreign", magic_type="potion")
    c = login(player)
    body = c.get(url("index", club) + "?magic_type=potion").content.decode()
    assert "Foreign" not in body
    assert c.get(url("detail", club, foreign.pk)).status_code == 404


def test_seed_demo_idempotent(db):
    call_command("seed_demo")
    call_command("seed_demo")
    assert Item.objects.filter(name="Healing potion", magic_type="potion").exists()
