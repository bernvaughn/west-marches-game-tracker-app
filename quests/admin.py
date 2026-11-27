from django.contrib import admin

from .models import Quest, QuestCompletion, QuestRequirement, QuestReward


class RequirementInline(admin.TabularInline):
    model = QuestRequirement
    extra = 0
    show_change_link = True
    autocomplete_fields = ["item"]


class RewardInline(admin.TabularInline):
    model = QuestReward
    extra = 0
    show_change_link = True
    autocomplete_fields = ["item"]


@admin.register(Quest)
class QuestAdmin(admin.ModelAdmin):
    list_display = ("name", "club", "start_date", "end_date")
    inlines = [RequirementInline, RewardInline]
    list_filter = ["club"]
    search_fields = ["name"]
    date_hierarchy = "start_date"
    ordering = ["name"]
    autocomplete_fields = ["club"]
    list_select_related = ["club"]


@admin.register(QuestRequirement)
class QuestRequirementAdmin(admin.ModelAdmin):
    list_display = ["quest", "item", "quantity"]
    list_filter = ["quest__club"]
    search_fields = ["quest__name", "item__name"]
    ordering = ["quest", "item"]
    autocomplete_fields = ["quest", "item"]
    list_select_related = ["quest", "item"]


@admin.register(QuestReward)
class QuestRewardAdmin(admin.ModelAdmin):
    list_display = ["quest", "item", "quantity", "coins"]
    list_filter = ["quest__club"]
    search_fields = ["quest__name", "item__name"]
    ordering = ["quest"]
    autocomplete_fields = ["quest", "item"]
    list_select_related = ["quest", "item"]


@admin.register(QuestCompletion)
class QuestCompletionAdmin(admin.ModelAdmin):
    list_display = ["character", "quest", "date", "created"]
    list_filter = ["quest__club"]
    search_fields = ["character__name", "quest__name"]
    date_hierarchy = "date"
    ordering = ["-date"]
    autocomplete_fields = ["quest", "character"]
    readonly_fields = ["created"]
    list_select_related = ["character", "quest"]
