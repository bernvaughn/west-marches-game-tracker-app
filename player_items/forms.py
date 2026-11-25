"""Form for adding or editing a player-written item."""

from django import forms

NAME_MAX = 80


class PlayerItemForm(forms.Form):
    """Name, quantity and optional note for a player-written item.

    Player-written items are free text: they are not sellable and never
    touch the ledger.
    """

    name = forms.CharField(
        max_length=NAME_MAX,
        required=True,
        label="Name",
        strip=True,
        widget=forms.TextInput(attrs={"maxlength": NAME_MAX}),
    )
    quantity = forms.IntegerField(
        required=True,
        initial=1,
        min_value=1,
        label="Quantity",
        widget=forms.NumberInput(attrs={"min": "1"}),
    )
    note = forms.CharField(
        required=False,
        label="Note",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
