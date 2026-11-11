from django import forms


class SellForm(forms.Form):
    character = forms.ModelChoiceField(queryset=None)
    item = forms.ModelChoiceField(queryset=None)
    quantity = forms.IntegerField(min_value=1, initial=1)

    def __init__(self, *args, characters, items, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["character"].queryset = characters
        self.fields["item"].queryset = items
