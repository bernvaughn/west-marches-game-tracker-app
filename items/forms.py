from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils.html import format_html, format_html_join

from ledger.coins import CoinsField

from . import rarity
from .magic_types import NONE_LABEL, MagicType
from .models import ContainerSlot, ContainerSlotOption, Item


class ItemForm(forms.ModelForm):
    value = CoinsField(required=False, label="Value")

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
        ]
        widgets = {"rarity": forms.Select(attrs={"data-rarity-select": ""})}

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club
        self.fields["rarity"].choices = [("", "—"), *rarity.GROUPS]
        self.fields["magic_type"].choices = [("", NONE_LABEL), *MagicType.choices]
        self.fields["magic_type"].label = "Magic item type"
        self.fields["value"].help_text = format_html(
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
        )
        if self.instance.pk:
            self.initial["value"] = self.instance.value_cp
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

    def save(self, commit=True):
        self.instance.club = self.club
        self.instance.value_cp = self.cleaned_data.get("value") or 0
        if "is_container" in self.cleaned_data:
            self.instance.is_container = self.cleaned_data["is_container"]
        return super().save(commit=commit)


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


class BaseSlotFormSet(BaseInlineFormSet):
    """Formset for container slots. Each slot form owns a nested options formset."""

    def __init__(self, *args, club=None, container=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club
        self.container = container

    def add_fields(self, form, index):
        super().add_fields(form, index)
        # Prevent empty_permitted from skipping validation when form data matches model defaults
        form.empty_permitted = False
        # Build the nested options formset for this slot
        prefix = f"{self.prefix}-{index}-opts"
        form.options = OptionFormSet(
            self.data if self.is_bound else None,
            instance=form.instance,
            prefix=prefix,
            club=self.club,
            container=self.container,
        )

    def _should_delete_form(self, form):
        """Check if form should be deleted, handling forms without cleaned_data."""
        if not hasattr(form, "cleaned_data"):
            return False
        return super()._should_delete_form(form)

    def clean(self):
        super().clean()
        # Validate that any posted slot IDs belong to this container's club
        if self.container and self.club:
            valid_slot_ids = set(
                ContainerSlot.objects.filter(container__club=self.club).values_list("pk", flat=True)
            )
            for form in self.forms:
                if self.can_delete and self._should_delete_form(form):
                    continue
                # Check raw form data for ID field (works even if form validation fails)
                id_field_name = form.add_prefix("id")
                slot_id = form.data.get(id_field_name)
                if slot_id:
                    try:
                        slot_id = int(slot_id)
                    except (TypeError, ValueError):
                        slot_id = None
                    if slot_id and slot_id not in valid_slot_ids:
                        raise forms.ValidationError(
                            "A posted slot ID does not belong to this club."
                        )
        # Every kept slot needs at least one kept option
        # Note: nested option formsets are validated in the view before calling is_valid()
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            # Check if form has been validated (has cleaned_data attr and it's not empty)
            if not hasattr(form, "cleaned_data") or not form.cleaned_data:
                continue
            opts = getattr(form, "options", None)
            if opts is None:
                continue
            # Check if opts forms have been validated (have cleaned_data attr and it's not empty)
            kept = []
            for f in opts.forms:
                if opts.can_delete and opts._should_delete_form(f):
                    continue
                if hasattr(f, "cleaned_data") and f.cleaned_data:
                    kept.append(f)
            if not kept:
                raise forms.ValidationError("Every slot must have at least one option.")


class BaseOptionFormSet(BaseInlineFormSet):
    """Formset for slot options."""

    def __init__(self, *args, club=None, container=None, **kwargs):
        self.club = club
        self.container = container
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs.update({"club": self.club, "container": self.container})
        return super()._construct_form(i, **kwargs)

    def _should_delete_form(self, form):
        """Check if form should be deleted, handling forms without cleaned_data."""
        if not hasattr(form, "cleaned_data"):
            return False
        return super()._should_delete_form(form)


SlotFormSet = inlineformset_factory(
    Item,
    ContainerSlot,
    form=SlotForm,
    formset=BaseSlotFormSet,
    extra=1,
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
