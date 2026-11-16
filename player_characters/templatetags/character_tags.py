"""Template tags for character-related functionality."""

from django import template

from ..selector_context import all_characters_selector_context, character_selector_context

register = template.Library()


@register.filter
def selector_context(characters):
    """Convert a queryset/list of characters to list of (character, context) tuples."""
    if hasattr(characters, "__iter__") and not isinstance(characters, (str, dict)):
        return [(c, character_selector_context(c)) for c in characters]
    return [(characters, character_selector_context(characters))]


@register.simple_tag(takes_context=True)
def all_selector_context(context):
    """Return list of (character, context) for all owned characters in current club."""
    request = context["request"]
    return all_characters_selector_context(request)


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary-like object (e.g., request.POST)."""
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    try:
        return dictionary[key]
    except (KeyError, TypeError):
        return None


@register.filter
def get_coins(dictionary, pk):
    """Get coins value for a character from request.POST."""
    return get_item(dictionary, f"coins_{pk}")