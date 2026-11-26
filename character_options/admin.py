"""Admin registration for character options."""

from django.contrib import admin

from .models import Background, CharacterClass, Species


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    """Playable species for a club."""

    list_display = ["name", "club", "is_active", "sort_order"]
    list_filter = ["club", "is_active"]
    search_fields = ["name"]
    ordering = ["sort_order", "name"]
    autocomplete_fields = ["club"]
    list_select_related = ["club"]
    date_hierarchy = "created"


@admin.register(CharacterClass)
class CharacterClassAdmin(admin.ModelAdmin):
    """Character classes for a club."""

    list_display = ["name", "club", "is_active", "sort_order"]
    list_filter = ["club", "is_active"]
    search_fields = ["name"]
    ordering = ["sort_order", "name"]
    autocomplete_fields = ["club"]
    list_select_related = ["club"]
    date_hierarchy = "created"


@admin.register(Background)
class BackgroundAdmin(admin.ModelAdmin):
    """Character backgrounds for a club."""

    list_display = ["name", "club", "is_active", "sort_order"]
    list_filter = ["club", "is_active"]
    search_fields = ["name"]
    ordering = ["sort_order", "name"]
    autocomplete_fields = ["club"]
    list_select_related = ["club"]
    date_hierarchy = "created"
