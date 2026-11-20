"""Management command to seed the General Store for an existing club."""

from django.core.management import BaseCommand, CommandError

from accounts.models import Club
from shops.seeding import seed_default_general_store


class Command(BaseCommand):
    help = "Seed the default General Store (Mabel Packwell) for a club. Idempotent."

    def add_arguments(self, parser):
        parser.add_argument("--club", required=True, help="Club slug")

    def handle(self, *args, **options):
        slug = options["club"]
        try:
            club = Club.objects.get(slug=slug)
        except Club.DoesNotExist as err:
            raise CommandError(f"Club '{slug}' does not exist") from err

        summary = seed_default_general_store(club)

        if summary.skipped:
            self.stdout.write("General Store already exists, nothing changed")
        else:
            self.stdout.write(
                f"Created General Store with {summary.items_created} new items "
                f"and {summary.stock_created} stock rows"
            )
