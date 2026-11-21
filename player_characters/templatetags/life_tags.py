"""Template filters for character life state."""

from django import template

from player_characters.life import buy_block_reason

register = template.Library()


@register.filter(name="buy_block_reason")
def buy_block_reason_filter(character):
    """Return the buy block reason text, or empty string for None character."""
    if character is None:
        return ""
    return buy_block_reason(character)


@register.filter
def is_dead(character):
    """Return True if the character is dead, False for None or living."""
    if character is None:
        return False
    return character.is_dead
