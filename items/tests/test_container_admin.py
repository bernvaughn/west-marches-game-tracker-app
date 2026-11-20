"""Tests for the container admin UI (Slice A)."""

import pytest
from django.urls import reverse

from items.models import Item
from items.tests.factories import add_slot, make_container

pytestmark = [pytest.mark.story("A"), pytest.mark.django_db]


def url(name, club, *args):
    return reverse(f"items:{name}", args=[club.slug, *args])


def form(**kw):
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


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["player", "game_master"])
def test_non_admins_cannot_view_edit_page(request, login, club, item, who):
    c = login(request.getfixturevalue(who))
    assert c.get(url("edit", club, item.pk)).status_code == 403


def test_anonymous_cannot_view_edit_page(client, club, item):
    assert client.get(url("edit", club, item.pk)).status_code == 302  # Redirects to login


@pytest.mark.parametrize("who", ["player", "game_master"])
def test_non_admins_cannot_post_edit_page(request, login, club, item, who):
    c = login(request.getfixturevalue(who))
    assert c.post(url("edit", club, item.pk), form(name="New")).status_code == 403


def test_anonymous_cannot_post_edit_page(client, club, item):
    assert client.post(url("edit", club, item.pk), form(name="New")).status_code == 302


def test_club_admin_can_view_edit_page(login, club_admin, club, item):
    c = login(club_admin)
    r = c.get(url("edit", club, item.pk))
    assert r.status_code == 200
    assert b"Is container" in r.content


def test_site_admin_can_view_edit_page(login, site_admin, club, item):
    c = login(site_admin)
    r = c.get(url("edit", club, item.pk))
    assert r.status_code == 200
    assert b"Is container" in r.content


def test_create_modal_does_not_show_container_toggle(login, club_admin, club):
    c = login(club_admin)
    r = c.get(url("create", club))
    assert r.status_code == 200
    assert b"Is container" not in r.content


# ---------------------------------------------------------------------------
# Scoping
# ---------------------------------------------------------------------------


def test_option_picker_lists_only_club_items(login, club_admin, club, other_club):
    c = login(club_admin)
    Item.objects.create(club=other_club, name="Foreign Item", value_cp=1)
    local = Item.objects.create(club=club, name="Local Item", value_cp=1)
    container = make_container(club, "Container")
    add_slot(container, [(local, 1, 1, 1)], position=0)

    r = c.get(url("edit", club, container.pk))
    assert r.status_code == 200
    assert b"Local Item" in r.content
    # Check that the option item picker (select field) only contains club items
    # The picker is in the nested option formset; verify foreign item not in select options
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(r.content, "html.parser")
    item_selects = soup.select('select[name*="-item"]')
    for select in item_selects:
        options = [opt.text for opt in select.find_all("option")]
        assert "Foreign Item" not in options, f"Foreign Item found in picker: {options}"
        assert "Local Item" in options, f"Local Item missing from picker: {options}"


