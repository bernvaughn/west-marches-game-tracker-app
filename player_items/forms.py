"""Forms for player-written items."""

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


class PromoteForm(forms.Form):
    """Form for promoting a player-written item group to a catalogue item.

    ``unit_name`` is required when the target is stacked. ``quantity_factor``
    converts the holder's total player-written quantity into catalogue units.
    """

    NAME_MAX = 200

    name = forms.CharField(
        max_length=NAME_MAX,
        required=True,
        label="Item name",
        strip=True,
        widget=forms.TextInput(attrs={"maxlength": NAME_MAX}),
    )
    is_stacked = forms.BooleanField(
        required=False,
        label="Stacked item (sold in bundles, used one unit at a time)",
        help_text="Checked when the new catalogue item is stacked.",
    )
    unit_name = forms.CharField(
        max_length=40,
        required=False,
        label="Unit name",
        widget=forms.TextInput(attrs={"maxlength": 40}),
        help_text="Required for stacked items, e.g. ft, sheet, arrow.",
    )
    quantity_factor = forms.IntegerField(
        required=False,
        initial=1,
        min_value=1,
        label="Quantity factor",
        widget=forms.NumberInput(attrs={"min": "1"}),
        help_text="Multiply the holder's total quantity by this factor.",
    )

    def clean(self):
        cleaned = super().clean()
        is_stacked = cleaned.get("is_stacked")
        unit_name = cleaned.get("unit_name") or ""
        if is_stacked and not unit_name:
            self.add_error("unit_name", "A unit name is required for stacked items.")
        if not is_stacked:
            cleaned["unit_name"] = ""
        return cleaned
