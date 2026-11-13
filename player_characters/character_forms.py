from django import forms

from accounts.models import Membership

from .models import ABILITIES, Character


class _OwnerChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.user.display_name


def _club_members(club):
    return (
        Membership.objects.filter(club=club).select_related("user").order_by("user__display_name")
    )


class CharacterForm(forms.ModelForm):
    class Meta:
        model = Character
        fields = [
            "name",
            "level",
            "char_class",
            "species",
            "pronouns",
            "alignment",
            *[a[0] for a in ABILITIES],
            "armor_class",
            "perception_bonus",
            "xp",
            "description",
        ]
        widgets = {
            "level": forms.NumberInput(attrs={"min": 1}),
            **{a[0]: forms.NumberInput(attrs={"min": 1, "max": 30}) for a in ABILITIES},
            "armor_class": forms.NumberInput(attrs={"min": 0, "max": 40}),
            "perception_bonus": forms.NumberInput(attrs={"min": -20, "max": 30}),
            "xp": forms.NumberInput(attrs={"min": 0}),
            "description": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, club, choose_owner=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club
        self.choose_owner = choose_owner
        if choose_owner:
            self.fields["owner"] = _OwnerChoice(queryset=_club_members(club))
            self.order_fields(["owner", *self.Meta.fields])

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
