"""Management command to prune old player notices.

Deletes PlayerNotice rows older than a cutoff (default 30 days) measured from
``created``. Safe to run on a schedule (e.g. via cron).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from player_items.models import PlayerNotice


class Command(BaseCommand):
    help = "Delete player notices older than 30 days (configurable with --days)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Delete notices older than this many days (default 30).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timedelta(days=days)
        qs = PlayerNotice.objects.filter(created__lt=cutoff)
        count = qs.count()
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Pruned {count} notice(s) older than {days} day(s)."))
