"""Forms for scheduling play sessions."""

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from accounts.models import Membership

from . import core


class SessionForm(forms.Form):
    """Form for creating or editing a play session.

    Constructor: (club, membership, instance=None, with_repeat=True, *args)
    """

    REPEAT_CHOICES = [
        ("none", "None"),
        ("weekly", "Weekly"),
        ("every_two_weeks", "Every two weeks"),
    ]

    title = forms.CharField(max_length=200)
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}), required=False)
    game_master = forms.ModelChoiceField(queryset=Membership.objects.none(), required=False)
    location = forms.CharField(max_length=200, required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)

    # Create-only fields
    repeat = forms.ChoiceField(choices=REPEAT_CHOICES, initial="none", required=False)
    count = forms.IntegerField(initial=4, required=False)

    def __init__(self, club, membership, instance=None, with_repeat=True, *args, **kwargs):
        self.club = club
        self.membership = membership
        self.instance = instance
        self.with_repeat = with_repeat
        super().__init__(*args, **kwargs)

        # Game master choices: club GMs and admins, plus instance's current GM
        gm_queryset = Membership.objects.for_club(club).filter(
            Q(is_game_master=True) | Q(is_club_admin=True)
        )
        if instance and instance.game_master_id:
            gm_queryset = gm_queryset | Membership.objects.filter(pk=instance.game_master_id)
        self.fields["game_master"].queryset = gm_queryset

        if not with_repeat:
            self.fields.pop("repeat", None)
            self.fields.pop("count", None)

        if instance:
            # Edit: initial values from club local time
            starts_local = core.to_club_local(club, instance.starts_at)
            ends_local = core.to_club_local(club, instance.ends_at) if instance.ends_at else None
            self.fields["title"].initial = instance.title
            self.fields["date"].initial = starts_local.date()
            self.fields["start_time"].initial = starts_local.time()
            if ends_local:
                self.fields["end_time"].initial = ends_local.time()
            self.fields["game_master"].initial = instance.game_master
            self.fields["location"].initial = instance.location
            self.fields["notes"].initial = instance.notes
        else:
            # Create: initial game master is the current membership
            self.fields["game_master"].initial = membership

    def clean(self):
        cleaned = super().clean()
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
        repeat = cleaned.get("repeat")
        count = cleaned.get("count")

        if end_time and start_time and end_time <= start_time:
            raise ValidationError({"end_time": "End time must be after start time."})

        if repeat and repeat != "none":
            if count is None:
                cleaned["count"] = 4
                count = 4
            if count < 2 or count > 26:
                raise ValidationError({"count": "Count must be between 2 and 26."})

        return cleaned
