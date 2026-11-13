from django import forms
from django.db.models import Q
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from items.models import Item
from ledger.coins import CoinsField
from player_characters.models import Character

from .models import DowntimeAction, DowntimeEntry, DowntimeEntryItem


class PointsForm(forms.Form):
    DIRECTIONS = [("give", "Give"), ("take", "Take")]

    characters = forms.ModelMultipleChoiceField(
        queryset=Character.objects.none(), widget=forms.CheckboxSelectMultiple
    )
    direction = forms.ChoiceField(choices=DIRECTIONS, widget=forms.RadioSelect, initial="give")
    points = forms.IntegerField(min_value=1)
    note = forms.CharField(max_length=500)
    date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["characters"].queryset = Character.objects.for_club(club).order_by("name", "id")

    def signed_delta(self):
        points = self.cleaned_data["points"]
        return points if self.cleaned_data["direction"] == "give" else -points


class DowntimeActionForm(forms.ModelForm):
    class Meta:
        model = DowntimeAction
        fields = ["name", "description", "cost", "start_date", "end_date"]
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


class EntryItemForm(forms.ModelForm):
    class Meta:
        model = DowntimeEntryItem
        fields = ["item", "quantity"]

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        current = self.instance.item_id if self.instance.pk else None
        self.fields["item"].queryset = Item.objects.for_club(club).filter(
            Q(retired=False) | Q(pk=current)
        )


EntryItemFormSet = inlineformset_factory(
    DowntimeEntry,
    DowntimeEntryItem,
    form=EntryItemForm,
    extra=2,
    can_delete=True,
)


class EntryForm(forms.ModelForm):
    coins = CoinsField(required=False, label="Coins")

    class Meta:
        model = DowntimeEntry
        fields = ["label", "weight", "order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["weight"].widget.attrs["data-weight"] = ""
        if self.instance.pk:
            self.initial["coins"] = self.instance.coins

    def save(self, commit=True):
        self.instance.coins = self.cleaned_data.get("coins") or 0
        return super().save(commit=commit)


class BaseEntryFormSet(BaseInlineFormSet):
    def __init__(self, *args, club=None, **kwargs):
        self.club = club
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        form.nested = EntryItemFormSet(
            self.data if self.is_bound else None,
            instance=form.instance,
            prefix=f"{form.prefix}-items",
            form_kwargs={"club": self.club},
        )
        return form

    def is_valid(self):
        ok = super().is_valid()
        for form in self.forms:
            if self._should_delete(form):
                continue
            if not form.nested.is_valid():
                ok = False
        return ok

    def _should_delete(self, form):
        return self.can_delete and self._should_delete_form(form)

    def save(self, commit=True):
        saved = super().save(commit=commit)
        for form in self.forms:
            if self._should_delete(form):
                continue
            entry = form.instance
            if entry.pk is None:
                continue
            form.nested.instance = entry
            form.nested.save(commit=commit)
        return saved

    def live_chances(self):
        """Attach .chance (percent) to each live form for server rendering."""
        live = [
            f
            for f in self.forms
            if getattr(f, "cleaned_data", None)
            and f.cleaned_data.get("label")
            and not f.cleaned_data.get("DELETE")
        ]
        if not self.is_bound:
            live = [f for f in self.forms if f.instance.pk]
            weights = {f: f.instance.weight for f in live}
        else:
            weights = {f: f.cleaned_data.get("weight") or 0 for f in live}
        total = sum(weights.values())
        for f in self.forms:
            f.chance = weights[f] * 100 / total if f in weights and total else None


EntryFormSet = inlineformset_factory(
    DowntimeAction,
    DowntimeEntry,
    form=EntryForm,
    formset=BaseEntryFormSet,
    extra=3,
    can_delete=True,
)
