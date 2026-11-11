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
