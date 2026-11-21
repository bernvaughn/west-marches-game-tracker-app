"""Tests for stacked-item conversion (story U124)."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from accounts.models import Membership, User
from agent_access.models import AgentConnection, ProposedBatch, ProposedLine
from items.models import Item
from items.services import (
    StackedConversionError,
    can_toggle_stacked,
    conversion_preview,
    convert_to_stacked,
)
from items.stacked import bundle_price, unit_label
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import Line, item_quantities, record
from player_characters.models import Character, JunkMark
from shops.models import Shop, ShopStock

pytestmark = [pytest.mark.story("U124"), pytest.mark.django_db]


def url(name, club, *args):
    return reverse(f"items:{name}", args=[club.slug, *args])


def _user(club, email, name):
    user = User.objects.create_user(email, password="pw", display_name=name)
    Membership.objects.create(user=user, club=club)
    return user


def make_character(club, name, user=None):
    if user is None:
        user = _user(club, f"{name.lower()}@example.com", name)
    membership = Membership.objects.get(user=user, club=club)
    return Character.objects.create(club=club, owner=membership, name=name)


@pytest.fixture
def owned_item(club):
    return Item.objects.create(club=club, name="Rope", value_cp=100)


@pytest.fixture
def two_holders(club, owned_item):
    """Two characters, one holding 2 ropes and the other 3."""
    c1 = make_character(club, "Aria")
    c2 = make_character(club, "Borin")
    record(c1, "award", [Line(item=owned_item, quantity=2)])
    record(c2, "award", [Line(item=owned_item, quantity=3)])
    return c1, c2


# ---------------------------------------------------------------------------
# Preview (writes nothing)
# ---------------------------------------------------------------------------


def test_preview_writes_nothing(club, owned_item, two_holders):
    before = LedgerEntry.objects.count()
    preview = conversion_preview(owned_item)
    assert LedgerEntry.objects.count() == before
    assert {h["name"] for h in preview.holders} == {"Aria", "Borin"}
    assert {h["owned"] for h in preview.holders} == {2, 3}
    assert preview.total_owned == 5
    assert preview.refusal_reasons == []
    assert preview.shop_line_count == 0
    assert preview.junk_mark_count == 0


def test_preview_refusal_container(club):
    item = Item.objects.create(club=club, name="Chest", is_container=True)
    preview = conversion_preview(item)
    assert preview.refusal_reasons == ['"Chest" is a container and cannot be stacked.']
    assert not item.is_stacked


def test_preview_refusal_already_stacked(club):
    item = Item.objects.create(
        club=club, name="Rope", is_stacked=True, unit_name="ft", value_units=50
    )
    preview = conversion_preview(item)
    assert preview.refusal_reasons == ['"Rope" is already stacked.']


def test_preview_refusal_pending_agent_proposal(club, owned_item, club_admin, character):
    conn = AgentConnection.objects.create(user=club_admin, club=club, label="agent")
    batch = ProposedBatch.objects.create(
        club=club,
        connection=conn,
        user=club_admin,
        date="2026-01-01",
        idempotency_key="k1",
        status=ProposedBatch.Status.PENDING,
    )
    ProposedLine.objects.create(batch=batch, character=character, item=owned_item, quantity=1)
    preview = conversion_preview(owned_item)
    assert any("pending agent proposal" in r for r in preview.refusal_reasons)


def test_preview_refusal_negative_total(club, owned_item, club_admin):
    from django.utils import timezone

    from ledger.models import LedgerEntry, LedgerLine

    c1 = make_character(club, "Aria")
    c2 = make_character(club, "Borin")
    record(c1, "award", [Line(item=owned_item, quantity=2)])
    # Create a negative net total directly via ledger entries (bypassing validation)
    entry = LedgerEntry.objects.create(
        character=c2,
        club=club,
        kind=LedgerEntry.Kind.ADJUSTMENT,
        note="test",
        date=timezone.localdate(),
    )
    LedgerLine.objects.create(entry=entry, item=owned_item, quantity=-1)
    preview = conversion_preview(owned_item)
    assert any("negative" in r for r in preview.refusal_reasons)
    assert any("Borin" in r for r in preview.refusal_reasons)
    # Aria (net +2) should not be in the refusal
    assert not any("Aria" in r for r in preview.refusal_reasons)


def test_preview_net_zero_skipped_not_refused(club, owned_item, club_admin):
    c1 = make_character(club, "Aria")
    c2 = make_character(club, "Borin")
    record(c1, "award", [Line(item=owned_item, quantity=2)])
    record(c2, "award", [Line(item=owned_item, quantity=1)])
    record(c2, "consumed", [Line(item=owned_item, quantity=-1)])  # net zero
    preview = conversion_preview(owned_item)
    assert preview.refusal_reasons == []  # no refusal for net zero
    # Borin should be marked as skipped
    borin = next(h for h in preview.holders if h["name"] == "Borin")
    assert borin["skipped"] is True
    assert borin["owned"] == 0
    assert borin["new"] == 0
    # Aria should not be skipped
    aria = next(h for h in preview.holders if h["name"] == "Aria")
    assert aria["skipped"] is False
    assert aria["owned"] == 2


def test_preview_overflow(club, club_admin):
    item = Item.objects.create(club=club, name="Rope", value_cp=1)
    c = make_character(club, "Aria")
    record(c, "award", [Line(item=item, quantity=2147483647)])
    preview = conversion_preview(item, factor=2)
    assert any("2147483647" in r for r in preview.refusal_reasons)


def test_preview_shows_non_ledger_references_as_warning(club, owned_item, club_admin):
    from quests.models import Quest, QuestRequirement

    quest = Quest.objects.create(club=club, name="The Quest")
    QuestRequirement.objects.create(quest=quest, item=owned_item, quantity=1)
    preview = conversion_preview(owned_item)
    assert preview.reference_count >= 1
    assert any("quest" in w.lower() for w in preview.non_blocking_warnings)


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def test_convert_multiplies_owned_quantities_once(club, owned_item, two_holders):
    c1, c2 = two_holders
    convert_to_stacked(owned_item, 50, "ft")
    owned_item.refresh_from_db()
    assert owned_item.is_stacked
    assert owned_item.unit_name == "ft"
    assert owned_item.value_units == 50
    assert owned_item.value_cp == 100  # unchanged

    assert item_quantities(c1)[owned_item.pk] == 100  # 2 * 50
    assert item_quantities(c2)[owned_item.pk] == 150  # 3 * 50

    # Second call is refused: already stacked.
    with pytest.raises(StackedConversionError):
        convert_to_stacked(owned_item, 2, "ft")
    owned_item.refresh_from_db()
    assert item_quantities(c1)[owned_item.pk] == 100  # unchanged


def test_convert_writes_one_adjustment_entry_per_holder(club, owned_item, two_holders):
    c1, c2 = two_holders
    adjustments_before = LedgerEntry.objects.filter(kind=LedgerEntry.Kind.ADJUSTMENT).count()
    convert_to_stacked(owned_item, 2, "ft")
    owned_item.refresh_from_db()
    entries = LedgerEntry.objects.filter(kind=LedgerEntry.Kind.ADJUSTMENT).order_by("id")
    assert entries.count() == adjustments_before + 2
    note = f"Converted to stacked item: each {owned_item.name} is now {unit_label(owned_item, 2)}"
    new_entries = list(entries)[-2:]
    assert all(e.kind == LedgerEntry.Kind.ADJUSTMENT and e.note == note for e in new_entries)
    deltas = sorted(e.lines.first().quantity for e in new_entries)
    assert deltas == [2, 3]  # 2 * (2 - 1) and 3 * (2 - 1)


def test_convert_delta_and_non_holders(club, owned_item, club_admin):
    c1 = make_character(club, "Aria")
    c2 = make_character(club, "Borin")
    bystander = make_character(club, "Neutral")
    record(c1, "award", [Line(item=owned_item, quantity=4)])
    record(c2, "award", [Line(item=owned_item, quantity=1)])
    convert_to_stacked(owned_item, 3, "ft")
    assert item_quantities(c1)[owned_item.pk] == 12  # 4 * 3
    assert item_quantities(c2)[owned_item.pk] == 3  # 1 * 3
    assert owned_item.pk not in item_quantities(bystander)
    entries = LedgerEntry.objects.filter(kind=LedgerEntry.Kind.ADJUSTMENT).order_by("id")
    assert entries.count() == 2
    deltas = sorted(e.lines.first().quantity for e in entries)
    assert deltas == [2, 8]  # 1 * (3 - 1) and 4 * (3 - 1)


def test_convert_factor_one_writes_no_entries(club, owned_item, two_holders):
    c1, c2 = two_holders
    entries_before = LedgerEntry.objects.count()
    convert_to_stacked(owned_item, 1, "ft")
    owned_item.refresh_from_db()
    assert owned_item.is_stacked
    assert owned_item.value_units == 1
    assert LedgerEntry.objects.count() == entries_before


def test_convert_shop_lines_become_bundle_lines(club, club_admin):
    item = Item.objects.create(club=club, name="Rope", value_cp=100)
    shop = Shop.objects.create(club=club, name="General Store")
    line = ShopStock.objects.create(
        shop=shop, item=item, bundle_units=1, quantity=7, sell_percent=100, buy_percent=50
    )
    convert_to_stacked(item, 20, "ft")
    item.refresh_from_db()
    line.refresh_from_db()
    assert line.bundle_units == 20
    assert line.quantity == 7  # stock count unchanged
    assert line.sell_percent == 100
    assert line.buy_percent == 50
    assert bundle_price(item, 20, 100) == 100  # same as the old whole-copper sell price


def test_convert_junk_marks_scaled(club, owned_item, two_holders):
    c1, c2 = two_holders
    JunkMark.objects.create(character=c1, item=owned_item, quantity=3)
    JunkMark.objects.create(character=c2, item=owned_item, quantity=4)
    convert_to_stacked(owned_item, 10, "ft")
    assert JunkMark.objects.get(character=c1, item=owned_item).quantity == 30
    assert JunkMark.objects.get(character=c2, item=owned_item).quantity == 40


def test_convert_all_or_nothing(club, club_admin):
    from django.utils import timezone

    from ledger.models import LedgerEntry, LedgerLine

    item = Item.objects.create(club=club, name="Rope", value_cp=100)
    c1 = make_character(club, "Aria")
    c2 = make_character(club, "Borin")
    record(c1, "award", [Line(item=item, quantity=2)])
    record(c2, "award", [Line(item=item, quantity=1)])
    # Create a negative net total directly via ledger entries (bypassing validation)
    entry = LedgerEntry.objects.create(
        character=c2,
        club=club,
        kind=LedgerEntry.Kind.ADJUSTMENT,
        note="test",
        date=timezone.localdate(),
    )
    LedgerLine.objects.create(entry=entry, item=item, quantity=-2)  # c2 net -1 -> refusal

    entries_before = LedgerEntry.objects.count()
    with pytest.raises(StackedConversionError):
        convert_to_stacked(item, 5, "ft")
    item.refresh_from_db()
    assert not item.is_stacked
    assert item.unit_name == ""
    assert item.value_units == 1
    assert LedgerEntry.objects.count() == entries_before  # nothing written


def test_convert_net_zero_skipped_no_ledger_entry(club, club_admin):
    item = Item.objects.create(club=club, name="Rope", value_cp=100)
    c1 = make_character(club, "Aria")
    c2 = make_character(club, "Borin")
    record(c1, "award", [Line(item=item, quantity=2)])
    record(c2, "award", [Line(item=item, quantity=1)])
    record(c2, "consumed", [Line(item=item, quantity=-1)])  # c2 net zero

    entries_before = LedgerEntry.objects.count()
    convert_to_stacked(item, 5, "ft")
    item.refresh_from_db()
    assert item.is_stacked
    assert item.unit_name == "ft"
    assert item.value_units == 5
    # Only Aria should have an adjustment entry (Borin net zero -> skipped)
    assert LedgerEntry.objects.count() == entries_before + 1
    # Quantities: Aria 2 * 5 = 10, Borin 0 * 5 = 0 (no ledger entry for Borin)
    assert item_quantities(c1)[item.pk] == 10
    assert item.pk not in item_quantities(c2)  # zero net means not in dict


def test_convert_refusals_write_nothing(club, club_admin, character):
    cases = [
        Item.objects.create(club=club, name="Chest", is_container=True),
        Item.objects.create(
            club=club, name="Sack", is_stacked=True, unit_name="slot", value_units=1
        ),
    ]
    for item in cases:
        was_stacked = item.is_stacked
        entries_before = LedgerEntry.objects.count()
        with pytest.raises(StackedConversionError):
            convert_to_stacked(item, 3, "unit")
        item.refresh_from_db()
        assert LedgerEntry.objects.count() == entries_before
        assert item.is_stacked == was_stacked
        assert item.unit_name == ("slot" if was_stacked else "")


def test_convert_rejects_bad_factor_and_unit_name(club, owned_item):
    with pytest.raises(StackedConversionError):
        convert_to_stacked(owned_item, 0, "ft")
    with pytest.raises(StackedConversionError):
        convert_to_stacked(owned_item, 1, "")
    with pytest.raises(StackedConversionError):
        convert_to_stacked(owned_item, 1, "x" * 41)
    owned_item.refresh_from_db()
    assert not owned_item.is_stacked


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def test_convert_get_shows_preview_and_writes_nothing(
    login, club_admin, club, owned_item, two_holders
):
    c = login(club_admin)
    lines_before = LedgerLine.objects.filter(item=owned_item).count()
    r = c.get(url("convert", club, owned_item.pk))
    assert r.status_code == 200
    assert b"Aria" in r.content
    assert b"Borin" in r.content
    assert b"Conversion impact" in r.content
    owned_item.refresh_from_db()
    assert not owned_item.is_stacked
    assert LedgerLine.objects.filter(item=owned_item).count() == lines_before


def test_convert_get_refused_item_redirects(login, club_admin, club):
    item = Item.objects.create(club=club, name="Chest", is_container=True)
    c = login(club_admin)
    r = c.get(url("convert", club, item.pk))
    assert r.status_code == 302  # refused items send you back to the detail page


def test_convert_full_flow(login, club_admin, club, owned_item, two_holders):
    c = login(club_admin)
    # Step 1: preview (no confirm) -> confirm step, nothing written yet.
    r = c.post(url("convert", club, owned_item.pk), {"unit_name": "ft", "factor": "2"})
    assert r.status_code == 200
    assert b'name="confirm" value="1"' in r.content
    assert b"Confirm conversion" in r.content
    owned_item.refresh_from_db()
    assert not owned_item.is_stacked

    # Step 2: confirm.
    r = c.post(
        url("convert", club, owned_item.pk),
        {"confirm": "1", "unit_name": "ft", "factor": "2"},
        follow=True,
    )
    assert r.status_code == 200
    assert b"Converted" in r.content
    owned_item.refresh_from_db()
    assert owned_item.is_stacked
    assert owned_item.unit_name == "ft"
    assert owned_item.value_units == 2
    assert item_quantities(two_holders[0])[owned_item.pk] == 4
    assert item_quantities(two_holders[1])[owned_item.pk] == 6
    assert LedgerEntry.objects.filter(kind=LedgerEntry.Kind.ADJUSTMENT).count() == 2


def test_convert_post_without_confirm_validates(login, club_admin, club, owned_item):
    c = login(club_admin)
    r = c.post(url("convert", club, owned_item.pk), {"unit_name": "", "factor": "0"})
    assert r.status_code == 200
    assert b"Unit name" in r.content
    owned_item.refresh_from_db()
    assert not owned_item.is_stacked


def test_convert_view_refusal_writes_nothing(login, club_admin, club, character):
    item = Item.objects.create(club=club, name="Chest", is_container=True)
    record(character, "award", [Line(item=item, quantity=1)])
    c = login(club_admin)
    entries_before = LedgerEntry.objects.count()
    r = c.post(
        url("convert", club, item.pk),
        {"confirm": "1", "unit_name": "slot", "factor": "2"},
    )
    assert r.status_code == 302  # refused items send you back to the detail page
    item.refresh_from_db()
    assert not item.is_stacked
    assert LedgerEntry.objects.count() == entries_before


# ---------------------------------------------------------------------------
# View permissions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("who,status", [("club_admin", 200), ("game_master", 403), ("player", 403)])
def test_convert_permissions_matrix(request, login, club, who, status, owned_item):
    c = login(request.getfixturevalue(who))
    assert c.get(url("convert", club, owned_item.pk)).status_code == status
    assert (
        c.post(url("convert", club, owned_item.pk), {"unit_name": "ft", "factor": "2"}).status_code
        == status
    )


def test_convert_anonymous_redirects(client, club, owned_item):
    assert client.get(url("convert", club, owned_item.pk)).status_code == 302


def test_convert_other_club_admin_404(login, club_admin, other_club, owned_item):
    c = login(club_admin)
    assert c.get(url("convert", other_club, owned_item.pk)).status_code == 404
    assert (
        c.post(
            url("convert", other_club, owned_item.pk), {"unit_name": "ft", "factor": "2"}
        ).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------


def test_command_happy_path(club, owned_item, two_holders):
    out = StringIO()
    call_command(
        "convert_to_stacked",
        "--club",
        club.slug,
        "--item",
        str(owned_item.pk),
        "--unit-name",
        "ft",
        "--factor",
        "3",
        stdout=out,
    )
    owned_item.refresh_from_db()
    assert owned_item.is_stacked
    assert owned_item.unit_name == "ft"
    assert owned_item.value_units == 3
    text = out.getvalue()
    assert "Converted to stacked." in text
    assert "Characters updated: 2" in text


def test_command_dry_run_rolls_back(club, owned_item, two_holders):
    out = StringIO()
    lines_before = LedgerLine.objects.filter(item=owned_item).count()
    call_command(
        "convert_to_stacked",
        "--club",
        club.slug,
        "--item",
        owned_item.name,
        "--unit-name",
        "ft",
        "--factor",
        "3",
        "--dry-run",
        stdout=out,
    )
    owned_item.refresh_from_db()
    assert not owned_item.is_stacked
    assert LedgerLine.objects.filter(item=owned_item).count() == lines_before
    assert "DRY RUN" in out.getvalue()
    assert "rolled back" in out.getvalue()


def test_command_unknown_club(club):
    with pytest.raises(CommandError):
        call_command(
            "convert_to_stacked",
            "--club",
            "no-such-club",
            "--item",
            "x",
            "--unit-name",
            "ft",
            stdout=StringIO(),
        )


def test_command_unknown_item(club):
    with pytest.raises(CommandError):
        call_command(
            "convert_to_stacked",
            "--club",
            club.slug,
            "--item",
            "no such item",
            "--unit-name",
            "ft",
            stdout=StringIO(),
        )


def test_command_container_refusal(club):
    item = Item.objects.create(club=club, name="Chest", is_container=True)
    with pytest.raises(CommandError):
        call_command(
            "convert_to_stacked",
            "--club",
            club.slug,
            "--item",
            str(item.pk),
            "--unit-name",
            "slot",
            stdout=StringIO(),
        )


# ---------------------------------------------------------------------------
# Django admin
# ---------------------------------------------------------------------------


def test_admin_convert_view_superuser(login, site_admin, club, owned_item, two_holders):
    c = login(site_admin)
    r = c.get(reverse("admin:items_item_convert", args=[owned_item.pk]))
    assert r.status_code == 200
    r = c.post(
        reverse("admin:items_item_convert", args=[owned_item.pk]),
        {"unit_name": "ft", "factor": "4"},
    )
    assert r.status_code == 302
    owned_item.refresh_from_db()
    assert owned_item.is_stacked
    assert owned_item.unit_name == "ft"
    assert owned_item.value_units == 4


def test_admin_convert_view_refusal(login, site_admin, club):
    item = Item.objects.create(club=club, name="Chest", is_container=True)
    c = login(site_admin)
    r = c.post(
        reverse("admin:items_item_convert", args=[item.pk]),
        {"unit_name": "slot", "factor": "2"},
    )
    assert r.status_code == 200
    item.refresh_from_db()
    assert not item.is_stacked


def test_admin_convert_denied_non_superuser(login, club_admin, club, owned_item):
    c = login(club_admin)
    assert (
        c.get(reverse("admin:items_item_convert", args=[owned_item.pk])).status_code == 302
    )  # admin login redirect


def test_can_toggle_stacked_false_for_referenced_item(club, owned_item, club_admin):
    c = make_character(club, "Aria")
    record(c, "award", [Line(item=owned_item, quantity=1)])
    assert can_toggle_stacked(owned_item) is False
    unreferenced = Item.objects.create(club=club, name="Untouched", value_cp=1)
    assert can_toggle_stacked(unreferenced) is True
