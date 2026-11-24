"""Tests for the shared item picker widget in starting equipment forms."""

import pytest
from django.urls import reverse

from items.models import Item
from items.widgets import ItemPickerWidget
from starting_equipment.forms import (
    BackgroundLineForm,
    ClassLineForm,
    MagicOptionForm,
)
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
)

pytestmark = pytest.mark.django_db


def u(name, club, *ids):
    keys = {
        "class_entry_edit": ["template_pk", "pk"],
        "background_entry_edit": ["template_pk", "pk"],
        "magic_option_create": ["template_pk"],
        "magic_option_edit": ["template_pk", "pk"],
    }[name]
    kwargs = {"club_slug": club.slug, **dict(zip(keys, ids, strict=True))}
    return reverse(f"starting_equipment:{name}", kwargs=kwargs)


@pytest.fixture
def admin_client(club_admin, login):
    return login(club_admin)


@pytest.fixture
def class_item(club):
    """Item for class equipment."""
    return Item.objects.create(club=club, name="Longsword", value_cp=1500)


@pytest.fixture
def class_item_2(club):
    """Second item for class equipment."""
    return Item.objects.create(club=club, name="Chain Mail", value_cp=7500)


@pytest.fixture
def bg_item(club):
    """Item for background equipment."""
    return Item.objects.create(club=club, name="Holy Symbol", value_cp=500)


@pytest.fixture
def magic_item(club):
    """Magic item for starting options."""
    return Item.objects.create(
        club=club,
        name="Potion of Healing",
        value_cp=5000,
        rarity="uncommon",
        magic_type="potion",
    )


@pytest.fixture
def class_entry(template, class_option_fighter):
    """Class entry for Fighter at levels 1-20."""
    return StartingEquipmentClassEntry.objects.create(
        template=template,
        class_option=class_option_fighter,
        min_level=1,
        max_level=20,
        coins_cp=1000,
    )


@pytest.fixture
def bg_entry(template, bg_option_acolyte):
    """Background entry for Acolyte."""
    return StartingEquipmentBackgroundEntry.objects.create(
        template=template,
        background_option=bg_option_acolyte,
        coins_cp=500,
    )


@pytest.fixture
def class_line(class_entry, class_item):
    """Class line with an item."""
    return StartingEquipmentClassLine.objects.create(
        class_entry=class_entry, item=class_item, quantity=1, is_choice=False
    )


@pytest.fixture
def bg_line(bg_entry, bg_item):
    """Background line with an item."""
    return StartingEquipmentBackgroundLine.objects.create(
        background_entry=bg_entry, item=bg_item, quantity=1, is_choice=False
    )


@pytest.fixture
def magic_option(template, magic_item):
    """Magic item starting option."""
    return MagicItemStartingOption.objects.create(
        template=template, item=magic_item, max_per_character=1, notes="Level 1+ only"
    )


@pytest.mark.story("S5")
def test_class_line_form_uses_item_picker_widget(club, class_entry, class_item):
    """ClassLineForm's item field uses ItemPickerWidget."""
    form = ClassLineForm(club=club)
    assert isinstance(form.fields["item"].widget, ItemPickerWidget)
    assert form.fields["item"].widget.club == club


@pytest.mark.story("S5")
def test_background_line_form_uses_item_picker_widget(club, bg_entry, bg_item):
    """BackgroundLineForm's item field uses ItemPickerWidget."""
    form = BackgroundLineForm(club=club)
    assert isinstance(form.fields["item"].widget, ItemPickerWidget)
    assert form.fields["item"].widget.club == club


@pytest.mark.story("S5")
def test_magic_option_form_uses_item_picker_widget(club, magic_option):
    """MagicOptionForm's item field uses ItemPickerWidget."""
    form = MagicOptionForm(club=club)
    assert isinstance(form.fields["item"].widget, ItemPickerWidget)
    assert form.fields["item"].widget.club == club


@pytest.mark.story("S5")
def test_class_line_form_queryset_club_scoped(club, other_club, class_entry, class_item):
    """ClassLineForm's item queryset is club-scoped."""
    Item.objects.create(club=other_club, name="Foreign Item", value_cp=100)
    fresh = Item.objects.create(club=club, name="Local Item", value_cp=200)

    form = ClassLineForm(club=club)
    qs = form.fields["item"].queryset
    # The queryset includes both the existing class_item and the fresh item, ordered by name
    assert list(qs) == [fresh, class_item]


