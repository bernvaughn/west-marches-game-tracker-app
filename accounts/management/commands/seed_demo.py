from django.core.management.base import BaseCommand
from django.db import transaction

from accounts import demo as accounts_demo
from agent_access import demo as agent_demo
from items import demo as items_demo
from ledger import demo as ledger_demo
from map import demo as map_demo
from player_characters import demo as characters_demo
from quests import demo as quests_demo
from shops import demo as shops_demo


class Command(BaseCommand):
    help = "Create demo data. Safe to run more than once."

    def handle(self, *args, **options):
        with transaction.atomic():
            club = accounts_demo.seed()
            for module in (
                items_demo,
                characters_demo,
                shops_demo,
                quests_demo,
                map_demo,
                ledger_demo,
                agent_demo,
            ):
                module.seed(club)
        out = self.stdout.write
        out(f"Demo club ready at /c/{club.slug}/")
        out("Demo logins:")
        for email, role in accounts_demo.DEMO_LOGINS:
            out(f"  {email}  ({role})")
        out(f"Password for all: {accounts_demo.DEMO_PASSWORD}")
