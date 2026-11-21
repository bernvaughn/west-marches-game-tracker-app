"""Demo seeding for starting_equipment: MagicItemStartingOption and a
pending StartingEquipmentRequest."""

from accounts.models import Message
from items.models import Item
from player_characters.models import Character

from .models import MagicItemStartingOption, StartingEquipmentRequest, StartingEquipmentTemplate


def seed(club):
    """Add a magic item option and a pending starting equipment request for the demo."""
    # Get the active template (seeded by seed_starting_equipment --force)
    template = StartingEquipmentTemplate.objects.filter(club=club, is_active=True).first()
    if template is None:
        return

    # The Moonstone amulet comes from the shops demo seeder. The request needs it.
    moonstone = Item.objects.filter(club=club, name="Moonstone amulet").first()
    if moonstone is None:
        return
    MagicItemStartingOption.objects.get_or_create(
        template=template,
        item=moonstone,
        defaults={"max_per_character": 1, "notes": "Level 5+ only"},
    )

    # Create a pending StartingEquipmentRequest for Tilda (unclaimed starting equipment)
    tilda = Character.objects.filter(club=club, name="Tilda Brightwater").first()
    if tilda is None or tilda.owner is None:
        return

    # Check if a pending request for Tilda already exists
    if StartingEquipmentRequest.objects.filter(
        club=club,
        character=tilda,
        status=StartingEquipmentRequest.Status.PENDING,
    ).exists():
        return

    note = "Would like this for my first adventure."
    request = StartingEquipmentRequest.objects.create(
        club=club,
        character=tilda,
        item=moonstone,
        quantity=1,
        note=note,
        status=StartingEquipmentRequest.Status.PENDING,
    )

    # Linked inbox message. Like request_new, the sender is the requesting player.
    msg = Message.objects.create(
        club=club,
        sender=tilda.owner,
        character=tilda,
        body=f"{tilda.name} requests 1x {moonstone.name} as starting equipment. Note: {note}",
        kind=Message.Kind.STARTING_REQUEST,
    )
    request.message = msg
    request.save(update_fields=["message"])
