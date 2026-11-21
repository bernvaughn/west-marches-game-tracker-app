from django import forms


class WhitelistForm(forms.Form):
    email = forms.EmailField()
    display_name = forms.CharField(max_length=100, required=False)
    is_club_admin = forms.BooleanField(
        required=False,
        label="Club admin",
        help_text="Manages members, items, shops and the inbox.",
    )
    is_game_master = forms.BooleanField(
        required=False,
        label="Game master",
        help_text="Runs games and awards loot.",
    )
    character_name = forms.CharField(max_length=200, required=False)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class RolesForm(forms.Form):
    is_club_admin = forms.BooleanField(
        required=False,
        label="Club admin",
        help_text="Manages members, items, shops and the inbox.",
    )
    is_game_master = forms.BooleanField(
        required=False,
        label="Game master",
        help_text="Runs games and awards loot.",
    )
