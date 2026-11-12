"""Filters for the club ledger (U50)."""

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import QueryDict

from accounts.models import Membership
from items.models import Item
from player_characters.models import Character

from .models import LedgerEntry

FIELDS = ("character", "player", "kind", "item", "recorded_by", "date_from", "date_to")


class LedgerFilterForm(forms.Form):
    character = forms.ModelChoiceField(Character.objects.none(), required=False)
    player = forms.ModelChoiceField(Membership.objects.none(), required=False)
    kind = forms.ChoiceField(choices=[("", "Any kind"), *LedgerEntry.Kind.choices], required=False)
    item = forms.ModelChoiceField(Item.objects.none(), required=False)
    recorded_by = forms.ModelChoiceField(get_user_model().objects.none(), required=False)
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, data, club):
        super().__init__(data or None)
        self.fields["character"].queryset = Character.objects.for_club(club).order_by("name", "id")
        self.fields["player"].queryset = Membership.objects.filter(club=club).select_related("user")
        self.fields["player"].label_from_instance = lambda m: m.user.display_name or m.user.email
        self.fields["item"].queryset = Item.objects.for_club(club).order_by("name", "id")
        users = get_user_model().objects.filter(
            Q(memberships__club=club)
            | Q(pk__in=LedgerEntry.objects.for_club(club).values("created_by"))
        )
        self.fields["recorded_by"].queryset = users.distinct().order_by("display_name", "id")
        self.fields["recorded_by"].label_from_instance = lambda u: u.display_name or u.email
        self.fields["recorded_by"].label = "Recorded by"
        self.fields["date_from"].label = "From"
        self.fields["date_to"].label = "To"
        for f in self.fields.values():
            cls = (
                "form-select"
                if isinstance(f, (forms.ModelChoiceField, forms.ChoiceField))
                else "form-control"
            )
            f.widget.attrs["class"] = f"{cls} form-control-sm"

    def _values(self):
        """Valid, non-empty filter values only."""
        if not self.is_bound:
            return {}
        cleaned = {}
        for name in FIELDS:
            if name in self.errors:
                continue
            value = self.cleaned_data.get(name)
            if value not in (None, ""):
                cleaned[name] = value
        return cleaned

    def filter(self, qs):
        v = self._values()
        if "character" in v:
            qs = qs.filter(character=v["character"])
        if "player" in v:
            qs = qs.filter(character__owner=v["player"])
        if "kind" in v:
            qs = qs.filter(kind=v["kind"])
        if "item" in v:
            qs = qs.filter(pk__in=LedgerEntry.objects.filter(lines__item=v["item"]).values("pk"))
        if "recorded_by" in v:
            qs = qs.filter(created_by=v["recorded_by"])
        if "date_from" in v:
            qs = qs.filter(date__gte=v["date_from"])
        if "date_to" in v:
            qs = qs.filter(date__lte=v["date_to"])
        return qs

    def querystring(self):
        q = QueryDict(mutable=True)
        for name, value in self._values().items():
            q[name] = value.pk if hasattr(value, "pk") else str(value)
        return q.urlencode()
