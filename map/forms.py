from django import forms
from django.utils import timezone

from .models import BANDS, Encounter, HexMap, Location

COLOUR_CHOICES = [
    ("", "Default"),
    ("red", "Red"),
    ("orange", "Orange"),
    ("yellow", "Yellow"),
    ("green", "Green"),
    ("teal", "Teal"),
    ("blue", "Blue"),
    ("purple", "Purple"),
    ("brown", "Brown"),
    ("grey", "Grey"),
    ("black", "Black"),
]


class MapForm(forms.ModelForm):
    class Meta:
        model = HexMap
        fields = ["name"]


class MapEditForm(forms.ModelForm):
    class Meta:
        model = HexMap
        fields = ["name", "archived"]


class LocationForm(forms.ModelForm):
    color = forms.ChoiceField(choices=COLOUR_CHOICES, required=False, label="Colour")
    symbol = forms.CharField(max_length=2, required=False, strip=True)
    target_band = forms.ChoiceField(
        choices=[("", "None")] + [(b, f"CR {b}") for b, _ in BANDS],
        required=False,
        label="Target level",
    )

    class Meta:
        model = Location
        fields = ["name", "color", "symbol", "player_notes", "gm_notes", "target_band"]


class EncounterForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        initial=timezone.localdate,
        required=False,
    )
    description = forms.CharField(widget=forms.Textarea, required=True)

    class Meta:
        model = Encounter
        fields = ["date", "description"]
