from django import forms
from django.core.validators import MaxValueValidator

from ledger.coins import format_coins
from ledger.services import available_coins


class CharacterChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.name} ({format_coins(available_coins(obj))} available)"


class BuyForm(forms.Form):
    character = CharacterChoiceField(queryset=None)
    quantity = forms.IntegerField(min_value=1, initial=1)

    def __init__(self, *args, characters, max_quantity=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["character"].queryset = characters
        if max_quantity is not None:
            self.fields["quantity"].max_value = max_quantity
            self.fields["quantity"].validators.append(MaxValueValidator(max_quantity))
            self.fields["quantity"].widget.attrs["max"] = max_quantity
