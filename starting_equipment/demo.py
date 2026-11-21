"""Demo seeding for starting_equipment: MagicItemStartingOption and a
pending StartingEquipmentRequest."""

from accounts.models import Membership, Message
from items.models import Item
from player_characters.models import Character

from .models import MagicItemStartingOption, StartingEquipmentRequest, StartingEquipmentTemplate


def seed(club):
    """Add a magic item option and a pending starting equipment request for the demo."""
    # Get the active template (seeded by seed_starting_equipment --force)
    template = StartingEquipmentTemplate.objects.filter(club=club, is_active=True).first()
    if template is None:
        return

    # Add a MagicItemStartingOption for "Moonstone amulet" if it exists in the catalogue
    moonstone = Item.objects.filter(club=club, name="Moonstone amulet").first()
    if moonstone:
        MagicItemStartingOption.objects.get_or_create(
            template=template,
            item=moonstone,
            defaults={"max_per_character": 1, "notes": "Level 5+ only"},
        )

    # Create a pending StartingEquipmentRequest for Tilda (unclaimed starting equipment)
    tilda = Character.objects.filter(club=club, name="Tilda Brightwater").first()
    if tilda is None:
        return

    # Check if a pending request for Tilda already exists
    if StartingEquipmentRequest.objects.filter(
        club=club,
        character=tilda,
        status=StartingEquipmentRequest.Status.PENDING,
    ).exists():
        return

    # Get the GM membership for the message sender
    gm_membership = Membership.objects.filter(club=club, is_game_master=True).first()
    if gm_membership is None:
        return

    # Create the request (matching request_new view: PENDING request + STARTING_REQUEST message)
    request = StartingEquipmentRequest.objects.create(
        club=club,
        character=tilda,
        item=moonstone,
        quantity=1,
        note="Would like this for my first adventure.",
        status=StartingEquipmentRequest.Status.PENDING,
    )

    # Create linked inbox Message (STARTING_REQUEST kind)
    if moonstone:
        body = (
            f"{tilda.name} requests 1x {moonstone.name} "
            f"as starting equipment. Note: Would like this for my first adventure."
        )
    else:
        body = (
            f"{tilda.name} requests a starting equipment item. "
            f"Note: Would like this for my first adventure."
        )

    msg = Message.objects.create(
        club=club,
        sender=gm_membership,
        character=tilda,
        body=body,
        kind=Message.Kind.STARTING_REQUEST,
    )
    request.message = msg
    request.save(update_fields=["message"])
