from .models import Item

ITEMS = [
    ("Rope", 100),
    ("Healing potion", 5000),
    ("Torch", 1),
    ("Longsword", 1500),
    ("Wolf pelt", 200),
    ("Moonstone amulet", 25000),
]


def seed(club):
    for name, value in ITEMS:
        Item.objects.get_or_create(club=club, name=name, defaults={"value_cp": value})
