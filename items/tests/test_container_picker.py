"""Tests for the container slot item picker (S2, U158/U157).

Only items/forms.py and items/templates/items/_container_form.html change in
this story. These tests prove the slot option item field now renders the
shared ItemPickerWidget while saving exactly the same data as before.
"""

import pytest
from django.test import Client
from django.urls import reverse

from items.models import Item
from items.tests.factories import add_slot, make_container
from items.widgets import ItemPickerWidget

pytestmark = [pytest.mark.django_db]


def url(name, club, *args):
    return reverse(f"items:{name}", args=[club.slug, *args])


def form(**kw):
    """Base item edit form data, matching items/tests/test_container_admin.py."""
    return {
        "name": "Test Item",
        "description": "",
        "traits": "",
        "details": "",
        "gm_details": "",
        "rarity": "",
        "magic_type": "",
        "value_pp": "",
        "value_gp": "",
        "value_sp": "",
        "value_cp": "",
        **kw,
    }


@pytest.fixture
def login():
    def _login(user):
        client = Client()
        client.force_login(user)
        return client

    return _login


def rendered_post(content):
    """Return the POST data a browser sends for the item form, without a button."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, "html.parser")
    data = {}
    root = soup.select_one("#item-form")
    for el in root.select("input[name], select[name], textarea[name]"):
        name = el["name"]
        if el.name == "select":
            chosen = el.select_one("option[selected]")
            data[name] = chosen["value"] if chosen else ""
        elif el.name == "textarea":
            data[name] = el.text
        elif el.get("type") == "checkbox":
            if el.has_attr("checked"):
                data[name] = el.get("value", "on")
        elif el.get("type") != "submit":
            data[name] = el.get("value", "")
    return data


# ---------------------------------------------------------------------------
# Widget in place
# ---------------------------------------------------------------------------


def test_slot_option_form_uses_picker_widget(club):
    """SlotOptionForm's item field renders ItemPickerWidget with the club set."""
    from items.forms import SlotOptionForm

    form = SlotOptionForm(club=club)
    widget = form.fields["item"].widget
    assert isinstance(widget, ItemPickerWidget)
    assert widget.club == club
    # The field name, queryset and validation are untouched.
    assert form.fields["item"].queryset.model is Item


def test_edit_page_renders_picker_not_select(login, club_admin, club):
    """The edit page renders the picker widget (hidden input + search), not a plain select."""
    container = make_container(club, "Box")
    add_slot(container, [], position=0)
    c = login(club_admin)
    r = c.get(url("edit", club, container.pk))
    assert r.status_code == 200
    content = r.content.decode()
    # The picker widget renders itself as a data-item-picker component.
    assert "data-item-picker" in content
    # The hidden input holds the selected item id under the field's name.
    assert 'name="slots-0-opts-0-item"' in content
    # The picker search endpoint is wired up for the club.
    assert url("picker_search", club) in content
    # No plain item select is rendered for the option row.
    assert '<select name="slots-0-opts-0-item"' not in content


# ---------------------------------------------------------------------------
# Saved data identical to before
# ---------------------------------------------------------------------------


def test_saved_data_identical_to_before(login, club_admin, club):
    """Submitting an option through the picker saves the same field name/value."""
    container = make_container(club, "Box")
    item = Item.objects.create(club=club, name="Gem", value_cp=1)

    c = login(club_admin)
    data = {
        **form(
            is_container="on",
            name="Box",
            **{
                "slots-TOTAL_FORMS": "1",
                "slots-INITIAL_FORMS": "0",
                "slots-0-chance_pct": "100",
                "slots-0-unknown": "",
                "slots-0-position": "0",
                "slots-0-opts-TOTAL_FORMS": "1",
                "slots-0-opts-INITIAL_FORMS": "0",
                "slots-0-opts-0-item": str(item.pk),
                "slots-0-opts-0-qty_min": "1",
                "slots-0-opts-0-qty_max": "2",
                "slots-0-opts-0-weight": "1",
            },
        )
    }
    r = c.post(url("edit", club, container.pk), data)
    assert r.status_code == 302
    container.refresh_from_db()
    option = container.slots.first().options.first()
    assert option.item == item
    assert option.qty_min == 1
    assert option.qty_max == 2
    assert option.weight == 1


