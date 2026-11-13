from django import forms

from items.models import Item
from ledger.coins import CoinsField, format_coins
from ledger.services import Line, available_coins, available_items

from .models import Character


class TradeSideForm(forms.Form):
    """Offer lines from one character's own available inventory."""

    def __init__(self, character, exclude_trade=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.character = character
        self.exclude_trade = exclude_trade
        avail = available_items(character, exclude_trade)
        self.items = {}
        for item in Item.objects.filter(pk__in=avail).order_by("name"):
            qty = avail[item.pk]
            if qty <= 0:
                continue
            self.items[item.pk] = item
            self.fields[f"item_{item.pk}"] = forms.IntegerField(
                min_value=0,
                max_value=qty,
                required=False,
                initial=0,
                label=f"{item.name} ({qty} available)",
            )
        self.available_coins = available_coins(character, exclude_trade)
        self.fields["coins"] = CoinsField(required=False, label="Coins to give")

    def clean_coins(self):
        coins = self.cleaned_data.get("coins") or 0
        if coins > self.available_coins:
            raise forms.ValidationError(f"Only {format_coins(self.available_coins)} available.")
        return coins

    def lines(self):
        out = []
        for pk, item in self.items.items():
            n = self.cleaned_data.get(f"item_{pk}") or 0
            if n > 0:
                out.append(Line(item=item, quantity=n))
        coins = self.cleaned_data.get("coins") or 0
        if coins > 0:
            out.append(Line(coins=coins))
        return out


class ProposeTradeForm(forms.Form):
    receiver = forms.ModelChoiceField(queryset=Character.objects.none())
    note = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, user, club, data=None, initial=None):
        super().__init__(data=data, initial=initial)
        chars = Character.objects.for_club(club)
        receivers = chars.exclude(owner__user=user).select_related("owner__user")
        self.fields["receiver"].queryset = receivers
        self.fields["receiver"].label_from_instance = lambda c: (
            f"{c.name} ({c.owner.user.display_name})"
        )
