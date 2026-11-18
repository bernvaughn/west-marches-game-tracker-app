from django.contrib import admin

from .models import Character


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "owner", "level", "char_class"]
    list_filter = ["club", "level"]
    search_fields = ["name", "char_class"]
    autocomplete_fields = ["club", "owner"]
