from django import forms

from shops.models import Rotation, Shop
from shops.services import ordered_shops


class CopyStockForm(forms.Form):
    """Form for copying stock entries from a source rotation or shop to target shops."""

    SOURCE_ROTATION = "rotation"
    SOURCE_SHOP = "shop"
    SOURCE_CHOICES = [
        (SOURCE_ROTATION, "Copy from a rotation"),
        (SOURCE_SHOP, "Copy from a single shop"),
    ]

    source_type = forms.ChoiceField(
        choices=SOURCE_CHOICES,
        widget=forms.RadioSelect,
        initial=SOURCE_ROTATION,
    )
    source_rotation = forms.ModelChoiceField(
        queryset=Rotation.objects.none(),
        required=False,
        label="Source rotation",
    )
    source_shop = forms.ModelChoiceField(
        queryset=Shop.objects.none(),
        required=False,
        label="Source shop",
    )
    target_shops = forms.ModelMultipleChoiceField(
        queryset=Shop.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Target shops",
    )

    def __init__(self, *args, club, rotation=None, **kwargs):
        super().__init__(*args, **kwargs)
        club_shops = ordered_shops(Shop.objects.for_club(club))
        self.fields["source_rotation"].queryset = Rotation.objects.for_club(club)
        self.fields["source_shop"].queryset = club_shops
        self.fields["target_shops"].queryset = club_shops
        if rotation is not None:
            self.fields["target_shops"].initial = rotation.shops.all()

    def clean(self):
        cleaned = super().clean()
        source_type = cleaned.get("source_type")
        source_rotation = cleaned.get("source_rotation")
        source_shop = cleaned.get("source_shop")
        target_shops = cleaned.get("target_shops")

        if source_type == self.SOURCE_ROTATION and not source_rotation:
            self.add_error("source_rotation", "Select a source rotation.")
        if source_type == self.SOURCE_SHOP and not source_shop:
            self.add_error("source_shop", "Select a source shop.")
        if not target_shops:
            self.add_error("target_shops", "Select at least one target shop.")
        return cleaned


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
        self.fields["shops"].queryset = ordered_shops(Shop.objects.for_club(club))
        self.fields["shops"].required = False

    def clean(self):
        cleaned = super().clean()
        open_date = cleaned.get("open_date")
        close_date = cleaned.get("close_date")
        if open_date and close_date and close_date < open_date:
            self.add_error("close_date", "The close date must be on or after the open date.")
        return cleaned
