from django import forms
from django.utils import timezone

from ledger.coins import CoinsField
from map.models import LocationCredit


class GrantBaseForm(forms.Form):
    """The fields every inbox grant shares: character, note, date, mark handled (U30, U38)."""

    character = forms.ModelChoiceField(queryset=None)
    note = forms.CharField(max_length=500)
    date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )
    mark_handled = forms.BooleanField(required=False, initial=True, label="Mark message handled")

    def __init__(self, *args, characters_qs, message, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message
        self.fields["character"].queryset = characters_qs
        self.fields["character"].initial = message.character_id
        self.fields["note"].initial = f"From message #{message.pk}"


class CoinsGrantForm(GrantBaseForm):
    coins = CoinsField(error_messages={"required": "Enter an amount."})

    def clean_coins(self):
        coins = self.cleaned_data["coins"]
        if not coins:
            raise forms.ValidationError("Enter an amount.")
        return coins


class ItemsGrantForm(GrantBaseForm):
    """Base fields only. The view pairs it with an item line formset."""


class MapGrantForm(GrantBaseForm):
    MAP_KINDS = [
        ("visit", "Visit"),
        (LocationCredit.Kind.DISCOVERED, "Discovered"),
        (LocationCredit.Kind.EXPLORED, "Explored"),
        ("found", "Found mark"),
    ]

    map_kind = forms.ChoiceField(
        choices=MAP_KINDS, widget=forms.RadioSelect, label="Kind of map credit"
    )
    location = forms.ModelChoiceField(queryset=None, required=False)
    hex_map = forms.ModelChoiceField(queryset=None, required=False, label="Map (tile visit)")
    q = forms.IntegerField(required=False)
    r = forms.IntegerField(required=False)

    def __init__(self, *args, locations_qs, maps_qs, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].queryset = locations_qs
        self.fields["location"].label_from_instance = lambda loc: (
            f"{loc.tile.map.name} – ({loc.tile.q}, {loc.tile.r}) – {loc.name}"
        )
        self.fields["hex_map"].queryset = maps_qs

    def clean(self):
        data = super().clean()
        kind = data.get("map_kind")
        if kind in ("discovered", "explored", "found") and not data.get("location"):
            self.add_error("location", "Choose a location.")
        if kind == "visit" and not data.get("location"):
            if not (
                data.get("hex_map") and data.get("q") is not None and data.get("r") is not None
            ):
                self.add_error(None, "A visit needs a location, or a map with q and r.")
        return data


GRANT_FORMS = {"coins": CoinsGrantForm, "items": ItemsGrantForm, "map": MapGrantForm}
GRANT_TITLES = {"coins": "Give coins", "items": "Give items", "map": "Give map credit"}
