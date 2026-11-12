from django import forms


class JunkForm(forms.Form):
    quantity = forms.IntegerField(min_value=0, help_text="0 removes the junk mark.")

    def __init__(self, *args, owned=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quantity"].max_value = owned
        self.fields["quantity"].widget.attrs.update(min=0, max=owned)
        self.owned = owned

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity > self.owned:
            raise forms.ValidationError(f"The character owns only {self.owned}.")
        return quantity
