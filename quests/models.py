from django.db import models

from accounts.scoping import ClubScopedManager


class Quest(models.Model):
    club_path = "club"

    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE, related_name="quests")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    max_completions = models.PositiveIntegerField(null=True, blank=True)
    max_per_character = models.PositiveIntegerField(null=True, blank=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class QuestRequirement(models.Model):
    club_path = "quest__club"

    quest = models.ForeignKey(Quest, on_delete=models.CASCADE, related_name="requirements")
    item = models.ForeignKey("items.Item", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)

    objects = ClubScopedManager()

    def __str__(self):
        return f"{self.quantity} x {self.item} for {self.quest}"


class QuestReward(models.Model):
    club_path = "quest__club"

    quest = models.ForeignKey(Quest, on_delete=models.CASCADE, related_name="rewards")
    item = models.ForeignKey("items.Item", null=True, blank=True, on_delete=models.PROTECT)
    quantity = models.IntegerField(default=0)
    coins = models.IntegerField(default=0)

    objects = ClubScopedManager()

    def __str__(self):
        return f"Reward {self.pk} for {self.quest}"


class QuestCompletion(models.Model):
    club_path = "quest__club"

    quest = models.ForeignKey(Quest, on_delete=models.CASCADE, related_name="completions")
    character = models.ForeignKey(
        "player_characters.Character", on_delete=models.PROTECT, related_name="quest_completions"
    )
    date = models.DateField()
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    def __str__(self):
        return f"{self.character} completed {self.quest}"
