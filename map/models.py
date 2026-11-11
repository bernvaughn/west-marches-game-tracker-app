from django.db import models

from accounts.scoping import ClubScopedManager

BANDS = [
    ("1-2", "Levels 1-2"),
    ("3-4", "Levels 3-4"),
    ("5-6", "Levels 5-6"),
    ("7-8", "Levels 7-8"),
    ("9-10", "Levels 9-10"),
    ("11-12", "Levels 11-12"),
    ("13-14", "Levels 13-14"),
    ("15-16", "Levels 15-16"),
    ("17-18", "Levels 17-18"),
    ("19-20", "Levels 19-20"),
]


class HexMap(models.Model):
    club_path = "club"

    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE, related_name="hex_maps")
    name = models.CharField(max_length=200)
    archived = models.BooleanField(default=False)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        creating = self._state.adding
        super().save(*args, **kwargs)
        if creating:
            Tile.objects.get_or_create(map=self, q=0, r=0, defaults={"is_safe_town": True})


class Tile(models.Model):
    club_path = "map__club"

    map = models.ForeignKey(HexMap, on_delete=models.CASCADE, related_name="tiles")
    q = models.IntegerField()
    r = models.IntegerField()
    color = models.CharField(max_length=20, blank=True)
    is_safe_town = models.BooleanField(default=False)

    objects = ClubScopedManager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["map", "q", "r"], name="unique_tile")]

    def __str__(self):
        return f"Tile ({self.q}, {self.r})"


class XPLevel(models.Model):
    club_path = "club"

    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE, related_name="xp_levels")
    band = models.CharField(max_length=10, choices=BANDS)
    discover_xp = models.PositiveIntegerField(default=0)
    explore_xp = models.PositiveIntegerField(default=0)

    objects = ClubScopedManager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["club", "band"], name="unique_xp_band")]

    def __str__(self):
        return f"{self.club} {self.band}"


class Location(models.Model):
    club_path = "tile__map__club"

    tile = models.ForeignKey(Tile, on_delete=models.CASCADE, related_name="locations")
    name = models.CharField(max_length=200)
    color = models.CharField(max_length=20, blank=True)
    symbol = models.CharField(max_length=20, blank=True)
    player_notes = models.TextField(blank=True)
    gm_notes = models.TextField(blank=True)
    target_band = models.CharField(max_length=10, choices=BANDS, blank=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Encounter(models.Model):
    club_path = "location__tile__map__club"

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="encounters")
    date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)

    objects = ClubScopedManager()

    def __str__(self):
        return f"Encounter at {self.location}"


class LocationCredit(models.Model):
    club_path = "location__tile__map__club"

    class Kind(models.TextChoices):
        DISCOVERED = "discovered", "Discovered"
        EXPLORED = "explored", "Explored"

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="credits")
    kind = models.CharField(max_length=12, choices=Kind)
    date = models.DateField(null=True, blank=True)
    characters = models.ManyToManyField("player_characters.Character", blank=True)

    objects = ClubScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["location", "kind"], name="unique_location_credit")
        ]

    def __str__(self):
        return f"{self.kind} {self.location}"


class MapRequest(models.Model):
    club_path = "club"

    class Kind(models.TextChoices):
        VISIT = "visit", "Visit"
        DISCOVERED = "discovered", "Discovered"
        EXPLORED = "explored", "Explored"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE, related_name="map_requests")
    kind = models.CharField(max_length=12, choices=Kind)
    status = models.CharField(max_length=10, choices=Status, default=Status.REQUESTED)
    date = models.DateField(null=True, blank=True)
    characters = models.ManyToManyField("player_characters.Character", blank=True)
    requested_by = models.ForeignKey(
        "accounts.Membership", on_delete=models.CASCADE, related_name="map_requests"
    )
    tile = models.ForeignKey(Tile, null=True, blank=True, on_delete=models.SET_NULL)
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.kind} request {self.pk}"


class TileVisit(models.Model):
    club_path = "map__club"

    map = models.ForeignKey(HexMap, on_delete=models.CASCADE, related_name="visits")
    q = models.IntegerField()
    r = models.IntegerField()
    character = models.ForeignKey(
        "player_characters.Character", on_delete=models.CASCADE, related_name="tile_visits"
    )
    date = models.DateField(null=True, blank=True)

    objects = ClubScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["map", "q", "r", "character"], name="unique_tile_visit")
        ]

    def __str__(self):
        return f"{self.character} visited ({self.q}, {self.r})"
