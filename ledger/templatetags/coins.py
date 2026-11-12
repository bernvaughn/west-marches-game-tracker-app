from django import template
from django.utils.html import format_html, format_html_join

from ledger.coins import coin_items, format_coins

register = template.Library()


@register.filter(name="coins")
def coins(value):
    if value is None or value == "":
        return ""
    html = format_html_join(
        " ",
        '<span class="coin coin-{}">{} {}</span>',
        ((u, f"{n:,}", u) for n, u in coin_items(value)),
    )
    return format_html("-{}", html) if value < 0 else html


@register.filter(name="coins_text")
def coins_text(value):
    return format_coins(value)
