"""Management command to seed the 2024 D&D Default starting equipment template."""

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Club
from starting_equipment.seeding import (
    DEFAULT_TEMPLATE_NAME,
    StartingEquipmentSeedError,
    seed_default_starting_equipment,
)


class Command(BaseCommand):
    help = (
        "Create the '2024 D&D Default' starting equipment template "
        "with all classes, backgrounds, and level coins."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--club",
            type=str,
            help="Club slug to create the template in (default: first club or 'demo')",
        )
        parser.add_argument(
            "--name",
            type=str,
            default=DEFAULT_TEMPLATE_NAME,
            help="Name for the template (default: '2024 D&D Default')",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update existing template entries instead of skipping",
        )

    def handle(self, *args, **options):
        club_slug = options["club"]
        template_name = options["name"]
        force = options["force"]

        # Get or create club
        if club_slug:
            try:
                club = Club.objects.get(slug=club_slug)
            except Club.DoesNotExist as err:
                raise CommandError(f"Club with slug '{club_slug}' does not exist.") from err
        else:
            club = Club.objects.first()
            if not club:
                raise CommandError("No clubs exist. Create a club first or specify --club.")
            self.stdout.write(f"Using club: {club.name} ({club.slug})")

        try:
            summary = seed_default_starting_equipment(club, name=template_name, force=force)
        except StartingEquipmentSeedError as err:
            raise CommandError(str(err)) from err

        if summary.template_created:
            self.stdout.write(f"Created template: {template_name}")
        else:
            self.stdout.write(f"Template exists: {template_name}")
            if summary.skipped:
                self.stdout.write(
                    self.style.WARNING("Template already exists. Use --force to update entries.")
                )
                return

        if summary.items_created:
            self.stdout.write(f"Created {summary.items_created} new items")

        self.stdout.write(
            f"Class entries: {summary.class_entries_created} created, "
            f"{summary.class_entries_updated} updated"
        )
        self.stdout.write(
            f"Background entries: {summary.background_entries_created} created, "
            f"{summary.background_entries_updated} updated"
        )
        self.stdout.write(
            f"Level coins: {summary.level_coins_created} created, "
            f"{summary.level_coins_updated} updated"
        )
        if summary.packs_configured:
            self.stdout.write(f"Packs configured: {summary.packs_configured}")

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded '{template_name}' template"))
