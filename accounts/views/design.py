from django import forms
from django.shortcuts import render

from ..design_tokens import token_groups
from ..permissions import site_admin_required


class DemoForm(forms.Form):
    name = forms.CharField(help_text="Shown on the character sheet.")
    level = forms.IntegerField(min_value=1, max_value=20, initial=3, required=False)
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    roles = forms.MultipleChoiceField(
        choices=[("fighter", "Fighter"), ("mage", "Mage"), ("thief", "Thief")],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Pick any that apply.",
    )
    agree = forms.BooleanField(label="I have read the house rules")


@site_admin_required
def design_reference(request):
    form = DemoForm(
        {"name": "", "level": 3, "agree": ""}
    )  # bound with an empty required name: shows an error
    context = {
        "groups": token_groups(),
        "form": form,
        "characters": ["Alice the Bold", "Bram Stonefoot", "Cinder"],
        "coin_values": [5, 120, 1250, 25000],
        "badge_statuses": ["success", "warning", "danger", "info", "neutral"],
        "dl_items": [("Class", "Fighter"), ("Level", 3), ("Home", "Rivermouth")],
        "breadcrumbs": [{"url": "/", "label": "Home"}, {"url": "", "label": "Design system"}],
        "secondary": [{"url": "#", "label": "Export"}],
        "sprite_icons": [
            "plus-lg",
            "inbox",
            "box-arrow-right",
            "check-circle-fill",
            "exclamation-triangle-fill",
            "x-octagon-fill",
            "info-circle-fill",
            "palette",
        ],
    }
    return render(request, "accounts/design/reference.html", context)
