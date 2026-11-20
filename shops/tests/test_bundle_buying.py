"""Buying tests for shop bundle lines (U125, U126, U127)."""

import pytest
from django.urls import reverse

from items.tests.factories import make_arrows, make_rope
from ledger.models import LedgerEntry
from ledger.services import InsufficientFunds, Line, item_quantities, record
from shops.buying import buy as buy_service
from shops.models import ShopStock
from shops.services import AlreadySold, ShopClosed

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def funded_other(other_character):
    record(other_character, "award", [Line(coins=1000)])
    return other_character


def url(club, shop, stock):
    return reverse("shops:buy", args=[club.slug, shop.pk, stock.pk])


def purchases(character):
    return LedgerEntry.objects.filter(kind="purchase", character=character)


@pytest.fixture
def arrows(club):
    return make_arrows(club)


@pytest.fixture
def rope(club):
    return make_rope(club)


@pytest.fixture
def rich_character(character):
    record(character, "award", [Line(coins=10000)])  # 100 gp
    return character


@pytest.mark.story("U126")
def test_buy_two_bundle_sizes_lands_in_one_inventory_row(
    shop, always_open, arrows, rich_character, player
):
    """Buying two bundle sizes of one item gives one inventory row with summed units."""
    # Arrows: 100 cp per 20 arrows. Bundle of 5 = 25 cp, bundle of 100 = 500 cp
    stock5 = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=5, quantity=10, sell_percent=100
    )
    stock100 = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=100, quantity=2, sell_percent=100
    )

    # Buy 1 bundle of 5 (5 arrows)
    buy_service(rich_character, stock5, quantity=1, actor=player)
    # Buy 1 bundle of 100 (100 arrows)
    buy_service(rich_character, stock100, quantity=1, actor=player)

    # Inventory shows one entry with 105 arrows
    quantities = item_quantities(rich_character)
    assert quantities[arrows.pk] == 105
    # Only one ledger item line per purchase, but both point to same item
    entries = purchases(rich_character)
    assert entries.count() == 2
    item_lines = [
        line for entry in entries for line in entry.lines.all() if line.item_id == arrows.pk
    ]
    assert len(item_lines) == 2
    total_units = sum(line.quantity for line in item_lines)
    assert total_units == 105


@pytest.mark.story("U126")
def test_buy_quantity_is_bundles(shop, always_open, arrows, rich_character, player):
    """Quantity in buy flow means number of bundles."""
    # Bundle of 10 arrows (100 cp per 20 -> bundle of 10 = 50 cp)
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=10, quantity=5, sell_percent=100
    )

    # Buy 3 bundles = 30 arrows
    entry = buy_service(rich_character, stock, quantity=3, actor=player)

    # Ledger shows 30 units
    item_line = entry.lines.get(item=arrows)
    assert item_line.quantity == 30
    # Coins: 3 * 50 = 150
    coin_line = entry.lines.get(coins__lt=0)
    assert coin_line.coins == -150


@pytest.mark.story("U127")
def test_ledger_note_names_units(shop, always_open, arrows, rich_character, player):
    """Ledger note says units ('Bought 100 arrow Arrows from Lantern')."""
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=100, quantity=2, sell_percent=100
    )
    entry = buy_service(rich_character, stock, quantity=1, actor=player)
    assert "Bought 100 arrow Arrows from" in entry.note


@pytest.mark.story("U127")
def test_non_stacked_note_unchanged(shop, always_open, rich_character, player):
    """Non-stacked ledger note identical to before ('Bought 2 × Torch from Lantern')."""
    from items.models import Item

    torch = Item.objects.create(club=shop.club, name="Torch", value_cp=10)
    stock = ShopStock.objects.create(shop=shop, item=torch, quantity=5)
    entry = buy_service(rich_character, stock, quantity=2, actor=player)
    assert entry.note == "Bought 2 × Torch from Lantern"


@pytest.mark.story("U125")
def test_stock_decrements_by_bundles(shop, always_open, arrows, rich_character, player):
    """Stock decrements by bundles, not units."""
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=10, quantity=5, sell_percent=100
    )
    buy_service(rich_character, stock, quantity=2, actor=player)
    stock.refresh_from_db()
    assert stock.quantity == 3  # 5 - 2 bundles


