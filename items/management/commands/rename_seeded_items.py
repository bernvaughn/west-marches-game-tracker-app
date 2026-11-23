"""Catch-up command to rename seeded items for existing clubs (U152).

Dry run by default: the whole run executes inside one transaction and is
rolled back unless ``--apply`` is given. A refusal (e.g., a character would
end up with a negative net quantity after a merge) writes nothing and exits
with an error. Running it twice changes nothing.

Per club it:
1. Renames in place any item whose name is an old seeded name and that was
   never edited by an admin. "Never edited" = no other record has the target
   name AND the item's value, symbol, and description still match the seed.
   If it does not match, it is skipped and listed as "left alone".
2. Merges duplicates: if both an old and a new record exist (or two old ones
   for the same instrument), keep the lower id, repoint every foreign key to
   Item (find them with ``Item._meta.related_objects``), add one ledger entry
   per holder with a note, and refuse if any holder would end negative.
   Holders at exactly 0 are skipped (no ledger entry).
3. Splits the map case: "Case, Map or Scroll" and "Map or Scroll Case"
   become "Map Case"; create "Scroll Case" if missing; update the seeded
   Diplomat's Pack slots (only if still the seeded shape).
4. Idempotent: a second run prints "nothing to do" and writes nothing.

Prints a clear report: renames, merges, splits, left alone, refusals.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Club
from items.services_rename import Refusal, run_rename


class Command(BaseCommand):
    help = (
        "Rename seeded items to their new names, merge duplicates, split map case, "
        "and update Diplomat's Pack slots for a club. Dry run by default; use --apply to write."
    )

    def add_arguments(self, parser):
        parser.add_argument("--club", type=str, required=True, help="Club slug to process.")
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

        self.stdout.write(f"Renaming seeded items for club '{club.name}' ({club.slug})")
        if not apply:
            self.stdout.write(self.style.WARNING("DRY RUN - changes will be rolled back"))

        def log(msg):
            self.stdout.write(msg)

        try:
            report = run_rename(club, apply=apply, log=log)
        except Refusal as err:
            self.stdout.write(self.style.ERROR(f"Refused: {err}"))
            raise CommandError(str(err)) from err

        # Print report
        self.stdout.write("")
        if report.nothing_to_do:
            self.stdout.write(self.style.SUCCESS("Nothing to do."))
            return

        self.stdout.write(self.style.SUCCESS("Done." if apply else "Dry run done."))
        self.stdout.write("")

        if report.renames:
            self.stdout.write(self.style.NOTICE(f"Renames ({len(report.renames)}):"))
            for r in report.renames:
                self.stdout.write(f"  {r}")
            self.stdout.write("")

        if report.merges:
            self.stdout.write(self.style.NOTICE(f"Merges ({len(report.merges)}):"))
            for m in report.merges:
                self.stdout.write(f"  {m}")
            self.stdout.write("")

        if report.splits:
            self.stdout.write(self.style.NOTICE(f"Splits ({len(report.splits)}):"))
            for s in report.splits:
                self.stdout.write(f"  {s}")
            self.stdout.write("")

        if report.left_alone:
            self.stdout.write(self.style.WARNING(f"Left alone ({len(report.left_alone)}):"))
            for l in report.left_alone:
                self.stdout.write(f"  {l}")
            self.stdout.write("")

        if report.refusals:
            self.stdout.write(self.style.ERROR(f"Refusals ({len(report.refusals)}):"))
            for r in report.refusals:
                self.stdout.write(f"  {r}")
            self.stdout.write("")