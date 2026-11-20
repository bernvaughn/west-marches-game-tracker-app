"""Convert a catalogue item to stacked (story U124).

Mirrors ``seed_pack_containers``: wrapped in a transaction, rolled back on
``--dry-run``, and failing with ``CommandError`` on refusal or a missing
club/item. Calls ``items.services.convert_to_stacked`` with no actor.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Club
from items.models import Item
from items.services import StackedConversionError, conversion_preview, convert_to_stacked


class Command(BaseCommand):
    help = (
        "Convert an item to stacked: owned quantities are multiplied by the "
        "factor once (one ledger entry per holder), shop lines become bundle "
        "lines of the factor size keeping their stock, and junk marks scale. "
        "All or nothing: a refusal writes nothing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--club",
            type=str,
            required=True,
            help="Club slug the item belongs to.",
        )
        parser.add_argument(
            "--item",
            type=str,
            required=True,
            help="Item id or exact item name within the club.",
        )
        parser.add_argument(
            "--unit-name",
            type=str,
            required=True,
            help="Name of one unit after conversion, e.g. sheet, ft or arrow.",
        )
        parser.add_argument(
            "--factor",
            type=int,
            default=1,
            help="How many units one old item is worth (default 1).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run the conversion but roll back all changes.",
        )

    def handle(self, *args, **options):
        club_slug = options["club"]
        item_ref = options["item"]
        unit_name = options["unit_name"]
        factor = options["factor"]
        dry_run = options["dry_run"]

        try:
            club = Club.objects.get(slug=club_slug)
        except Club.DoesNotExist as err:
            raise CommandError(f"Club with slug '{club_slug}' does not exist.") from err

        try:
            item_pk = int(item_ref)
            item = Item.objects.get(pk=item_pk, club=club)
        except (ValueError, TypeError):
            try:
                item = Item.objects.get(club=club, name=item_ref)
            except Item.DoesNotExist as err:
                raise CommandError(f"No item named '{item_ref}' in club '{club.name}'.") from err
        except Item.DoesNotExist as err:
            raise CommandError(f"No item with id {item_pk} in club '{club.name}'.") from err

        self.stdout.write(f"Converting '{item.name}' in club '{club.name}' ({club.slug})")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - changes will be rolled back"))

        preview = conversion_preview(item, factor=factor)
        self.stdout.write("")
        self.stdout.write("Preview:")
        self.stdout.write(f"  Characters holding the item: {len(preview.holders)}")
        self.stdout.write(f"  Total owned: {preview.total_owned}")
        self.stdout.write(f"  Shop lines to convert: {preview.shop_line_count}")
        self.stdout.write(f"  Junk marks to scale: {preview.junk_mark_count}")
        if preview.reference_count:
            self.stdout.write(f"  Non-ledger references (not changed): {preview.reference_count}")
        for reason in preview.refusal_reasons:
            self.stdout.write(self.style.ERROR(f"  Refusal: {reason}"))
        for warning in preview.non_blocking_warnings:
            self.stdout.write(self.style.WARNING(f"  Warning: {warning}"))

        if preview.refusal_reasons:
            raise CommandError("Refused: " + " ".join(preview.refusal_reasons))

        with transaction.atomic():
            try:
                convert_to_stacked(item, factor, unit_name)
            except StackedConversionError as err:
                raise CommandError(str(err)) from err
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run complete - rolled back"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Converted to stacked."))
        self.stdout.write(f"  Characters updated: {len(preview.holders)}")
        self.stdout.write(f"  Units added per holder: owned x ({factor} - 1)")
        self.stdout.write(f"  Shop lines now bundle size {factor}: {preview.shop_line_count}")
        self.stdout.write(f"  Junk marks scaled by {factor}: {preview.junk_mark_count}")
