import datetime

from accounts.models import User
from items.models import Item
from player_characters.models import Character

from .models import AgentConnection, ProposedBatch, ProposedItem, ProposedLine
from .tokens import create_token, hash_secret

# Local use only. This token must never exist on a hosted site.
DEMO_TOKEN = "wm_demo_local_token_change_me"


def seed(club):
    gm = User.objects.get(email="gm@example.com")
    connection = AgentConnection.objects.filter(token_hash=hash_secret(DEMO_TOKEN)).first()
    if connection is None:
        connection, _ = create_token(gm, club, "Demo agent", secret=DEMO_TOKEN)

    batch, created = ProposedBatch.objects.get_or_create(
        connection=connection,
        idempotency_key="demo-session-1",
        defaults={
            "club": club,
            "user": gm,
            "date": datetime.date.today(),
            "source_notes": "Session 1: the party killed a wolf and found a purse of coins.",
        },
    )
    if created:
        aria = Character.objects.get(club=club, name="Aria Windrunner")
        borin = Character.objects.get(club=club, name="Borin Stonefist")
        pelt = Item.objects.get(club=club, name="Wolf pelt")
        ProposedLine.objects.create(batch=batch, character=aria, item=pelt, quantity=1)
        ProposedLine.objects.create(batch=batch, character=borin, coins=500, note="Purse")

    ProposedItem.objects.get_or_create(
        club=club,
        name="Frost-touched dagger",
        status=ProposedItem.Status.PENDING,
        defaults={
            "connection": connection,
            "value_cp": 3000,
            "description": "A pale dagger, cold to the touch.",
        },
    )
