"""Tests for the container admin UI (Slice A)."""

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from items.containers import validate_container_config
from items.models import ContainerSlot, ContainerSlotOption, Item
from items.tests.factories import add_slot, make_container, make_diplomats_pack

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
    foreign = Item.objects.create(club=other_club, name="Foreign Item", value_cp=1)
    local = Item.objects.create(club=club, name="Local Item", value_cp=1)
    container = make_container(club, "Container")
    add_slot(container, [(local, 1, 1, 1)], position=0)

    r = c.get(url("edit", club, container.pk))
    assert r.status_code == 200
    assert b"Local Item" in r.content
    assert b"Foreign Item" not in r.content


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
    assert b"invalid choice" in r.content.lower() or b"not in the same club" in r.content.lower()


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
                "slots-0-opts-0-item": str(Item.objects.create(club=club, name="Item", value_cp=1).pk),
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
    add_slot(d, [(c_, 1, 1, 1)], position=0)
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
    assert b'slots-1-chance_pct' in r.content
    # Nothing saved to DB
    container.refresh_from_db()
    assert container.slots.count() == 0


def test_add_option_button(login, club_admin, club):
    c = login(club_admin)
    container = make_container(club, "Container")
    item1 = Item.objects.create(club=club, name="Item 1", value_cp=1)
    item2 = Item.objects.create(club=club, name="Item 2", value_cp=1)
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
    assert b'slots-0-opts-1-item' in r.content
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
    from items.containers import validate_container_config
    # This should not raise because we don't call it for non-containers
    # But if we did call it, it would fail - so we just verify the flag is off
    assert not container.is_container