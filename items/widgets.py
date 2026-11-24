"""Form widgets for the shared item picker component."""

from django import forms
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe


class ItemPickerWidget(forms.Widget):
    """
    Widget for picking a single item.

    Renders a search box, result list, and hidden input for the selected item ID.
    Falls back to a plain <select> when JavaScript is disabled.
    """

    template_name = "components/item_picker.html"

    def __init__(self, club=None, multi=False, attrs=None):
        super().__init__(attrs)
        self.club = club
        self.multi = multi

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["club"] = self.club
        context["widget"]["multi"] = self.multi
        if self.club:
            context["widget"]["search_url"] = reverse("items:picker_search", args=[self.club.slug])
        else:
            context["widget"]["search_url"] = ""
        # Ensure value is string for template comparison in no-JS fallback
        context["widget"]["value"] = str(value) if value not in (None, "") else ""
        return context

    def render(self, name, value, attrs=None, renderer=None):
        context = self.get_context(name, value, attrs)
        return mark_safe(render_to_string(self.template_name, context))

    def value_from_datadict(self, data, files, name):
        return data.get(name)


class ItemMultiPickerWidget(ItemPickerWidget):
    """
    Widget for picking multiple items.

    Renders a search box, result list, and hidden input for comma-separated item IDs.
    """

    def __init__(self, club=None, attrs=None):
        super().__init__(club=club, multi=True, attrs=attrs)

    def value_from_datadict(self, data, files, name):
        value = data.get(name, "")
        if not value:
            return []
        return [int(v) for v in value.split(",") if v.isdigit()]

    def format_value(self, value):
        if not value:
            return ""
        if isinstance(value, (list, tuple)):
            return ",".join(str(v) for v in value)
        return str(value)
