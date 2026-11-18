"""Forms and formsets for starting equipment entry management.

Item fields are club-scoped so a club can only pick from its own catalogue.
"""

from django import forms
from django.forms import inlineformset_factory

from items.models import Item
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
)


def _item_queryset(club):
    """Return the club's items ordered by name for entry item pickers."""
    return Item.objects.filter(club=club).order_by("name")


class ClubItemMixin:
    """Mixin that scopes a form's ``item`` field to the current club."""

    def __init__(self, *args, club=None, **kwargs):
        super().__init__(*args, **kwargs)
        if club is not None and "item" in self.fields:
            self.fields["item"].queryset = _item_queryset(club)


class ClassEntryForm(forms.ModelForm):
    def __init__(self, *args, club=None, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        model = StartingEquipmentClassEntry
        fields = ["char_class", "min_level", "max_level", "coins_cp"]


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
    def __init__(self, *args, club=None, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        model = StartingEquipmentBackgroundEntry
        fields = ["background", "coins_cp"]


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
    def __init__(self, *args, club=None, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        model = StartingEquipmentLevelCoins
        fields = ["level", "coins_cp"]


class MagicOptionForm(ClubItemMixin, forms.ModelForm):
    class Meta:
        model = MagicItemStartingOption
        fields = ["item", "max_per_character", "notes"]
