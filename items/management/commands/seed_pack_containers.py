"""Management command to seed 5e packs as containers with fixed slots."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Club
from items.pack_seeding import PACKS, PackSeedingError, seed_pack_containers

__all__ = ["PACKS", "Command"]


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

        with transaction.atomic():
            try:
                summary = seed_pack_containers(club, log=self.stdout.write)
            except PackSeedingError as err:
                raise CommandError(str(err)) from err

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run complete - rolled back"))

        self.stdout.write("")
        self.stdout.write("Summary:")
        self.stdout.write(f"  Packs configured: {summary.configured}")
        self.stdout.write(f"  Packs skipped (not in catalogue): {summary.skipped_not_in_catalogue}")
        self.stdout.write(
            f"  Packs skipped (already configured): {summary.skipped_already_configured}"
        )