@pytest.mark.story("S5")
def test_saved_class_line_data_identical(admin_client, club, template, class_entry, class_item):
    """POSTing to create a class line saves the same data as before."""
    url = u("class_entry_edit", club, template.pk, class_entry.pk)
    formset_prefix = "lines"

    response = admin_client.post(
        url,
        {
            "class_option": class_entry.class_option.pk,
            "min_level": "1",
            "max_level": "20",
            "coins_cp": "1000",
            f"{formset_prefix}-TOTAL_FORMS": "1",
            f"{formset_prefix}-INITIAL_FORMS": "0",
            f"{formset_prefix}-MIN_NUM_FORMS": "0",
            f"{formset_prefix}-MAX_NUM_FORMS": "1000",
            f"{formset_prefix}-0-item": class_item.pk,
            f"{formset_prefix}-0-quantity": "2",
            f"{formset_prefix}-0-is_choice": "False",
            f"{formset_prefix}-0-choice_group": "",
        },
    )
    assert response.status_code == 302

    line = StartingEquipmentClassLine.objects.get(class_entry=class_entry, item=class_item)
    assert line.quantity == 2
    assert line.is_choice is False
    assert line.choice_group == ""


@pytest.mark.story("S5")
def test_saved_background_line_data_identical(admin_client, club, template, bg_entry, bg_item):
    """POSTing to create a background line saves the same data as before."""
    url = u("background_entry_edit", club, template.pk, bg_entry.pk)
    formset_prefix = "lines"

    response = admin_client.post(
        url,
        {
            "background_option": bg_entry.background_option.pk,
            "coins_cp": "500",
            f"{formset_prefix}-TOTAL_FORMS": "1",
            f"{formset_prefix}-INITIAL_FORMS": "0",
            f"{formset_prefix}-MIN_NUM_FORMS": "0",
            f"{formset_prefix}-MAX_NUM_FORMS": "1000",
            f"{formset_prefix}-0-item": bg_item.pk,
            f"{formset_prefix}-0-quantity": "1",
            f"{formset_prefix}-0-is_choice": "False",
            f"{formset_prefix}-0-choice_group": "",
        },
    )
    assert response.status_code == 302

    line = StartingEquipmentBackgroundLine.objects.get(background_entry=bg_entry, item=bg_item)
    assert line.quantity == 1
    assert line.is_choice is False


@pytest.mark.story("S5")
def test_saved_magic_option_data_identical(admin_client, club, template, magic_item):
    """POSTing to create a magic option saves the same data as before."""
    url = u("magic_option_create", club, template.pk)

    response = admin_client.post(
        url,
        {
            "item": magic_item.pk,
            "max_per_character": "2",
            "notes": "Test notes",
        },
    )
    assert response.status_code == 302

    option = MagicItemStartingOption.objects.get(template=template, item=magic_item)
    assert option.max_per_character == 2
    assert option.notes == "Test notes"


@pytest.mark.story("S5")
def test_entry_form_page_renders_picker_widget(admin_client, club, template, class_entry):
    """The entry edit page renders the picker widget for class lines."""
    url = u("class_entry_edit", club, template.pk, class_entry.pk)
    response = admin_client.get(url)
    assert response.status_code == 200

    html = response.content.decode()
    # Widget renders search input and hidden input
    assert 'type="search"' in html
    assert 'placeholder="Search items by name, type, or trait..."' in html
    assert 'name="lines-0-item"' in html or 'name="lines-1-item"' in html
    assert 'type="hidden"' in html
    # The "Browse catalogue" button is still present
    assert "Browse catalogue" in html


@pytest.mark.story("S5")
def test_magic_option_form_page_renders_picker_widget(admin_client, club, template):
    """The magic option create page renders the picker widget."""
    url = u("magic_option_create", club, template.pk)
    response = admin_client.get(url)
    assert response.status_code == 200

    html = response.content.decode()
    assert 'type="search"' in html
    assert 'placeholder="Search items by name, type, or trait..."' in html
    assert 'name="item"' in html
    assert 'type="hidden"' in html
    assert "Browse catalogue" in html


@pytest.mark.story("S5")
def test_entry_form_shows_item_value_on_each_line(
    admin_client, club, template, class_entry, class_line
):
    """Each class line shows the item's value."""
    url = u("class_entry_edit", club, template.pk, class_entry.pk)
    response = admin_client.get(url)
    html = response.content.decode()

    # The item value should be displayed (1500 cp = 15 gp)
    assert "Value:" in html
    assert "15 gp" in html


