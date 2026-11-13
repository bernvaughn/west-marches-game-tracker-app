from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from .scoping import ClubScopedManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=100, blank=True)
    must_change_password = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def __str__(self):
        return self.display_name or self.email


class Club(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    created = models.DateTimeField(auto_now_add=True)
    street_min_gap = models.PositiveSmallIntegerField(
        "Minimum empty buildings between shops", default=0
    )
    street_max_gap = models.PositiveSmallIntegerField(
        "Maximum empty buildings between shops", default=2
    )
    street_stall_gap = models.PositiveSmallIntegerField(
        "Minimum empty buildings before player stalls", default=1
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    club_path = "club"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="memberships")
    is_club_admin = models.BooleanField(default=False)
    is_game_master = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "club"], name="unique_membership"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.club}"


class WhitelistEntry(models.Model):
    club_path = "club"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="whitelist")
    email = models.EmailField()
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    class Meta:
        verbose_name_plural = "whitelist entries"
        constraints = [
            models.UniqueConstraint(fields=["club", "email"], name="unique_whitelist_email"),
        ]

    def __str__(self):
        return f"{self.email} ({self.club})"


class Message(models.Model):
    club_path = "club"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        HANDLED = "handled", "Handled"
        CLOSED = "closed", "Closed"

    class Kind(models.TextChoices):
        MESSAGE = "message", "Message"
        STOCK_REQUEST = "stock_request", "Stock request"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="messages")
    character = models.ForeignKey(
        "player_characters.Character", null=True, blank=True, on_delete=models.SET_NULL
    )
    body = models.TextField()
    kind = models.CharField(max_length=20, choices=Kind, default=Kind.MESSAGE)
    status = models.CharField(max_length=10, choices=Status, default=Status.OPEN)
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"Message {self.pk} from {self.sender}"


class SiteSettings(models.Model):
    donate_url = models.URLField(blank=True)

    class Meta:
        verbose_name_plural = "site settings"

    def __str__(self):
        return "Site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
