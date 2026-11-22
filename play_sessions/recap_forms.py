"""Forms for the recap feature."""

from django import forms

from .models import PlaySession


class RecapForm(forms.ModelForm):
    """Form for editing a session's recap and GM notes."""

    class Meta:
        model = PlaySession
        fields = ["recap", "gm_notes"]
        widgets = {
            "recap": forms.Textarea(attrs={"rows": 8}),
            "gm_notes": forms.Textarea(attrs={"rows": 6}),
        }
        labels = {
            "recap": "Recap",
            "gm_notes": "GM notes",
        }
        help_texts = {
            "gm_notes": "Only game masters and club admins can see this",
        }
