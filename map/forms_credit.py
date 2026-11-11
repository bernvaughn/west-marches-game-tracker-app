from django import forms
from django.utils import timezone


class PickForm(forms.Form):
    """Date for a visit or credit. Characters are read from POST and club-filtered in the view."""

    date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
