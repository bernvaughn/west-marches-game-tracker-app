from django import forms
from django.utils import timezone

from ledger.coins import CoinsField
from ledger.services import Line
from player_characters.forms import item_line_formset


class _DateNoteMixin(forms.Form):
    date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )


class BulkAwardItemLineForm(forms.Form):
    """Form for a single item line in the bulk award."""

    item = forms.ModelChoiceField(queryset=None, required=False)
    quantity = forms.IntegerField(min_value=1, required=False)
    value_override = forms.IntegerField(
        required=False,
        min_value=0,
        label="Value (cp)",
        help_text="Override item value in cp (optional)",
    )

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


class BaseBulkAwardItemLineFormSet(forms.BaseFormSet):
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


class BulkAwardCharacterForm(forms.Form):
    """Form for a single character's coins and items in the bulk award."""

    character = forms.ModelChoiceField(queryset=None, widget=forms.HiddenInput)
    coins = CoinsField(required=False, label="Coins")
    note = forms.CharField(max_length=500, required=False)

    def __init__(self, *args, items, **kwargs):
        super().__init__(*args, **kwargs)
        char = self.initial.get("character")
        char_pk = char.pk if char else "new"
        self.item_formset = item_line_formset(
            items,
            data=self.data if self.is_bound else None,
            prefix=f"items-{char_pk}",
        )

    def clean(self):
        data = super().clean()
        if not self.item_formset.is_valid():
            raise forms.ValidationError("Invalid item lines.")
        return data

    def get_lines(self, sign):
        """Return list of Line objects for this character."""
        lines = []
        coins = self.cleaned_data.get("coins") or 0
        if coins:
            lines.append(Line(coins=sign * coins))
        for form in self.item_formset.forms:
            cd = form.cleaned_data
            item = cd.get("item")
            qty = cd.get("quantity")
            if item and qty:
                lines.append(Line(item=item, quantity=sign * qty))
        return lines


class BulkAwardForm(forms.Form):
    """Main form for bulk award - character selection and shared fields."""

    characters = forms.ModelMultipleChoiceField(
        queryset=None, widget=forms.CheckboxSelectMultiple, required=True
    )
    note = forms.CharField(max_length=500, required=False)
    date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        from player_characters.models import Character

        self.fields["characters"].queryset = Character.objects.for_club(club).order_by("name", "id")

    def clean(self):
        data = super().clean()
        characters = data.get("characters")
        if not characters:
            self.add_error("characters", "Select at least one character.")
        return data


class AdjustForm(_DateNoteMixin):
    DIRECTIONS = [("give", "Give"), ("take", "Take")]
    KINDS = [
        ("", "Default"),
        ("award", "Award"),
        ("adjustment", "Adjustment"),
    ]
    direction = forms.ChoiceField(choices=DIRECTIONS, widget=forms.RadioSelect, initial="give")
    kind = forms.ChoiceField(
        choices=KINDS,
        required=False,
        help_text="Default: award when giving, adjustment when taking.",
    )
    coins = CoinsField(required=False)
    note = forms.CharField(max_length=500)

    def clean(self):
        data = super().clean()
        direction = data.get("direction")
        if direction:
            data["sign"] = 1 if direction == "give" else -1
            if not data.get("kind"):
                data["kind"] = "award" if direction == "give" else "adjustment"
        return data


class ConsumeForm(_DateNoteMixin):
    coins = CoinsField(required=False)
    note = forms.CharField(max_length=500, required=False)

    def clean_note(self):
        return self.cleaned_data["note"].strip() or "Consumed"


class PlayerConsumeForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, initial=1)
    note = forms.CharField(max_length=500, required=False)

    def __init__(self, *args, available=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.available = available
        self.fields["quantity"].widget.attrs.update(
            {"min": 1, "max": available, "class": "wm-inline-number"}
        )

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity > self.available:
            raise forms.ValidationError(f"Only {self.available} available to consume.")
        return quantity

    def clean_note(self):
        return self.cleaned_data["note"].strip() or "Consumed"
