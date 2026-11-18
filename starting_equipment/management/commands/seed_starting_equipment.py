"""Management command to seed the 2024 D&D Default starting equipment template."""

from django.core.exceptions import MultipleObjectsReturned
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Club
from items.models import Item
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
    StartingEquipmentTemplate,
)

# 2024 D&D Class starting equipment (PHB 2024)
CLASS_EQUIPMENT = {
    "Barbarian": {
        "coins_cp": 200,  # 2d4 × 10 gp average = 50 gp = 5000 cp, but 2024 uses fixed
        "items": [
            ("Greataxe", 3000, "🪓", "standard", "", 1, False, ""),
            ("Handaxe", 500, "🪓", "standard", "", 2, False, ""),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, False, ""),
            ("Javelin", 50, "🏹", "standard", "", 4, False, ""),
        ],
        "choices": [
            # Greataxe OR any martial melee weapon - we'll use Greataxe as default
            # Two handaxes OR any simple weapon - we'll use Handaxe as default
        ],
    },
    "Bard": {
        "coins_cp": 1000,  # 5d4 × 10 gp average = 125 gp
        "items": [
            ("Rapier", 2500, "🗡️", "fine", "", 1, False, ""),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, False, ""),
            ("Dagger", 200, "🗡️", "standard", "", 1, False, ""),
            ("Diplomat's Pack", 3900, "🎒", "standard", "", 1, False, ""),
            ("Lute", 3500, "🎵", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Rapier OR longsword OR any simple weapon
            # Diplomat's pack OR entertainer's pack
            # Lute OR any musical instrument
        ],
    },
    "Cleric": {
        "coins_cp": 500,  # 5d4 × 10 gp
        "items": [
            ("Mace", 500, "⚔️", "standard", "", 1, False, ""),
            ("Scale Mail", 5000, "🛡️", "standard", "", 1, False, ""),
            ("Light Crossbow", 2500, "🏹", "standard", "", 1, False, ""),
            ("Crossbow Bolt", 1, "🏹", "trivial", "", 20, False, ""),
            ("Priest's Pack", 1900, "🎒", "standard", "", 1, False, ""),
            ("Shield", 1000, "🛡️", "standard", "", 1, False, ""),
            ("Holy Symbol (Amulet)", 500, "✝️", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Mace OR warhammer
            # Scale mail OR leather armor OR chain mail
            # Light crossbow + 20 bolts OR any simple weapon
            # Priest's pack OR explorer's pack
        ],
    },
    "Druid": {
        "coins_cp": 200,  # 2d4 × 10 gp
        "items": [
            ("Wooden Shield", 1000, "🛡️", "standard", "", 1, False, ""),
            ("Scimitar", 2500, "🗡️", "fine", "", 1, False, ""),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, False, ""),
            ("Explorer's Pack", 1000, "🎒", "standard", "", 1, False, ""),
            ("Druidic Focus (Staff)", 500, "🪄", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Wooden shield OR any simple weapon
            # Scimitar OR any simple melee weapon
        ],
    },
    "Fighter": {
        "coins_cp": 500,  # 5d4 × 10 gp
        "items": [
            ("Chain Mail", 7500, "🛡️", "standard", "", 1, False, ""),
            ("Longsword", 1500, "🗡️", "fine", "", 1, False, ""),
            ("Shield", 1000, "🛡️", "standard", "", 1, False, ""),
            ("Light Crossbow", 2500, "🏹", "standard", "", 1, False, ""),
            ("Crossbow Bolt", 1, "🏹", "trivial", "", 20, False, ""),
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Chain mail OR leather armor + longbow + 20 arrows
            # Martial weapon + shield OR two martial weapons
            # Light crossbow + 20 bolts OR two handaxes
            # Dungeoneer's pack OR explorer's pack
        ],
    },
    "Monk": {
        "coins_cp": 50,  # 5d4 gp (not ×10)
        "items": [
            ("Shortsword", 1000, "🗡️", "fine", "", 1, False, ""),
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, False, ""),
            ("Dart", 5, "🏹", "trivial", "", 10, False, ""),
        ],
        "choices": [
            # Shortsword OR any simple weapon
            # Dungeoneer's pack OR explorer's pack
        ],
    },
    "Paladin": {
        "coins_cp": 1500,  # 5d4 × 10 gp
        "items": [
            ("Longsword", 1500, "🗡️", "fine", "", 1, False, ""),
            ("Shield", 1000, "🛡️", "standard", "", 1, False, ""),
            ("Javelin", 50, "🏹", "standard", "", 5, False, ""),
            ("Priest's Pack", 1900, "🎒", "standard", "", 1, False, ""),
            ("Chain Mail", 7500, "🛡️", "standard", "", 1, False, ""),
            ("Holy Symbol (Amulet)", 500, "✝️", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Martial weapon + shield OR two martial weapons
            # Five javelins OR any simple melee weapon
            # Priest's pack OR explorer's pack
        ],
    },
    "Ranger": {
        "coins_cp": 1000,  # 5d4 × 10 gp
        "items": [
            ("Scale Mail", 5000, "🛡️", "standard", "", 1, False, ""),
            ("Shortsword", 1000, "🗡️", "fine", "", 2, False, ""),
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, False, ""),
            ("Longbow", 5000, "🏹", "fine", "", 1, False, ""),
            ("Arrow", 1, "🏹", "trivial", "", 20, False, ""),
        ],
        "choices": [
            # Scale mail OR leather armor
            # Two shortswords OR two simple melee weapons
            # Dungeoneer's pack OR explorer's pack
        ],
    },
    "Rogue": {
        "coins_cp": 400,  # 4d4 × 10 gp
        "items": [
            ("Rapier", 2500, "🗡️", "fine", "", 1, False, ""),
            ("Shortbow", 2500, "🏹", "fine", "", 1, False, ""),
            ("Arrow", 1, "🏹", "trivial", "", 20, False, ""),
            ("Burglar's Pack", 1600, "🎒", "standard", "", 1, False, ""),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, False, ""),
            ("Dagger", 200, "🗡️", "standard", "", 2, False, ""),
            ("Thieves' Tools", 2500, "🔧", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Rapier OR shortsword
            # Shortbow + 20 arrows OR shortsword
            # Burglar's pack OR dungeoneer's pack OR explorer's pack
        ],
    },
    "Sorcerer": {
        "coins_cp": 300,  # 3d4 × 10 gp
        "items": [
            ("Light Crossbow", 2500, "🏹", "standard", "", 1, False, ""),
            ("Crossbow Bolt", 1, "🏹", "trivial", "", 20, False, ""),
            ("Component Pouch", 2500, "💼", "standard", "", 1, False, ""),
            ("Dungeoneer's Pack", 1200, "🎒", "standard", "", 1, False, ""),
            ("Dagger", 200, "🗡️", "standard", "", 2, False, ""),
        ],
        "choices": [
            # Light crossbow + 20 bolts OR any simple weapon
            # Component pouch OR arcane focus
            # Dungeoneer's pack OR explorer's pack
        ],
    },
    "Warlock": {
        "coins_cp": 1000,  # 4d4 × 10 gp
        "items": [
            ("Light Crossbow", 2500, "🏹", "standard", "", 1, False, ""),
            ("Crossbow Bolt", 1, "🏹", "trivial", "", 20, False, ""),
            ("Component Pouch", 2500, "💼", "standard", "", 1, False, ""),
            ("Scholar's Pack", 4000, "🎒", "standard", "", 1, False, ""),
            ("Leather Armor", 1000, "🧥", "standard", "", 1, False, ""),
            ("Dagger", 200, "🗡️", "standard", "", 2, False, ""),
        ],
        "choices": [
            # Light crossbow + 20 bolts OR any simple weapon
            # Component pouch OR arcane focus
            # Scholar's pack OR dungeoneer's pack
        ],
    },
    "Wizard": {
        "coins_cp": 200,  # 4d4 × 10 gp
        "items": [
            ("Quarterstaff", 200, "🪄", "standard", "", 1, False, ""),
            ("Component Pouch", 2500, "💼", "standard", "", 1, False, ""),
            ("Scholar's Pack", 4000, "🎒", "standard", "", 1, False, ""),
            ("Spellbook", 5000, "📖", "standard", "", 1, False, ""),
        ],
        "choices": [
            # Quarterstaff OR dagger
            # Component pouch OR arcane focus
            # Scholar's pack OR explorer's pack
        ],
    },
}

