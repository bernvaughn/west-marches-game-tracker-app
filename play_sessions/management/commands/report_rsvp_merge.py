"""Merge per-character RSVPs into per-player RSVPs and report the counts.

Safe to run repeatedly: the merge is idempotent and creates no duplicate
PlayerRSVP rows.
"""

from django.core.management.base import BaseCommand

from play_sessions.models import merge_rsvps_to_player


class Command(BaseCommand):
    help = "Merge per-character RSVPs into per-player RSVPs and report the counts."

    def handle(self, *args, **options):
        merged, mixed = merge_rsvps_to_player()
        self.stdout.write(
            self.style.SUCCESS(f"Merged {merged} player RSVPs; {mixed} players had mixed answers.")
        )
