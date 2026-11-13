from django import forms


class PointRequestForm(forms.Form):
    characters = forms.ModelMultipleChoiceField(
        queryset=None, widget=forms.CheckboxSelectMultiple, required=True
    )
    points = forms.IntegerField(min_value=1, initial=1)
    note = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=True)

    def __init__(self, *args, characters_qs, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["characters"].queryset = characters_qs
