from django import forms
from django.db.models import Q
from django.forms import BaseInlineFormSet, inlineformset_factory

from items.models import Item
from ledger.coins import CoinsField

from .models import Quest, QuestRequirement, QuestReward

LIMIT_ERROR = "Use 1 or more, or leave empty for no limit."


class QuestForm(forms.ModelForm):
    max_completions = forms.IntegerField(
        required=False, min_value=1, error_messages={"min_value": LIMIT_ERROR}
    )
    max_per_character = forms.IntegerField(
        required=False, min_value=1, error_messages={"min_value": LIMIT_ERROR}
    )

    class Meta:
        model = Quest
        fields = [
            "name",
            "description",
            "start_date",
            "end_date",
            "max_completions",
            "max_per_character",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and start > end:
            self.add_error("end_date", "The end date must not be before the start date.")
        return cleaned

    def save(self, commit=True):
        self.instance.club = self.club
        return super().save(commit=commit)


class _ItemRowForm(forms.ModelForm):
    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        current = self.instance.item_id if self.instance.pk else None
        self.fields["item"].queryset = Item.objects.for_club(club).filter(
            Q(retired=False) | Q(pk=current)
        )


class RequirementForm(_ItemRowForm):
    quantity = forms.IntegerField(min_value=1)

    class Meta:
        model = QuestRequirement
        fields = ["item", "quantity"]


class RewardForm(_ItemRowForm):
    quantity = forms.IntegerField(min_value=0, required=False)
    coins = CoinsField(required=False, label="Coins")

    class Meta:
        model = QuestReward
        fields = ["item", "quantity"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].required = False
        if self.instance.pk:
            self.initial["coins"] = self.instance.coins

    def has_changed(self):
        # A quantity of 0 or blank is the untouched state of a new row.
        changed = set(self.changed_data)
        if not self.instance.pk and not (self.data.get(self.add_prefix("quantity")) or "").strip(
            "0"
        ):
            changed.discard("quantity")
        return bool(changed)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE") or not self.has_changed():
            return cleaned
        item = cleaned.get("item")
        coins = cleaned.get("coins") or 0
        quantity = cleaned.get("quantity") or 0
        if item:
            if quantity < 1 and "quantity" not in self.errors:
                self.add_error("quantity", "Quantity must be 1 or more.")
        else:
            cleaned["quantity"] = 0
            if coins < 1 and not self.errors:
                raise forms.ValidationError("Give an item or coins.")
        return cleaned

    def save(self, commit=True):
        self.instance.coins = self.cleaned_data.get("coins") or 0
        return super().save(commit=commit)


def _live_forms(formset):
    return [
        f
        for f in formset.forms
        if getattr(f, "cleaned_data", None) and not f.cleaned_data.get("DELETE")
    ]


class BaseRequirementFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        live = _live_forms(self)
        if not live:
            raise forms.ValidationError("Add at least one requirement.")
        items = [f.cleaned_data.get("item") for f in live if f.cleaned_data.get("item")]
        if len(items) != len(set(items)):
            raise forms.ValidationError("Each item can appear only once in requirements.")


class BaseRewardFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if not _live_forms(self):
            raise forms.ValidationError("Add at least one reward.")


RequirementFormSet = inlineformset_factory(
    Quest,
    QuestRequirement,
    form=RequirementForm,
    formset=BaseRequirementFormSet,
    extra=3,
    can_delete=True,
)
RewardFormSet = inlineformset_factory(
    Quest,
    QuestReward,
    form=RewardForm,
    formset=BaseRewardFormSet,
    extra=3,
    can_delete=True,
)
