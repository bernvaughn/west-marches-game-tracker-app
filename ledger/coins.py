"""Coin helpers. 1 pp = 10 gp = 100 sp = 1000 cp."""

from django import forms

CP_PER_SP = 10
CP_PER_GP = 100
CP_PER_PP = 1000


def split_copper(cp):
    """Split copper into (pp, gp, sp, cp). A negative value negates every part."""
    sign = -1 if cp < 0 else 1
    pp, rest = divmod(abs(cp), CP_PER_PP)
    gp, rest = divmod(rest, CP_PER_GP)
    sp, copper = divmod(rest, CP_PER_SP)
    return (sign * pp, sign * gp, sign * sp, sign * copper)


UNITS = ("pp", "gp", "sp", "cp")


def display_parts(cp):
    """(pp, gp, sp, cp) for display. Under 10,000 gp, gold holds everything above silver."""
    if abs(cp) >= 10_000 * CP_PER_GP:
        return split_copper(cp)
    sign = -1 if cp < 0 else 1
    gp, rest = divmod(abs(cp), CP_PER_GP)
    sp, copper = divmod(rest, CP_PER_SP)
    return (0, sign * gp, sign * sp, sign * copper)


def coin_items(cp):
    """(amount, unit) for each non-zero part of abs(cp); zero gives [(0, "cp")]."""
    items = [(n, u) for n, u in zip(display_parts(abs(cp)), UNITS, strict=True) if n]
    return items or [(0, "cp")]


def format_coins(cp):
    if cp is None:
        return ""
    text = " ".join(f"{n:,} {unit}" for n, unit in coin_items(cp))
    return f"-{text}" if cp < 0 else text


class CoinsWidget(forms.MultiWidget):
    template_name = "ledger/widgets/coins.html"

    def __init__(self, attrs=None):
        widgets = {
            suffix: forms.NumberInput(attrs={"min": 0}) for suffix in ("pp", "gp", "sp", "cp")
        }
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value is None or value == "":
            return [None] * 4
        return list(display_parts(abs(value)))


class CoinsField(forms.MultiValueField):
    widget = CoinsWidget

    def __init__(self, **kwargs):
        fields = [forms.IntegerField(min_value=0, required=False) for _ in range(4)]
        kwargs.setdefault("require_all_fields", False)
        super().__init__(fields=fields, **kwargs)

    def compress(self, data_list):
        if not data_list:
            return 0
        pp, gp, sp, cp = (n or 0 for n in data_list)
        return pp * CP_PER_PP + gp * CP_PER_GP + sp * CP_PER_SP + cp
