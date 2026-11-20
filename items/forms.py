from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from ledger.coins import CoinsField

from . import rarity
from .magic_types import NONE_LABEL, MagicType
from .models import ContainerSlot, ContainerSlotOption, Item
from .services import can_toggle_stacked


class ItemForm(forms.ModelForm):
    value = CoinsField(required=False, label="Value")
    is_stacked = forms.BooleanField(
        required=False,
        label="Stacked item",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="The item is sold in bundles but used one unit at a time "
        "(parchment by the sheet, rope by the foot).",
    )
    unit_name = forms.CharField(
        required=False,
        max_length=40,
        label="Unit name",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Name of one unit, e.g. sheet, ft or arrow.",
    )
    value_units = forms.IntegerField(
        required=False,
        min_value=1,
        initial=1,
        label="Units the value covers",
        widget=forms.NumberInput(attrs={"min": 1, "class": "form-control"}),
        help_text="How many units the value covers. 1 for a normal item.",
    )

    class Meta:
        model = Item
        fields = [
            "name",
            "symbol",
            "description",
            "traits",
            "details",
            "gm_details",
            "rarity",
            "magic_type",
            "value",
            "is_stacked",
            "unit_name",
            "value_units",
        ]
        field_order = [
            "name",
            "symbol",
            "description",
            "traits",
            "details",
            "gm_details",
            "rarity",
            "magic_type",
            "value",
            "is_stacked",
            "unit_name",
            "value_units",
        ]
        widgets = {"rarity": forms.Select(attrs={"data-rarity-select": ""})}

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club
        self.fields["rarity"].choices = [("", "—"), *rarity.GROUPS]
        self.fields["magic_type"].choices = [("", NONE_LABEL), *MagicType.choices]
        self.fields["magic_type"].label = "Magic item type"
        self.fields["value"].help_text = format_html(
            '{}<span class="wm-stacked-hint">This price covers the units entered in '
            '"Units the value covers" (1 for a normal item).</span>',
            format_html(
                '<span class="wm-rarity-hint" data-rarity-hint>Suggested value:{}'
                '<span data-rarity-item="special" style="display:block">'
                "No suggested range.</span></span>",
                format_html_join(
                    "",
                    '<span data-rarity-item="{}" style="display:block">{} {}{}</span>',
                    (
                        (key, name, text, f" — e.g. {ex}" if ex else "")
                        for key, name, text, ex in rarity.ranges()
                    ),
                ),
            ),
        )
        if self.instance.pk:
            self.initial["value"] = self.instance.value_cp
            self.initial["is_stacked"] = self.instance.is_stacked
            self.initial["unit_name"] = self.instance.unit_name
            self.initial["value_units"] = self.instance.value_units
            # Add is_container field only on edit page (instance exists)
            self.fields["is_container"] = forms.BooleanField(
                required=False,
                label="Is container",
                initial=self.instance.is_container,
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
            )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clash = (
            Item.objects.for_club(self.club)
            .filter(name__iexact=name)
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if clash:
            raise forms.ValidationError("An item with this name already exists in this club.")
        return name

    def clean(self):
        cleaned = super().clean()
        is_stacked = cleaned.get("is_stacked")
        is_container = cleaned.get("is_container", False)
        if is_stacked and is_container:
            raise forms.ValidationError("An item is a container or stacked, never both.")
        if is_stacked and not cleaned.get("unit_name"):
            self.add_error("unit_name", "A stacked item needs a unit name.")
        if (
            self.instance.pk
            and not can_toggle_stacked(self.instance)
            and "is_stacked" in self.changed_data
        ):
            convert_url = reverse("items:convert", args=[self.club.slug, self.instance.pk])
            self.add_error(
                "is_stacked",
                format_html(
                    'This item is owned or in use, so "stacked" cannot be toggled here. '
                    '<a href="{}">Convert to stacked&hellip;</a>',
                    convert_url,
                ),
            )
        return cleaned

    def save(self, commit=True):
        self.instance.club = self.club
        self.instance.value_cp = self.cleaned_data.get("value") or 0
        if self.cleaned_data.get("is_stacked"):
            self.instance.is_stacked = True
            self.instance.unit_name = self.cleaned_data.get("unit_name") or ""
            self.instance.value_units = self.cleaned_data.get("value_units") or 1
        else:
            self.instance.is_stacked = False
            self.instance.unit_name = ""
            self.instance.value_units = 1
        if "is_container" in self.cleaned_data:
            self.instance.is_container = self.cleaned_data["is_container"]
        return super().save(commit=commit)


class ConvertToStackedForm(forms.Form):
    """Form for the units one existing item is worth (story U124)."""

    unit_name = forms.CharField(
        required=True,
        max_length=40,
        label="Unit name",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Name of one unit after conversion, e.g. sheet, ft or arrow.",
    )
    factor = forms.IntegerField(
        required=True,
        min_value=1,
        initial=1,
        label="Units one existing {item} is worth",
        widget=forms.NumberInput(attrs={"min": 1, "class": "form-control"}),
        help_text="Multiplying factor: one old item becomes this many units.",
    )

    def __init__(self, *args, item=None, **kwargs):
        super().__init__(*args, **kwargs)
        if item is not None:
            self.fields["factor"].label = f"Units one existing {item.name} is worth"


class SlotForm(forms.ModelForm):
    """Form for a single container slot."""

    class Meta:
        model = ContainerSlot
        fields = ["chance_pct", "unknown", "position"]
        widgets = {
            "chance_pct": forms.NumberInput(
                attrs={"min": 1, "max": 100, "class": "form-control form-control-sm"}
            ),
            "position": forms.NumberInput(
                attrs={"min": 0, "class": "form-control form-control-sm"}
            ),
            "unknown": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, container=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.container = container
        self.fields["chance_pct"].label = "Chance %"
        self.fields["chance_pct"].help_text = "1-100"
        self.fields["unknown"].label = "Unknown"
        self.fields["position"].label = "Order"
        self.fields["position"].help_text = "Display order"

    def clean_chance_pct(self):
        chance = self.cleaned_data["chance_pct"]
        if not 1 <= chance <= 100:
            raise forms.ValidationError("Chance must be between 1 and 100.")
        return chance

    def clean_position(self):
        position = self.cleaned_data["position"]
        if position < 0:
            raise forms.ValidationError("Order must be 0 or greater.")
        return position


class SlotOptionForm(forms.ModelForm):
    """Form for a single slot option."""

    class Meta:
        model = ContainerSlotOption
        fields = ["item", "qty_min", "qty_max", "weight"]
        widgets = {
            "item": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "qty_min": forms.NumberInput(attrs={"min": 1, "class": "form-control form-control-sm"}),
            "qty_max": forms.NumberInput(attrs={"min": 1, "class": "form-control form-control-sm"}),
            "weight": forms.NumberInput(attrs={"min": 1, "class": "form-control form-control-sm"}),
        }

    def __init__(self, *args, club=None, container=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club
        self.container = container
        if club is not None:
            self.fields["item"].queryset = (
                Item.objects.filter(club=club)
                .exclude(pk=container.pk if container else None)
                .order_by("name")
            )
        self.fields["item"].label = "Item"
        self.fields["qty_min"].label = "Qty min"
        self.fields["qty_max"].label = "Qty max"
        self.fields["weight"].label = "Weight"
        self.fields["weight"].help_text = "Relative weight for weighted pick"

    def clean_item(self):
        item = self.cleaned_data["item"]
        # Reject retired items unless this row already holds it
        if item.retired and not (self.instance.pk and self.instance.item_id == item.pk):
            raise forms.ValidationError(f'Item "{item}" is retired and cannot be added.')
        # Foreign club items are excluded by queryset, but double-check
        if self.club and item.club_id != self.club.id:
            raise forms.ValidationError("Item must belong to the same club.")
        # Self-reference check (cycle of length 1)
        if self.container and item.pk == self.container.pk:
            raise forms.ValidationError("A container cannot contain itself.")
        return item

    def clean(self):
        cleaned = super().clean()
        qty_min = cleaned.get("qty_min")
        qty_max = cleaned.get("qty_max")
        if qty_min is not None and qty_max is not None and qty_max < qty_min:
            raise forms.ValidationError("Qty max must be >= qty min.")
        return cleaned


class _OwnedFormSetMixin:
    """Shared helpers for the nested container formsets."""

    def _should_delete_form(self, form):
        if not hasattr(form, "cleaned_data"):
            return False
        return super()._should_delete_form(form)

    def in_use(self, form):
        """True for a row that is kept: not deleted and not an untouched blank row."""
        if self._should_delete_form(form):
            return False
        return not (form.empty_permitted and not form.has_changed())

    def kept_forms(self):
        return [f for f in self.forms if self.in_use(f)]

    def check_owned_ids(self):
        """Reject a posted row id that belongs to another parent."""
        owner = self.instance.pk
        for form in self.forms:
            obj = getattr(form, "cleaned_data", {}).get("id")
            if obj is not None and (owner is None or getattr(obj, self.fk.attname) != owner):
                raise forms.ValidationError(self.foreign_id_message)


class BaseSlotFormSet(_OwnedFormSetMixin, BaseInlineFormSet):
    """Formset for container slots. Each slot form owns a nested options formset."""

    foreign_id_message = "A posted slot does not belong to this container."

    def __init__(self, *args, club=None, container=None, **kwargs):
        self.club = club
        self.container = container
        super().__init__(*args, **kwargs)

    def add_fields(self, form, index):
        super().add_fields(form, index)
        prefix = f"{self.prefix}-{index}-opts"
        # A slot added in the browser has no nested management form yet.
        data = self.data if self.is_bound and f"{prefix}-TOTAL_FORMS" in self.data else None
        form.options = OptionFormSet(
            data,
            instance=form.instance,
            prefix=prefix,
            club=self.club,
            container=self.container,
        )
        # A new slot that keeps its default values still counts when it has an option.
        if form.empty_permitted and form.options.is_bound:
            if any(f.has_changed() for f in form.options.forms):
                form.empty_permitted = False

    def clean(self):
        super().clean()
        self.check_owned_ids()
        for form in self.kept_forms():
            opts = form.options
            if not opts.is_bound:
                raise forms.ValidationError("Every slot must have at least one option.")
            if not opts.is_valid():
                continue
            if not opts.kept_forms():
                raise forms.ValidationError("Every slot must have at least one option.")

    def is_valid(self):
        valid = super().is_valid()
        return valid and all(f.options.is_valid() for f in self.kept_forms())


class BaseOptionFormSet(_OwnedFormSetMixin, BaseInlineFormSet):
    """Formset for slot options."""

    foreign_id_message = "A posted option does not belong to this slot."

    def __init__(self, *args, club=None, container=None, **kwargs):
        self.club = club
        self.container = container
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs.update({"club": self.club, "container": self.container})
        return super()._construct_form(i, **kwargs)

    def clean(self):
        super().clean()
        self.check_owned_ids()


SlotFormSet = inlineformset_factory(
    Item,
    ContainerSlot,
    form=SlotForm,
    formset=BaseSlotFormSet,
    extra=0,
    can_delete=True,
    can_order=False,
)


OptionFormSet = inlineformset_factory(
    ContainerSlot,
    ContainerSlotOption,
    form=SlotOptionForm,
    formset=BaseOptionFormSet,
    extra=1,
    can_delete=True,
    can_order=False,
)
