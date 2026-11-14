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


@register.filter(name="downtime_reward_text")
def downtime_reward_text(entry):
    """Plain text of what a ledger entry granted, read from its stored lines."""
    parts = []
    for line in entry.lines.all():
        if line.coins:
            parts.append(f"{'+' if line.coins > 0 else ''}{format_coins(line.coins)}")
        if line.item_id and line.quantity:
            sign = "+" if line.quantity > 0 else ""
            parts.append(f"{sign}{line.quantity} {line.item.name}")
    return ", ".join(parts)
