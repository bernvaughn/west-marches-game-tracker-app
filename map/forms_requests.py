from django import forms
from django.utils import timezone


class _CharactersMixin(forms.Form):
    characters = forms.ModelMultipleChoiceField(
        queryset=None, widget=forms.CheckboxSelectMultiple, required=True
    )
    date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )
    note = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    def __init__(self, *args, characters_qs, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["characters"].queryset = characters_qs


class VisitRequestForm(_CharactersMixin):
    q = forms.IntegerField(label="Column (q)")
    r = forms.IntegerField(label="Row (r)")
    field_order = ["q", "r", "characters", "date", "note"]


class CreditRequestForm(_CharactersMixin):
    pass
