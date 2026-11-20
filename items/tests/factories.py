"""Test factories for the container contract.

Content items are created with ``get_or_create`` by name inside a club so the
same fixture can be reused across tests without duplicates.
"""

from items.models import ContainerSlot, ContainerSlotOption, Item


def _get_or_create_item(club, name, **kw):
    defaults = {"club": club, "value_cp": 0, "retired": False, "is_container": False}
    defaults.update(kw)
    item, _ = Item.objects.get_or_create(club=club, name=name, defaults=defaults)
    return item


def make_container(club, name="Mystery Box", **kw):
    """Create a container item in ``club``."""

    defaults = {"club": club, "name": name, "is_container": True}
    defaults.update(kw)
    return Item.objects.create(**defaults)


def add_slot(container, options, chance_pct=100, unknown=False, position=None):
    """Add a slot to ``container``.

    ``options`` is a list of ``(item, qty_min, qty_max, weight)`` tuples; a
    bare item is treated as ``qty 1, weight 1``.
    """

    if position is None:
        position = ContainerSlot.objects.filter(container=container).count()
    slot = ContainerSlot.objects.create(
        container=container,
        chance_pct=chance_pct,
        unknown=unknown,
        position=position,
    )
    for option in options:
        if isinstance(option, Item):
            item, qty_min, qty_max, weight = option, 1, 1, 1
        else:
            item, qty_min, qty_max, weight = option
        ContainerSlotOption.objects.create(
            slot=slot,
            item=item,
            qty_min=qty_min,
            qty_max=qty_max,
            weight=weight,
        )
    return slot


def make_diplomats_pack(club):
    """Diplomat's Pack fixture: fixed, ranged, 50%, weighted and unknown slots."""

    container = make_container(club, name="Diplomat's Pack")
    fine_clothes = _get_or_create_item(club, "Fine clothes")
    flask_of_oil = _get_or_create_item(club, "Flask of oil")
    vial_of_perfume = _get_or_create_item(club, "Vial of perfume")
    sealing_wax = _get_or_create_item(club, "Sealing wax")
    soap = _get_or_create_item(club, "Soap")
    sealed_letter = _get_or_create_item(club, "Sealed letter")

    add_slot(container, [(fine_clothes, 1, 1, 1)], chance_pct=100, position=0)
    add_slot(container, [(flask_of_oil, 1, 2, 1)], chance_pct=100, position=1)
    add_slot(container, [(vial_of_perfume, 1, 1, 1)], chance_pct=50, position=2)
    add_slot(
        container,
        [(sealing_wax, 1, 1, 3), (soap, 1, 1, 1)],
        chance_pct=100,
        position=3,
    )
    add_slot(container, [(sealed_letter, 1, 1, 1)], chance_pct=100, unknown=True, position=4)
    return container


def make_stacked(club, name, unit_name, value_cp, value_units):
    """Create a stacked item in ``club``.

    ``value_cp`` is the price that ``value_units`` units cover.
    """
    return Item.objects.create(
        club=club,
        name=name,
        is_stacked=True,
        unit_name=unit_name,
        value_cp=value_cp,
        value_units=value_units,
    )


def make_parchment(club):
    """Parchment: 100 cp per 10 sheets."""
    return make_stacked(club, "Parchment", "sheet", 100, 10)


def make_rope(club):
    """Rope: 100 cp per 50 ft."""
    return make_stacked(club, "Rope", "ft", 100, 50)


def make_arrows(club):
    """Arrows: 100 cp per 20 arrows."""
    return make_stacked(club, "Arrows", "arrow", 100, 20)
