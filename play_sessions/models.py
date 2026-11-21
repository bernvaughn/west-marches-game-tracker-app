from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Q

from accounts.scoping import ClubScopedManager
from ledger.models import AppendOnlyManager, AppendOnlyModel


class SessionSeries(models.Model):
    """A recurring series of play sessions (weekly or every two weeks)."""

    club_path = "club"

    class Rule(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        EVERY_TWO_WEEKS = "every_two_weeks", "Every two weeks"

    club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="session_series"
    )
    created_by = models.ForeignKey(
        "accounts.Membership",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_session_series",
    )
    rule = models.CharField(max_length=20, choices=Rule.choices)
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.get_rule_display()} series for {self.club}"


class PlaySession(models.Model):
    """A single scheduled play session."""

    club_path = "club"

    club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="play_sessions"
    )
    title = models.CharField(max_length=200)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    game_master = models.ForeignKey(
        "accounts.Membership",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="game_mastered_sessions",
    )
    location = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    recap = models.TextField(blank=True)
    gm_notes = models.TextField(blank=True)
    cancelled = models.BooleanField(default=False)
    series = models.ForeignKey(
        SessionSeries,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sessions",
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["starts_at"]
        indexes = [
            models.Index(fields=["club", "starts_at"]),
        ]
        constraints = [
            CheckConstraint(
                check=Q(ends_at__isnull=True) | Q(ends_at__gte=models.F("starts_at")),
                name="session_ends_after_starts",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.starts_at:%Y-%m-%d %H:%M})"


class SessionRSVP(models.Model):
    """A character's RSVP to a session."""

    club_path = "session__club"

    class Answer(models.TextChoices):
        YES = "yes", "Yes"
        MAYBE = "maybe", "Maybe"
        NO = "no", "No"

    session = models.ForeignKey(PlaySession, on_delete=models.CASCADE, related_name="rsvps")
    character = models.ForeignKey(
        "player_characters.Character", on_delete=models.CASCADE, related_name="session_rsvps"
    )
    answer = models.CharField(max_length=5, choices=Answer.choices)
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="answered_rsvps",
    )
    answered_at = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "character"], name="unique_session_character_rsvp"
            ),
        ]

    def __str__(self):
        return f"{self.character} -> {self.session}: {self.get_answer_display()}"


class SessionAttendance(models.Model):
    """A character's attendance at a session."""

    club_path = "session__club"

    session = models.ForeignKey(PlaySession, on_delete=models.CASCADE, related_name="attendance")
    character = models.ForeignKey(
        "player_characters.Character", on_delete=models.PROTECT, related_name="session_attendance"
    )
    played = models.BooleanField()
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_attendance",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    objects = ClubScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "character"], name="unique_session_character_attendance"
            ),
        ]

    def __str__(self):
        status = "played" if self.played else "absent"
        return f"{self.character} @ {self.session}: {status}"


class AttendanceChange(AppendOnlyModel):
    """Append-only history of attendance corrections."""

    club_path = "session__club"

    session = models.ForeignKey(
        PlaySession, on_delete=models.PROTECT, related_name="attendance_changes"
    )
    character = models.ForeignKey(
        "player_characters.Character", on_delete=models.PROTECT, related_name="attendance_changes"
    )
    old_played = models.BooleanField(null=True)
    new_played = models.BooleanField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="attendance_changes_made",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    objects = AppendOnlyManager()

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"Attendance change for {self.character} @ {self.session}"


class SessionAward(models.Model):
    """Downtime points awarded for attending a session."""

    club_path = "session__club"

    session = models.ForeignKey(PlaySession, on_delete=models.CASCADE, related_name="awards")
    character = models.ForeignKey(
        "player_characters.Character", on_delete=models.PROTECT, related_name="session_awards"
    )
    points = models.PositiveSmallIntegerField()

    objects = ClubScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "character"], name="unique_session_character_award"
            ),
        ]

    def __str__(self):
        return f"{self.points} pts for {self.character} @ {self.session}"


class SessionSettings(models.Model):
    """Per-club settings for play sessions."""

    club_path = "club"

    club = models.OneToOneField(
        "accounts.Club", on_delete=models.CASCADE, related_name="session_settings"
    )
    award_points = models.PositiveSmallIntegerField(default=0)
    feed_token = models.CharField(max_length=64, blank=True)

    objects = ClubScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["feed_token"],
                condition=~Q(feed_token=""),
                name="unique_session_feed_token",
            ),
        ]

    def __str__(self):
        return f"Session settings for {self.club}"
