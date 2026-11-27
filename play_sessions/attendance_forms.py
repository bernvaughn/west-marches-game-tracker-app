"""Forms for attendance feature (P5, P6, P14, P15, P19)."""

from django import forms

from accounts.models import Membership
from player_characters.models import Character

from .models import PlayerRSVP
from .services_attendance import attendance_rows


class AttendanceForm(forms.Form):
    """Form for the attendance page.

    One ``members-<membership id>`` checkbox field per yes member, listing that
    member's active characters as checkboxes. Plus an ``add_member`` field for
    adding any club member who is not already "yes" (recorded as a yes RSVP by
    the GM). Each option is labelled with the member's current answer, e.g.
    "Bob (maybe)"; unanswered members show "no answer".
    """

    add_member = forms.ModelChoiceField(
        queryset=Membership.objects.none(),
        required=False,
        label="Add a member",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="Choose a member",
    )

    def __init__(self, club, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        yes_member_ids = set(
            PlayerRSVP.objects.filter(session=session, answer=PlayerRSVP.Answer.YES).values_list(
                "member_id", flat=True
            )
        )
        self.fields["add_member"].queryset = (
            Membership.objects.for_club(club)
            .exclude(id__in=yes_member_ids)
            .select_related("user")
            .order_by("user__display_name", "user__email")
        )

        # Label each option with the member's answer so the GM can tell an
        # unanswered member from a maybe or a no.
        answers = {r.member_id: r.answer for r in PlayerRSVP.objects.filter(session=session)}

        def label_from_instance(member):
            answer = answers.get(member.id)
            if answer is None:
                answer_text = "no answer"
            else:
                answer_text = answer
            return f"{member.user} ({answer_text})"

        self.fields["add_member"].label_from_instance = label_from_instance

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
