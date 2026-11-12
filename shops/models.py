from django.db import models

from accounts.scoping import ClubScopedManager


class Shop(models.Model):
    class Color(models.TextChoices):
        PARCHMENT = "parchment", "Parchment"
        FOREST = "forest", "Forest"
        EMBER = "ember", "Ember"
        OCEAN = "ocean", "Ocean"
        VIOLET = "violet", "Violet"
        SLATE = "slate", "Slate"

    class Silhouette(models.TextChoices):
        HOODED_TRADER = "hooded_trader", "Hooded trader"
        DWARF_SMITH = "dwarf_smith", "Dwarf smith"
        ROBED_MAGE = "robed_mage", "Robed mage"
        HALFLING_GROCER = "halfling_grocer", "Halfling grocer"
        ELF_FLETCHER = "elf_fletcher", "Elf fletcher"
        BURLY_INNKEEPER = "burly_innkeeper", "Burly innkeeper"
        OLD_ALCHEMIST = "old_alchemist", "Old alchemist"
        GOBLIN_PEDDLER = "goblin_peddler", "Goblin peddler"
        WANDERING_BARD = "wandering_bard", "Wandering bard"
        VEILED_MERCHANT = "veiled_merchant", "Veiled merchant"

    club_path = "club"

    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE, related_name="shops")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    keeper_name = models.CharField(max_length=200, blank=True)
    keeper_description = models.TextField(blank=True)
    sell_percent = models.PositiveIntegerField(default=100)
    buy_percent = models.PositiveIntegerField(default=50)
    color = models.CharField(max_length=16, choices=Color.choices, default=Color.PARCHMENT)
    silhouette = models.CharField(
        max_length=24, choices=Silhouette.choices, default=Silhouette.HOODED_TRADER
    )
    symbol = models.CharField(max_length=8, blank=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ShopStock(models.Model):
    club_path = "shop__club"

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="stock")
    item = models.ForeignKey("items.Item", on_delete=models.PROTECT, related_name="stock_entries")
    quantity = models.PositiveIntegerField(null=True, blank=True)
    sell_percent = models.PositiveIntegerField(null=True, blank=True)
    buy_percent = models.PositiveIntegerField(null=True, blank=True)

    objects = ClubScopedManager()

    class Meta:
        verbose_name_plural = "shop stock"
        constraints = [
            models.UniqueConstraint(fields=["shop", "item"], name="unique_shop_item"),
        ]

    def __str__(self):
        return f"{self.item} in {self.shop}"


class Rotation(models.Model):
    club_path = "club"

    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE, related_name="rotations")
    name = models.CharField(max_length=200)
    open_date = models.DateField()
    close_date = models.DateField(null=True, blank=True)
    shops = models.ManyToManyField(Shop, blank=True, related_name="rotations")

    objects = ClubScopedManager()

    class Meta:
        ordering = ["-open_date"]

    def __str__(self):
        return self.name
