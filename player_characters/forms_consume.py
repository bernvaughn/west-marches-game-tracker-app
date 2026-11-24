"""Unit-aware consume forms (U127, U128).

The player consume form subclasses the existing ``PlayerConsumeForm`` (owned by
slice E in ``forms_adjust.py``; this file only imports it) and words the cap
error with ``unit_label``. The capped GM formset caps each posted row at the
units available for the item.
"""

from django import forms
from django.forms import formset_factory

from items.services import StackedPricingService
from player_characters.forms import BaseItemLineFormSet, ItemLineForm
from player_characters.forms_adjust import PlayerConsumeForm as BasePlayerConsumeForm


class PlayerConsumeForm(BasePlayerConsumeForm):
    """Player consume form: unit-aware quantity label and capped error wording."""

    def __init__(self, *args, item=None, available=1, **kwargs):
        super().__init__(*args, available=available, **kwargs)
        self.item = item
        if item is not None and item.is_stacked:
            self.fields["quantity"].label = f"Units ({item.unit_name})"

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity > self.available:
            if self.item is not None:
                label = StackedPricingService.unit_label(self.item, self.available)
                raise forms.ValidationError(f"Only {label} available to consume.")
            raise forms.ValidationError(f"Only {self.available} available to consume.")
        return quantity


class ConsumeLineFormSet(BaseItemLineFormSet):
    """Item line formset for the GM consume page.

    Each posted row is capped at the units available for the chosen item,
    using ``unit_label`` in the error. A cap error appears before the ledger
    is touched.
    """

    def __init__(self, *args, available=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.available = available or {}

    def clean(self):
        super().clean()
        for form in self.forms:
            if form.errors:
                continue
            item = form.cleaned_data.get("item")
            qty = form.cleaned_data.get("quantity")
            if item is None or qty is None:
                continue
            available = self.available.get(item.pk, 0)
            if qty > available:
                label = StackedPricingService.unit_label(item, available)
                form.add_error("quantity", f"Only {label} available to consume.")


def consume_line_formset(items, available, data=None, *, prefix="items"):
    """Formset for the GM consume page, capped at units available per item."""
    factory = formset_factory(
        ItemLineForm, formset=ConsumeLineFormSet, extra=3, max_num=3, validate_max=True
    )
    formset = factory(data, prefix=prefix, form_kwargs={"items": items})
    formset.available = available or {}
    return formset
