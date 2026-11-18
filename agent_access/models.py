from django.conf import settings
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
    oauth_application = models.ForeignKey(
        settings.OAUTH2_PROVIDER_APPLICATION_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    objects = ClubScopedManager()

    def __str__(self):
        return self.label or f"Connection {self.pk}"

    @property
    def is_expired(self):
        """Check if the token has expired."""
        from django.utils import timezone

        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at


class TokenAuditLog(models.Model):
    """Audit log for token lifecycle events: create, use, revoke, expire."""

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        USE = "use", "Use"
        REVOKE = "revoke", "Revoke"
        EXPIRE = "expire", "Expire"

    action = models.CharField(max_length=10, choices=Action.choices)
    connection = models.ForeignKey(
        AgentConnection, on_delete=models.CASCADE, related_name="audit_logs"
    )
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="token_audit_logs"
    )
    club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="token_audit_logs"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["user"]),
            models.Index(fields=["club"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"{self.action} - {self.user} @ {self.club} at {self.timestamp}"


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
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

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
    gm_details = models.TextField(
        blank=True,
        verbose_name="GM-only details",
        help_text=(
            "Only game masters and club admins see this. Use it for secrets, such as a curse."
        ),
    )
    value_cp = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    approved_item = models.ForeignKey(
        "items.Item", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    batch = models.ForeignKey(
        ProposedBatch, null=True, blank=True, on_delete=models.CASCADE, related_name="new_items"
    )
    connection = models.ForeignKey(
        AgentConnection,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="proposed_items",
    )
    created = models.DateTimeField(auto_now_add=True)

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
    date = models.DateField(null=True, blank=True)
    quantity = models.IntegerField(default=0)
    coins = models.IntegerField(default=0)
    note = models.TextField(blank=True)

    objects = ClubScopedManager()

    def __str__(self):
        return f"Proposed line {self.pk}"
