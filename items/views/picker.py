"""Picker search endpoint for the shared item picker component."""

from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from accounts.mixins import ClubScopedMixin, PermissionMixin
from accounts.permissions import admin_or_gm_required

from ..picker import search_items
from ..values import format_item_value


@method_decorator(admin_or_gm_required, name="dispatch")
class PickerSearchView(ClubScopedMixin, PermissionMixin, View):
    """HTMX endpoint for item picker search results."""

    def get(self, request, club_slug):
        membership = request.membership
        query = request.GET.get("q", "").strip()
        include_retired = request.GET.get("retired") == "1"
        multi = request.GET.get("multi") == "1"

        items = search_items(
            club=request.club,
            membership=membership,
            query=query,
            include_retired=include_retired,
        )

        # Format values for each item
        for item in items:
            item.display_value = format_item_value(item)

        context = {
            "items": items,
            "query": query,
            "include_retired": include_retired,
            "multi": multi,
        }
        return render(request, "items/_picker_results.html", context)
