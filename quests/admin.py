from django.contrib import admin

from .models import Quest, QuestCompletion, QuestRequirement, QuestReward

admin.site.register([Quest, QuestRequirement, QuestReward, QuestCompletion])
