"""Management command to seed 5e packs as containers with fixed slots."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Club
from items.containers import validate_container_config
from items.models import ContainerSlot, ContainerSlotOption, Item

# Pack definitions: pack name -> list of (content name, qty_min, qty_max, value_cp, symbol)
# Based on 2024 PHB contents. All slots are fixed (chance 100, one option, not unknown).
PACKS = {
    "Diplomat's Pack": [
        ("Fine clothes", 1, 1, 1500, "👔"),
        ("Flask of oil", 1, 2, 100, "🛢️"),
        ("Vial of perfume", 1, 1, 500, "🧴"),
        ("Sealing wax", 1, 1, 50, "🕯️"),
        ("Sealed letter", 1, 1, 10, "📜"),
    ],
    "Explorer's Pack": [
        ("Backpack", 1, 1, 200, "🎒"),
        ("Bedroll", 1, 1, 100, "🛌"),
        ("Mess kit", 1, 1, 20, "🍳"),
        ("Tinderbox", 1, 1, 50, "🔥"),
        ("Torch", 10, 10, 1, "🔦"),
        ("Ration", 10, 10, 50, "🍞"),
        ("Waterskin", 1, 1, 20, "💧"),
        ("Hempen rope (50 ft)", 1, 1, 100, "🪢"),
    ],
    "Priest's Pack": [
        ("Backpack", 1, 1, 200, "🎒"),
        ("Blanket", 1, 1, 50, "🛌"),
        ("Candle", 10, 10, 1, "🕯️"),
        ("Tinderbox", 1, 1, 50, "🔥"),
        ("Alms box", 1, 1, 10, "📦"),
        ("Block of incense", 2, 2, 10, "🕯️"),
        ("Censer", 1, 1, 50, "⚱️"),
        ("Vestments", 1, 1, 500, "👘"),
        ("Ration", 2, 2, 50, "🍞"),
        ("Waterskin", 1, 1, 20, "💧"),
    ],
    "Dungeoneer's Pack": [
        ("Backpack", 1, 1, 200, "🎒"),
        ("Crowbar", 1, 1, 200, "🔨"),
        ("Hammer", 1, 1, 100, "🔨"),
        ("Piton", 10, 10, 5, "⚓"),
        ("Torch", 10, 10, 1, "🔦"),
        ("Tinderbox", 1, 1, 50, "🔥"),
        ("Ration", 10, 10, 50, "🍞"),
        ("Waterskin", 1, 1, 20, "💧"),
        ("Hempen rope (50 ft)", 1, 1, 100, "🪢"),
    ],
    "Burglar's Pack": [
        ("Backpack", 1, 1, 200, "🎒"),
        ("Ball bearings (1,000)", 1, 1, 100, "⚪"),
        ("String (10 ft)", 1, 1, 1, "🧵"),
        ("Bell", 1, 1, 10, "🔔"),
        ("Candle", 5, 5, 1, "🕯️"),
        ("Crowbar", 1, 1, 200, "🔨"),
        ("Hammer", 1, 1, 100, "🔨"),
        ("Piton", 10, 10, 5, "⚓"),
        ("Hooded lantern", 1, 1, 500, "🏮"),
        ("Oil (flask)", 2, 2, 100, "🛢️"),
        ("Ration", 5, 5, 50, "🍞"),
        ("Tinderbox", 1, 1, 50, "🔥"),
        ("Waterskin", 1, 1, 20, "💧"),
        ("Hempen rope (50 ft)", 1, 1, 100, "🪢"),
    ],
    "Scholar's Pack": [
        ("Backpack", 1, 1, 200, "🎒"),
        ("Book", 1, 1, 2500, "📖"),
        ("Ink pen", 1, 1, 20, "🖋️"),
        ("Ink (1 oz)", 1, 1, 100, "🖋️"),
        ("Parchment (10 sheets)", 1, 1, 100, "📜"),
        ("Little bag of sand", 1, 1, 1, "🏖️"),
        ("Small knife", 1, 1, 20, "🔪"),
    ],
    "Entertainer's Pack": [
        ("Backpack", 1, 1, 200, "🎒"),
        ("Bedroll", 1, 1, 100, "🛌"),
        ("Costume", 2, 2, 500, "🎭"),
        ("Ration", 5, 5, 50, "🍞"),
        ("Waterskin", 1, 1, 20, "💧"),
        ("Instrument (lute)", 1, 1, 3500, "🎵"),
        ("Mirror", 1, 1, 500, "🪞"),
    ],
}


class Command(BaseCommand):
    help = (
        "Seed 5e packs as containers with fixed slots for a club. "
        "Idempotent: existing packs with slots are skipped. "
        "Only configures packs already in the club's catalogue."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--club",
            type=str,
            required=True,
            help="Club slug to seed packs for.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run the command but roll back all changes.",
        )

    def handle(self, *args, **options):
        club_slug = options["club"]
        dry_run = options["dry_run"]

        try:
            club = Club.objects.get(slug=club_slug)
        except Club.DoesNotExist as err:
            raise CommandError(f"Club with slug '{club_slug}' does not exist.") from err

        self.stdout.write(f"Seeding pack containers for club: {club.name} ({club.slug})")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - changes will be rolled back"))

        packs_configured = 0
        packs_skipped_not_in_catalogue = 0
        packs_skipped_already_configured = 0

        with transaction.atomic():
            for pack_name, contents in PACKS.items():
                result = self._process_pack(
                    club,
                    pack_name,
                    contents,
                    dry_run,
                )
                if result == "configured":
                    packs_configured += 1
                elif result == "not_in_catalogue":
                    packs_skipped_not_in_catalogue += 1
                elif result == "already_configured":
                    packs_skipped_already_configured += 1

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run complete - rolled back"))

        # Summary
        self.stdout.write("")
        self.stdout.write("Summary:")
        self.stdout.write(f"  Packs configured: {packs_configured}")
        self.stdout.write(f"  Packs skipped (not in catalogue): {packs_skipped_not_in_catalogue}")
        self.stdout.write(
            f"  Packs skipped (already configured): {packs_skipped_already_configured}"
        )

    def _process_pack(self, club, pack_name, contents, dry_run):
        """Process a single pack. Returns status string."""
        # Find the pack item in the club (case-insensitive, prefer non-retired)
        pack = (
            Item.objects.filter(club=club, name__iexact=pack_name).order_by("retired", "pk").first()
        )
        if not pack:
            self.stdout.write(f"  {pack_name}: not in catalogue, skipping")
            return "not_in_catalogue"

        # Check if already configured (has slots)
        if pack.slots.exists():
            self.stdout.write(f"  {pack_name}: already configured, skipping")
            return "already_configured"

        # Set is_container if not already
        if not pack.is_container:
            pack.is_container = True
            pack.save(update_fields=["is_container"])
            self.stdout.write(f"  {pack_name}: set is_container=True")

        # Create content items and slots
        content_items_created = 0

        for position, (content_name, qty_min, qty_max, value_cp, symbol) in enumerate(contents):
            # Skip if content is the pack itself
            if content_name.lower() == pack_name.lower():
                continue

            # Reuse or create content item (case-insensitive, prefer non-retired)
            content_item = (
                Item.objects.filter(club=club, name__iexact=content_name)
                .order_by("retired", "pk")
                .first()
            )
            if not content_item:
                content_item = Item.objects.create(
                    club=club,
                    name=content_name,
                    value_cp=value_cp,
                    symbol=symbol,
                    retired=False,
                    is_container=False,
                )
                content_items_created += 1
                self.stdout.write(f"    Created content item: {content_name}")

            # Create slot
            slot = ContainerSlot.objects.create(
                container=pack,
                chance_pct=100,
                unknown=False,
                position=position,
            )

            # Create single option for this slot (fixed or ranged quantity)
            ContainerSlotOption.objects.create(
                slot=slot,
                item=content_item,
                qty_min=qty_min,
                qty_max=qty_max,
                weight=1,
            )

        # Validate the container configuration
        try:
            validate_container_config(pack)
        except Exception as e:
            raise CommandError(f"Validation failed for {pack_name}: {e}") from e

        self.stdout.write(
            f"  {pack_name}: configured ({len(contents)} slots, "
            f"{content_items_created} new content items)"
        )
        return "configured"
