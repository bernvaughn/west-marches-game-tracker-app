from django.db import models

from accounts.scoping import ClubScopedManager


class AgentConnection(models.Model):
    club_path = "club"

    class Kind(models.TextChoices):
        OAUTH = "oauth", "OAuth"
        TOKEN = "token", "Token"

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="agent_connections"
    )
    club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="agent_connections"
    )
    label = models.CharField(max_length=200, blank=True)
    kind = models.CharField(max_length=10, choices=Kind, default=Kind.OAUTH)
    token_hash = models.CharField(max_length=128, blank=True, db_index=True)
    token_prefix = models.CharField(max_length=16, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = ClubScopedManager()

    def __str__(self):
        return self.label or f"Connection {self.pk}"


class ProposedBatch(models.Model):
    club_path = "club"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        DISCARDED = "discarded", "Discarded"
        REVERSED = "reversed", "Reversed"

    club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="proposed_batches"
    )
    connection = models.ForeignKey(
        AgentConnection, on_delete=models.CASCADE, related_name="batches"
    )
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="+")
    date = models.DateField()
    idempotency_key = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    source_notes = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    class Meta:
        verbose_name_plural = "proposed batches"
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "idempotency_key"], name="unique_batch_idempotency"
            )
        ]

    def __str__(self):
        return f"Batch {self.pk} ({self.status})"


class ProposedItem(models.Model):
    club_path = "club"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="proposed_items"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    traits = models.TextField(blank=True)
    details = models.TextField(blank=True)
    value_cp = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    approved_item = models.ForeignKey(
        "items.Item", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    batch = models.ForeignKey(
        ProposedBatch, null=True, blank=True, on_delete=models.CASCADE, related_name="new_items"
    )

    objects = ClubScopedManager()

    def __str__(self):
        return self.name


class ProposedLine(models.Model):
    club_path = "batch__club"

    batch = models.ForeignKey(ProposedBatch, on_delete=models.CASCADE, related_name="lines")
    character = models.ForeignKey("player_characters.Character", on_delete=models.CASCADE)
    item = models.ForeignKey("items.Item", null=True, blank=True, on_delete=models.CASCADE)
    proposed_item = models.ForeignKey(
        ProposedItem, null=True, blank=True, on_delete=models.CASCADE, related_name="lines"
    )
    quantity = models.IntegerField(default=0)
    coins = models.IntegerField(default=0)
    note = models.TextField(blank=True)

    objects = ClubScopedManager()

    def __str__(self):
        return f"Proposed line {self.pk}"
