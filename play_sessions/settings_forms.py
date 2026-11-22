"""Forms for play session settings."""

from django import forms
from django.forms import NumberInput

from .models import SessionSettings


class SessionSettingsForm(forms.ModelForm):
    """Form for editing session settings."""

    class Meta:
        model = SessionSettings
        fields = ["award_points"]
        widgets = {
            "award_points": NumberInput(attrs={"min": "0", "max": "10", "step": "1"}),
        }
        help_texts = {
            "award_points": (
                "Whole downtime points per character that played. "
                "0 means no award. Past awards never change."
            ),
        }

    def clean_award_points(self):
        value = self.cleaned_data["award_points"]
        if not isinstance(value, int):
            raise forms.ValidationError("Award points must be a whole number.")
        if value < 0 or value > 10:
            raise forms.ValidationError("Award points must be between 0 and 10.")
        return value
