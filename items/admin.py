from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Item
from .services import (
    StackedConversionError,
    can_toggle_stacked,
    convert_to_stacked,
)


class ItemAdminForm(forms.ModelForm):
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
            "value_cp",
            "retired",
            "is_container",
            "is_stacked",
            "unit_name",
            "value_units",
        ]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_stacked") and cleaned.get("is_container"):
            raise forms.ValidationError("An item is a container or stacked, never both.")
        if cleaned.get("is_stacked") and not cleaned.get("unit_name"):
            self.add_error("unit_name", "A stacked item needs a unit name.")
        if (
            self.instance.pk
            and not can_toggle_stacked(self.instance)
            and "is_stacked" in self.changed_data
        ):
            convert_url = reverse("admin:items_item_convert", args=[self.instance.pk])
            raise forms.ValidationError(
                format_html(
                    'This item is owned or in use, so "stacked" cannot be toggled here. '
                    '<a href="{}">Convert to stacked&hellip;</a>',
                    convert_url,
                )
            )
        return cleaned


class ConvertAdminForm(forms.Form):
    unit_name = forms.CharField(max_length=40, label="Unit name")
    factor = forms.IntegerField(min_value=1, initial=1, label="Factor")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    form = ItemAdminForm
    list_display = ["name", "club", "rarity", "magic_type", "value_cp", "is_stacked"]
    list_filter = ["club", "rarity", "magic_type", "is_stacked"]
    search_fields = ["name", "description"]
    autocomplete_fields = ["club"]

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/convert/",
                self.admin_site.admin_view(self.convert_view),
                name="items_item_convert",
            ),
        ]
        return custom + urls

    def convert_view(self, request, pk):
        """Intermediate admin page: unit name and factor, then convert."""
        item = get_object_or_404(Item, pk=pk)
        if request.method == "POST":
            form = ConvertAdminForm(request.POST)
            if form.is_valid():
                try:
                    convert_to_stacked(
                        item,
                        form.cleaned_data["factor"],
                        form.cleaned_data["unit_name"],
                    )
                    messages.success(request, f"Converted {item.name} to stacked.")
                    return HttpResponseRedirect(reverse("admin:items_item_changelist"))
                except StackedConversionError as exc:
                    messages.error(request, str(exc))
        form = ConvertAdminForm()
        context = dict(
            self.admin_site.each_context(request),
            item=item,
            form=form,
            opts=self.model._meta,
            action=False,
        )
        return TemplateResponse(request, "admin/items/convert_to_stacked.html", context)

    @admin.action(description="Convert selected item to stacked")
    def convert_selected(self, request, queryset):
        if not (request.user.is_superuser or request.user.has_perm("items.change_item")):
            self.message_user(
                request,
                "Only a superuser or a user with items.change_item can convert items.",
                level=messages.ERROR,
            )
            return None
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one item to convert.", level=messages.ERROR)
            return None
        item = queryset.first()
        return HttpResponseRedirect(reverse("admin:items_item_convert", args=[item.pk]))
