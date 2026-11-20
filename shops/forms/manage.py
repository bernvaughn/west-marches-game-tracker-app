from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator

from accounts.models import Club
from items.models import Item
from shops.models import Shop, ShopStock

PERCENT = [MinValueValidator(0), MaxValueValidator(1000)]


class SilhouetteSelect(forms.RadioSelect):
    """Radio buttons, each with a small preview of the silhouette."""

    template_name = "shops/widgets/silhouette_radios.html"
    option_template_name = "shops/widgets/silhouette_option.html"


class BuildingSelect(forms.RadioSelect):
    """Radio buttons, each with a small preview of the building."""

    template_name = "shops/widgets/building_radios.html"
    option_template_name = "shops/widgets/building_option.html"


class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = [
            "name", "description", "keeper_name", "keeper_description",
            "color", "silhouette", "building", "street_position", "symbol",
            "sell_percent", "buy_percent",
        ]  # fmt: skip
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "keeper_description": forms.Textarea(attrs={"rows": 3}),
            "silhouette": SilhouetteSelect,
            "building": BuildingSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("sell_percent", "buy_percent"):
            self.fields[name].validators.extend(PERCENT)
        # Left out of a post, these keep their model defaults.
        self.fields["building"].required = False
        self.fields["street_position"].required = False

    def clean_building(self):
        return self.cleaned_data.get("building") or Shop.Building.GENERAL_STORE

    def clean_street_position(self):
        value = self.cleaned_data.get("street_position")
        return 0 if value is None else value


class _StockPercentMixin:
    def _setup_percent(self):
        self.fields["quantity"].help_text = "Leave blank for unlimited."
        for name in ("sell_percent", "buy_percent"):
            self.fields[name].validators.extend(PERCENT)
            self.fields[name].help_text = "Leave blank to use the shop default."


class _StockBundleMixin:
    """Shared bundle_units field and validation for add/edit forms."""

    def _setup_bundle(self, shop):
        self.fields[
            "bundle_units"
        ].help_text = (
            "Units in one bundle. Use 1 for normal items. Price override applies per bundle."
        )
        self.fields["bundle_units"].validators.extend([MinValueValidator(1)])
        # Model has default=1, so field is not required in POST
        self.fields["bundle_units"].required = False

    def clean_bundle_units(self):
        bundle_units = self.cleaned_data.get("bundle_units")
        if bundle_units is None:
            bundle_units = 1
        item = self.cleaned_data.get("item") or getattr(self.instance, "item", None)
        if item and not item.is_stacked and bundle_units != 1:
            raise forms.ValidationError("Non-stacked items must have bundle size 1.")
        return bundle_units

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("item") or getattr(self.instance, "item", None)
        bundle_units = cleaned.get("bundle_units")
        shop = getattr(self, "shop", getattr(self.instance, "shop", None))
        if item and bundle_units and shop:
            qs = ShopStock.objects.filter(shop=shop, item=item, bundle_units=bundle_units)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f"This shop already has a bundle of {bundle_units} for this item."
                )
        return cleaned


class StockAddForm(_StockBundleMixin, _StockPercentMixin, forms.ModelForm):
    class Meta:
        model = ShopStock
        fields = ["item", "bundle_units", "quantity", "sell_percent", "buy_percent"]

    def __init__(self, *args, shop, **kwargs):
        super().__init__(*args, **kwargs)
        self.shop = shop
        self.fields["item"].queryset = (
            Item.objects.for_club(shop.club).filter(retired=False).exclude(stock_entries__shop=shop)
        )
        # Allow adding a stacked item again with a different bundle size:
        # include items that are stacked OR have no line in this shop.
        # The queryset above already excludes items with any line in this shop.
        # For stacked items we want to allow re-adding, so we need to adjust.
        # Rebuild the queryset to exclude only non-stacked items that already have a line.
        from django.db.models import Q

        self.fields["item"].queryset = (
            Item.objects.for_club(shop.club)
            .filter(retired=False)
            .exclude(
                # Exclude non-stacked items that already have a line in this shop
                Q(is_stacked=False) & Q(stock_entries__shop=shop)
            )
        )
        self._setup_percent()
        self._setup_bundle(shop)
        # Default bundle_units to 1
        self.fields["bundle_units"].initial = 1


class StockEditForm(_StockBundleMixin, _StockPercentMixin, forms.ModelForm):
    class Meta:
        model = ShopStock
        fields = ["bundle_units", "quantity", "sell_percent", "buy_percent"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_percent()
        self._setup_bundle(self.instance.shop)
        # Non-stacked items: bundle_units is forced to 1, disable the field
        if not self.instance.item.is_stacked:
            self.fields["bundle_units"].disabled = True
            self.fields["bundle_units"].help_text = "Non-stacked items always use bundle size 1."


class StreetSettingsForm(forms.ModelForm):
    class Meta:
        model = Club
        fields = ["street_min_gap", "street_max_gap", "street_stall_gap"]

    def clean(self):
        data = super().clean()
        low, high = data.get("street_min_gap"), data.get("street_max_gap")
        if low is not None and high is not None and high < low:
            self.add_error("street_max_gap", "The maximum can't be lower than the minimum.")
        return data
