"""Forms for club settings."""

from zoneinfo import available_timezones

from django import forms

from items.models import ClubWeightSettings

from ..models import Club


def timezone_choices(current=None):
    """Sorted (name, name) choices from zoneinfo.available_timezones().

    If `current` is set and not in the list, add it so an odd stored zone still shows.
    """
    choices = [(name, name) for name in sorted(available_timezones())]
    if current and current not in {name for name, _ in choices}:
        choices.insert(0, (current, current))
    return choices


class TimezoneChoiceField(forms.ChoiceField):
    """A time zone select built from the IANA database."""

    def __init__(self, **kwargs):
        kwargs.setdefault("label", "Time zone")
        kwargs.setdefault(
            "help_text",
            "Sessions are shown on this clock. Changing the zone keeps each session's moment, "
            "so a session can shift on the clock (for example 19:00 can become 16:00). "
            "Dates elsewhere in the app do not change.",
        )
        kwargs.setdefault("error_messages", {"invalid_choice": "Choose a time zone from the list."})
        super().__init__(**kwargs)


class ClubSettingsForm(forms.ModelForm):
    """Form for editing club settings (currently just time zone)."""

    timezone = TimezoneChoiceField()

    class Meta:
        model = Club
        fields = ["timezone"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["timezone"].choices = timezone_choices(self.instance.timezone)
        self.fields["timezone"].initial = self.instance.timezone


class ClubWeightSettingsForm(forms.ModelForm):
    """Form for editing club weight settings."""

    class Meta:
        model = ClubWeightSettings
        fields = ["count_coin_weight"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["count_coin_weight"].help_text = (
            "Count coins toward carrying weight at 50 coins per pound. "
            "Uses the minimum number of physical coins (platinum, gold, silver, copper)."
        )
