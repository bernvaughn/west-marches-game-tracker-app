from django import forms
from django.utils import timezone

from ledger.coins import CoinsField


class _DateNoteMixin(forms.Form):
    date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )


class AdjustForm(_DateNoteMixin):
    DIRECTIONS = [("give", "Give"), ("take", "Take")]
    KINDS = [
        ("", "Default (award for give, adjustment for take)"),
        ("award", "Award"),
        ("adjustment", "Adjustment"),
    ]
    direction = forms.ChoiceField(choices=DIRECTIONS, widget=forms.RadioSelect, initial="give")
    kind = forms.ChoiceField(choices=KINDS, required=False)
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
        self.fields["quantity"].widget.attrs.update(min=1, max=available)

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity > self.available:
            raise forms.ValidationError(f"Only {self.available} available to consume.")
        return quantity

    def clean_note(self):
        return self.cleaned_data["note"].strip() or "Consumed"
