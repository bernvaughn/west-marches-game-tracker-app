"""Template tags for character death actions."""

from django import template

from player_characters.death_permissions import can_mark_dead, can_undo_death

register = template.Library()


@register.simple_tag
def can_mark_dead_tag(user, character):
    """Return True if user can mark this character as dead."""
    return can_mark_dead(user, character)


@register.simple_tag
def can_undo_death_tag(user, character):
    """Return True if user can undo this character's death."""
    return can_undo_death(user, character)
