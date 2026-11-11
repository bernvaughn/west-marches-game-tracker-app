from django import template

from ledger.coins import format_coins

register = template.Library()


@register.filter(name="coins")
def coins(value):
    return format_coins(value)
