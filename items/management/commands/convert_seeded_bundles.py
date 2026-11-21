"""Convert all seeded bundle items to stacked items for an existing club (story U124/U125).

This command finds the old plain bundle items (e.g., "Arrows (20)", "Crossbow Bolt")
and converts them to the new stacked items ("Arrows", "Crossbow Bolts") using the
existing `items.services.convert_to_stacked`. It also merges the duplicate
"Crossbow Bolt" / "Arrow" items from starting equipment into the stacked items.

Run with --dry-run first to preview changes. Use --apply to commit.

For each club it:
1. Converts old bundle-named items ("Arrows (20)" -> "Arrows" stacked, factor=20)
2. Merges old plain ammo items ("Crossbow Bolt" -> "Crossbow Bolts" stacked) with ledger transfer
3. Refuses if any character holds BOTH the old plain ammo AND the old bundle item
4. Is idempotent: running twice changes nothing
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from accounts.models import Club
from items.models import Item
from items.services import (
    StackedConversionError,
    conversion_preview,
    convert_to_stacked,
    delete_or_retire,
)
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import Line, record_many
from player_characters.models import Character

# Mapping from old bundle item name to (new stacked item name, factor, unit_name)
# These match the gear list and starting equipment specs.
BUNDLE_CONVERSIONS = [
    ("Arrows (20)", "Arrows", 20, "arrow"),
    ("Crossbow Bolts (20)", "Crossbow Bolts", 20, "bolt"),
    ("Firearm Bullets (10)", "Firearm Bullets", 10, "bullet"),
    ("Sling Bullets (20)", "Sling Bullets", 20, "bullet"),
    ("Needles (50)", "Needles", 50, "needle"),
    ("Caltrops", "Caltrops", 20, "caltrop"),
    ("Ball Bearings", "Ball Bearings", 1000, "ball bearing"),
    ("Spikes, Iron", "Spikes, Iron", 10, "spike"),
]

# Mapping from old plain ammo item name to new stacked item name
# These are the separate "Crossbow Bolt" (qty 1, value 1 cp) items from
# starting equipment that need to be merged into the stacked "Crossbow Bolts".
PLAIN_AMMO_MERGES = [
    ("Crossbow Bolt", "Crossbow Bolts"),
    ("Arrow", "Arrows"),
]


class Command(BaseCommand):
    help = (
        "Convert seeded bundle items to stacked items for a club. "
        "Dry run by default; use --apply to commit changes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--club",
            type=str,
            required=True,
            help="Club slug to convert.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes (default is dry run).",
        )

    def handle(self, *args, **options):
        club_slug = options["club"]
        apply = options["apply"]

        try:
            club = Club.objects.get(slug=club_slug)
        except Club.DoesNotExist as err:
            raise CommandError(f"Club with slug '{club_slug}' does not exist.") from err

        self.stdout.write(f"Converting seeded bundles for club '{club.name}' ({club.slug})")
        if not apply:
            self.stdout.write(self.style.WARNING("DRY RUN - changes will be rolled back"))

        total_converted = 0
        total_merged = 0
        errors = []

        with transaction.atomic():
            # Step 1: Convert bundle-named items to stacked
            for old_name, new_name, factor, unit_name in BUNDLE_CONVERSIONS:
                result = self._convert_bundle_item(
                    club, old_name, new_name, factor, unit_name, apply
                )
                if result is True:
                    total_converted += 1
                elif isinstance(result, str):
                    errors.append(result)

            # Step 2: Merge plain ammo items into stacked items
            for old_name, new_name in PLAIN_AMMO_MERGES:
                result = self._merge_plain_ammo(club, old_name, new_name, apply)
                if result is True:
                    total_merged += 1
                elif isinstance(result, str):
                    errors.append(result)

            if errors:
                for err in errors:
                    self.stdout.write(self.style.ERROR(f"  {err}"))
                raise CommandError(f"{len(errors)} conversion(s) refused; see errors above.")

            if not apply:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run complete - rolled back"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Conversion complete."))
        self.stdout.write(f"  Bundle items converted: {total_converted}")
        self.stdout.write(f"  Plain ammo items merged: {total_merged}")

    def _convert_bundle_item(self, club, old_name, new_name, factor, unit_name, apply):
        """Convert a bundle-named item (e.g., 'Arrows (20)') to stacked ('Arrows')."""
        try:
            old_item = Item.objects.get(club=club, name=old_name)
        except Item.DoesNotExist:
            self.stdout.write(f"  {old_name}: not found, skipping")
            return None
        except Item.MultipleObjectsReturned:
            return f"{old_name}: multiple items exist, refusing"

        # Check if already converted (either already stacked with correct name, or retired)
        if old_item.name == new_name and old_item.is_stacked and old_item.value_units == factor:
            self.stdout.write(f"  {old_name}: already converted, skipping")
            return None
        if old_item.retired:
            self.stdout.write(f"  {old_name}: retired, skipping")
            return None

        # Check if new item already exists (and is not the same item)
        if old_name != new_name:
            try:
                new_item = Item.objects.get(club=club, name=new_name)
                if not new_item.retired:
                    return f"{old_name}: target '{new_name}' already exists, refusing"
            except Item.DoesNotExist:
                pass
            except Item.MultipleObjectsReturned:
                return f"{old_name}: multiple target items '{new_name}' exist, refusing"

        preview = conversion_preview(old_item, factor=factor)
        self.stdout.write(
            f"  {old_name}: {len(preview.holders)} holders, {preview.total_owned} total owned"
        )

        if preview.refusal_reasons:
            return f"{old_name}: " + " ".join(preview.refusal_reasons)

        if not apply:
            return True  # dry run would succeed

        # Rename the item first, then convert
        # We need to rename before converting because convert_to_stacked doesn't rename
        old_item.name = new_name
        old_item.save(update_fields=["name"])

        try:
            convert_to_stacked(old_item, factor, unit_name)
        except StackedConversionError as err:
            raise CommandError(f"{old_name}: {err}") from err

        self.stdout.write(
            f"    Converted to stacked: {new_name} (factor={factor}, unit={unit_name})"
        )
        return True

    def _merge_plain_ammo(self, club, old_name, new_name, apply):
        """Merge plain ammo item (e.g., 'Crossbow Bolt') into stacked item ('Crossbow Bolts')."""
        try:
            old_item = Item.objects.get(club=club, name=old_name)
        except Item.DoesNotExist:
            self.stdout.write(f"  {old_name}: not found, skipping")
            return None
        except Item.MultipleObjectsReturned:
            return f"{old_name}: multiple items exist, refusing"

        if old_item.retired:
            self.stdout.write(f"  {old_name}: already retired, skipping")
            return None

        # Get the target stacked item
        try:
            new_item = Item.objects.get(club=club, name=new_name)
        except Item.DoesNotExist:
            return f"{old_name}: target '{new_name}' not found, refusing"
        except Item.MultipleObjectsReturned:
            return f"{old_name}: multiple target items '{new_name}' exist, refusing"

        if not new_item.is_stacked:
            return f"{old_name}: target '{new_name}' is not stacked, refusing"

        factor = new_item.value_units

        # Check for characters holding BOTH items
        old_holders = set(
            LedgerLine.objects.filter(item=old_item)
            .values_list("entry__character_id", flat=True)
            .distinct()
        )
        new_holders = set(
            LedgerLine.objects.filter(item=new_item)
            .values_list("entry__character_id", flat=True)
            .distinct()
        )
        both_holders = old_holders & new_holders
        if both_holders:
            chars = Character.objects.filter(pk__in=both_holders)
            names = ", ".join(c.name for c in chars)
            return f"{old_name}: characters hold both '{old_name}' AND '{new_name}': {names}"

        # Preview the merge
        old_rows = (
            LedgerLine.objects.filter(item=old_item)
            .values("entry__character_id")
            .annotate(total=Sum("quantity"))
            .order_by("entry__character_id")
        )
        total_old = sum(r["total"] or 0 for r in old_rows)
        self.stdout.write(
            f"  {old_name}: {len(old_rows)} holders, {total_old} total units -> {new_name}"
        )

        if not apply:
            return True  # dry run would succeed

        # Transfer ledger quantities: negative on old, positive on new
        transfer_specs = []
        note = f"Merged '{old_name}' into stacked '{new_name}'"
        for row in old_rows:
            owned = row["total"] or 0
            if owned <= 0:
                continue
            character = Character.objects.get(pk=row["entry__character_id"])
            # Subtract from old item
            transfer_specs.append(
                dict(
                    character=character,
                    kind=LedgerEntry.Kind.ADJUSTMENT,
                    lines=[Line(item=old_item, quantity=-owned)],
                    note=note,
                    actor=None,
                )
            )
            # Add to new item (convert to units)
            transfer_specs.append(
                dict(
                    character=character,
                    kind=LedgerEntry.Kind.ADJUSTMENT,
                    lines=[Line(item=new_item, quantity=owned * factor)],
                    note=note,
                    actor=None,
                )
            )

        if transfer_specs:
            record_many(transfer_specs)

        # Update starting equipment lines that reference the old item
        from starting_equipment.models import (
            StartingEquipmentBackgroundLine,
            StartingEquipmentClassLine,
        )

        StartingEquipmentClassLine.objects.filter(item=old_item).update(item=new_item)
        StartingEquipmentBackgroundLine.objects.filter(item=old_item).update(item=new_item)

        # Retire the old item (it's referenced so it will be retired, not deleted)
        delete_or_retire(old_item)

        self.stdout.write(f"    Merged into {new_name}, retired {old_name}")
        return True
