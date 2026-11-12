from django.db import models
from django.utils import timezone

from accounts.scoping import ClubScopedQuerySet


class AppendOnlyError(Exception):
    """Raised on any attempt to change or delete a ledger row."""


class AppendOnlyQuerySet(ClubScopedQuerySet):
    def update(self, **kwargs):
        raise AppendOnlyError("Ledger rows cannot be updated.")

    def delete(self):
        raise AppendOnlyError("Ledger rows cannot be deleted.")


AppendOnlyManager = models.Manager.from_queryset(AppendOnlyQuerySet)


class AppendOnlyModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk is not None and not self._state.adding:
            raise AppendOnlyError("Ledger rows cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError("Ledger rows cannot be deleted.")


class LedgerEntry(AppendOnlyModel):
    club_path = "club"

    class Kind(models.TextChoices):
        AWARD = "award", "Award"
        PURCHASE = "purchase", "Purchase"
        SALE = "sale", "Sale"
        TRADE = "trade", "Trade"
        TRANSFER = "transfer", "Transfer"
        QUEST_TURN_IN = "quest_turn_in", "Quest turn-in"
        QUEST_REWARD = "quest_reward", "Quest reward"
        CONSUMED = "consumed", "Consumed"
        ADJUSTMENT = "adjustment", "Adjustment"
        REVERSAL = "reversal", "Reversal"

    club = models.ForeignKey(
        "accounts.Club", on_delete=models.PROTECT, related_name="ledger_entries"
    )
    character = models.ForeignKey(
        "player_characters.Character", on_delete=models.PROTECT, related_name="ledger_entries"
    )
    date = models.DateField(default=timezone.localdate)
    note = models.TextField(blank=True)
    kind = models.CharField(max_length=20, choices=Kind)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    via_agent = models.BooleanField(default=False)
    shop = models.ForeignKey("shops.Shop", null=True, blank=True, on_delete=models.PROTECT)
    agent_batch = models.ForeignKey(
        "agent_access.ProposedBatch", null=True, blank=True, on_delete=models.PROTECT
    )
    reverses = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversals"
    )
    source_message = models.ForeignKey(
        "accounts.Message",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="granted_entries",
    )
    created = models.DateTimeField(auto_now_add=True)

    objects = AppendOnlyManager()

    class Meta:
        verbose_name_plural = "ledger entries"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.kind} for {self.character} on {self.date}"


class LedgerLine(AppendOnlyModel):
    club_path = "entry__club"

    entry = models.ForeignKey(LedgerEntry, on_delete=models.PROTECT, related_name="lines")
    item = models.ForeignKey("items.Item", null=True, blank=True, on_delete=models.PROTECT)
    quantity = models.IntegerField(default=0)
    coins = models.IntegerField(default=0)

    objects = AppendOnlyManager()

    def __str__(self):
        return f"Line {self.pk} of entry {self.entry_id}"
