"""Convert seeded bundle items to stacked items for an existing club (stories U124, U125).

Old seeding created count-in-the-name bundles as plain items ("Arrows (20)") and
starting equipment created a second, unrelated plain item ("Crossbow Bolt").
This command turns them into stacked items ("Arrows", "Crossbow Bolts") that
players can use one unit at a time.

Dry run by default: the whole conversion runs inside one transaction and is
rolled back unless ``--apply`` is given, so a dry run shows exactly what an
apply would do, including refusals. A refusal (for example a character holding
both the old plain item and the bundle item) writes nothing and exits with an
error. Running it twice changes nothing.

Per club it:
1. Converts bundle items with ``items.services.convert_to_stacked`` after
   renaming them: "Arrows (20)" becomes "Arrows" and each owned bundle becomes
   20 units, with one ledger entry per holder. Holders whose net total is
   exactly zero are skipped (no ledger entry, shown as "skipped (owns none)").
   Holders with a negative net total refuse the whole conversion.
2. Merges the plain "Crossbow Bolt" / "Arrow" items into the stacked item
   1:1 (the plain items already count single units). If the stacked item does
   not exist, the plain item is turned into it in place.

Assumption: "Caltrops", "Ball Bearings" and "Spikes, Iron" never had a count
in their name. They are assumed to be one bag/bundle per owned item (factor 20,
1000 and 10) and are converted by that factor.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from accounts.models import Club
from agent_access.models import ProposedBatch, ProposedLine
from items.models import ContainerSlotOption, Item
from items.services import (
    StackedConversionError,
    conversion_preview,
    convert_to_stacked,
    delete_or_retire,
)
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import Line, record_many
from player_characters.models import Character
from quests.models import QuestRequirement, QuestReward
from starting_equipment.models import (
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassLine,
)
from starting_equipment.seeding import STACKED_AMMO_SPECS

# (old name, new stacked name, factor, unit name)
BUNDLE_CONVERSIONS = [
    ("Arrows (20)", "Arrows", 20, "arrow"),
    ("Crossbow Bolts (20)", "Crossbow Bolts", 20, "bolt"),
    ("Firearm Bullets (10)", "Firearm Bullets", 10, "bullet"),
    ("Sling Bullets (20)", "Sling Bullets", 20, "bullet"),
    ("Needles (50)", "Needles", 50, "needle"),
    # No count in the old name: assumed to be one bag/bundle per owned item.
    ("Caltrops", "Caltrops", 20, "caltrop"),
    ("Ball Bearings", "Ball Bearings", 1000, "ball bearing"),
    ("Spikes, Iron", "Spikes, Iron", 10, "spike"),
]
ASSUMED_ONE_BUNDLE_PER_ITEM = ("Caltrops", "Ball Bearings", "Spikes, Iron")

# (old plain item, stacked item). Plain items already count single units.
PLAIN_AMMO_MERGES = [
    ("Crossbow Bolt", "Crossbow Bolts"),
    ("Arrow", "Arrows"),
]

# (model, FK name to the owning entry)
STARTING_LINE_MODELS = [
    (StartingEquipmentClassLine, "class_entry"),
    (StartingEquipmentBackgroundLine, "background_entry"),
]


class Refusal(Exception):
    """A step refuses to guess; the whole run is rolled back."""


class Command(BaseCommand):
    help = (
        "Convert seeded bundle items (Arrows (20), Crossbow Bolt, ...) to stacked "
        "items for a club. Dry run by default; use --apply to change data."
    )

    def add_arguments(self, parser):
        parser.add_argument("--club", type=str, required=True, help="Club slug to convert.")
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

        self.stdout.write(f"Converting seeded bundles for club '{club.name}' ({club.slug})")
        if not apply:
            self.stdout.write(self.style.WARNING("DRY RUN - changes will be rolled back"))
        self.stdout.write(
            "  Assumption: "
            + ", ".join(f'"{n}"' for n in ASSUMED_ONE_BUNDLE_PER_ITEM)
            + " are treated as one bag/bundle per owned item "
            + "(factor 20, 1000 and 10)."
        )

        converted = merged = 0
        errors = []
        with transaction.atomic():
            for old_name, new_name, factor, unit_name in BUNDLE_CONVERSIONS:
                try:
                    converted += self._convert_bundle(club, old_name, new_name, factor, unit_name)
                except Refusal as err:
                    errors.append(str(err))
            for old_name, new_name in PLAIN_AMMO_MERGES:
                try:
                    merged += self._merge_plain_ammo(club, old_name, new_name)
                except Refusal as err:
                    errors.append(str(err))

            if errors:
                for err in errors:
                    self.stdout.write(self.style.ERROR(f"  Refused: {err}"))
                raise CommandError(
                    f"{len(errors)} conversion(s) refused; nothing was changed. See above."
                )
            if not apply:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run complete - rolled back"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Done." if apply else "Dry run done."))
        self.stdout.write(f"  Bundle items converted: {converted}")
        self.stdout.write(f"  Plain ammo items merged: {merged}")

    # -- helpers ----------------------------------------------------------

    def _one(self, club, name):
        """The single non-retired item with this name, or None. Refuse on duplicates."""
        items = list(Item.objects.filter(club=club, name=name, retired=False))
        if len(items) > 1:
            raise Refusal(f'"{name}": {len(items)} items share this name, refusing to guess.')
        return items[0] if items else None

    def _repoint_lines(self, old, new, multiplier=1):
        """Point starting-equipment lines at ``new``, scaling quantities.

        A line that would duplicate an existing line for ``new`` in the same entry
        and group is folded into it.
        """
        count = 0
        for model, fk in STARTING_LINE_MODELS:
            for line in model.objects.filter(item=old):
                dup = (
                    model.objects.filter(
                        **{
                            fk: getattr(line, fk),
                            "item": new,
                            "is_choice": line.is_choice,
                            "choice_group": line.choice_group,
                        }
                    )
                    .exclude(pk=line.pk)
                    .first()
                )
                if dup:
                    dup.quantity += line.quantity * multiplier
                    dup.save(update_fields=["quantity"])
                    line.delete()
                else:
                    line.item = new
                    line.quantity = line.quantity * multiplier
                    line.save(update_fields=["item", "quantity"])
                count += 1
        return count

    def _warn_other_references(self, item, what):
        other = (
            QuestRequirement.objects.filter(item=item).count()
            + QuestReward.objects.filter(item=item).count()
            + ContainerSlotOption.objects.filter(item=item).count()
        )
        if other:
            self.stdout.write(
                self.style.WARNING(
                    f'  Warning: {other} quest or container rows reference "{item.name}" '
                    f"({what}). Their quantities were not changed; check them by hand."
                )
            )

    # -- step 1: bundle-named items ----------------------------------------

    def _convert_bundle(self, club, old_name, new_name, factor, unit_name):
        old_item = self._one(club, old_name)
        if old_item is None:
            self.stdout.write(f'  "{old_name}": not found or retired, skipping')
            return 0
        if old_item.is_stacked:
            self.stdout.write(f'  "{old_name}": already stacked, skipping')
            return 0

        if old_name != new_name and self._one(club, new_name) is not None:
            raise Refusal(
                f'"{old_name}": an item named "{new_name}" already exists. '
                "Merge or rename one of them by hand, then run again."
            )

        preview = conversion_preview(old_item, factor=factor)
        non_skipped = sum(1 for h in preview.holders if not h.get("skipped"))
        self.stdout.write(
            f'  "{old_name}": {non_skipped} holders, {preview.total_owned} owned '
            f'-> "{new_name}" ({factor} x {unit_name})'
        )
        for h in preview.holders:
            if h.get("skipped"):
                self.stdout.write(f"    {h['name']}: skipped (owns none)")
        if preview.refusal_reasons:
            raise Refusal(f'"{old_name}": ' + " ".join(preview.refusal_reasons))

        # If there are holders but all are skipped (zero net), don't convert.
        # If there are no holders at all, still convert (e.g., for starting equipment).
        if preview.holders and non_skipped == 0:
            self.stdout.write(f'    All holders have zero net; skipping conversion of "{old_name}"')
            return 0

        if old_name != new_name:
            old_item.name = new_name
            old_item.save(update_fields=["name"])
        try:
            convert_to_stacked(old_item, factor, unit_name)
        except StackedConversionError as err:
            raise Refusal(f'"{old_name}": {err}') from err

        lines = self._repoint_lines(old_item, old_item, multiplier=factor)
        if lines:
            self.stdout.write(
                f"    {lines} starting-equipment line(s) multiplied by {factor} (now units)"
            )
        self._warn_other_references(old_item, "now counted in units")
        return 1

    # -- step 2: plain ammo duplicates -------------------------------------

    def _merge_plain_ammo(self, club, old_name, new_name):
        plain = self._one(club, old_name)
        if plain is None:
            self.stdout.write(f'  "{old_name}": not found or retired, skipping')
            return 0
        if plain.is_stacked or plain.is_container:
            raise Refusal(f'"{old_name}" is already stacked or a container, refusing.')
        if ProposedLine.objects.filter(
            item=plain, batch__status=ProposedBatch.Status.PENDING
        ).exists():
            raise Refusal(
                f'A pending agent proposal names "{old_name}". Confirm or discard it first.'
            )

        value_cp, symbol, _rarity, _magic, unit_name, value_units = STACKED_AMMO_SPECS[new_name]
        target = self._one(club, new_name)

        if target is None:
            # No stacked item to merge into: turn the plain item into it, keeping
            # its owners and lines. Plain quantities already count units.
            plain.name = new_name
            plain.is_stacked = True
            plain.unit_name = unit_name
            plain.value_units = value_units
            plain.value_cp = value_cp
            plain.save(update_fields=["name", "is_stacked", "unit_name", "value_units", "value_cp"])
            self.stdout.write(
                f'  "{old_name}": no "{new_name}" found, renamed in place to stacked '
                f"({value_units} x {unit_name} for {value_cp} cp)"
            )
            return 1

        if not target.is_stacked:
            raise Refusal(f'"{old_name}": target "{new_name}" is not stacked, refusing.')

        def net_by_character(item):
            rows = (
                LedgerLine.objects.filter(item=item)
                .values("entry__character_id")
                .annotate(total=Sum("quantity"))
            )
            return {r["entry__character_id"]: r["total"] or 0 for r in rows}

        old_net = net_by_character(plain)
        new_net = net_by_character(target)
        both = sorted(c for c, n in old_net.items() if n != 0 and new_net.get(c, 0) != 0)
        if both:
            names = ", ".join(c.name for c in Character.objects.filter(pk__in=both))
            raise Refusal(
                f'characters hold both "{old_name}" and "{new_name}": {names}. '
                "Fix their items by hand, then run again."
            )
        negative = [c for c, n in old_net.items() if n < 0]
        if negative:
            names = ", ".join(c.name for c in Character.objects.filter(pk__in=negative))
            raise Refusal(f'"{old_name}": negative net total for: {names}.')

        self.stdout.write(
            f'  "{old_name}": {sum(1 for n in old_net.values() if n > 0)} holders, '
            f'{sum(n for n in old_net.values() if n > 0)} units -> "{new_name}" (1:1)'
        )
        note = f'Merged "{old_name}" into stacked "{new_name}"'
        specs = [
            dict(
                character=Character.objects.get(pk=char_id),
                kind=LedgerEntry.Kind.ADJUSTMENT,
                lines=[Line(item=plain, quantity=-owned), Line(item=target, quantity=owned)],
                note=note,
                actor=None,
            )
            for char_id, owned in sorted(old_net.items())
            if owned > 0
        ]
        if specs:
            record_many(specs)

        self._repoint_lines(plain, target)
        self._warn_other_references(plain, f'merged into "{new_name}"')
        delete_or_retire(plain)
        return 1
