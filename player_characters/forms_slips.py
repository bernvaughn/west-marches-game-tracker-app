from django import forms


class SlipsForm(forms.Form):
    characters = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
        error_messages={
            "required": "Tick at least one character.",
            "invalid_choice": "That character is not available.",
            "invalid_pk_value": "That character is not available.",
        },
    )

    def __init__(self, *args, queryset, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["characters"].queryset = queryset
