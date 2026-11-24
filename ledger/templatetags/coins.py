from django import template
from django.utils.html import format_html, format_html_join

from items.services import StackedPricingService
from items.values import format_item_value
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


@register.filter
def signed_units(line):
    """Signed quantity text for a ledger line, quantity part only.

    Stacked items: "+40 ft" (units plus unit name; the template adds the item
    name via _item_name so it is not repeated). Normal items: "+3".
    """
    if line.item is None or not line.item.is_stacked:
        return f"{line.quantity:+d}"
    sign = "+" if line.quantity > 0 else "-"
    return f"{sign}{abs(line.quantity)} {line.item.unit_name}"


@register.filter(name="downtime_reward_text")
def downtime_reward_text(entry):
    """Plain text of what a ledger entry granted, read from its stored lines."""
    parts = []
    for line in entry.lines.all():
        if line.coins:
            parts.append(f"{'+' if line.coins > 0 else ''}{format_coins(line.coins)}")
        if line.item_id and line.quantity:
            if line.item.is_stacked:
                sign = "+" if line.quantity > 0 else "-"
                parts.append(
                    f"{sign}{StackedPricingService.unit_label(line.item, abs(line.quantity))}"
                )
            else:
                parts.append(f"{'+' if line.quantity > 0 else ''}{line.quantity} {line.item.name}")
    return ", ".join(parts)


@register.filter(name="item_value")
def item_value(item):
    """Format an item's value for display."""
    return format_item_value(item)
