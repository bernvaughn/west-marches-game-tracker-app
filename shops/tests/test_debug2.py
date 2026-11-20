import pytest
from django.template import Context, Template

@pytest.mark.django_db
def test_debug_loot_preview_in_template(club, game_master, rich_character, shop, always_open):
    from items.tests.factories import make_container, add_slot, _get_or_create_item
    from shops.models import ShopStock
    
    container = make_container(club, 'Test Container Debug2')
    item = _get_or_create_item(club, 'Test Item Debug2')
    add_slot(container, [(item, 1, 1, 1)], chance_pct=100, unknown=False)
    
    stock = ShopStock.objects.create(shop=shop, item=container, quantity=5)
    
    print(f'Stock item: {stock.item}')
    print(f'Stock item is_container: {stock.item.is_container}')
    print(f'Stock item pk: {stock.item.pk}')
    print(f'Slots: {list(stock.item.slots.all())}')
    for slot in stock.item.slots.all():
        print(f'  Slot: {slot}')
        print(f'  Options: {list(slot.options.all())}')
    
    # Render the actual template used by the view
    template = Template('''
{% load coins loot_tags %}
{% if not in_modal %}<h2 class="h5">{% include "items/_item_name.html" with item=stock.item %}</h2>{% endif %}
{% if stock.item.description %}<p>{{ stock.item.description }}</p>{% endif %}
{% loot_preview stock.item as loot_rows %}
LOOT_ROWS_LENGTH={{ loot_rows|length }}
{% if loot_rows %}{% include "components/loot_rows.html" with rows=loot_rows %}{% endif %}
''')
    
    # Create a mock request object
    class MockRequest:
        def __init__(self, user, club):
            self.user = user
            self.club = club
            self.headers = {"HX-Request": "true"}
    
    context = Context({
        'request': MockRequest(game_master, club),
        'stock': stock,
        'in_modal': True,
        'shop': shop,
        'price': 100,
        'base_value': 100,
        'sell_percent': 100,
        'vs_base_text': 'vs base: 0 gp',
        'character': rich_character,
    })
    
    result = template.render(context)
    print(f'Template result: {result}')
    
    assert 'LOOT_ROWS_LENGTH=1' in result
    assert 'Test Item Debug2' in result