"""Forms for character options admin."""

from django import forms

from character_options.kinds import get_kind
from character_options.services import create_option


class OptionForm(forms.Form):
    """Form for creating/editing a character option (species, class, background)."""

    name = forms.CharField(
        max_length=60,
        strip=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Name"}),
    )

    def __init__(self, *args, club=None, kind_slug=None, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club
        self.kind_slug = kind_slug
        self.instance = instance
        kind = get_kind(kind_slug)
        self.fields["name"].label = kind.singular
        if instance:
            self.fields["name"].initial = instance.name

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Name is required.")

        kind = get_kind(self.kind_slug)
        model = kind.model

        # Check for case-insensitive duplicate in the same club, excluding self
        queryset = model.objects.for_club(self.club).filter(name__iexact=name)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError(f"A {kind.singular.lower()} named {name} already exists.")

        return name

    def save(self, commit=True):
        """Create or update the option."""
        name = self.cleaned_data["name"]

        if self.instance:
            self.instance.name = name
            if commit:
                self.instance.save(update_fields=["name"])
            return self.instance
        else:
            return create_option(self.kind_slug, self.club, name)
