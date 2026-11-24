"""Backfill SRD weights onto seeded items for an existing club (story U154 seeding).

Dry run by default: the whole run executes inside one transaction and is
rolled back unless ``--apply`` is given, so a dry run shows exactly what an
apply would do without writing anything. Running it twice changes nothing.

Per club it:
1. Builds ``{name: weight_hundredths}`` from ``shops/gear.GENERAL_STORE_GEAR``
   and ``starting_equipment.seeding.STARTING_EQUIPMENT_WEIGHTS``.
2. For each seeded name with a weight, finds the club item by exact name:
   - missing: skipped, counted as "not in club"
   - weight already set: skipped, counted as "already set" (a weight an admin
     set is never overwritten)
   - blank weight: set and saved, counted as "filled"
3. Prints filled / already-set / not-in-club counts.

Safe to run once per existing club per deploy (dry run first, then
``--apply``). Idempotent: a second apply run fills nothing.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Club
from items.models import Item
from shops.gear import GENERAL_STORE_GEAR
from starting_equipment.seeding import STARTING_EQUIPMENT_WEIGHTS


def _seed_weight_map() -> dict[str, int]:
    """Build ``{seeded name: weight in hundredths of a pound}``."""
    weights: dict[str, int] = {}
    for gear in GENERAL_STORE_GEAR:
        if gear.weight_lb is not None:
            weights[gear.name] = round(gear.weight_lb * 100)
    for name, weight_lb in STARTING_EQUIPMENT_WEIGHTS.items():
        if weight_lb is not None:
            weights[name] = round(weight_lb * 100)
    return weights


class Command(BaseCommand):
    help = (
        "Backfill SRD weights onto seeded items whose weight is blank for a club. "
        "Dry run by default; use --apply to write. Never overwrites an admin-set weight."
    )

    def add_arguments(self, parser):
        parser.add_argument("--club", type=str, required=True, help="Club slug to backfill.")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes (default is a dry run that rolls everything back).",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        try:
            club = Club.objects.get(slug=options["club"])
        except Club.DoesNotExist as err:
            raise CommandError(f"Club with slug '{options['club']}' does not exist.") from err

        self.stdout.write(f"Seeding item weights for club '{club.name}' ({club.slug})")
        if not apply:
            self.stdout.write(self.style.WARNING("DRY RUN - changes will be rolled back"))

        seed_weights = _seed_weight_map()

        filled = already_set = not_in_club = 0
        with transaction.atomic():
            for name, weight_hundredths in sorted(seed_weights.items()):
                item = Item.objects.filter(club=club, name=name).first()
                if item is None:
                    not_in_club += 1
                    self.stdout.write(f'  "{name}": not in club, skipping')
                    continue
                if item.weight_hundredth_lb is not None:
                    already_set += 1
                    self.stdout.write(
                        f'  "{name}": weight already set '
                        f"({item.weight_hundredth_lb / 100:.2f} lb), not overwritten"
                    )
                    continue
                item.weight_hundredth_lb = weight_hundredths
                item.save(update_fields=["weight_hundredth_lb"])
                filled += 1
                self.stdout.write(f'  "{name}": weight set to {weight_hundredths / 100:.2f} lb')

            if not apply:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run complete - rolled back"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Done." if apply else "Dry run done."))
        self.stdout.write(f"  Weights filled: {filled}")
        self.stdout.write(f"  Already set: {already_set}")
        self.stdout.write(f"  Not in club: {not_in_club}")
