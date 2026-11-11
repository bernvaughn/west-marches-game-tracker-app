from django import forms
from django.forms import formset_factory

from ledger.services import Line


class ItemLineForm(forms.Form):
    item = forms.ModelChoiceField(queryset=None, required=False)
    quantity = forms.IntegerField(min_value=1, required=False)

    def __init__(self, *args, items, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = items

    def clean(self):
        data = super().clean()
        item, qty = data.get("item"), data.get("quantity")
        if "item" in self.errors or "quantity" in self.errors:
            return data
        if (item is None) != (qty is None):
            raise forms.ValidationError("Pick an item and a quantity, or leave the row blank.")
        return data


class BaseItemLineFormSet(forms.BaseFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            item = getattr(form, "cleaned_data", {}).get("item")
            if item is None:
                continue
            if item.pk in seen:
                raise forms.ValidationError("Pick each item once.")
            seen.add(item.pk)


def item_line_formset(items, data=None, *, extra=3, prefix="items"):
    factory = formset_factory(
        ItemLineForm, formset=BaseItemLineFormSet, extra=extra, max_num=extra, validate_max=True
    )
    return factory(data, prefix=prefix, form_kwargs={"items": items})


def formset_lines(formset, sign):
    if sign not in (1, -1):
        raise ValueError("sign must be 1 or -1")
    if not formset.is_valid():
        raise ValueError("formset is not valid")
    return [
        Line(item=f.cleaned_data["item"], quantity=sign * f.cleaned_data["quantity"])
        for f in formset.forms
        if f.cleaned_data.get("item") is not None
    ]
