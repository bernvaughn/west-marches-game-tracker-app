"""Forms for character death actions."""

from django import forms
from django.utils import timezone


class DeathForm(forms.Form):
    """Form for marking a character as dead."""

    died_on = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
        required=True,
        help_text="Date of death. Cannot be in the future.",
    )
    note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        max_length=1000,
        help_text="Optional. A brief note about the circumstances.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Computed per request so a long-running server never keeps a stale max date.
        self.fields["died_on"].widget.attrs["max"] = timezone.localdate().isoformat()

    def clean_died_on(self):
        died_on = self.cleaned_data["died_on"]
        if died_on > timezone.localdate():
            raise forms.ValidationError("The death date cannot be in the future.")
        return died_on

    def clean_note(self):
        """Normalize line endings in note."""
        note = self.cleaned_data.get("note", "")
        return note.replace("\r\n", "\n")
