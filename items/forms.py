from django import forms
from django.utils.html import format_html, format_html_join

from ledger.coins import CoinsField

from . import rarity
from .models import Item


class ItemForm(forms.ModelForm):
    value = CoinsField(required=False, label="Value")

    class Meta:
        model = Item
        fields = ["name", "symbol", "description", "traits", "details", "rarity"]
        field_order = ["name", "symbol", "description", "traits", "details", "rarity", "value"]
        widgets = {"rarity": forms.Select(attrs={"data-rarity-select": ""})}

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club
        self.fields["rarity"].choices = [("", "—"), *rarity.Rarity.choices]
        self.fields["value"].help_text = format_html(
            '<span class="wm-rarity-hint" data-rarity-hint>Suggested value (2014 DMG):{}</span>',
            format_html_join(
                "",
                '<span data-rarity-item="{}" style="display:block">{} {}</span>',
                rarity.ranges(),
            ),
        )
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
