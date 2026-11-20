"""Forms and formsets for starting equipment entry management.

Item fields are club-scoped so a club can only pick from its own catalogue.
"""

from django import forms
from django.forms import inlineformset_factory

from character_options.models import Background, CharacterClass
from items.models import Item
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
    StartingEquipmentTemplate,
)


def _item_queryset(club):
    """Return the club's items ordered by name for entry item pickers."""
    return Item.objects.filter(club=club).order_by("name")


def _class_option_queryset(club):
    """Return the club's CharacterClass records for entry class pickers."""
    return CharacterClass.objects.for_club(club).order_by("sort_order", "name")


def _background_option_queryset(club):
    """Return the club's Background records for entry background pickers."""
    return Background.objects.for_club(club).order_by("sort_order", "name")


class ClubItemMixin:
    """Mixin that scopes a form's ``item`` field to the current club."""

    def __init__(self, *args, club=None, template=None, **kwargs):
        # ``template`` is accepted (and ignored) so the shared entry view can
        # pass the same form_kwargs to the entry form and its line formset.
        super().__init__(*args, **kwargs)
        if club is not None and "item" in self.fields:
            self.fields["item"].queryset = _item_queryset(club)


class ClassEntryForm(forms.ModelForm):
    def __init__(self, *args, club=None, template=None, **kwargs):
        # ``template`` is accepted (and ignored) so the shared entry view can
        # pass it to every entry form; only background entries need it.
        super().__init__(*args, **kwargs)
        if club is not None:
            self.fields["class_option"].queryset = _class_option_queryset(club)

    class Meta:
        model = StartingEquipmentClassEntry
        fields = ["class_option", "min_level", "max_level", "coins_cp"]


class ClassLineForm(ClubItemMixin, forms.ModelForm):
    class Meta:
        model = StartingEquipmentClassLine
        fields = ["item", "quantity", "is_choice", "choice_group"]


ClassLineFormSet = inlineformset_factory(
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    form=ClassLineForm,
    extra=3,
    can_delete=False,
)


class BackgroundEntryForm(forms.ModelForm):
    def __init__(self, *args, club=None, template=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = template
        if club is not None:
            self.fields["background_option"].queryset = _background_option_queryset(club)

    class Meta:
        model = StartingEquipmentBackgroundEntry
        fields = ["background_option", "coins_cp"]

    def clean(self):
        cleaned_data = super().clean()
        option = cleaned_data.get("background_option")
        if option is not None and self.template is not None:
            qs = StartingEquipmentBackgroundEntry.objects.filter(
                template=self.template, background_option=option
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    "background_option",
                    f"This template already has a background entry for '{option.name}'. "
                    "Backgrounds are unique per template.",
                )
        return cleaned_data


class BackgroundLineForm(ClubItemMixin, forms.ModelForm):
    class Meta:
        model = StartingEquipmentBackgroundLine
        fields = ["item", "quantity", "is_choice", "choice_group"]


BackgroundLineFormSet = inlineformset_factory(
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    form=BackgroundLineForm,
    extra=3,
    can_delete=False,
)


class LevelCoinsForm(forms.ModelForm):
    def __init__(self, *args, club=None, template=None, **kwargs):
        # ``template`` is accepted (and ignored) so the shared entry view can
        # pass the same form_kwargs to every entry form.
        super().__init__(*args, **kwargs)

    class Meta:
        model = StartingEquipmentLevelCoins
        fields = ["level", "coins_cp"]


class MagicOptionForm(ClubItemMixin, forms.ModelForm):
    class Meta:
        model = MagicItemStartingOption
        fields = ["item", "max_per_character", "notes"]


class TemplateForm(forms.ModelForm):
    """Form for creating and editing StartingEquipmentTemplate."""

    class Meta:
        model = StartingEquipmentTemplate
        fields = ["name", "description", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club
        self.fields["name"].help_text = "Unique within this club."
        self.fields["description"].help_text = "Optional description of this template."
        self.fields[
            "is_active"
        ].help_text = (
            "Only one template can be active per club. Activating this will deactivate others."
        )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clash = (
            StartingEquipmentTemplate.objects.for_club(self.club)
            .filter(name__iexact=name)
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if clash:
            raise forms.ValidationError("A template with this name already exists in this club.")
        return name

    def save(self, commit=True):
        self.instance.club = self.club
        return super().save(commit=commit)
