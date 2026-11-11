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


def format_coins(cp):
    if cp is None:
        return ""
    parts = split_copper(abs(cp))
    text = " ".join(
        f"{n} {unit}" for n, unit in zip(parts, ("pp", "gp", "sp", "cp"), strict=True) if n
    )
    if not text:
        return "0 cp"
    return f"-{text}" if cp < 0 else text


class CoinsWidget(forms.MultiWidget):
    template_name = "django/forms/widgets/multiwidget.html"

    def __init__(self, attrs=None):
        widgets = {
            suffix: forms.NumberInput(attrs={"min": 0}) for suffix in ("pp", "gp", "sp", "cp")
        }
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value is None or value == "":
            return [None] * 4
        return list(split_copper(abs(value)))


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
