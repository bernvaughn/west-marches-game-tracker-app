from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.scoping import ClubScopedManager, ClubScopedQuerySet
from ledger.models import AppendOnlyManager, AppendOnlyModel


class DowntimePointEntry(AppendOnlyModel):
    club_path = "character__club"

    class Kind(models.TextChoices):
        AWARD = "award", "Award"
        REMOVE = "remove", "Remove"
        SPEND = "spend", "Spend"
        REQUEST = "request", "Request"

    character = models.ForeignKey(
        "player_characters.Character",
        on_delete=models.PROTECT,
        related_name="downtime_point_entries",
    )
    delta = models.IntegerField()
    note = models.TextField(blank=True)
    date = models.DateField(default=timezone.localdate)
    kind = models.CharField(max_length=10, choices=Kind)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    source = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    objects = AppendOnlyManager()

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.character}: {self.delta:+d} ({self.kind})"


class DowntimeActionQuerySet(ClubScopedQuerySet):
    def live_on(self, date):
        return self.filter(
            Q(start_date__isnull=True) | Q(start_date__lte=date),
            Q(end_date__isnull=True) | Q(end_date__gte=date),
        )


class DowntimeAction(models.Model):
    club_path = "club"

    club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="downtime_actions"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cost = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    objects = models.Manager.from_queryset(DowntimeActionQuerySet)()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(cost__gte=1), name="downtime_action_cost_min"),
        ]

    def __str__(self):
        return self.name

    def status_on(self, date):
        if self.start_date and date < self.start_date:
            return "upcoming"
        if self.end_date and date > self.end_date:
            return "ended"
        return "live"

    def is_live_on(self, date):
        return self.status_on(date) == "live"


class DowntimeEntry(models.Model):
    club_path = "action__club"

    action = models.ForeignKey(DowntimeAction, on_delete=models.CASCADE, related_name="entries")
    label = models.CharField(max_length=200)
    weight = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    coins = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    order = models.PositiveIntegerField(default=0)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(weight__gte=1), name="downtime_entry_weight_min"),
            models.CheckConstraint(condition=Q(coins__gte=0), name="downtime_entry_coins_min"),
        ]

    def __str__(self):
        return self.label


class DowntimeEntryItem(models.Model):
    club_path = "entry__action__club"

    entry = models.ForeignKey(DowntimeEntry, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey("items.Item", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    objects = ClubScopedManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1), name="downtime_entry_item_quantity_min"
            ),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.item} for {self.entry}"


class DowntimeResult(models.Model):
    club_path = "character__club"

    character = models.ForeignKey(
        "player_characters.Character", on_delete=models.PROTECT, related_name="downtime_results"
    )
    action = models.ForeignKey(DowntimeAction, on_delete=models.PROTECT, related_name="results")
    entry = models.ForeignKey(
        DowntimeEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name="results"
    )
    ledger_entry = models.OneToOneField(
        "ledger.LedgerEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="downtime_result",
    )
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["-created", "-id"]

    def __str__(self):
        return f"{self.character} on {self.action}"


class DowntimePointRequest(models.Model):
    club_path = "club"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="downtime_point_requests"
    )
    requested_by = models.ForeignKey(
        "accounts.Membership", on_delete=models.CASCADE, related_name="downtime_point_requests"
    )
    characters = models.ManyToManyField("player_characters.Character", blank=True)
    points = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    note = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    decided_by = models.ForeignKey(
        "accounts.Membership",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decided_downtime_requests",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["-created"]
        constraints = [
            models.CheckConstraint(condition=Q(points__gte=1), name="downtime_request_points_min"),
        ]

    def __str__(self):
        return f"Request {self.pk}: {self.points} points"
