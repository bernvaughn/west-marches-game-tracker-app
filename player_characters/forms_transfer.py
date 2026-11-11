from django import forms

from ledger.coins import CoinsField


class TransferForm(forms.Form):
    destination = forms.ModelChoiceField(queryset=None)
    coins = CoinsField(required=False)
    note = forms.CharField(max_length=500, required=False)

    def __init__(self, *args, destinations, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destination"].queryset = destinations
