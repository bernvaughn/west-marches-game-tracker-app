from django import forms

from accounts.models import Membership

from .models import (
    ABILITIES,
    ALIGNMENT_CHOICES,
    BACKGROUND_CHOICES,
    CLASS_CHOICES,
    OTHER,
    PRONOUNS_CHOICES,
    SPECIES_CHOICES,
    Character,
)


class _OwnerChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.user.display_name


def _club_members(club):
    return (
        Membership.objects.filter(club=club).select_related("user").order_by("user__display_name")
    )


# Dropdown choices: the officially published options, alphabetized, then "Other".
# "Other" is appended last so the official options stay alphabetized.
def _dropdown_with_other(choices):
    return list(choices) + [(OTHER, OTHER)]


class CharacterForm(forms.ModelForm):
    # A Select widget with the officially published options, but a plain
    # CharField: any value stays valid (the model is an unrestricted CharField),
    # and "Other" plus freetext is the supported escape hatch for custom values.
    char_class = forms.CharField(
        label="Class",
        required=False,
        widget=forms.Select(choices=_dropdown_with_other(CLASS_CHOICES)),
    )
    species = forms.CharField(
        label="Species",
        required=False,
        widget=forms.Select(choices=_dropdown_with_other(SPECIES_CHOICES)),
    )
    background = forms.CharField(
        label="Background",
        required=False,
        widget=forms.Select(choices=_dropdown_with_other(BACKGROUND_CHOICES)),
    )
    pronouns = forms.CharField(
        label="Pronouns",
        required=False,
        widget=forms.Select(choices=_dropdown_with_other(PRONOUNS_CHOICES)),
    )
    alignment = forms.CharField(
        label="Alignment",
        required=False,
        widget=forms.Select(choices=ALIGNMENT_CHOICES),
    )
    # Freetext inputs revealed when "Other" is chosen. Not model fields: they
    # feed back into the matching dropdown field via clean().
    char_class_freetext = forms.CharField(label="Class (other)", required=False)
    species_freetext = forms.CharField(label="Species (other)", required=False)
    background_freetext = forms.CharField(label="Background (other)", required=False)
    pronouns_freetext = forms.CharField(label="Pronouns (other)", required=False)

    class Meta:
        model = Character
        fields = [
            "name",
            "level",
            "char_class",
            "species",
            "background",
            "pronouns",
            "alignment",
            *[a[0] for a in ABILITIES],
            "armor_class",
            "max_hp",
            "perception_bonus",
            "xp",
            "description",
        ]
        widgets = {
            "level": forms.NumberInput(attrs={"min": 1}),
            **{a[0]: forms.NumberInput(attrs={"min": 1, "max": 30}) for a in ABILITIES},
            "armor_class": forms.NumberInput(attrs={"min": 0, "max": 40}),
            "max_hp": forms.NumberInput(attrs={"min": 1}),
            "perception_bonus": forms.NumberInput(attrs={"min": -20, "max": 30}),
            "xp": forms.NumberInput(attrs={"min": 0}),
            "description": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, club, choose_owner=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club
        self.choose_owner = choose_owner
        if not self.instance.pk:
            # New characters start every ability at 10, matching the model defaults.
            for name, _abbr, _label in ABILITIES:
                self.fields[name].initial = Character._meta.get_field(name).default
        if choose_owner:
            self.fields["owner"] = _OwnerChoice(queryset=_club_members(club))
            self.order_fields(["owner", *self.Meta.fields])

    def clean(self):
        cleaned_data = super().clean()
        for field in ("char_class", "species", "background", "pronouns"):
            if cleaned_data.get(field) == OTHER:
                cleaned_data[field] = cleaned_data.get(f"{field}_freetext") or ""
        return cleaned_data

    def save(self, commit=True):
        self.instance.club = self.club
        if self.choose_owner:
            self.instance.owner = self.cleaned_data["owner"]
        return super().save(commit=commit)


class HandoverForm(forms.Form):
    owner = _OwnerChoice(queryset=Membership.objects.none(), label="New owner")

    def __init__(self, *args, character, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = _club_members(character.club).exclude(pk=character.owner_id)
