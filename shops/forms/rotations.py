from django import forms

from shops.models import Rotation, Shop


class RotationForm(forms.ModelForm):
    class Meta:
        model = Rotation
        fields = ["name", "open_date", "close_date", "shops"]
        widgets = {
            "open_date": forms.DateInput(attrs={"type": "date"}),
            "close_date": forms.DateInput(attrs={"type": "date"}),
            "shops": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["shops"].queryset = Shop.objects.for_club(club)
        self.fields["shops"].required = False

    def clean(self):
        cleaned = super().clean()
        open_date = cleaned.get("open_date")
        close_date = cleaned.get("close_date")
        if open_date and close_date and close_date < open_date:
            self.add_error("close_date", "The close date must be on or after the open date.")
        return cleaned
