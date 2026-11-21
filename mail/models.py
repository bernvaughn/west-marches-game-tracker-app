from dataclasses import dataclass

from django.conf import settings
from django.db import models


class EmailMessage(models.Model):
    """An email queued for delivery.

    Never stores a body or a link. The body lives in EmailPayload (deleted on send/fail).
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        BOUNCED = "bounced", "Bounced"
        COMPLAINED = "complained", "Complained"

    class Kind(models.TextChoices):
        WELCOME = "welcome", "Welcome"
        PASSWORD_RESET = "password_reset", "Password reset"
        RSVP = "rsvp", "RSVP"
        REMINDER = "reminder", "Reminder"
        CANCEL = "cancel", "Cancelled"
        CHANGE = "change", "Changed"
        DIGEST = "digest", "Digest"
        UNSUBSCRIBE = "unsubscribe", "Unsubscribe"
        EMAIL_CHANGE = "email_change", "Email change"

    club = models.ForeignKey(
        "accounts.Club", null=True, blank=True, on_delete=models.SET_NULL, related_name="emails"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="emails"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    to_address = models.EmailField()
    subject = models.CharField(max_length=200)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    provider_id = models.CharField(max_length=100, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=200, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "next_attempt_at"], name="mail_msg_status_next"),
            models.Index(fields=["club", "created"], name="mail_msg_club_created"),
        ]
        ordering = ["-created"]

    def __str__(self):
        return f"{self.kind} to {self.to_address} ({self.status})"


class EmailPayload(models.Model):
    """The email body and optional HTML, deleted after send or final failure."""

    message = models.OneToOneField(EmailMessage, on_delete=models.CASCADE, related_name="payload")
    text = models.TextField()
    html = models.TextField(blank=True)
    reply_to = models.EmailField(blank=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Payload for {self.message}"


class DoNotEmail(models.Model):
    """An address that must never receive email."""

    class Reason(models.TextChoices):
        BOUNCE = "bounce", "Bounce"
        COMPLAINT = "complaint", "Complaint"
        MANUAL = "manual", "Manual"

    address = models.EmailField(unique=True)
    reason = models.CharField(max_length=10, choices=Reason.choices, default=Reason.MANUAL)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def save(self, *args, **kwargs):
        self.address = self.address.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.address} ({self.reason})"


class OneTimeToken(models.Model):
    """A single-use, expiring token. Only the SHA-256 hash is stored."""

    class Purpose(models.TextChoices):
        WELCOME = "welcome", "Welcome"
        PASSWORD_RESET = "password_reset", "Password reset"
        RSVP = "rsvp", "RSVP"
        UNSUBSCRIBE = "unsubscribe", "Unsubscribe"
        EMAIL_CHANGE = "email_change", "Email change"

    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tokens")
    club = models.ForeignKey(
        "accounts.Club", null=True, blank=True, on_delete=models.CASCADE, related_name="tokens"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["purpose", "user", "club"], name="mail_token_purpose_user_club"),
        ]
        ordering = ["-created"]

    def __str__(self):
        return f"{self.purpose} for {self.user} ({'used' if self.used_at else 'unused'})"


class EmailPreference(models.Model):
    """Per-membership email preference for a given kind."""

    class Kind(models.TextChoices):
        REMINDER = "reminder", "Reminder"
        NOTICE = "notice", "Notice"
        DIGEST = "digest", "Digest"

    membership = models.ForeignKey("accounts.Membership", on_delete=models.CASCADE, related_name="email_preferences")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["membership", "kind"], name="unique_email_preference"),
        ]
        ordering = ["membership", "kind"]

    def __str__(self):
        return f"{self.membership} - {self.kind}: {'on' if self.enabled else 'off'}"


def default_reminder_days():
    return [3]


class ClubMailSettings(models.Model):
    """Club-level email settings."""

    club = models.OneToOneField("accounts.Club", on_delete=models.CASCADE, related_name="mail_settings")
    contact_email = models.EmailField(blank=True)
    reminder_days = models.JSONField(default=default_reminder_days)

    def __str__(self):
        return f"Mail settings for {self.club}"


class NoticeSent(models.Model):
    """Deduplication table for notices (reminders, cancel, change, digests)."""

    class Kind(models.TextChoices):
        REMINDER = "reminder", "Reminder"
        CANCEL = "cancel", "Cancelled"
        CHANGE = "change", "Changed"
        DIGEST = "digest", "Digest"

    kind = models.CharField(max_length=10, choices=Kind.choices)
    key = models.CharField(max_length=200)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notices_sent")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "key", "user"], name="unique_notice_sent"),
        ]
        ordering = ["-created"]

    def __str__(self):
        return f"{self.kind} {self.key} -> {self.user}"


class JobRun(models.Model):
    """Track job executions."""

    name = models.CharField(max_length=100, unique=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        status = "ok" if self.ok else "failed"
        return f"{self.name} ({status})"


@dataclass
class QueueResult:
    """Result of queue_email."""

    status: str  # "queued", "refused", "failed"
    message: EmailMessage | None