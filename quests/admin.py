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


admin.site.register([QuestCompletion])
