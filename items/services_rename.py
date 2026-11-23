"""Core service for the rename_seeded_items catch-up command (U152).

This module contains the business logic for:
- Renaming seeded items in place (keeping IDs)
- Merging duplicate items (keeping lower ID, repointing FKs)
- Splitting the map case into Map Case and Scroll Case
- Updating Diplomat's Pack slots to the new choice format
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Sum

from accounts.models import Club
from agent_access.models import ProposedItem, ProposedLine
from downtime.models import DowntimeEntryItem
from items.models import ContainerOpening, ContainerSlot, ContainerSlotOption, Item
from items.seed_names import (
    MAP_CASE,
    OLD_MAP_CASE_NAMES,
    SCROLL_CASE,
    VARIANT_RENAMES,
)
from items.services import delete_or_retire
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import Line, record_many
from player_characters.models import Character, JunkMark
from quests.models import QuestRequirement, QuestReward
from shops.models import ShopStock
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassLine,
    StartingEquipmentRequest,
)


class Refusal(Exception):
    """A step refuses to proceed; the whole run is rolled back."""


@dataclass
class RenameReport:
    """Report of a rename_seeded_items run."""

    renames: list[str] = field(default_factory=list)  # "old_name -> new_name"
    merges: list[str] = field(default_factory=list)  # "source_name -> target_name"
    splits: list[str] = field(default_factory=list)  # "old_case -> Map Case + Scroll Case"
    left_alone: list[str] = field(default_factory=list)  # "item_name: reason"
    refusals: list[str] = field(default_factory=list)  # refusal reason
    nothing_to_do: bool = False


def get_related_objects_to_item():
    """Return all FK relations from other models to Item (for test validation)."""
    return list(Item._meta.related_objects)


def _build_seed_profile():
    """Build a lookup of seeded item profiles from gear and starting equipment seeds.

    Returns dict: name -> (value_cp, symbol, description)
    """
    from shops.gear import GENERAL_STORE_GEAR
    from starting_equipment.seeding import BACKGROUND_EQUIPMENT, CLASS_EQUIPMENT, STACKED_AMMO_SPECS

    profile = {}

    # From GENERAL_STORE_GEAR
    for gear in GENERAL_STORE_GEAR:
        profile[gear.name] = (gear.value_cp, gear.icon, gear.description)

    # From CLASS_EQUIPMENT
    for class_data in CLASS_EQUIPMENT.values():
        for item_data in class_data["items"]:
            name, value_cp, symbol, rarity, magic_type, qty, is_choice, choice_group = item_data
            if name not in profile:
                profile[name] = (value_cp, symbol, "")

    # From BACKGROUND_EQUIPMENT
    for bg_data in BACKGROUND_EQUIPMENT.values():
        for item_data in bg_data["items"]:
            name, value_cp, symbol, rarity, magic_type, qty, is_choice, choice_group = item_data
            if name not in profile:
                profile[name] = (value_cp, symbol, "")

    # Stacked ammo specs may add extra items
    for name, (
        value_cp,
        symbol,
        _rarity,
        _magic_type,
        _unit_name,
        _value_units,
    ) in STACKED_AMMO_SPECS.items():
        if name not in profile:
            profile[name] = (value_cp, symbol, "")

    return profile


SEED_PROFILE = _build_seed_profile()


def _item_matches_seed(item: Item, seed_name: str) -> tuple[bool, list[str]]:
    """Check if item's value_cp, symbol, description match the seed profile for seed_name.

    Returns (matches, list_of_mismatch_reasons).
    """
    if seed_name not in SEED_PROFILE:
        return True, []  # No seed profile means we can't verify; treat as match

    expected_value, expected_symbol, expected_desc = SEED_PROFILE[seed_name]
    reasons = []
    if item.value_cp != expected_value:
        reasons.append(f"value_cp {item.value_cp} != seed {expected_value}")
    if item.symbol != expected_symbol:
        reasons.append(f"symbol {item.symbol!r} != seed {expected_symbol!r}")
    if item.description != expected_desc:
        reasons.append("description differs from seed")
    return len(reasons) == 0, reasons


def _get_non_retired_items(club: Club, name: str) -> list[Item]:
    """Get all non-retired items with this name in the club."""
    return list(Item.objects.filter(club=club, name=name, retired=False).order_by("pk"))


def _net_by_character(item: Item) -> dict[int, int]:
    """Return {character_id: net_quantity} for the item."""
    rows = (
        LedgerLine.objects.filter(item=item)
        .values("entry__character_id")
        .annotate(total=Sum("quantity"))
    )
    return {r["entry__character_id"]: r["total"] or 0 for r in rows}


def _repoint_fk(source: Item, target: Item, log: Callable[[str], None]) -> dict[str, int]:
    """Repoint all FKs from source to target, handling unique constraints.

    Returns a dict of relation_name -> count of rows updated.
    """
    counts = {}

    # Relations to repoint (excluding LedgerLine which is append-only)
    # Format: (accessor_name, model, field_name, unique_fields_list_or_None)
    # unique_fields_list: if not None, these fields plus 'item' form a unique constraint
    relations = [
        # (accessor, model, fk_field, unique_with_item_fields)
        ("slots", ContainerSlot, "container", None),
        ("container_option_uses", ContainerSlotOption, "item", None),
        ("openings", ContainerOpening, "container", None),
        ("stock_entries", ShopStock, "item", ["shop", "bundle_units"]),
        ("questrequirement_set", QuestRequirement, "item", None),
        ("questreward_set", QuestReward, "item", None),
        ("downtimeentryitem_set", DowntimeEntryItem, "item", None),
        ("proposedline_set", ProposedLine, "item", None),
        (
            "startingequipmentclassline_set",
            StartingEquipmentClassLine,
            "item",
            ["class_entry", "is_choice", "choice_group"],
        ),
        (
            "startingequipmentbackgroundline_set",
            StartingEquipmentBackgroundLine,
            "item",
            ["background_entry", "is_choice", "choice_group"],
        ),
        ("magicitemstartingoption_set", MagicItemStartingOption, "item", ["template"]),
        ("startingequipmentrequest_set", StartingEquipmentRequest, "item", None),
        ("junk_marks", JunkMark, "item", ["character"]),
    ]

    for accessor, model, fk_field, unique_with in relations:
        qs = getattr(source, accessor).all()
        if not qs.exists():
            counts[accessor] = 0
            continue

        if unique_with is None:
            # Simple repoint
            updated = qs.update(**{fk_field: target})
            counts[accessor] = updated
            if updated:
                log(f"    Repointed {updated} {model.__name__}.{fk_field}")
        else:
            # Need to handle unique constraint conflicts
            unique_with + ["item"]
            updated = 0
            for obj in qs:
                # Check if target already has a row with same unique fields
                filter_kwargs = {fk_field: target}
                for uf in unique_with:
                    filter_kwargs[uf] = getattr(obj, uf)
                existing = model.objects.filter(**filter_kwargs).first()
                if existing:
                    # Merge: combine quantities if applicable, or just keep one
                    if hasattr(obj, "quantity") and hasattr(existing, "quantity"):
                        existing.quantity += obj.quantity
                        existing.save(update_fields=["quantity"])
                    elif hasattr(obj, "qty_min") and hasattr(existing, "qty_min"):
                        # ContainerSlotOption: merge quantities
                        existing.qty_min += obj.qty_min
                        existing.qty_max += obj.qty_max
                        existing.save(update_fields=["qty_min", "qty_max"])
                    elif hasattr(obj, "max_per_character") and hasattr(
                        existing, "max_per_character"
                    ):
                        # MagicItemStartingOption: keep max
                        existing.max_per_character = max(
                            existing.max_per_character, obj.max_per_character
                        )
                        existing.save(update_fields=["max_per_character"])
                    obj.delete()
                    updated += 1
                    log(f"    Merged duplicate {model.__name__} (unique constraint)")
                else:
                    setattr(obj, fk_field, target)
                    obj.save(update_fields=[fk_field])
                    updated += 1
            counts[accessor] = updated
            if updated:
                log(f"    Repointed/merged {updated} {model.__name__}.{fk_field}")

    # Handle ProposedItem.approved_item (related_name="+", no accessor)
    proposed_items = ProposedItem.objects.filter(approved_item=source)
    pi_updated = proposed_items.update(approved_item=target)
    if pi_updated:
        log(f"    Repointed {pi_updated} ProposedItem.approved_item")
    counts["proposeditem_approved_item"] = pi_updated

    return counts


def _merge_items(club: Club, source: Item, target: Item, log: Callable[[str], None]) -> list[str]:
    """Merge source into target (target has lower ID).

    Returns list of merge report lines.
    """
    report_lines = []

    # 1. Compute holder nets for source
    source_nets = _net_by_character(source)
    _net_by_character(target)

    # Check for negative nets in source
    negative_holders = [cid for cid, net in source_nets.items() if net < 0]
    if negative_holders:
        names = ", ".join(
            Character.objects.filter(pk__in=negative_holders).values_list("name", flat=True)
        )
        raise Refusal(f'"{source.name}": negative net total for holders: {names}.')

    # 2. Prepare ledger entries for holders with net > 0
    specs = []
    note = f'Merged "{source.name}" into "{target.name}"'
    for char_id, net in sorted(source_nets.items()):
        if net <= 0:
            continue
        character = Character.objects.get(pk=char_id)
        specs.append(
            dict(
                character=character,
                kind=LedgerEntry.Kind.ADJUSTMENT,
                lines=[Line(item=source, quantity=-net), Line(item=target, quantity=net)],
                note=note,
                actor=None,
            )
        )

    # 3. Repoint all FKs
    _repoint_fk(source, target, log)

    # 4. Record ledger entries
    if specs:
        record_many(specs)

    # 5. Delete or retire source
    deleted = delete_or_retire(source)
    if deleted:
        log(f'    Deleted source item "{source.name}" (pk={source.pk})')
    else:
        log(f'    Retired source item "{source.name}" (pk={source.pk})')

    report_lines.append(f"{source.name} -> {target.name}")
    return report_lines


def _rename_step(club: Club, log: Callable[[str], None]) -> tuple[list[str], list[str]]:
    """Step 1: Rename items in place where name matches old seed name and item was never edited.

    Only renames if there's exactly one source item for a target and no target exists.
    If multiple items map to the same target, all are deferred to merge step.

    Returns (renames, left_alone).
    """
    renames = []
    left_alone = []

    # Build a set of all target names that already exist (non-retired)
    existing_targets = set(
        Item.objects.filter(
            club=club, name__in=VARIANT_RENAMES.values(), retired=False
        ).values_list("name", flat=True)
    )

    # Group source items by target name
    target_to_sources = {}
    for old_name, new_name in VARIANT_RENAMES.items():
        items = _get_non_retired_items(club, old_name)
        if not items:
            continue
        target_to_sources.setdefault(new_name, []).extend(items)

    # Process each target
    for new_name, source_items in target_to_sources.items():
        # If target already exists in DB, defer all to merge
        if new_name in existing_targets:
            for item in source_items:
                log(f'  "{item.name}": target "{new_name}" exists, deferring to merge')
            continue

        # If multiple source items for this target, defer all to merge
        if len(source_items) > 1:
            for item in source_items:
                log(f'  "{item.name}": multiple sources for "{new_name}", deferring to merge')
            continue

        # Exactly one source item, no target exists - check if it matches seed
        item = source_items[0]
        matches, reasons = _item_matches_seed(item, new_name)
        if matches:
            item.name = new_name
            item.save(update_fields=["name"])
            renames.append(f"{item.name} -> {new_name}")
            log(f'  Renamed "{item.name}" -> "{new_name}" (pk={item.pk})')
            existing_targets.add(new_name)
        else:
            reason = "; ".join(reasons)
            left_alone.append(f"{item.name}: edited ({reason})")
            log(f'  Left alone "{item.name}" (pk={item.pk}): {reason}')

    return renames, left_alone


def _merge_step(club: Club, log: Callable[[str], None]) -> list[str]:
    """Step 2: Merge duplicate items (old names + new names that map to same target).

    Returns list of merge report lines.
    """
    merges = []

    # Build reverse mapping: target_name -> list of source names
    target_to_sources = {}
    for old_name, new_name in VARIANT_RENAMES.items():
        target_to_sources.setdefault(new_name, set()).add(old_name)
    # Also include the target name itself as a possible source
    for target_name in target_to_sources:
        target_to_sources[target_name].add(target_name)

    for target_name, source_names in target_to_sources.items():
        # Gather all items with names in source_names
        items = list(
            Item.objects.filter(club=club, name__in=source_names, retired=False).order_by("pk")
        )
        if len(items) <= 1:
            continue

        # Keep lowest ID as target
        target = items[0]
        sources = items[1:]

        log(f'  Merging {len(sources)} item(s) into "{target.name}" (pk={target.pk})')
        for source in sources:
            merge_lines = _merge_items(club, source, target, log)
            merges.extend(merge_lines)

        # Ensure target has the correct final name
        if target.name != target_name:
            target.name = target_name
            target.save(update_fields=["name"])
            log(f'  Renamed merged target to "{target_name}"')

    return merges


def _split_map_case_step(club: Club, log: Callable[[str], None]) -> list[str]:
    """Step 3: Split the map case.

    - "Case, Map or Scroll" and "Map or Scroll Case" -> "Map Case"
    - Create "Scroll Case" if missing (only if there were old case items or Map Case exists)
    Returns list of split report lines.
    """
    splits = []

    # Find all items with old map case names
    old_items = list(
        Item.objects.filter(club=club, name__in=OLD_MAP_CASE_NAMES, retired=False).order_by("pk")
    )

    # Also check if "Map Case" already exists
    map_case_item = Item.objects.filter(club=club, name=MAP_CASE, retired=False).first()
    if map_case_item:
        old_items.insert(0, map_case_item)  # Put existing Map Case first (lowest ID wins)

    # Only proceed if there are old case items or Map Case exists
    if not old_items:
        # No old case items and no Map Case - nothing to do
        return splits

    if len(old_items) > 1:
        # Merge all into the lowest ID
        target = old_items[0]
        sources = old_items[1:]
        log(f'  Merging {len(sources)} map case item(s) into "{MAP_CASE}" (pk={target.pk})')
        for source in sources:
            merge_lines = _merge_items(club, source, target, log)
            splits.extend(merge_lines)

    # Ensure the survivor is named "Map Case"
    survivor = old_items[0]
    if survivor.name != MAP_CASE:
        survivor.name = MAP_CASE
        survivor.save(update_fields=["name"])
        splits.append(f"{survivor.name} -> {MAP_CASE}")
        log(f'  Renamed map case to "{MAP_CASE}"')

    # Create Scroll Case if missing
    scroll_case = Item.objects.filter(club=club, name=SCROLL_CASE, retired=False).first()
    if not scroll_case:
        scroll_case = Item.objects.create(
            club=club,
            name=SCROLL_CASE,
            value_cp=100,
            symbol="📜",
            description="Holds scrolls.",
            retired=False,
        )
        splits.append(f"Created {SCROLL_CASE}")
        log(f'  Created "{SCROLL_CASE}" (pk={scroll_case.pk})')
    else:
        log(f'  "{SCROLL_CASE}" already exists (pk={scroll_case.pk})')

    # Only report split if something actually changed
    if splits:
        splits.append(f"Split: {', '.join(OLD_MAP_CASE_NAMES)} -> {MAP_CASE} + {SCROLL_CASE}")

    return splits


def _update_diplomats_pack_slots(club: Club, log: Callable[[str], None]) -> list[str]:
    """Step 4: Update Diplomat's Pack slots to new choice format.

    Only updates if pack still has the old seeded shape (fixed slot with 2x Map/Scroll Case).
    Returns list of report lines.
    """
    report = []

    pack = Item.objects.filter(club=club, name="Diplomat's Pack", retired=False).first()
    if not pack:
        log("  Diplomat's Pack not found, skipping")
        return report

    # Check if pack already has slots
    if not pack.slots.exists():
        log("  Diplomat's Pack has no slots, skipping")
        return report

    # Check for old shape: fixed slot at position 1 or 2 with "Map or Scroll Case" qty 2
    # or "Map Case" qty 2 (already partially converted)
    old_shape = False
    case_slots_to_remove = []
    for slot in pack.slots.all().order_by("position"):
        opts = list(slot.options.all())
        if len(opts) == 1:
            opt = opts[0]
            if (
                opt.item.name in ("Map or Scroll Case", "Case, Map or Scroll", "Map Case")
                and opt.qty_min == 2
            ):
                old_shape = True
                case_slots_to_remove.append(slot)

    if not old_shape:
        log("  Diplomat's Pack does not have old seeded shape, leaving alone")
        report.append("Diplomat's Pack: left alone (not old seeded shape)")
        return report

    # Check if already converted to new choice slots (positions 1 and 2 with Map/Scroll options)
    choice_slots = 0
    for slot in pack.slots.all().order_by("position"):
        opts = list(slot.options.all())
        if len(opts) == 2:
            names = {o.item.name for o in opts}
            if names == {MAP_CASE, SCROLL_CASE}:
                choice_slots += 1

    if choice_slots >= 2:
        log("  Diplomat's Pack already has choice slots, leaving alone")
        report.append("Diplomat's Pack: left alone (already converted)")
        return report

    # Remove old case slots
    for slot in case_slots_to_remove:
        log(f"  Removing old case slot at position {slot.position}")
        slot.delete()

    # Find next available positions for new slots
    used_positions = set(pack.slots.values_list("position", flat=True))
    pos1 = 1
    while pos1 in used_positions:
        pos1 += 1
    used_positions.add(pos1)
    pos2 = pos1 + 1
    while pos2 in used_positions:
        pos2 += 1

    # Create new choice slots
    map_case = Item.objects.get(club=club, name=MAP_CASE)
    scroll_case = Item.objects.get(club=club, name=SCROLL_CASE)

    for pos in (pos1, pos2):
        slot = ContainerSlot.objects.create(
            container=pack,
            chance_pct=100,
            unknown=False,
            position=pos,
        )
        ContainerSlotOption.objects.create(slot=slot, item=map_case, qty_min=1, qty_max=1, weight=1)
        ContainerSlotOption.objects.create(
            slot=slot, item=scroll_case, qty_min=1, qty_max=1, weight=1
        )
        log(f"  Created choice slot at position {pos} with Map Case / Scroll Case")

    # Validate
    from items.containers import validate_container_config

    validate_container_config(pack)

    report.append("Diplomat's Pack: updated to two choice slots (Map Case / Scroll Case)")
    return report


def run_rename(
    club: Club, apply: bool = False, log: Callable[[str], None] | None = None
) -> RenameReport:
    """Run the full rename_seeded_items process for a club.

    Args:
        club: The club to process.
        apply: If False, runs in a transaction that is rolled back (dry run).
        log: Optional callback for progress lines.

    Returns:
        RenameReport with all actions taken.
    """
    log = log or (lambda _: None)
    report = RenameReport()

    log(f"Renaming seeded items for club '{club.name}' ({club.slug})")
    if not apply:
        log("DRY RUN - changes will be rolled back")

    with transaction.atomic():
        # Step 1: Rename in place
        log("Step 1: Renaming items in place...")
        renames, left_alone = _rename_step(club, log)
        report.renames.extend(renames)
        report.left_alone.extend(left_alone)

        # Step 2: Merge duplicates
        log("Step 2: Merging duplicate items...")
        merges = _merge_step(club, log)
        report.merges.extend(merges)

        # Step 3: Split map case
        log("Step 3: Splitting map case...")
        splits = _split_map_case_step(club, log)
        report.splits.extend(splits)

        # Step 4: Update Diplomat's Pack slots
        log("Step 4: Updating Diplomat's Pack slots...")
        pack_updates = _update_diplomats_pack_slots(club, log)
        report.left_alone.extend(pack_updates)  # Pack updates reported as left_alone style

        # Check if nothing was done
        if not (report.renames or report.merges or report.splits or report.left_alone):
            report.nothing_to_do = True
            log("Nothing to do.")

        if not apply:
            transaction.set_rollback(True)
            log("Dry run complete - rolled back")

    return report
