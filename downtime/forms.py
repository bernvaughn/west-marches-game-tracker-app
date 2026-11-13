from django import forms
from django.utils import timezone

from player_characters.models import Character


class PointsForm(forms.Form):
    DIRECTIONS = [("give", "Give"), ("take", "Take")]

    characters = forms.ModelMultipleChoiceField(
        queryset=Character.objects.none(), widget=forms.CheckboxSelectMultiple
    )
    direction = forms.ChoiceField(choices=DIRECTIONS, widget=forms.RadioSelect, initial="give")
    points = forms.IntegerField(min_value=1)
    note = forms.CharField(max_length=500)
    date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["characters"].queryset = Character.objects.for_club(club).order_by("name", "id")

    def signed_delta(self):
        points = self.cleaned_data["points"]
        return points if self.cleaned_data["direction"] == "give" else -points
