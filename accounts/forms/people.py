from django import forms


class WhitelistForm(forms.Form):
    email = forms.EmailField()
    display_name = forms.CharField(max_length=100, required=False)
    is_game_master = forms.BooleanField(required=False, label="Game master")
    character_name = forms.CharField(max_length=200, required=False)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
