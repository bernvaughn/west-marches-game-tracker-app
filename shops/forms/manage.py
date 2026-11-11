from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator

from items.models import Item
from shops.models import Shop, ShopStock

PERCENT = [MinValueValidator(0), MaxValueValidator(1000)]


class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = [
            "name", "description", "keeper_name", "keeper_description",
            "color", "symbol", "sell_percent", "buy_percent",
        ]  # fmt: skip
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "keeper_description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("sell_percent", "buy_percent"):
            self.fields[name].validators.extend(PERCENT)


class _StockPercentMixin:
    def _setup_percent(self):
        self.fields["quantity"].help_text = "Leave blank for unlimited."
        for name in ("sell_percent", "buy_percent"):
            self.fields[name].validators.extend(PERCENT)
            self.fields[name].help_text = "Leave blank to use the shop default."


class StockAddForm(_StockPercentMixin, forms.ModelForm):
    class Meta:
        model = ShopStock
        fields = ["item", "quantity", "sell_percent", "buy_percent"]

    def __init__(self, *args, shop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = (
            Item.objects.for_club(shop.club).filter(retired=False).exclude(stock_entries__shop=shop)
        )
        self._setup_percent()


class StockEditForm(_StockPercentMixin, forms.ModelForm):
    class Meta:
        model = ShopStock
        fields = ["quantity", "sell_percent", "buy_percent"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_percent()
