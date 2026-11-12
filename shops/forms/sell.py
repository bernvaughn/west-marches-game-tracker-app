from django import forms


class SellForm(forms.Form):
    item = forms.ModelChoiceField(queryset=None)
    quantity = forms.IntegerField(min_value=1, initial=1)

    def __init__(self, *args, items, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = items
