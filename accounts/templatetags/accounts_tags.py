from django import template

from ..permissions import can_reset_password, can_see_email

register = template.Library()


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
def initials(value):
    """Up to two capital initials: 'Gwen the GM' -> 'GG', 'Alice' -> 'A'."""
    words = [w for w in str(value or "").replace("@", " ").split() if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[-1][0]).upper()
