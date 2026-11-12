from django import forms

from ledger.coins import CoinsField

from .models import Item


class ItemForm(forms.ModelForm):
    value = CoinsField(required=False, label="Value")

    class Meta:
        model = Item
        fields = ["name", "symbol", "description", "traits", "details"]

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club
        if self.instance.pk:
            self.initial["value"] = self.instance.value_cp

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clash = (
            Item.objects.for_club(self.club)
            .filter(name__iexact=name)
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if clash:
            raise forms.ValidationError("An item with this name already exists in this club.")
        return name

    def save(self, commit=True):
        self.instance.club = self.club
        self.instance.value_cp = self.cleaned_data.get("value") or 0
        return super().save(commit=commit)
