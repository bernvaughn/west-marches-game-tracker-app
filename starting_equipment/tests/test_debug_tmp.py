import pytest
from starting_equipment.services import get_choice_groups

pytestmark = [pytest.mark.django_db]

def test_debug_groups(club, player, active_template, class_option_fighter, bg_option_acolyte):
    from accounts.models import Membership
    from character_options.models import Background
    from items.models import Item
    from starting_equipment.models import (
        StartingEquipmentClassEntry, StartingEquipmentClassLine,
        StartingEquipmentBackgroundEntry, StartingEquipmentBackgroundLine,
    )
    owner, _ = Membership.objects.get_or_create(user=player, club=club)
    longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
    battleaxe = Item.objects.create(club=club, name="Battleaxe", value_cp=1000)
    class_entry = StartingEquipmentClassEntry.objects.create(
        template=active_template, class_option=class_option_fighter, min_level=1, max_level=20, coins_cp=1000)
    StartingEquipmentClassLine.objects.create(class_entry=class_entry, item=longsword, quantity=1, is_choice=True, choice_group="weapon")
    StartingEquipmentClassLine.objects.create(class_entry=class_entry, item=battleaxe, quantity=1, is_choice=True, choice_group="weapon")
    holy_symbol = Item.objects.create(club=club, name="Holy Symbol", value_cp=500)
    prayer_book = Item.objects.create(club=club, name="Prayer Book", value_cp=500)
    bg_entry = StartingEquipmentBackgroundEntry.objects.create(template=active_template, background_option=bg_option_acolyte, coins_cp=500)
    StartingEquipmentBackgroundLine.objects.create(background_entry=bg_entry, item=holy_symbol, quantity=1, is_choice=True, choice_group="holy_item")
    StartingEquipmentBackgroundLine.objects.create(background_entry=bg_entry, item=prayer_book, quantity=1, is_choice=True, choice_group="holy_item")
    from player_characters.models import Character
    character = Character.objects.create(club=club, owner=owner, name="Test", char_class="Fighter", class_option=class_option_fighter, background="Acolyte", background_option=bg_option_acolyte, level=1)
    groups = get_choice_groups(character, active_template)
    print("NUM GROUPS", len(groups), [g.key for g in groups])
    for g in groups:
        print(g.key, [o.line_id for o in g.options])
    assert True
