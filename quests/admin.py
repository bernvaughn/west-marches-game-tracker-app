from django.contrib import admin

from .models import Quest, QuestCompletion, QuestRequirement, QuestReward


class RequirementInline(admin.TabularInline):
    model = QuestRequirement
    extra = 1


class RewardInline(admin.TabularInline):
    model = QuestReward
    extra = 1


@admin.register(Quest)
class QuestAdmin(admin.ModelAdmin):
    list_display = ("name", "club", "start_date", "end_date")
    inlines = [RequirementInline, RewardInline]
    list_filter = ["club"]
    search_fields = ["name"]
    date_hierarchy = "start_date"
    ordering = ["name"]


@admin.register(QuestRequirement)
class QuestRequirementAdmin(admin.ModelAdmin):
    list_display = ["quest", "item", "quantity"]
    list_filter = ["quest__club"]
    search_fields = ["quest__name", "item__name"]
    ordering = ["quest", "item"]


@admin.register(QuestReward)
class QuestRewardAdmin(admin.ModelAdmin):
    list_display = ["quest", "item", "quantity", "coins"]
    list_filter = ["quest__club"]
    search_fields = ["quest__name", "item__name"]
    ordering = ["quest"]


@admin.register(QuestCompletion)
class QuestCompletionAdmin(admin.ModelAdmin):
    list_display = ["character", "quest", "date", "created"]
    list_filter = ["quest__club"]
    search_fields = ["character__name", "quest__name"]
    date_hierarchy = "date"
    ordering = ["-date"]
