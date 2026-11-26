"""Forms for attendance feature (P5, P6, P14, P15)."""

from django import forms

from accounts.models import Membership
from player_characters.models import Character

from .models import PlayerRSVP
from .services_attendance import attendance_rows


class AttendanceForm(forms.Form):
    """Form for the attendance page.

    One ``members-<membership id>`` checkbox field per yes member, listing that
    member's active characters as checkboxes. Plus an ``add_member`` field for
    adding a member who never answered (recorded as a yes RSVP).
    """

    add_member = forms.ModelChoiceField(
        queryset=Membership.objects.none(),
        required=False,
        label="Add a member who never answered",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, club, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        answered = PlayerRSVP.objects.filter(session=session).values_list("member_id", flat=True)
        self.fields["add_member"].queryset = Membership.objects.for_club(club).exclude(
            id__in=answered
        )

        # One checkbox field per yes member, holding that member's active characters.
        for row in attendance_rows(session, club):
            member = row["member"]
            pks = [cr["character"].pk for cr in row["characters"]]
            self.fields[f"members-{member.id}"] = forms.ModelMultipleChoiceField(
                queryset=Character.objects.filter(pk__in=pks),
                required=False,
                widget=forms.CheckboxSelectMultiple,
                label=str(member.user),
            )

    def member_field_names(self):
        """Return the names of the per-member character checkbox fields."""
        return [name for name in self.fields if name.startswith("members-")]


class RsvpForMemberForm(forms.Form):
    """Form for a GM/admin to set a per-player RSVP for any club member."""

    member = forms.ModelChoiceField(
        queryset=Membership.objects.none(),
        required=True,
    )
    answer = forms.ChoiceField(
        choices=PlayerRSVP.Answer.choices,
        required=True,
    )

    def __init__(self, club, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["member"].queryset = Membership.objects.for_club(club)
