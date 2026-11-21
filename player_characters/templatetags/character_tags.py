"""Template tags for character-related functionality."""

from django import template
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from ..selector_context import all_characters_selector_context, character_selector_context
from ..sheet_sections import get_sheet_sections

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
    if hasattr(dictionary, "get"):
        return dictionary.get(key)
    try:
        return dictionary[key]
    except (KeyError, TypeError):
        return None


@register.filter
def get_coins(dictionary, pk):
    """Get coins value for a character from request.POST."""
    return get_item(dictionary, f"coins_{pk}")


@register.simple_tag(takes_context=True)
def sheet_sections(context):
    """Render all registered sheet sections for the current character.

    Each section is wrapped in a ``<section>`` with ``no-print`` so it
    appears on screen but not in the printed sheet. Sections whose
    ``visible_fn`` is false, whose ``context_fn`` returns ``None``, or
    whose template fails to render are skipped (logged). The tag returns
    an empty string when no sections are registered or when
    ``request``/``character`` are missing from the context.
    """
    request = context.get("request")
    character = context.get("character")
    club = context.get("club")

    if request is None or character is None:
        return ""

    sections = get_sheet_sections(request, character)
    if not sections:
        return ""

    rendered = []
    for section in sections:
        # Build context for the section template
        section_ctx = {
            **section["context"],
            "request": request,
            "character": character,
            "club": club,
        }
        try:
            html = render_to_string(
                section["template"],
                section_ctx,
                request=request,
            )
        except Exception:
            # Log and skip a broken template; do not break the sheet.
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Template render failed for sheet section %r", section["key"])
            continue

        # Wrap in a section with no-print and data attribute
        wrapper = format_html(
            '<section class="wm-sheet-box wm-sheet-full no-print wm-sheet-extra" '
            'data-sheet-section="{}" aria-label="{}">{}',
            section["key"],
            section["key"].replace("_", " ").title(),
            mark_safe(html),
        )
        rendered.append(wrapper)

    return mark_safe("".join(rendered))