"""Demo data for player_items. Safe to run more than once."""

from accounts.models import Membership
from player_items.models import PlayerItem, PlayerNotice, normalize_name_key
from player_items.services import add_player_item


def seed(club):
    """Seed demo player-written items and notices.

    Uses add_player_item only when no row with that name_key exists for
    the character, so re-runs are idempotent.
    """
    gm = Membership.objects.get(club=club, user__email="gm@example.com")
    alice = Membership.objects.get(club=club, user__email="alice@example.com")

    from player_characters.models import Character

    aria = Character.objects.get(club=club, name="Aria Windrunner")
    wren = Character.objects.get(club=club, name="Wren Thistledown")
    borin = Character.objects.get(club=club, name="Borin Stonefist")

    # Aria: Grandmother's locket
    _add_item(
        club,
        aria,
        "Grandmother's locket",
        1,
        "A small silver locket with a painted portrait inside.",
        gm.user,
    )

    # Wren: Lockpicks
    _add_item(club, wren, "Lockpicks", 1, "Fine steel lockpicks, barely used.", gm.user)

    # Borin: two lockpicks (same name_key as Wren's, so the review page groups them for merge)
    _add_item(club, borin, "lockpicks", 2, "Borin's spare set.", gm.user)

    # Borin: Whetstone
    _add_item(club, borin, "Whetstone", 1, "Keeps the longsword edge sharp.", gm.user)

    # One PlayerNotice for Alice (get_or_create on membership + kind + text)
    PlayerNotice.objects.get_or_create(
        membership=alice,
        kind=PlayerNotice.Kind.ITEM_PROMOTED,
        text="Your item 'Grandmother's locket' was reviewed and promoted to the catalogue.",
        defaults={"club": club},
    )


def _add_item(club, character, name, quantity, note, by):
    """Add a player-written item only when no row with that name_key exists for the character."""

    name_key = normalize_name_key(name)
    exists = (
        PlayerItem.objects.for_club(club).filter(character=character, name_key=name_key).exists()
    )
    if not exists:
        add_player_item(club, character, name, quantity, note, by)