@pytest.mark.story("U125")
def test_unlimited_line(shop, always_open, arrows, rich_character, player):
    """Unlimited stock line works."""
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=5, quantity=None, sell_percent=100
    )
    entry = buy_service(rich_character, stock, quantity=10, actor=player)
    stock.refresh_from_db()
    assert stock.quantity is None
    item_line = entry.lines.get(item=arrows)
    assert item_line.quantity == 50  # 10 bundles * 5 units


@pytest.mark.story("U126")
def test_insufficient_funds_rolls_back_stock(shop, always_open, arrows, character, player):
    """Insufficient funds rolls back stock decrement."""
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=5, quantity=10, sell_percent=100
    )
    # Character has 0 coins, bundle costs 25 cp
    with pytest.raises(InsufficientFunds):
        buy_service(character, stock, quantity=1, actor=player)
    stock.refresh_from_db()
    assert stock.quantity == 10  # Unchanged


@pytest.mark.story("U126")
def test_closed_shop_refused(shop, closed_shop, arrows, rich_character, player):
    """Closed shop refuses purchase."""
    stock = ShopStock.objects.create(
        shop=closed_shop, item=arrows, bundle_units=5, quantity=10, sell_percent=100
    )
    with pytest.raises(ShopClosed):
        buy_service(rich_character, stock, quantity=1, actor=player)


@pytest.mark.story("U126")
def test_other_club_character_refused(club, other_club, shop, other_shop):
    """Character from other club refused."""
    from datetime import date

    from accounts.models import Membership, User
    from items.tests.factories import make_arrows
    from player_characters.models import Character
    from shops.models import Rotation

    # Create a user who is a member of club (not other_club)
    outsider = User.objects.create_user("out@example.com", password="pw", display_name="Outsider")
    Membership.objects.create(user=outsider, club=club)
    owner = Membership.objects.get(user=outsider, club=club)
    other_char = Character.objects.create(club=club, owner=owner, name="Other")
    record(other_char, "award", [Line(coins=1000)])
    # Make other_shop open (it's in other_club)
    rotation = Rotation.objects.create(club=other_club, name="Always", open_date=date(2000, 1, 1))
    rotation.shops.add(other_shop)
    # Create arrows in other_club
    arrows = make_arrows(other_club)
    stock = ShopStock.objects.create(
        shop=other_shop, item=arrows, bundle_units=5, quantity=10, sell_percent=100
    )
    from shops.services import NotStocked

    with pytest.raises(NotStocked):
        buy_service(other_char, stock, quantity=1, actor=outsider)


# C3: Concurrent buy of last bundle
@pytest.mark.story("C3")
def test_last_bundle_two_sequential_buys_one_wins(
    shop, always_open, arrows, rich_character, funded_other, player, other_player, login
):
    """Last bundle: two sequential buys from stale objects, one wins."""
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=5, quantity=1, sell_percent=100
    )
    # First buyer succeeds
    buy_service(rich_character, stock, quantity=1, actor=player)
    # Second buyer gets AlreadySold
    with pytest.raises(AlreadySold):
        buy_service(funded_other, stock, quantity=1, actor=other_player)
    # Only one purchase recorded
    assert purchases(rich_character).count() == 1
    assert purchases(funded_other).count() == 0


@pytest.mark.story("C3")
def test_last_bundle_stale_object_fails(
    shop, always_open, arrows, rich_character, funded_other, player
):
    """Last bundle: stale object test (like test_buy.py:80)."""
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=5, quantity=1, sell_percent=100
    )
    stale = ShopStock.objects.get(pk=stock.pk)
    buy_service(rich_character, ShopStock.objects.get(pk=stock.pk), quantity=1, actor=player)
    with pytest.raises(AlreadySold):
        buy_service(funded_other, stale, quantity=1, actor=player)
    assert purchases(rich_character).count() == 1
    stock.refresh_from_db()
    assert stock.quantity == 0


# View tests
@pytest.mark.story("U127")
def test_browse_page_shows_bundle_label(shop, always_open, arrows, player, login):
    """Browse page shows 'bundle of 100 arrow' for each line and two lines are separate rows."""
    stock5 = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=5, quantity=10, sell_percent=100
    )
    stock100 = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=100, quantity=2, sell_percent=100
    )
    client = login(player)
    resp = client.get(reverse("shops:detail", args=[shop.club.slug, shop.pk]))
    assert resp.status_code == 200
    html = resp.content.decode()
    # Both lines appear as separate rows
    assert "bundle of 5 arrow" in html
    assert "bundle of 100 arrow" in html
    # Each has its own buy link
    assert f'href="/c/{shop.club.slug}/shops/{shop.pk}/buy/{stock5.pk}/"' in html
    assert f'href="/c/{shop.club.slug}/shops/{shop.pk}/buy/{stock100.pk}/"' in html


