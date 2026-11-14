from django import template
from django.utils.safestring import mark_safe

from ..permissions import can_reset_password, can_see_email

register = template.Library()

_FLASH_KEY = "wm_flash_slot"
_FLASH_TEMPLATE = "components/messages.html"


class FlashSlotNode(template.Node):
    """Wraps the page content in base.html. A page header shows the flash messages below itself.
    If none did, the messages go at the top of main."""

    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        slot = {"shown": False}
        with context.push(**{_FLASH_KEY: slot}):
            body = self.nodelist.render(context)
            if slot["shown"] or not context.get("messages"):
                return body
            slot["shown"] = True
            return context.template.engine.get_template(_FLASH_TEMPLATE).render(context) + body


@register.tag
def flash_slot(parser, token):
    nodelist = parser.parse(("endflash_slot",))
    parser.delete_first_token()
    return FlashSlotNode(nodelist)


@register.simple_tag(takes_context=True)
def flash_messages(context):
    """Render flash messages once, inside a flash_slot. Outside one, render nothing."""
    slot = context.get(_FLASH_KEY)
    if slot is None or slot["shown"] or not context.get("messages"):
        return ""
    slot["shown"] = True
    return mark_safe(context.template.engine.get_template(_FLASH_TEMPLATE).render(context))


@register.simple_tag(takes_context=True)
def member_email(context, user_obj):
    request = context["request"]
    if can_see_email(request.user, getattr(request, "club", None)):
        return user_obj.email
    return ""


@register.filter
def can_reset(target, actor):
    return can_reset_password(actor, target)


@register.simple_tag(takes_context=True)
def nav_entries(context):
    from .. import navigation

    return navigation.entries_for(context["request"])


@register.filter
def menu_sections(nav):
    """Non-empty Menu groups as (key, heading, links), in display order (U60)."""
    from .. import navigation

    return [(k, h, nav[k]) for k, h in navigation.MENU_GROUPS if nav.get(k)]


@register.filter
def initials(value):
    """Up to two capital initials: 'Gwen the GM' -> 'GG', 'Alice' -> 'A'."""
    words = [w for w in str(value or "").replace("@", " ").split() if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[-1][0]).upper()
