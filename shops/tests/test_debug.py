import pytest
from django.template import Context, Template

@pytest.mark.django_db
def test_debug_loot_preview(club, game_master, rich_character):
    from items.tests.factories import make_container, add_slot, _get_or_create_item
    
    container = make_container(club, 'Test Container Debug')
    item = _get_or_create_item(club, 'Test Item Debug')
    add_slot(container, [(item, 1, 1, 1)], chance_pct=100, unknown=False)
    
    print(f'Container: {container}')
    print(f'Container is_container: {container.is_container}')
    print(f'Slots: {list(container.slots.all())}')
    for slot in container.slots.all():
        print(f'  Slot: {slot}')
        print(f'  Options: {list(slot.options.all())}')
    
    template = Template('{% load loot_tags %}{% loot_preview container as rows %}{{ rows|length }}')
    context = Context({'request': type('Request', (), {'user': game_master, 'club': club})(), 'container': container})
    result = template.render(context)
    print(f'Template result: {result}')
    
    assert result == "1"