"""Forms for player-written items."""

from django import forms

from items.widgets import ItemPickerWidget

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


class MergeForm(forms.Form):
    """Form for merging or matching multiple player-written item groups.

    Mode choices:
    - merge: create one new catalogue item from multiple groups
    - match: match multiple groups to an existing catalogue item
    """

    NAME_MAX = 200

    MODE_CHOICES = [
        ("merge", "Make one new item"),
        ("match", "Match to existing item"),
    ]

    # Selected name_keys passed from the review page (multiple)
    name_keys = forms.MultipleChoiceField(
        choices=[],
        required=True,
        widget=forms.MultipleHiddenInput(),
    )

    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        required=True,
        label="Action",
        widget=forms.RadioSelect,
        initial="merge",
    )

    # Fields for "Make one new item" (merge mode)
    name = forms.CharField(
        max_length=NAME_MAX,
        required=False,
        label="New item name",
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

    # Field for "Match to existing item" (match mode)
    item = forms.ModelChoiceField(
        queryset=None,  # Set in __init__ with club-scoped queryset
        required=False,
        label="Existing item",
        empty_label="-- Select an item --",
    )

    quantity_factor = forms.IntegerField(
        required=False,
        initial=1,
        min_value=1,
        label="Quantity factor",
        widget=forms.NumberInput(attrs={"min": "1"}),
        help_text="Multiply each holder's total quantity by this factor.",
    )

    def __init__(self, *args, club=None, **kwargs):
        super().__init__(*args, **kwargs)
        if club is not None:
            from items.models import Item

            self.fields["item"].queryset = Item.objects.for_club(club).order_by("name")
            self.fields["item"].widget = ItemPickerWidget(club=club)
        # Populate name_keys choices from initial data or submitted data
        name_keys = self.initial.get("name_keys")
        if not name_keys and hasattr(self.data, "getlist"):
            name_keys = self.data.getlist("name_keys")
        elif not name_keys and isinstance(self.data, dict):
            name_keys = self.data.get("name_keys")
            if isinstance(name_keys, str):
                name_keys = [name_keys]
        if name_keys:
            self.fields["name_keys"].choices = [(nk, nk) for nk in name_keys]

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        is_stacked = cleaned.get("is_stacked")
        unit_name = cleaned.get("unit_name") or ""

        if mode == "merge":
            name = cleaned.get("name")
            if not name:
                self.add_error("name", "A name is required for the new item.")
            if is_stacked and not unit_name:
                self.add_error("unit_name", "A unit name is required for stacked items.")
            if not is_stacked:
                cleaned["unit_name"] = ""
        elif mode == "match":
            item = cleaned.get("item")
            if not item:
                self.add_error("item", "An existing item is required for matching.")
            # For match, name/is_stacked/unit_name are not used
            cleaned["name"] = ""
            cleaned["is_stacked"] = False
            cleaned["unit_name"] = ""

        return cleaned
