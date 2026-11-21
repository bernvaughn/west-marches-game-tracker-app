"""Forms for attendance feature (P5, P6)."""

from django import forms

from player_characters.models import Character

from .models import SessionRSVP
from .services_attendance import active_characters


class AttendanceForm(forms.Form):
    """Form for the attendance page: multiple character selection.

    The queryset is limited to active characters so that an inactive or
    other-club character ID posted in the form will be invalid.
    """

    characters = forms.ModelMultipleChoiceField(
        queryset=Character.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, club, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only active characters for this club
        active = active_characters(club)
        active_pks = [c.pk for c in active]
        self.fields["characters"].queryset = Character.objects.filter(pk__in=active_pks)


class RsvpForClubForm(forms.Form):
    """Form for a GM/admin to set an RSVP for any active club character."""

    character = forms.ModelChoiceField(
        queryset=Character.objects.none(),
        required=True,
    )
    answer = forms.ChoiceField(
        choices=SessionRSVP.Answer.choices,
        required=True,
    )

    def __init__(self, club, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active = active_characters(club)
        active_pks = [c.pk for c in active]
        self.fields["character"].queryset = Character.objects.filter(pk__in=active_pks)