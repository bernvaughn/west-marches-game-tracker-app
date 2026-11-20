from django import forms

from ..models import SiteFeedback


class FeedbackForm(forms.ModelForm):
    """Form for a site-level bug report or feature request."""

    kind = forms.ChoiceField(
        label="What are you reporting?",
        choices=[
            (SiteFeedback.Kind.BUG, "Bug: something in the app is broken"),
            (SiteFeedback.Kind.FEATURE, "Feature: something the app should do"),
        ],
        widget=forms.RadioSelect,
    )
    body = forms.CharField(
        label="What's happening?",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    class Meta:
        model = SiteFeedback
        fields = ["kind", "body", "page_url"]
        widgets = {
            "page_url": forms.HiddenInput(),
        }
