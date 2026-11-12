from django import forms
from django.utils import timezone

from ledger.coins import CoinsField
from map.models import LocationCredit

NOTHING = "Enter something to grant, or mark the message handled."


class GrantForm(forms.Form):
    """Grant coins, items and one map entry from an inbox message (U30)."""

    MAP_KINDS = [
        ("", "No map grant"),
        ("visit", "Visit"),
        (LocationCredit.Kind.DISCOVERED, "Discovered"),
        (LocationCredit.Kind.EXPLORED, "Explored"),
        ("found", "Found mark"),
    ]

    character = forms.ModelChoiceField(queryset=None)
    coins = CoinsField(required=False)
    map_kind = forms.ChoiceField(choices=MAP_KINDS, required=False, label="Map grant")
    location = forms.ModelChoiceField(queryset=None, required=False)
    hex_map = forms.ModelChoiceField(queryset=None, required=False, label="Map (tile visit)")
    q = forms.IntegerField(required=False)
    r = forms.IntegerField(required=False)
    note = forms.CharField(max_length=500)
    date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )
    mark_handled = forms.BooleanField(required=False, initial=True, label="Mark message handled")

    def __init__(self, *args, characters_qs, locations_qs, maps_qs, message, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message
        self.fields["character"].queryset = characters_qs
        self.fields["character"].initial = message.character_id
        self.fields["location"].queryset = locations_qs
        self.fields["location"].label_from_instance = lambda loc: (
            f"{loc.tile.map.name} – ({loc.tile.q}, {loc.tile.r}) – {loc.name}"
        )
        self.fields["hex_map"].queryset = maps_qs
        self.fields["note"].initial = f"From message #{message.pk}"

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
