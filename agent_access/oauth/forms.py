from django import forms
from oauth2_provider.forms import AllowForm

from accounts.models import Club, Membership


def game_master_clubs(user):
    if user.is_superuser:
        return Club.objects.all().order_by("name")
    return Club.objects.filter(
        pk__in=Membership.objects.filter(user=user, is_game_master=True).values("club_id")
    ).order_by("name")


class ConsentForm(AllowForm):
    club = forms.ModelChoiceField(queryset=Club.objects.none(), required=False, empty_label=None)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["club"].queryset = game_master_clubs(user)

    def clean(self):
        data = super().clean()
        if data.get("allow") and not data.get("club") and "club" not in self.errors:
            self.add_error("club", "Pick a club you are a game master of.")
        return data
