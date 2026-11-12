from django import forms
from django.core.validators import MaxValueValidator


class BuyForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, initial=1)

    def __init__(self, *args, max_quantity=None, **kwargs):
        super().__init__(*args, **kwargs)
        if max_quantity is not None:
            self.fields["quantity"].max_value = max_quantity
            self.fields["quantity"].validators.append(MaxValueValidator(max_quantity))
            self.fields["quantity"].widget.attrs["max"] = max_quantity
