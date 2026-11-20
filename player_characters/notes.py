"""Item notes (U122): a player's private notes on items in their inventory.

One row per character and item, never per unit in a stack. Only the character's
owner may add, change or clear a note; game masters and club admins can read it
on the sheet but not edit it.
"""

from django.core.exceptions import PermissionDenied

from .access import owns_character
from .models import ItemNote


class NoteError(Exception):
    pass


NOTE_MAX = 1000


def item_notes(character):
    """Return {item_pk: text} for the character's item notes."""
    return {
        note.item_id: note.text
        for note in ItemNote.objects.filter(character=character).select_related("item")
    }


def set_note(character, item, text, actor):
    """Add, change or (empty text) clear a note. Owner only, no superuser bypass."""
    if not owns_character(actor, character):
        raise PermissionDenied
    if item.club_id != character.club_id:
        raise NoteError("This item is not in the character's club.")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        ItemNote.objects.filter(character=character, item=item).delete()
        return None
    if len(text) > NOTE_MAX:
        raise NoteError(f"Notes can be at most {NOTE_MAX} characters.")
    ItemNote.objects.update_or_create(character=character, item=item, defaults={"text": text})
    return text