@pytest.mark.story("S5")
def test_magic_option_form_shows_item_value(admin_client, club, template, magic_option):
    """The magic option form shows the item's value."""
    url = u("magic_option_edit", club, template.pk, magic_option.pk)
    response = admin_client.get(url)
    html = response.content.decode()

    # The item value should be displayed (5000 cp = 50 gp)
    assert "Value:" in html
    assert "50 gp" in html


@pytest.mark.story("S5")
def test_browse_catalogue_button_still_works_in_entry_form(
    admin_client, club, template, class_entry
):
    """The 'Browse catalogue' button is present in entry form."""
    url = u("class_entry_edit", club, template.pk, class_entry.pk)
    response = admin_client.get(url)
    html = response.content.decode()

    assert "Browse catalogue" in html
    assert f"/c/{club.slug}/items/references/" in html


@pytest.mark.story("S5")
def test_browse_catalogue_button_still_works_in_magic_option_form(admin_client, club, template):
    """The 'Browse catalogue' button is present in magic option form."""
    url = u("magic_option_create", club, template.pk)
    response = admin_client.get(url)
    html = response.content.decode()

    assert "Browse catalogue" in html
    assert f"/c/{club.slug}/items/references/" in html


@pytest.mark.story("S5")
def test_widget_search_url_includes_club_slug(club, class_entry):
    """The widget's search URL includes the club slug."""
    form = ClassLineForm(club=club)
    widget = form.fields["item"].widget
    context = widget.get_context("item", None, {})
    assert f"/c/{club.slug}/items/picker/search/" in context["widget"]["search_url"]


@pytest.mark.story("S5")
def test_class_line_form_validation_unchanged(
    admin_client, club, template, class_entry, class_item
):
    """ClassLineForm validation works identically to before."""
    url = u("class_entry_edit", club, template.pk, class_entry.pk)
    formset_prefix = "lines"

    # Valid submission
    response = admin_client.post(
        url,
        {
            "class_option": class_entry.class_option.pk,
            "min_level": "1",
            "max_level": "20",
            "coins_cp": "1000",
            f"{formset_prefix}-TOTAL_FORMS": "1",
            f"{formset_prefix}-INITIAL_FORMS": "0",
            f"{formset_prefix}-MIN_NUM_FORMS": "0",
            f"{formset_prefix}-MAX_NUM_FORMS": "1000",
            f"{formset_prefix}-0-item": class_item.pk,
            f"{formset_prefix}-0-quantity": "1",
            f"{formset_prefix}-0-is_choice": "False",
            f"{formset_prefix}-0-choice_group": "",
        },
    )
    assert response.status_code == 302

    # Invalid item (non-existent PK) should fail
    response = admin_client.post(
        url,
        {
            "class_option": class_entry.class_option.pk,
            "min_level": "1",
            "max_level": "20",
            "coins_cp": "1000",
            f"{formset_prefix}-TOTAL_FORMS": "1",
            f"{formset_prefix}-INITIAL_FORMS": "0",
            f"{formset_prefix}-MIN_NUM_FORMS": "0",
            f"{formset_prefix}-MAX_NUM_FORMS": "1000",
            f"{formset_prefix}-0-item": "99999",
            f"{formset_prefix}-0-quantity": "1",
            f"{formset_prefix}-0-is_choice": "False",
            f"{formset_prefix}-0-choice_group": "",
        },
    )
    assert response.status_code == 200
    formset = response.context["formset"]
    assert any(f.errors for f in formset.forms)


@pytest.mark.story("S5")
def test_stacked_item_value_display(admin_client, club, template, class_entry):
    """Stacked items show 'N gp per unit' format."""
    stacked = Item.objects.create(
        club=club, name="Arrow", value_cp=2000, is_stacked=True, value_units=20, unit_name="arrow"
    )
    url = u("class_entry_edit", club, template.pk, class_entry.pk)

    # Create a line with the stacked item
    StartingEquipmentClassLine.objects.create(
        class_entry=class_entry, item=stacked, quantity=1, is_choice=False
    )

    response = admin_client.get(url)
    html = response.content.decode()

    # 2000 cp for 20 arrows = 100 cp per arrow = 1 gp per arrow
    assert "Value:" in html
    assert "1 gp per arrow" in html