@pytest.mark.story("U127")
def test_buy_modal_shows_bundle_label(shop, always_open, arrows, rich_character, player, login):
    """Buy modal shows bundle label in title."""
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=100, quantity=2, sell_percent=100
    )
    client = login(player)
    resp = client.get(url(shop.club, shop, stock), HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    html = resp.content.decode()
    # Bundle label appears in the title (with_units in summary shows it)
    assert "100 arrow Arrows" in html


@pytest.mark.story("U127")
def test_buy_modal_shows_units_gained(shop, always_open, arrows, rich_character, player, login):
    """Buy modal shows units gained in summary."""
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=10, quantity=5, sell_percent=100
    )
    client = login(player)
    resp = client.get(url(shop.club, shop, stock) + "?quantity=3", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    html = resp.content.decode()
    # Units gained = 3 * 10 = 30
    assert "30 arrow" in html  # with_units filter output
    assert "Units gained" in html


@pytest.mark.story("U127")
def test_buy_modal_shows_price_per_bundle(shop, always_open, arrows, rich_character, player, login):
    """Buy modal shows price per bundle."""
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=10, quantity=5, sell_percent=100
    )
    client = login(player)
    resp = client.get(url(shop.club, shop, stock), HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Price per bundle" in html
    # Price is 50 cp = 5 sp, displayed as '5 sp' by coins filter
    assert "5 sp" in html


@pytest.mark.story("U127")
def test_post_buy_works(shop, always_open, arrows, rich_character, player, login):
    """POST buy works for bundle lines."""
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=10, quantity=5, sell_percent=100
    )
    client = login(player)
    resp = client.post(url(shop.club, shop, stock), {"quantity": "2"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert resp["HX-Redirect"] == reverse("shops:detail", args=[shop.club.slug, shop.pk])
    assert purchases(rich_character).count() == 1


@pytest.mark.story("U125")
def test_error_text_already_sold(shop, always_open, arrows, rich_character, player, login):
    """Error text 'Already sold' when sold out."""
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=5, quantity=0, sell_percent=100
    )
    client = login(player)
    resp = client.post(url(shop.club, shop, stock), {"quantity": "1"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "Already sold" in resp.content.decode()


# Rotations copy-stock keeps both lines
@pytest.mark.story("U125")
def test_rotation_copy_stock_keeps_both_lines(admin_client, club, shop, arrows):
    """Copy-stock preserves both bundle lines."""
    # Create a second shop in the same club
    from shops.models import Shop

    other_shop = Shop.objects.create(club=club, name="Elsewhere")
    ShopStock.objects.create(shop=shop, item=arrows, bundle_units=5, quantity=10, sell_percent=100)
    ShopStock.objects.create(shop=shop, item=arrows, bundle_units=100, quantity=2, sell_percent=100)

    from shops.forms.rotations import CopyStockForm

    form = CopyStockForm(
        data={
            "source_type": "shop",
            "source_shop": str(shop.pk),
            "target_shops": [str(other_shop.pk)],
        },
        club=club,
        rotation=None,
    )
    if not form.is_valid():
        print(f"Form errors: {form.errors}")
    assert form.is_valid()

    from shops.views.rotations import _copy_stock

    class FakeRotation:
        shops = type("obj", (object,), {"all": lambda self: Shop.objects.filter(pk=shop.pk)})()

    count = _copy_stock(form, FakeRotation())
    assert count == 2

    # Both lines copied
    copied5 = ShopStock.objects.get(shop=other_shop, item=arrows, bundle_units=5)
    copied100 = ShopStock.objects.get(shop=other_shop, item=arrows, bundle_units=100)
    assert copied5.quantity == 10
    assert copied100.quantity == 2


# Regression: existing shops tests still pass
@pytest.mark.story("U125")
def test_existing_non_stacked_buy_unchanged(shop, always_open, rich_character, player):
    """Non-stacked items buy exactly as before."""
    from items.models import Item

    torch = Item.objects.create(club=shop.club, name="Torch", value_cp=100)
    stock = ShopStock.objects.create(shop=shop, item=torch, quantity=5)
    entry = buy_service(rich_character, stock, quantity=2, actor=player)
    item_line = entry.lines.get(item=torch)
    assert item_line.quantity == 2
    assert entry.note == "Bought 2 × Torch from Lantern"
