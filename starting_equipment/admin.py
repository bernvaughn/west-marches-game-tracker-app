from django.contrib import admin

from .models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
    StartingEquipmentRequest,
    StartingEquipmentTemplate,
)


class StartingEquipmentClassLineInline(admin.TabularInline):
    model = StartingEquipmentClassLine
    extra = 0
    fields = ["item", "quantity", "is_choice", "choice_group"]
    autocomplete_fields = ["item"]
    search_fields = ["item__name"]


class StartingEquipmentClassEntryInline(admin.StackedInline):
    model = StartingEquipmentClassEntry
    extra = 0
    fields = ["char_class", "min_level", "max_level", "coins_cp"]
    inlines = [StartingEquipmentClassLineInline]


class StartingEquipmentBackgroundLineInline(admin.TabularInline):
    model = StartingEquipmentBackgroundLine
    extra = 0
    fields = ["item", "quantity", "is_choice", "choice_group"]
    autocomplete_fields = ["item"]
    search_fields = ["item__name"]


class StartingEquipmentBackgroundEntryInline(admin.StackedInline):
    model = StartingEquipmentBackgroundEntry
    extra = 0
    fields = ["background", "coins_cp"]
    inlines = [StartingEquipmentBackgroundLineInline]


class StartingEquipmentLevelCoinsInline(admin.StackedInline):
    model = StartingEquipmentLevelCoins
    extra = 0
    fields = ["level", "coins_cp"]


class MagicItemStartingOptionInline(admin.StackedInline):
    model = MagicItemStartingOption
    extra = 0
    fields = ["item", "max_per_character", "notes"]
    autocomplete_fields = ["item"]
    search_fields = ["item__name"]


class StartingEquipmentRequestInline(admin.StackedInline):
    model = StartingEquipmentRequest
    extra = 0
    fields = [
        "character",
        "item",
        "quantity",
        "note",
        "status",
        "decided_by",
        "decided_at",
        "decision_note",
    ]
    readonly_fields = ["created", "decided_by", "decided_at"]
    autocomplete_fields = ["character", "item"]
    search_fields = ["character__name", "item__name"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(StartingEquipmentTemplate)
class StartingEquipmentTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "is_active", "created"]
    list_filter = ["club", "is_active"]
    search_fields = ["name", "description"]
    inlines = [
        StartingEquipmentClassEntryInline,
        StartingEquipmentBackgroundEntryInline,
        StartingEquipmentLevelCoinsInline,
        MagicItemStartingOptionInline,
    ]


@admin.register(StartingEquipmentClassEntry)
class StartingEquipmentClassEntryAdmin(admin.ModelAdmin):
    list_display = ["template", "char_class", "min_level", "max_level", "coins_cp"]
    list_filter = ["template__club", "template"]
    search_fields = ["char_class"]
    inlines = [StartingEquipmentClassLineInline]


@admin.register(StartingEquipmentClassLine)
class StartingEquipmentClassLineAdmin(admin.ModelAdmin):
    list_display = ["class_entry", "item", "quantity", "is_choice", "choice_group"]
    list_filter = ["class_entry__template__club", "class_entry__template"]
    autocomplete_fields = ["item"]
    search_fields = ["item__name"]


@admin.register(StartingEquipmentBackgroundEntry)
class StartingEquipmentBackgroundEntryAdmin(admin.ModelAdmin):
    list_display = ["template", "background", "coins_cp"]
    list_filter = ["template__club", "template"]
    search_fields = ["background"]
    inlines = [StartingEquipmentBackgroundLineInline]


@admin.register(StartingEquipmentBackgroundLine)
class StartingEquipmentBackgroundLineAdmin(admin.ModelAdmin):
    list_display = ["background_entry", "item", "quantity", "is_choice", "choice_group"]
    list_filter = ["background_entry__template__club", "background_entry__template"]
    autocomplete_fields = ["item"]
    search_fields = ["item__name"]


@admin.register(StartingEquipmentLevelCoins)
class StartingEquipmentLevelCoinsAdmin(admin.ModelAdmin):
    list_display = ["template", "level", "coins_cp"]
    list_filter = ["template__club", "template"]
    search_fields = ["level"]


@admin.register(MagicItemStartingOption)
class MagicItemStartingOptionAdmin(admin.ModelAdmin):
    list_display = ["template", "item", "max_per_character"]
    list_filter = ["template__club", "template"]
    autocomplete_fields = ["item"]
    search_fields = ["item__name"]


@admin.register(StartingEquipmentRequest)
class StartingEquipmentRequestAdmin(admin.ModelAdmin):
    list_display = ["character", "item", "quantity", "status", "created", "decided_by"]
    list_filter = ["club", "status"]
    search_fields = ["character__name", "item__name", "note"]
    autocomplete_fields = ["character", "item"]
    readonly_fields = ["created", "decided_by", "decided_at"]
    actions = ["approve_requests", "decline_requests"]

    @admin.action(description="Approve selected requests")
    def approve_requests(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status=StartingEquipmentRequest.Status.PENDING).update(
            status=StartingEquipmentRequest.Status.APPROVED,
            decided_by=request.user,
            decided_at=timezone.now(),
        )

    @admin.action(description="Decline selected requests")
    def decline_requests(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status=StartingEquipmentRequest.Status.PENDING).update(
            status=StartingEquipmentRequest.Status.DECLINED,
            decided_by=request.user,
            decided_at=timezone.now(),
        )