# 2024 D&D Background starting equipment (PHB 2024)
BACKGROUND_EQUIPMENT = {
    "Acolyte": {
        "coins_cp": 1500,  # 15 gp
        "items": [
            ("Holy Symbol (Amulet)", 500, "✝️", "standard", "", 1, False, ""),
            ("Prayer Book", 500, "📖", "standard", "", 1, False, ""),
            ("Incense (5 sticks)", 10, "🕯️", "trivial", "", 5, False, ""),
            ("Vestments", 500, "👘", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Artisan": {
        "coins_cp": 2000,  # 20 gp
        "items": [
            ("Artisan's Tools", 2000, "🔨", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Charlatan": {
        "coins_cp": 1500,  # 15 gp
        "items": [
            ("Fine Clothes", 1500, "👔", "standard", "", 1, False, ""),
            ("Disguise Kit", 2500, "🎭", "standard", "", 1, False, ""),
            ("Forgery Kit", 1500, "📝", "standard", "", 1, False, ""),
        ],
    },
    "Criminal": {
        "coins_cp": 1500,  # 15 gp
        "items": [
            ("Crowbar", 200, "🔨", "standard", "", 1, False, ""),
            ("Dark Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Entertainer": {
        "coins_cp": 1500,  # 15 gp
        "items": [
            ("Musical Instrument (Lute)", 3500, "🎵", "standard", "", 1, False, ""),
            ("Costume", 500, "🎭", "standard", "", 1, False, ""),
            ("Mirror", 500, "🪞", "standard", "", 1, False, ""),
        ],
    },
    "Farmer": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Carpenter's Tools", 1000, "🔨", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Guard": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Uniform", 500, "👕", "standard", "", 1, False, ""),
            ("Horn", 300, "📯", "standard", "", 1, False, ""),
            ("Manacles", 200, "⛓️", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Guide": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Navigator's Tools", 2500, "🧭", "standard", "", 1, False, ""),
            ("Walking Stick", 10, "🦯", "trivial", "", 1, False, ""),
            ("Traveler's Clothes", 200, "👕", "standard", "", 1, False, ""),
        ],
    },
    "Hermit": {
        "coins_cp": 500,  # 5 gp
        "items": [
            ("Herbalism Kit", 500, "🌿", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Merchant": {
        "coins_cp": 1500,  # 15 gp
        "items": [
            ("Merchant's Scale", 500, "⚖️", "standard", "", 1, False, ""),
            ("Fine Clothes", 1500, "👔", "standard", "", 1, False, ""),
        ],
    },
    "Noble": {
        "coins_cp": 2500,  # 25 gp
        "items": [
            ("Fine Clothes", 1500, "👔", "standard", "", 1, False, ""),
            ("Signet Ring", 500, "💍", "standard", "", 1, False, ""),
            ("Scroll of Pedigree", 100, "📜", "trivial", "", 1, False, ""),
        ],
    },
    "Sage": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Ink Pen", 20, "🖋️", "trivial", "", 1, False, ""),
            ("Ink (1 oz)", 100, "🖋️", "trivial", "", 1, False, ""),
            ("Parchment (10 sheets)", 100, "📜", "trivial", "", 10, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Sailor": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Navigator's Tools", 2500, "🧭", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Scribe": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Calligrapher's Supplies", 1000, "🖋️", "standard", "", 1, False, ""),
            ("Fine Clothes", 1500, "👔", "standard", "", 1, False, ""),
        ],
    },
    "Soldier": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Insignia of Rank", 100, "🎖️", "trivial", "", 1, False, ""),
            ("Gaming Set (Dice)", 100, "🎲", "trivial", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
    "Wayfarer": {
        "coins_cp": 1000,  # 10 gp
        "items": [
            ("Thieves' Tools", 2500, "🔧", "standard", "", 1, False, ""),
            ("Common Clothes", 50, "👕", "trivial", "", 1, False, ""),
        ],
    },
}

# DMG 2024 Starting Equipment at Higher Levels - additional coins per level tier
# These are ADDITIONAL coins on top of class + background equipment
# Based on DMG 2024 table:
# Levels 2-4: no extra coins (normal starting equipment only)
# Levels 5-10: 500 gp + 1d10x25 gp (average 637.5 gp = 63,750 cp)
# Levels 11-16: 5,000 gp + 1d10x250 gp (average 6,375 gp = 637,500 cp)
# Levels 17-20: 20,000 gp + 1d10x250 gp (average 21,375 gp = 2,137,500 cp)
LEVEL_COINS_CP = {
    # Level: additional coins in cp
    2: 0,
    3: 0,
    4: 0,
    5: 63750,   # 637.5 gp avg
    6: 63750,
    7: 63750,
    8: 63750,
    9: 63750,
    10: 63750,
    11: 637500,  # 6,375 gp avg
    12: 637500,
    13: 637500,
    14: 637500,
    15: 637500,
    16: 637500,
    17: 2137500, # 21,375 gp avg
    18: 2137500,
    19: 2137500,
    20: 2137500,
}


class Command(BaseCommand):
    help = (
        "Create the '2024 D&D Default' starting equipment template "
        "with all classes, backgrounds, and level coins."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--club",
            type=str,
            help="Club slug to create the template in (default: first club or 'demo')",
        )
        parser.add_argument(
            "--name",
            type=str,
            default="2024 D&D Default",
            help="Name for the template (default: '2024 D&D Default')",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update existing template entries instead of skipping",
        )

    def handle(self, *args, **options):
        club_slug = options["club"]
        template_name = options["name"]
        force = options["force"]

        # Get or create club
        if club_slug:
            try:
                club = Club.objects.get(slug=club_slug)
            except Club.DoesNotExist as err:
                raise CommandError(f"Club with slug '{club_slug}' does not exist.") from err
        else:
            club = Club.objects.first()
            if not club:
                raise CommandError("No clubs exist. Create a club first or specify --club.")
            self.stdout.write(f"Using club: {club.name} ({club.slug})")

        with transaction.atomic():
            # Create or get template
            template, created = StartingEquipmentTemplate.objects.get_or_create(
                club=club,
                name=template_name,
                defaults={
                    "description": (
                        "Default starting equipment per 2024 D&D Player's Handbook "
                        "and Dungeon Master's Guide."
                    ),
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(f"Created template: {template_name}")
            else:
                self.stdout.write(f"Template exists: {template_name}")
                if not force:
                    self.stdout.write(
                        self.style.WARNING(
                            "Template already exists. Use --force to update entries."
                        )
                    )
                    return

            # Create all items needed
            self._create_items(club)

            # Create class entries
            self._create_class_entries(template, force)

            # Create background entries
            self._create_background_entries(template, force)

            # Create level coins
            self._create_level_coins(template, force)

            self.stdout.write(self.style.SUCCESS(f"Successfully seeded '{template_name}' template"))

    def _create_items(self, club):
        """Create all items needed for class and background equipment."""
        item_specs = {}

        # Collect all unique items from class equipment
        for class_data in CLASS_EQUIPMENT.values():
            for item_data in class_data["items"]:
                name, value_cp, symbol, rarity, magic_type, qty, is_choice, choice_group = item_data
                if name not in item_specs:
                    item_specs[name] = {
                        "value_cp": value_cp,
                        "symbol": symbol,
                        "rarity": rarity,
                        "magic_type": magic_type,
                    }

        # Collect all unique items from background equipment
        for bg_data in BACKGROUND_EQUIPMENT.values():
            for item_data in bg_data["items"]:
                name, value_cp, symbol, rarity, magic_type, qty, is_choice, choice_group = item_data
                if name not in item_specs:
                    item_specs[name] = {
                        "value_cp": value_cp,
                        "symbol": symbol,
                        "rarity": rarity,
                        "magic_type": magic_type,
                    }

        # Create items
        created_count = 0
        for name, specs in item_specs.items():
            try:
                item, created = Item.objects.get_or_create(
                    club=club,
                    name=name,
                    defaults=specs,
                )
            except MultipleObjectsReturned:
                raise CommandError(
                    f"Multiple items named '{name}' exist for club {club}. "
                    "Please resolve duplicates in the admin before seeding."
                ) from None
            if created:
                created_count += 1

        if created_count:
            self.stdout.write(f"Created {created_count} new items")

    def _get_item(self, club, name):
        """Get item by name, raise if not found."""
        try:
            return Item.objects.for_club(club).get(name=name)
        except Item.DoesNotExist as err:
            raise CommandError(
                f"Item '{name}' not found for club {club}. "
                "Run without --force first to create items."
            ) from err
        except MultipleObjectsReturned:
            raise CommandError(
                f"Multiple items named '{name}' exist for club {club}. "
                "Please resolve duplicates in the admin before seeding."
            ) from None

    def _create_class_entries(self, template, force):
        """Create StartingEquipmentClassEntry for each class."""
        club = template.club
        created_count = 0
        updated_count = 0

        for class_name, class_data in CLASS_EQUIPMENT.items():
            entry, created = StartingEquipmentClassEntry.objects.get_or_create(
                template=template,
                char_class=class_name,
                defaults={
                    "min_level": 1,
                    "max_level": 20,
                    "coins_cp": class_data["coins_cp"],
                },
            )
            if created:
                created_count += 1
            elif force:
                entry.coins_cp = class_data["coins_cp"]
                entry.save(update_fields=["coins_cp"])
                updated_count += 1

            # Create lines for this class entry
            for item_data in class_data["items"]:
                name, value_cp, symbol, rarity, magic_type, qty, is_choice, choice_group = item_data
                item = self._get_item(club, name)
                line, line_created = StartingEquipmentClassLine.objects.get_or_create(
                    class_entry=entry,
                    item=item,
                    defaults={
                        "quantity": qty,
                        "is_choice": is_choice,
                        "choice_group": choice_group,
                    },
                )
                if line_created:
                    pass  # count handled below
                elif force:
                    line.quantity = qty
                    line.is_choice = is_choice
                    line.choice_group = choice_group
                    line.save(update_fields=["quantity", "is_choice", "choice_group"])

        self.stdout.write(
            f"Class entries: {created_count} created, {updated_count} updated"
        )

    def _create_background_entries(self, template, force):
        """Create StartingEquipmentBackgroundEntry for each background."""
        club = template.club
        created_count = 0
        updated_count = 0

        for bg_name, bg_data in BACKGROUND_EQUIPMENT.items():
            entry, created = StartingEquipmentBackgroundEntry.objects.get_or_create(
                template=template,
                background=bg_name,
                defaults={"coins_cp": bg_data["coins_cp"]},
            )
            if created:
                created_count += 1
            elif force:
                entry.coins_cp = bg_data["coins_cp"]
                entry.save(update_fields=["coins_cp"])
                updated_count += 1

            # Create lines for this background entry
            for item_data in bg_data["items"]:
                name, value_cp, symbol, rarity, magic_type, qty, is_choice, choice_group = item_data
                item = self._get_item(club, name)
                line, line_created = StartingEquipmentBackgroundLine.objects.get_or_create(
                    background_entry=entry,
                    item=item,
                    defaults={
                        "quantity": qty,
                        "is_choice": is_choice,
                        "choice_group": choice_group,
                    },
                )
                if line_created:
                    pass
                elif force:
                    line.quantity = qty
                    line.is_choice = is_choice
                    line.choice_group = choice_group
                    line.save(update_fields=["quantity", "is_choice", "choice_group"])

        self.stdout.write(
            f"Background entries: {created_count} created, {updated_count} updated"
        )

    def _create_level_coins(self, template, force):
        """Create StartingEquipmentLevelCoins for levels 2-20."""
        created_count = 0
        updated_count = 0

        for level, coins_cp in LEVEL_COINS_CP.items():
            lc, created = StartingEquipmentLevelCoins.objects.get_or_create(
                template=template,
                level=level,
                defaults={"coins_cp": coins_cp},
            )
            if created:
                created_count += 1
            elif force:
                lc.coins_cp = coins_cp
                lc.save(update_fields=["coins_cp"])
                updated_count += 1

        self.stdout.write(
            f"Level coins: {created_count} created, {updated_count} updated"
        )