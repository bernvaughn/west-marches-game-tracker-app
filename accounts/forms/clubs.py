from django import forms
from django.utils.text import slugify

from ..forms.club_settings import TimezoneChoiceField, timezone_choices
from ..models import Club, default_timezone


class ClubCreateForm(forms.Form):
    name = forms.CharField(max_length=200)
    slug = forms.SlugField(required=False, max_length=50)
    admin_email = forms.EmailField()
    admin_display_name = forms.CharField(required=False, max_length=150)
    timezone = TimezoneChoiceField(initial=default_timezone)
    contact_email = forms.EmailField(required=False, label="Contact email")
    # Set when the site admin has seen the "already has an account" notice.
    confirm_existing = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["timezone"].choices = timezone_choices(default_timezone())

    def clean_admin_email(self):
        return self.cleaned_data["admin_email"].strip().lower()

    def clean(self):
        data = super().clean()
        name = data.get("name")
        if name is None or "slug" in self.errors:
            return data
        slug = data.get("slug") or slugify(name)
        if not slug:
            self.add_error("name", "Name must contain letters or numbers.")
            return data
        if Club.objects.filter(slug=slug).exists():
            self.add_error("slug", "A club with this slug already exists.")
            return data
        data["slug"] = slug
        return data
