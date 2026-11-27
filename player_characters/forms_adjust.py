from django import forms
from django.utils import timezone

from items.widgets import ItemPickerWidget
from ledger.coins import CoinsField
from ledger.services import Line
from player_characters.forms import BaseItemLineFormSet, ItemLineForm, item_line_formset

# Safety cap for item rows per character in bulk award.
# The UI has no limit via the "Add item" button; this prevents
# excessive formset processing on malicious or runaway submissions.
BULK_MAX_ROWS = 500


def bulk_item_line_formset(items, data=None, *, prefix, club=None):
    """Formset factory for bulk award with a high max_num.

    Uses the same ItemLineForm and BaseItemLineFormSet as the
    shared item_line_formset but allows many more rows (default
    extra=3, max_num=BULK_MAX_ROWS). The caller must provide a
    unique prefix per character.
    """
    from django.forms import formset_factory

    factory = formset_factory(
        ItemLineForm,
        formset=BaseItemLineFormSet,
        extra=3,
        max_num=BULK_MAX_ROWS,
        validate_max=True,
    )
    return factory(data, prefix=prefix, form_kwargs={"items": items, "club": club})


class _DateNoteMixin(forms.Form):
    date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )


class BulkAwardItemLineForm(forms.Form):
    """Form for a single item line in the bulk award."""

    item = forms.ModelChoiceField(queryset=None, required=False)
    quantity = forms.IntegerField(min_value=1, required=False)
    value_override = forms.IntegerField(
        required=False,
        min_value=0,
        label="Value (cp)",
        help_text="Override item value in cp (optional)",
    )

    def __init__(self, *args, items, club=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = items
        if club is not None:
            self.fields["item"].widget = ItemPickerWidget(club=club)

    def clean(self):
        data = super().clean()
        item, qty = data.get("item"), data.get("quantity")
        if "item" in self.errors or "quantity" in self.errors:
            return data
        if (item is None) != (qty is None):
            raise forms.ValidationError("Pick an item and a quantity, or leave the row blank.")
        return data


class BaseBulkAwardItemLineFormSet(forms.BaseFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            item = getattr(form, "cleaned_data", {}).get("item")
            if item is None:
                continue
            if item.pk in seen:
                raise forms.ValidationError("Pick each item once.")
            seen.add(item.pk)


class BulkAwardCharacterForm(forms.Form):
    """Form for a single character's coins and items in the bulk award."""

    character = forms.ModelChoiceField(queryset=None, widget=forms.HiddenInput)
    coins = CoinsField(required=False, label="Coins")
    note = forms.CharField(max_length=500, required=False)

    def __init__(self, *args, items, club=None, **kwargs):
        super().__init__(*args, **kwargs)
        char = self.initial.get("character")
        char_pk = char.pk if char else "new"
        self.item_formset = item_line_formset(
            items,
            data=self.data if self.is_bound else None,
            prefix=f"items-{char_pk}",
            club=club,
        )

    def clean(self):
        data = super().clean()
        if not self.item_formset.is_valid():
            raise forms.ValidationError("Invalid item lines.")
        return data

    def get_lines(self, sign):
        """Return list of Line objects for this character."""
        lines = []
        coins = self.cleaned_data.get("coins") or 0
        if coins:
            lines.append(Line(coins=sign * coins))
        for form in self.item_formset.forms:
            cd = form.cleaned_data
            item = cd.get("item")
            qty = cd.get("quantity")
            if item and qty:
                lines.append(Line(item=item, quantity=sign * qty))
        return lines


class BulkAwardForm(forms.Form):
    """Main form for bulk award - character selection and shared fields."""

    characters = forms.ModelMultipleChoiceField(
        queryset=None, widget=forms.CheckboxSelectMultiple, required=True
    )
    note = forms.CharField(max_length=500, required=False)
    date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        from player_characters.models import Character

        self.fields["characters"].queryset = Character.objects.for_club(club).order_by("name", "id")

    def clean(self):
        data = super().clean()
        characters = data.get("characters")
        if not characters:
            self.add_error("characters", "Select at least one character.")
        return data


class AdjustForm(_DateNoteMixin):
    DIRECTIONS = [("give", "Give"), ("take", "Take")]
    KINDS = [
        ("", "Default"),
        ("award", "Award"),
        ("adjustment", "Adjustment"),
    ]
    direction = forms.ChoiceField(choices=DIRECTIONS, widget=forms.RadioSelect, initial="give")
    kind = forms.ChoiceField(
        choices=KINDS,
        required=False,
        help_text="Default: award when giving, adjustment when taking.",
    )
    coins = CoinsField(required=False)
    note = forms.CharField(max_length=500)

    def clean(self):
        data = super().clean()
        direction = data.get("direction")
        if direction:
            data["sign"] = 1 if direction == "give" else -1
            if not data.get("kind"):
                data["kind"] = "award" if direction == "give" else "adjustment"
        return data


class ConsumeForm(_DateNoteMixin):
    coins = CoinsField(required=False)
    note = forms.CharField(max_length=500, required=False)

    def clean_note(self):
        return self.cleaned_data["note"].strip() or "Consumed"


class PlayerConsumeForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, initial=1)
    note = forms.CharField(max_length=500, required=False)

    def __init__(self, *args, available=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.available = available
        self.fields["quantity"].widget.attrs.update(
            {"min": 1, "max": available, "class": "wm-inline-number"}
        )

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity > self.available:
            raise forms.ValidationError(f"Only {self.available} available to consume.")
        return quantity

    def clean_note(self):
        return self.cleaned_data["note"].strip() or "Consumed"


def prefill_from_session(club, raw_id):
    """Return prefill data for bulk award from a session.

    Args:
        club: The club the session belongs to.
        raw_id: The session ID from the query string (may be invalid).

    Returns:
        A tuple of (session, initial_dict, played_pks) or (None, None, set()) if
        the ID is invalid or the session belongs to another club.
        - session: The PlaySession object or None.
        - initial_dict: Dict with 'note' and 'date' for the form initial data.
        - played_pks: Set of character PKs that have played=True attendance.
    """
    from play_sessions.models import PlaySession, SessionAttendance

    try:
        session_id = int(raw_id)
    except (TypeError, ValueError):
        return None, None, set()

    session = PlaySession.objects.for_club(club).filter(pk=session_id).first()
    if not session:
        return None, None, set()

    # Get characters who played
    played_pks = set(
        SessionAttendance.objects.filter(session=session, played=True).values_list(
            "character_id", flat=True
        )
    )

    # Build initial data
    from play_sessions.core import to_club_local

    date_local = to_club_local(club, session.starts_at).date()
    initial = {
        "note": session.title,
        "date": date_local,
    }

    return session, initial, played_pks