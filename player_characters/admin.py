from django.contrib import admin

from .models import Character, CharacterStatusChange, ItemNote, JunkMark, SelectedCharacter


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "owner", "level", "char_class", "died_on", "archived_at"]
    list_filter = ["club", "level", "died_on", "archived_at"]
    search_fields = ["name", "char_class"]
    autocomplete_fields = ["club", "owner", "species_option", "class_option", "background_option"]
    list_select_related = [
        "club",
        "owner__user",
        "species_option",
        "class_option",
        "background_option",
    ]
    readonly_fields = ["last_printed_at", "created"]
    fieldsets = [
        ("Identity", {"fields": ["club", "owner", "name", "pronouns", "alignment", "description"]}),
        (
            "Build",
            {
                "fields": [
                    "species_option",
                    "species",
                    "class_option",
                    "char_class",
                    "background_option",
                    "background",
                    "level",
                    "xp",
                    "strength",
                    "dexterity",
                    "constitution",
                    "intelligence",
                    "wisdom",
                    "charisma",
                    "armor_class",
                    "max_hp",
                    "carrying_capacity_lb",
                    "perception_bonus",
                ]
            },
        ),
        (
            "Status",
            {
                "fields": [
                    "shop_open",
                    "starting_equipment_claimed",
                    "died_on",
                    "death_note",
                    "archived_at",
                    "last_printed_at",
                    "created",
                ]
            },
        ),
    ]


@admin.register(CharacterStatusChange)
class CharacterStatusChangeAdmin(admin.ModelAdmin):
    list_display = ["character", "kind", "by", "at", "date"]
    list_filter = ["kind", "at"]
    search_fields = ["character__name", "by__user__display_name"]
    readonly_fields = ["character", "kind", "by", "at", "note", "date"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SelectedCharacter)
class SelectedCharacterAdmin(admin.ModelAdmin):
    list_display = ["membership", "character"]
    list_filter = ["membership__club"]
    search_fields = ["membership__user__email", "membership__user__display_name", "character__name"]
    date_hierarchy = "membership__created"
    ordering = ["membership__user__display_name"]
    autocomplete_fields = ["membership", "character"]


@admin.register(JunkMark)
class JunkMarkAdmin(admin.ModelAdmin):
    list_display = ["character", "item", "quantity"]
    list_filter = ["character__club"]
    search_fields = ["character__name", "item__name"]
    ordering = ["character__name", "item__name"]
    autocomplete_fields = ["character", "item"]


@admin.register(ItemNote)
class ItemNoteAdmin(admin.ModelAdmin):
    list_display = ["character", "item", "truncated_text"]
    list_filter = ["character__club"]
    search_fields = ["character__name", "item__name", "text"]
    ordering = ["character__name", "item__name"]
    autocomplete_fields = ["character", "item"]
    readonly_fields = ["text"]

    def truncated_text(self, obj):
        """Return truncated text for list display."""
        if len(obj.text) > 50:
            return obj.text[:47] + "..."
        return obj.text

    truncated_text.short_description = "Text"
