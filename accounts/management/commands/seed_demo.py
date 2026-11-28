from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts import demo as accounts_demo
from agent_access import demo as agent_demo
from downtime import demo as downtime_demo
from items import demo as items_demo
from ledger import demo as ledger_demo
from mail import demo as mail_demo
from map import demo as map_demo
from play_sessions import demo as sessions_demo
from player_characters import demo as characters_demo
from player_items import demo as player_items_demo
from quests import demo as quests_demo
from shops import demo as shops_demo
from starting_equipment import demo as starting_equipment_demo


class Command(BaseCommand):
    help = "Create demo data. Safe to run more than once."

    def handle(self, *args, **options):
        with transaction.atomic():
            club = accounts_demo.seed()
            items_demo.seed(club)

            # Seed starting equipment BEFORE characters so packs exist when demo gear is given.
            # Pass --force so an existing demo DB upgrades its default template
            # (demo data is disposable; admin edits to the demo template
            # are expected to be overwritten).
            call_command(
                "seed_starting_equipment",
                "--club",
                club.slug,
                "--force",
                stdout=self.stdout,
            )

            # Backfill SRD weights onto seeded demo items (never overwrites admin-set weights).
            call_command(
                "seed_item_weights",
                "--club",
                club.slug,
                "--apply",
                stdout=self.stdout,
            )

            for module in (
                characters_demo,
                sessions_demo,
                shops_demo,
                quests_demo,
                map_demo,
                ledger_demo,
                downtime_demo,
                agent_demo,
                starting_equipment_demo,
                player_items_demo,
                mail_demo,
            ):
                module.seed(club)

        out = self.stdout.write
        out(f"Demo club ready at /c/{club.slug}/")
        out("Demo logins:")
        for email, role in accounts_demo.DEMO_LOGINS:
            out(f"  {email}  ({role})")
        out(f"Password for all: {accounts_demo.DEMO_PASSWORD}")