def test_posting_foreign_club_item_rejected(login, club_admin, club, other_club):
    c = login(club_admin)
    foreign = Item.objects.create(club=other_club, name="Foreign", value_cp=1)
    container = make_container(club, "Container")
    add_slot(container, [], position=0)

    # Build POST with foreign item in option
    post = form(
        is_container="on",
        name="Container",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "1",
            "slots-0-id": str(container.slots.first().pk),
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "0",
            "slots-0-opts-0-item": str(foreign.pk),
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 200  # Re-renders with error, not redirect
    # Nothing should be saved
    container.refresh_from_db()
    assert container.slots.first().options.count() == 0


def test_posting_foreign_slot_id_rejected(login, club_admin, club, other_club):
    c = login(club_admin)
    container = make_container(club, "Container")
    add_slot(container, [], position=0)
    foreign_container = make_container(other_club, "Foreign Container")
    add_slot(foreign_container, [], position=0)
    foreign_slot = foreign_container.slots.first()

    post = form(
        is_container="on",
        name="Container",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "1",
            "slots-0-id": str(foreign_slot.pk),  # Foreign slot ID
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 200
    assert b"does not belong to this container" in r.content
    assert container.slots.count() == 1
    foreign_slot.refresh_from_db()
    assert foreign_slot.container == foreign_container


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_reject_chance_out_of_range(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")

    for bad_chance in ["0", "101", ""]:
        post = form(
            is_container="on",
            name="Container",
            **{
                "slots-TOTAL_FORMS": "1",
                "slots-INITIAL_FORMS": "0",
                "slots-0-chance_pct": bad_chance,
                "slots-0-unknown": "",
                "slots-0-position": "0",
                "slots-0-opts-TOTAL_FORMS": "1",
                "slots-0-opts-INITIAL_FORMS": "0",
                "slots-0-opts-0-item": str(
                    Item.objects.create(club=club, name="Item", value_cp=1).pk
                ),
                "slots-0-opts-0-qty_min": "1",
                "slots-0-opts-0-qty_max": "1",
                "slots-0-opts-0-weight": "1",
            },
        )
        r = c.post(url("edit", club, container.pk), post)
        assert r.status_code == 200  # Re-renders with error, not redirect
        # Nothing should be saved
        container.refresh_from_db()
        assert container.slots.count() == 0


def test_reject_qty_min_below_1(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    item = Item.objects.create(club=club, name="Item", value_cp=1)

    post = form(
        is_container="on",
        name="Container",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "0",
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "0",
            "slots-0-opts-0-item": str(item.pk),
            "slots-0-opts-0-qty_min": "0",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 200  # Re-renders with error, not redirect
    container.refresh_from_db()
    assert container.slots.count() == 0


def test_reject_qty_max_below_qty_min(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    item = Item.objects.create(club=club, name="Item", value_cp=1)

    post = form(
        is_container="on",
        name="Container",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "0",
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "0",
            "slots-0-opts-0-item": str(item.pk),
            "slots-0-opts-0-qty_min": "5",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 200  # Re-renders with error, not redirect
    container.refresh_from_db()
    assert container.slots.count() == 0


def test_reject_weight_below_1(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    item = Item.objects.create(club=club, name="Item", value_cp=1)

    post = form(
        is_container="on",
        name="Container",
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
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "0",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 200  # Re-renders with error, not redirect
    container.refresh_from_db()
    assert container.slots.count() == 0


def test_reject_newly_added_retired_item(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    retired = Item.objects.create(club=club, name="Retired", value_cp=1, retired=True)

    post = form(
        is_container="on",
        name="Container",
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


def test_existing_retired_option_survives_resave(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    retired = Item.objects.create(club=club, name="Retired", value_cp=1, retired=True)
    slot = add_slot(container, [(retired, 1, 1, 1)], position=0)

    post = form(
        is_container="on",
        name="Container",
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


def test_reject_self_reference_cycle(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    add_slot(container, [], position=0)
    initial_slot_count = container.slots.count()

    post = form(
        is_container="on",
        name="Container",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "0",
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "0",
            "slots-0-opts-0-item": str(container.pk),  # Self reference
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 200  # Re-renders with error, not redirect
    container.refresh_from_db()
    # No new slots should be added
    assert container.slots.count() == initial_slot_count


def test_reject_ab_cycle(login, club_admin, club):
    c = login(club_admin)
    a = make_container(club, "A")
    b = make_container(club, "B")
    add_slot(a, [], position=0)
    add_slot(b, [], position=0)
    a_slot = a.slots.first()
    b_slot = b.slots.first()

    # A contains B
    post = form(
        is_container="on",
        name="A",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "1",
            "slots-0-id": str(a_slot.pk),
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "0",
            "slots-0-opts-0-item": str(b.pk),
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, a.pk), post)
    assert r.status_code == 302  # First save succeeds

    # Now B contains A - should fail
    post = form(
        is_container="on",
        name="B",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "1",
            "slots-0-id": str(b_slot.pk),
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "0",
            "slots-0-opts-0-item": str(a.pk),
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, b.pk), post)
    assert r.status_code == 200  # Re-renders with error, not redirect
    b.refresh_from_db()
    assert b.slots.first().options.count() == 0


def test_reject_depth_over_3(login, club_admin, club):
    c = login(club_admin)
    a = make_container(club, "A")
    b = make_container(club, "B")
    c_ = make_container(club, "C")
    d = make_container(club, "D")
    add_slot(b, [(a, 1, 1, 1)], position=0)
    add_slot(c_, [(b, 1, 1, 1)], position=0)
    # D has an empty slot initially
    add_slot(d, [], position=0)
    d_slot = d.slots.first()

    post = form(
        is_container="on",
        name="D",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "1",
            "slots-0-id": str(d_slot.pk),
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "0",
            "slots-0-opts-0-item": str(c_.pk),
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, d.pk), post)
    assert r.status_code == 200  # Re-renders with error, not redirect
    d.refresh_from_db()
    assert d.slots.first().options.count() == 0


def test_reject_empty_slot(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    add_slot(container, [], position=0)
    slot = container.slots.first()

    post = form(
        is_container="on",
        name="Container",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "1",
            "slots-0-id": str(slot.pk),
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "0",
            "slots-0-opts-INITIAL_FORMS": "0",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 200  # Re-renders with error, not redirect
    container.refresh_from_db()
    assert container.slots.first().options.count() == 0


def test_reject_zero_slots(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    # No slots added

    post = form(
        is_container="on",
        name="Container",
        **{
            "slots-TOTAL_FORMS": "0",
            "slots-INITIAL_FORMS": "0",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 200  # Re-renders with error, not redirect
    container.refresh_from_db()
    assert container.slots.count() == 0


# ---------------------------------------------------------------------------
# Save and edit
# ---------------------------------------------------------------------------


def test_save_diplomats_pack_layout(login, club_admin, club):
    c = login(club_admin)
    # Build the Diplomat's Pack layout through the form
    container = make_container(club, "Diplomat's Pack")
    # Remove any existing slots
    container.slots.all().delete()

    fine_clothes = Item.objects.create(club=club, name="Fine clothes", value_cp=1000)
    flask_of_oil = Item.objects.create(club=club, name="Flask of oil", value_cp=50)
    vial_of_perfume = Item.objects.create(club=club, name="Vial of perfume", value_cp=200)
    sealing_wax = Item.objects.create(club=club, name="Sealing wax", value_cp=10)
    soap = Item.objects.create(club=club, name="Soap", value_cp=5)
    sealed_letter = Item.objects.create(club=club, name="Sealed letter", value_cp=1)

    post = form(
        is_container="on",
        name="Diplomat's Pack",
        **{
            "slots-TOTAL_FORMS": "5",
            "slots-INITIAL_FORMS": "0",
            # Slot 0: Fine clothes x1 (fixed)
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "0",
            "slots-0-opts-0-item": str(fine_clothes.pk),
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
            # Slot 1: Flask of oil 1-2
            "slots-1-chance_pct": "100",
            "slots-1-unknown": "",
            "slots-1-position": "1",
            "slots-1-opts-TOTAL_FORMS": "1",
            "slots-1-opts-INITIAL_FORMS": "0",
            "slots-1-opts-0-item": str(flask_of_oil.pk),
            "slots-1-opts-0-qty_min": "1",
            "slots-1-opts-0-qty_max": "2",
            "slots-1-opts-0-weight": "1",
            # Slot 2: Vial of perfume 50%
            "slots-2-chance_pct": "50",
            "slots-2-unknown": "",
            "slots-2-position": "2",
            "slots-2-opts-TOTAL_FORMS": "1",
            "slots-2-opts-INITIAL_FORMS": "0",
            "slots-2-opts-0-item": str(vial_of_perfume.pk),
            "slots-2-opts-0-qty_min": "1",
            "slots-2-opts-0-qty_max": "1",
            "slots-2-opts-0-weight": "1",
            # Slot 3: Sealing wax (3) / Soap (1) - weighted
            "slots-3-chance_pct": "100",
            "slots-3-unknown": "",
            "slots-3-position": "3",
            "slots-3-opts-TOTAL_FORMS": "2",
            "slots-3-opts-INITIAL_FORMS": "0",
            "slots-3-opts-0-item": str(sealing_wax.pk),
            "slots-3-opts-0-qty_min": "1",
            "slots-3-opts-0-qty_max": "1",
            "slots-3-opts-0-weight": "3",
            "slots-3-opts-1-item": str(soap.pk),
            "slots-3-opts-1-qty_min": "1",
            "slots-3-opts-1-qty_max": "1",
            "slots-3-opts-1-weight": "1",
            # Slot 4: Sealed letter (unknown)
            "slots-4-chance_pct": "100",
            "slots-4-unknown": "on",
            "slots-4-position": "4",
            "slots-4-opts-TOTAL_FORMS": "1",
            "slots-4-opts-INITIAL_FORMS": "0",
            "slots-4-opts-0-item": str(sealed_letter.pk),
            "slots-4-opts-0-qty_min": "1",
            "slots-4-opts-0-qty_max": "1",
            "slots-4-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 302

    container.refresh_from_db()
    assert container.is_container is True
    assert container.slots.count() == 5

    # Verify slots match make_diplomats_pack fixture
    slots = list(container.slots.order_by("position"))
    assert slots[0].chance_pct == 100
    assert slots[0].options.first().item == fine_clothes
    assert slots[1].options.first().qty_max == 2
    assert slots[2].chance_pct == 50
    assert slots[3].options.count() == 2
    assert slots[4].unknown is True

    # Verify loot_preview masks unknown
    from items.containers import loot_preview

    rows = loot_preview(container, viewer_can_see_unknown=False)
    assert rows[4].masked is True
    assert rows[4].label == "???"

    rows_gm = loot_preview(container, viewer_can_see_unknown=True)
    assert rows_gm[4].masked is False
    assert rows_gm[4].item == sealed_letter


def test_edit_and_remove_slots_options(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    item1 = Item.objects.create(club=club, name="Item 1", value_cp=1)
    item2 = Item.objects.create(club=club, name="Item 2", value_cp=1)
    slot = add_slot(container, [(item1, 1, 1, 1), (item2, 1, 1, 1)], position=0)
    opt1, opt2 = slot.options.all()

    # Edit: change chance, delete one option, reorder
    post = form(
        is_container="on",
        name="Container",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "1",
            "slots-0-id": str(slot.pk),
            "slots-0-chance_pct": "50",  # Changed
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "2",
            "slots-0-opts-INITIAL_FORMS": "2",
            "slots-0-opts-0-id": str(opt1.pk),
            "slots-0-opts-0-item": str(item1.pk),
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
            "slots-0-opts-0-DELETE": "on",  # Delete option 1
            "slots-0-opts-1-id": str(opt2.pk),
            "slots-0-opts-1-item": str(item2.pk),
            "slots-0-opts-1-qty_min": "1",
            "slots-0-opts-1-qty_max": "1",
            "slots-0-opts-1-weight": "1",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 302

    container.refresh_from_db()
    slot = container.slots.first()
    assert slot.chance_pct == 50
    assert slot.options.count() == 1
    assert slot.options.first().item == item2


def test_add_slot_button(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    item = Item.objects.create(club=club, name="Item", value_cp=1)

    # Initial GET
    r = c.get(url("edit", club, container.pk))
    assert r.status_code == 200

    # POST add_slot
    post = form(
        is_container="on",
        name="Container",
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
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
            "add_slot": "1",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 200
    # Should have 2 slot forms now
    assert b"slots-1-chance_pct" in r.content
    # Nothing saved to DB
    container.refresh_from_db()
    assert container.slots.count() == 0


def test_add_option_button(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    item1 = Item.objects.create(club=club, name="Item 1", value_cp=1)
    Item.objects.create(club=club, name="Item 2", value_cp=1)
    slot = add_slot(container, [(item1, 1, 1, 1)], position=0)

    post = form(
        is_container="on",
        name="Container",
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
            "slots-0-opts-0-item": str(item1.pk),
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
            "add_option": "0",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 200
    # Should have 2 option forms now
    assert b"slots-0-opts-1-item" in r.content
    # Nothing saved to DB
    slot.refresh_from_db()
    assert slot.options.count() == 1


def test_toggle_off_keeps_data_skips_validation(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    item = Item.objects.create(club=club, name="Item", value_cp=1)
    add_slot(container, [(item, 1, 1, 1)], position=0)

    # Toggle off (don't send is_container)
    post = form(
        name="Container",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "1",
            "slots-0-id": str(container.slots.first().pk),
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "1",
            "slots-0-opts-0-id": str(container.slots.first().options.first().pk),
            "slots-0-opts-0-item": str(item.pk),
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, container.pk), post)
    assert r.status_code == 302

    container.refresh_from_db()
    assert container.is_container is False
    # Slots still exist but are inert
    assert container.slots.count() == 1
    assert container.slots.first().options.count() == 1


def test_toggle_off_container_no_longer_counts_as_container(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    item = Item.objects.create(club=club, name="Item", value_cp=1)
    add_slot(container, [(item, 1, 1, 1)], position=0)

    # Toggle off
    post = form(
        name="Container",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "1",
            "slots-0-id": str(container.slots.first().pk),
            "slots-0-chance_pct": "100",
            "slots-0-unknown": "",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "1",
            "slots-0-opts-0-id": str(container.slots.first().options.first().pk),
            "slots-0-opts-0-item": str(item.pk),
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
        },
    )
    c.post(url("edit", club, container.pk), post)
    container.refresh_from_db()
    assert container.is_container is False

    # Validate should not run (would fail with empty slots if it did)
    # But since is_container is False, validate_container_config is not called
    # This should not raise because we don't call it for non-containers
    # But if we did call it, it would fail - so we just verify the flag is off
    assert not container.is_container


# ---------------------------------------------------------------------------
# Round trips through the rendered page
# ---------------------------------------------------------------------------


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


def test_resave_rendered_page_unchanged(login, club_admin, club):
    c = login(club_admin)
    gem = Item.objects.create(club=club, name="Gem", value_cp=1)
    box = make_container(club, "Box")
    slot = add_slot(box, [(gem, 1, 2, 1)], chance_pct=50, position=0)

    page = c.get(url("edit", club, box.pk))
    assert page.content.count(b'id="id_is_container"') == 1
    r = c.post(url("edit", club, box.pk), rendered_post(page.content))
    assert r.status_code == 302
    box.refresh_from_db()
    assert box.is_container is True
    assert list(box.slots.values_list("pk", "chance_pct")) == [(slot.pk, 50)]
    assert list(slot.options.values_list("item", "qty_min", "qty_max")) == [(gem.pk, 1, 2)]


def test_add_slot_then_add_option_then_save_resave_and_delete(login, club_admin, club):
    c = login(club_admin)
    gem = Item.objects.create(club=club, name="Gem", value_cp=1)
    coin = Item.objects.create(club=club, name="Coin", value_cp=1)
    box = make_container(club, "Box")
    add_slot(box, [(gem, 1, 1, 1)], position=0)
    edit = url("edit", club, box.pk)

    # Add a slot. The new slot renders a valid nested management form.
    r = c.post(edit, {**rendered_post(c.get(edit).content), "add_slot": "1"})
    assert r.status_code == 200
    data = rendered_post(r.content)
    assert data["slots-TOTAL_FORMS"] == "2"
    assert data["slots-1-opts-TOTAL_FORMS"] == "1"
    assert data["slots-1-opts-INITIAL_FORMS"] == "0"

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
    assert box.slots.count() == 2
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


def test_untouched_new_slot_is_skipped(login, club_admin, club):
    c = login(club_admin)
    gem = Item.objects.create(club=club, name="Gem", value_cp=1)
    box = make_container(club, "Box")
    add_slot(box, [(gem, 1, 1, 1)], position=0)
    edit = url("edit", club, box.pk)

    r = c.post(edit, {**rendered_post(c.get(edit).content), "add_slot": "1"})
    assert c.post(edit, rendered_post(r.content)).status_code == 302
    assert box.slots.count() == 1


def test_add_option_with_blank_count_does_not_crash(login, club_admin, club):
    c = login(club_admin)
    box = make_container(club, "Box")
    edit = url("edit", club, box.pk)
    data = {
        **rendered_post(c.get(edit).content),
        "slots-TOTAL_FORMS": "1",
        "slots-0-chance_pct": "100",
        "slots-0-position": "0",
        "slots-0-opts-TOTAL_FORMS": "",
        "slots-0-opts-INITIAL_FORMS": "",
        "add_option": "0",
    }
    r = c.post(edit, data)
    assert r.status_code == 200
    assert b"slots-0-opts-0-item" in r.content


def test_cycle_failure_saves_nothing(login, club_admin, club):
    c = login(club_admin)
    crate = Item.objects.create(club=club, name="Crate A", value_cp=1)
    box = make_container(club, "Diplomat Box")
    add_slot(box, [(crate, 1, 1, 1)], position=0)
    edit = url("edit", club, crate.pk)

    data = rendered_post(c.get(edit).content)
    data.update(name="Crate A RENAMED", is_container="on", add_slot="1")
    data = rendered_post(c.post(edit, data).content)
    data["slots-0-opts-0-item"] = str(box.pk)
    r = c.post(edit, data)
    assert r.status_code == 200
    assert b"contains itself" in r.content
    crate.refresh_from_db()
    assert crate.name == "Crate A"
    assert crate.is_container is False
    assert crate.slots.count() == 0


def test_same_club_foreign_slot_id_rejected(login, club_admin, club):
    c = login(club_admin)
    gem = Item.objects.create(club=club, name="Gem", value_cp=1)
    box = make_container(club, "Box")
    foreign_slot = add_slot(box, [(gem, 1, 1, 1)], position=0)
    crate = make_container(club, "Crate C")
    post = form(
        is_container="on",
        name="Crate C",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "1",
            "slots-0-id": str(foreign_slot.pk),
            "slots-0-chance_pct": "100",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "0",
            "slots-0-opts-0-item": str(gem.pk),
            "slots-0-opts-0-qty_min": "1",
            "slots-0-opts-0-qty_max": "1",
            "slots-0-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, crate.pk), post)
    assert r.status_code == 200
    assert b"does not belong to this container" in r.content
    assert crate.slots.count() == 0
    assert box.slots.count() == 1


def test_foreign_option_id_rejected(login, club_admin, club):
    c = login(club_admin)
    gem = Item.objects.create(club=club, name="Gem", value_cp=1)
    box = make_container(club, "Box")
    other = add_slot(box, [(gem, 1, 1, 1)], position=0)
    crate = make_container(club, "Crate")
    slot = add_slot(crate, [(gem, 1, 1, 1)], position=0)
    foreign_opt = other.options.get()
    post = form(
        is_container="on",
        name="Crate",
        **{
            "slots-TOTAL_FORMS": "1",
            "slots-INITIAL_FORMS": "1",
            "slots-0-id": str(slot.pk),
            "slots-0-chance_pct": "100",
            "slots-0-position": "0",
            "slots-0-opts-TOTAL_FORMS": "1",
            "slots-0-opts-INITIAL_FORMS": "1",
            "slots-0-opts-0-id": str(foreign_opt.pk),
            "slots-0-opts-0-item": str(gem.pk),
            "slots-0-opts-0-qty_min": "2",
            "slots-0-opts-0-qty_max": "2",
            "slots-0-opts-0-weight": "1",
        },
    )
    r = c.post(url("edit", club, crate.pk), post)
    assert r.status_code == 200
    assert b"does not belong to this slot" in r.content
    foreign_opt.refresh_from_db()
    assert foreign_opt.slot == other and foreign_opt.qty_min == 1
    assert slot.options.get().qty_min == 1
