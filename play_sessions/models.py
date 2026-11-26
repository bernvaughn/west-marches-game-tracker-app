from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Q
from django.utils import timezone

from accounts.scoping import ClubScopedManager
from ledger.models import AppendOnlyManager, AppendOnlyModel


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
                condition=Q(ends_at__isnull=True) | Q(ends_at__gte=models.F("starts_at")),
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


class PlayerRSVP(models.Model):
    """A player's RSVP to a session, one per (session, membership).

    Answers are per player, not per character. Existing per-character
    ``SessionRSVP`` rows are merged into this model by the
    ``0004_merge_rsvps_to_player`` data migration, which keeps ``SessionRSVP``
    untouched so the merge can run before code is switched over.
    """

    club_path = "session__club"

    session = models.ForeignKey(PlaySession, on_delete=models.CASCADE, related_name="player_rsvps")
    member = models.ForeignKey(
        "accounts.Membership",
        on_delete=models.CASCADE,
        related_name="player_rsvps",
    )
    answer = models.CharField(max_length=5, choices=SessionRSVP.Answer.choices)
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="answered_player_rsvps",
    )
    answered_at = models.DateTimeField(default=timezone.now)

    objects = ClubScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "member"], name="unique_session_member_rsvp"
            ),
        ]

    def __str__(self):
        return f"{self.member} -> {self.session}: {self.get_answer_display()}"


class AttendanceHint(models.Model):
    """A player's hint that they are bringing a character to a session.

    Only pre-ticks the attendance checkbox for the manager; never creates a
    ``SessionAttendance`` row. Deleted when attendance is confirmed.
    """

    club_path = "session__club"

    session = models.ForeignKey(
        PlaySession, on_delete=models.CASCADE, related_name="attendance_hints"
    )
    character = models.ForeignKey(
        "player_characters.Character",
        on_delete=models.CASCADE,
        related_name="attendance_hints",
    )
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    def __str__(self):
        return f"{self.character} brought to {self.session}"


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


def merge_rsvps_to_player():
    """Merge per-character SessionRSVP rows into per-player PlayerRSVP rows.

    For each (session, owning membership) group of SessionRSVP rows:
      * all answers agree -> that answer is used
      * answers disagree -> the most recent by answered_at (ties broken by id)
    answered_by and answered_at are copied from the chosen old row.

    Idempotent: uses get_or_create keyed on (session, member), so re-running
    creates no duplicates and changes no existing PlayerRSVP rows.

    SessionAttendance rows are never touched.

    Returns:
        (merged_count, mixed_answer_player_count)
    """
    from django.db import transaction

    merged = 0
    mixed = 0

    rsvps = SessionRSVP.objects.select_related("character__owner").order_by(
        "session_id", "character__owner_id", "-answered_at", "-id"
    )

    current_key = None
    group = []

    def flush():
        nonlocal merged, mixed
        if current_key is None:
            return
        session_id, member_id = current_key
        answers = {row.answer for row in group}
        chosen = group[0]  # most recent by answered_at, then id
        if len(answers) != 1:
            mixed += 1
        _, created = PlayerRSVP.objects.get_or_create(
            session_id=session_id,
            member_id=member_id,
            defaults={
                "answer": chosen.answer,
                "answered_by_id": chosen.answered_by_id,
                "answered_at": chosen.answered_at,
            },
        )
        if created:
            merged += 1

    with transaction.atomic():
        for row in rsvps:
            member_id = row.character.owner_id
            if member_id is None:
                continue
            key = (row.session_id, member_id)
            if key != current_key:
                flush()
                current_key = key
                group = []
            group.append(row)
        flush()

    return merged, mixed
