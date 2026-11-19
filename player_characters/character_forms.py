from django import forms

from accounts.models import Membership
from character_options.models import Background, CharacterClass, Species
from character_options.services import match_option

from .models import (
    ABILITIES,
    ALIGNMENT_CHOICES,
    OTHER,
    PRONOUNS_CHOICES,
    Character,
)


class _OwnerChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.user.display_name


def _club_members(club):
    return (
        Membership.objects.filter(club=club).select_related("user").order_by("user__display_name")
    )


# A leading blank option means "not set". Without it, a blank saved value
# preselects the first option and saving silently stores that option.
BLANK_CHOICE = ("", "\u2014")


def _dropdown(choices):
    return [BLANK_CHOICE, *choices]


# Dropdown choices: blank, the officially published options, alphabetized, then
# "Other". "Other" is appended last so the official options stay alphabetized.
def _dropdown_with_other(choices):
    return [*_dropdown(choices), (OTHER, OTHER)]


def _option_choices(model, club, current_value=None):
    """Build choices for a club-scoped option field.

    Includes active records, plus the current record even if archived.
    Returns a list of (value, label) tuples where value is the record name.
    """
    qs = model.objects.for_club(club).filter(is_active=True)
    if current_value:
        # Include the current record even if archived, for edit preselection.
        qs = qs | model.objects.for_club(club).filter(name__iexact=current_value)
    qs = qs.order_by("sort_order", "name").distinct()

    choices = []
    for obj in qs:
        label = obj.name
        if not obj.is_active:
            label = f"{obj.name} (archived)"
        choices.append((obj.name, label))
    return choices


class CharacterForm(forms.ModelForm):
    # A Select widget with the club's active options, but a plain
    # CharField: any value stays valid (the model is an unrestricted CharField),
    # and "Other" plus freetext is the supported escape hatch for custom values.
    char_class = forms.CharField(
        label="Class",
        required=False,
        widget=forms.Select(),
    )
    species = forms.CharField(
        label="Species",
        required=False,
        widget=forms.Select(),
    )
    background = forms.CharField(
        label="Background",
        required=False,
        widget=forms.Select(),
    )
    pronouns = forms.CharField(
        label="Pronouns",
        required=False,
        widget=forms.Select(choices=_dropdown_with_other(PRONOUNS_CHOICES)),
    )
    alignment = forms.CharField(
        label="Alignment",
        required=False,
        widget=forms.Select(choices=_dropdown(ALIGNMENT_CHOICES)),
    )
    # Freetext inputs revealed when "Other" is chosen. Not model fields: they
    # feed back into the matching dropdown field via clean().
    char_class_freetext = forms.CharField(label="Class (other)", required=False, max_length=60)
    species_freetext = forms.CharField(label="Species (other)", required=False, max_length=60)
    background_freetext = forms.CharField(label="Background (other)", required=False, max_length=60)
    pronouns_freetext = forms.CharField(label="Pronouns (other)", required=False, max_length=60)

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

        # Build dropdown choices from club records.
        # Pass current value to include archived record if the character uses it.
        self.fields["char_class"].widget.choices = _dropdown_with_other(
            _option_choices(CharacterClass, club, self.instance.char_class)
        )
        self.fields["species"].widget.choices = _dropdown_with_other(
            _option_choices(Species, club, self.instance.species)
        )
        self.fields["background"].widget.choices = _dropdown_with_other(
            _option_choices(Background, club, self.instance.background)
        )

        # The record as saved, before the dropdowns are matched below. The edit
        # page shows these as the "Current" values.
        self.saved_values = dict(self.initial)
        self._match_saved_dropdowns()

        # Compute custom flags before is_valid() mutates the instance.
        # A field is "custom" when the FK is null and the text is non-empty.
        self.custom_fields = set()
        for field_name, fk_name in [
            ("char_class", "class_option"),
            ("species", "species_option"),
            ("background", "background_option"),
        ]:
            fk_val = getattr(self.instance, fk_name + "_id", None)
            text_val = getattr(self.instance, field_name, "")
            if fk_val is None and text_val:
                self.custom_fields.add(field_name)

    def _match_saved_dropdowns(self):
        """Preselect the right option for a saved value that is not an exact choice.

        Without this, a select whose value matches no option shows its first
        option, and saving the form silently overwrites the saved value.
        """
        for field in ("char_class", "species", "background", "pronouns", "alignment"):
            saved = (self.initial.get(field) or "").strip()
            if not saved:
                continue
            choices = self.fields[field].widget.choices
            match = next(
                (
                    value
                    for value, _label in choices
                    if value and value.casefold() == saved.casefold()
                ),
                None,
            )
            if match is not None:
                self.initial[field] = match
            elif field == "alignment":
                # Alignment has no "Other": keep the saved value as its own option.
                self.fields[field].widget.choices = [*choices, (saved, saved)]
            else:
                self.initial[field] = OTHER
                self.initial[f"{field}_freetext"] = saved

    def clean(self):
        cleaned_data = super().clean()
        # Resolve the three option fields into FK records.
        self._options = {}
        for field_name, model in [
            ("char_class", CharacterClass),
            ("species", Species),
            ("background", Background),
        ]:
            value = cleaned_data.get(field_name, "").strip()
            if value == OTHER:
                # "Other" -> freetext, no FK.
                cleaned_data[field_name] = cleaned_data.get(f"{field_name}_freetext") or ""
                self._options[field_name] = None
            elif value == "":
                # Blank -> no FK, empty text.
                cleaned_data[field_name] = ""
                self._options[field_name] = None
            else:
                # Listed value -> look up in club (includes archived for current record).
                record = match_option(self.club, model, value)
                if record:
                    # Matched a record: use its canonical name and set FK.
                    cleaned_data[field_name] = record.name
                    self._options[field_name] = record
                else:
                    # No match (legacy POSTs, unseeded test clubs): keep as custom text, no FK.
                    self._options[field_name] = None

        # Pronouns: handle "Other" -> freetext (no FK for pronouns).
        if cleaned_data.get("pronouns") == OTHER:
            cleaned_data["pronouns"] = cleaned_data.get("pronouns_freetext") or ""

        return cleaned_data

    def save(self, commit=True):
        # Assign the FKs on the instance before saving.
        for field_name, fk_name in [
            ("char_class", "class_option"),
            ("species", "species_option"),
            ("background", "background_option"),
        ]:
            record = self._options.get(field_name)
            setattr(self.instance, fk_name, record)

        self.instance.club = self.club
        if self.choose_owner:
            self.instance.owner = self.cleaned_data["owner"]
        return super().save(commit=commit)


class HandoverForm(forms.Form):
    owner = _OwnerChoice(queryset=Membership.objects.none(), label="New owner")

    def __init__(self, *args, character, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = _club_members(character.club).exclude(pk=character.owner_id)