# ---------------------------------------------------------------------------
# Retired items cannot be picked
# ---------------------------------------------------------------------------


def test_retired_item_rejected(login, club_admin, club):
    """A newly added retired item is rejected by the existing clean_item validation."""
    container = make_container(club, "Box")
    retired = Item.objects.create(club=club, name="Retired", value_cp=1, retired=True)

    c = login(club_admin)
    post = form(
        is_container="on",
        name="Box",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "0",
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "0",
            "slots-0-opts-0-item": str(retired.pk),
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 200  # Re-renders with error, not redirect
    container.refresh_from_db()
    assert container.slots.count() == 0


# ---------------------------------------------------------------------------
# Value shown on each option row (via picker results)
# ---------------------------------------------------------------------------


def test_picker_results_show_value(login, club_admin, club):
    """The picker search results include the item's value per choice."""
    Item.objects.create(club=club, name="Gem", value_cp=500)
    c = login(club_admin)
    r = c.get(url("picker_search", club) + "?q=Gem")
    assert r.status_code == 200
    content = r.content.decode()
    assert "Gem" in content
    assert "500" in content or "gp" in content or "cp" in content


# ---------------------------------------------------------------------------
# Add slot / add option still work through the picker
# ---------------------------------------------------------------------------


def test_add_slot_then_add_option_then_save_resave_and_delete(login, club_admin, club):
    """Multi-add flow still works with the picker: add slot, add option, save,
    resave unchanged, delete an option."""
    gem = Item.objects.create(club=club, name="Gem", value_cp=1)
    coin = Item.objects.create(club=club, name="Coin", value_cp=1)
    box = make_container(club, "Box")
    add_slot(box, [(gem, 1, 1, 1)], position=0)
    edit = url("edit", club, box.pk)
    c = login(club_admin)

    # Add a slot.
    r = c.post(edit, {**rendered_post(c.get(edit).content), "add_slot": "1"})
    assert r.status_code == 200
    data = rendered_post(r.content)
    assert data["slots-TOTAL_FORMS"] == "2"

    # Add an option on the new slot.
    r = c.post(edit, {**data, "add_option": "1"})
    assert r.status_code == 200
    data = rendered_post(r.content)
    assert data["slots-1-opts-TOTAL_FORMS"] == "2"

    # Fill both options and save.
    data["slots-1-chance_pct"] = "25"
    data["slots-1-opts-0-item"] = str(gem.pk)
    data["slots-1-opts-1-item"] = str(coin.pk)
    data["slots-1-opts-1-weight"] = "3"
    assert c.post(edit, data).status_code == 302
    box.refresh_from_db()
    new_slot = box.slots.get(chance_pct=25)
    assert sorted(new_slot.options.values_list("item__name", "weight")) == [
        ("Coin", 3),
        ("Gem", 1),
    ]

    # Re-save unchanged.
    assert c.post(edit, rendered_post(c.get(edit).content)).status_code == 302
    assert box.slots.count() == 2
    assert new_slot.options.count() == 2

    # Delete one option.
    data = rendered_post(c.get(edit).content)
    idx = next(
        k.split("-")[3]
        for k, v in data.items()
        if k.startswith("slots-1-opts-") and k.endswith("-item") and v == str(coin.pk)
    )
    data[f"slots-1-opts-{idx}-DELETE"] = "on"
    assert c.post(edit, data).status_code == 302
    assert list(new_slot.options.values_list("item__name", flat=True)) == ["Gem"]


# ---------------------------------------------------------------------------
# Existing container option behaviour still applies
# ---------------------------------------------------------------------------


def test_existing_retired_option_survives_resave(login, club_admin, club):
    """An already-saved retired option is allowed to stay on resave."""
    container = make_container(club, "Box")
    retired = Item.objects.create(club=club, name="Retired", value_cp=1, retired=True)
    slot = add_slot(container, [(retired, 1, 1, 1)], position=0)

    c = login(club_admin)
    post = form(
        is_container="on",
        name="Box",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "1",
            "slots-0-id": str(slot.pk),
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "1",
            "slots-0-opts-0-id": str(slot.options.first().pk),
            "slots-0-opts-0-item": str(retired.pk),
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 302  # Success
    container.refresh_from_db()
    assert container.slots.first().options.first().item == retired
