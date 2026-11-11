from django import forms
from django.db.models import Q

from items.models import Item
from ledger.coins import CoinsField
from player_characters.models import Character

from .models import ProposedItem


class LineForm(forms.Form):
    character = forms.ModelChoiceField(queryset=Character.objects.none())
    item = forms.ModelChoiceField(queryset=Item.objects.none(), required=False)
    proposed_item = forms.ModelChoiceField(queryset=ProposedItem.objects.none(), required=False)
    quantity = forms.IntegerField(min_value=0, required=False)
    coins = CoinsField(required=False)
    note = forms.CharField(max_length=1000, required=False)
    date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, club, line, **kwargs):
        kwargs.setdefault("prefix", f"line-{line.pk}")
        kwargs.setdefault("initial", initial_for(line))
        super().__init__(*args, **kwargs)
        self.fields["character"].queryset = Character.objects.for_club(club)
        self.fields["item"].queryset = Item.objects.for_club(club).filter(
            Q(retired=False) | Q(pk=line.item_id)
        )
        self.fields["proposed_item"].queryset = ProposedItem.objects.for_club(club).filter(
            ~Q(status=ProposedItem.Status.REJECTED) | Q(pk=line.proposed_item_id)
        )

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        item, proposed = data.get("item"), data.get("proposed_item")
        coins = data.get("coins") or 0
        quantity = data.get("quantity") or 0
        kinds = [bool(item), bool(proposed), coins > 0]
        if sum(kinds) != 1:
            raise forms.ValidationError("Give exactly one of an item, a proposed item or coins.")
        if item or proposed:
            if quantity <= 0:
                raise forms.ValidationError("An item line needs a quantity above zero.")
            data["coins"] = 0
        else:
            data["quantity"] = 0
        return data


def initial_for(line):
    return {
        "character": line.character_id,
        "item": line.item_id,
        "proposed_item": line.proposed_item_id,
        "quantity": line.quantity,
        "coins": line.coins or None,
        "note": line.note,
        "date": line.date,
    }
