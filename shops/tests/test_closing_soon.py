from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from shops.models import Rotation, Shop
from shops.services import (
    closing_soon_on,
    leave_dates,
    leaves_street_on,
)

pytestmark = [pytest.mark.django_db, pytest.mark.story("ClosingSoon")]


def street_url(club):
    return reverse("shops:index", args=[club.slug])


def detail_url(club, shop):
    return reverse("shops:detail", args=[club.slug, shop.pk])


def make_rotation(club, shop, open_date, close_date=None, name="R"):
    r = Rotation.objects.create(club=club, name=name, open_date=open_date, close_date=close_date)
    r.shops.add(shop)
    return r


def open_shop(club, name, open_date, close_date=None, **kw):
    shop = Shop.objects.create(club=club, name=name, **kw)
    make_rotation(club, shop, open_date, close_date)
    return shop


# --- Unit tests for service functions ---


def test_leaves_street_on_no_rotation(club):
    shop = Shop.objects.create(club=club, name="Empty")
    today = timezone.localdate()
    assert leaves_street_on(shop, today) is None


def test_leaves_street_on_single_dated_rotation(club):
    today = timezone.localdate()
    shop = open_shop(club, "Dated", today, today + timedelta(days=10))
    assert leaves_street_on(shop, today) == today + timedelta(days=10)


def test_leaves_street_on_undated_rotation(club):
    today = timezone.localdate()
    shop = open_shop(club, "Undated", today, close_date=None)
    assert leaves_street_on(shop, today) is None


def test_leaves_street_on_two_dated_rotations_uses_latest(club):
    today = timezone.localdate()
    shop = Shop.objects.create(club=club, name="TwoDated")
    make_rotation(club, shop, today, today + timedelta(days=2), "R1")
    make_rotation(club, shop, today, today + timedelta(days=20), "R2")
    assert leaves_street_on(shop, today) == today + timedelta(days=20)


def test_leaves_street_on_mixed_rotations_none(club):
    today = timezone.localdate()
    shop = Shop.objects.create(club=club, name="Mixed")
    make_rotation(club, shop, today, today + timedelta(days=2), "Dated")
    make_rotation(club, shop, today, None, "Undated")
    assert leaves_street_on(shop, today) is None


def test_leave_dates_batch_query_count(club, django_assert_num_queries):
    """leave_dates should use ONE query regardless of number of shops."""
    today = timezone.localdate()
    shops = [open_shop(club, f"Shop{i}", today, today + timedelta(days=i + 1)) for i in range(5)]
    with django_assert_num_queries(1):
        result = leave_dates(shops, today)
    assert len(result) == 5
    for shop in shops:
        assert result[shop.pk] == today + timedelta(days=shops.index(shop) + 1)


def test_closing_soon_on_window():
    today = date(2030, 1, 15)
    assert closing_soon_on(today, today) == today  # today
    assert closing_soon_on(today + timedelta(days=1), today) == today + timedelta(days=1)
    assert closing_soon_on(today + timedelta(days=3), today) == today + timedelta(days=3)
    assert closing_soon_on(today + timedelta(days=4), today) is None  # 4 days = outside
    assert closing_soon_on(today + timedelta(days=10), today) is None
    assert closing_soon_on(today - timedelta(days=1), today) is None  # past
    assert closing_soon_on(None, today) is None


# --- Street page tests ---


def test_ribbon_shows_when_closes_in_2_days(login, player, club):
    today = timezone.localdate()
    shop = open_shop(club, "ClosingSoon", today, today + timedelta(days=2))
    body = login(player).get(street_url(club)).content.decode()
    assert "wm-closing-ribbon" in body
    assert "Closing soon" in body
    assert shop.name in body


def test_ribbon_hidden_when_closes_in_10_days(login, player, club):
    today = timezone.localdate()
    shop = open_shop(club, "NotClosingSoon", today, today + timedelta(days=10))
    body = login(player).get(street_url(club)).content.decode()
    assert "wm-closing-ribbon" not in body
    assert shop.name in body


def test_ribbon_hidden_when_undated_rotation(login, player, club):
    today = timezone.localdate()
    shop = open_shop(club, "AlwaysOpen", today, close_date=None)
    body = login(player).get(street_url(club)).content.decode()
    assert "wm-closing-ribbon" not in body
    assert shop.name in body


def test_ribbon_uses_latest_close_date_two_rotations(login, player, club):
    today = timezone.localdate()
    shop = Shop.objects.create(club=club, name="TwoRotations")
    make_rotation(club, shop, today, today + timedelta(days=2), "Soon")
    make_rotation(club, shop, today, today + timedelta(days=20), "Later")
    body = login(player).get(street_url(club)).content.decode()
    # Latest is 20 days, so no ribbon
    assert "wm-closing-ribbon" not in body


def test_ribbon_shows_with_latest_of_1_and_3_days(login, player, club):
    today = timezone.localdate()
    shop = Shop.objects.create(club=club, name="TwoSoon")
    make_rotation(club, shop, today, today + timedelta(days=1), "VerySoon")
    make_rotation(club, shop, today, today + timedelta(days=3), "JustInTime")
    body = login(player).get(street_url(club)).content.decode()
    assert "wm-closing-ribbon" in body
    # Notice on detail page should show the 3-day date
    detail_body = login(player).get(detail_url(club, shop)).content.decode()
    assert "Leaves the street on" in detail_body
    assert (today + timedelta(days=3)).strftime("%-d %b %Y") in detail_body.replace("'", "'")


def test_closed_shop_not_on_street_no_ribbon(login, player, club):
    today = timezone.localdate()
    # Rotation closed yesterday
    shop = open_shop(club, "WasOpen", today - timedelta(days=10), today - timedelta(days=1))
    body = login(player).get(street_url(club)).content.decode()
    assert shop.name not in body
    assert "wm-closing-ribbon" not in body


def test_future_rotation_not_on_street_no_ribbon(login, player, club):
    today = timezone.localdate()
    shop = open_shop(club, "FutureShop", today + timedelta(days=5), today + timedelta(days=10))
    body = login(player).get(street_url(club)).content.decode()
    assert shop.name not in body
    assert "wm-closing-ribbon" not in body


def test_player_stall_no_ribbon_even_when_shop_has_one(login, player, club, item):
    today = timezone.localdate()
    # Club shop with ribbon
    open_shop(club, "ClubShop", today, today + timedelta(days=2))
    # Player stall
    from accounts.models import Membership
    from ledger.services import Line, record
    from player_characters.models import Character, JunkMark

    owner = Membership.objects.get(user=player, club=club)
    stall = Character.objects.create(club=club, owner=owner, name="StallOwner", shop_open=True)
    record(stall, "award", [Line(item=item, quantity=1)])
    JunkMark.objects.create(character=stall, item=item, quantity=1)

    body = login(player).get(street_url(club)).content.decode()
    # Count ribbons - should be exactly 1 (for the club shop)
    assert body.count("wm-closing-ribbon") == 1
    assert "ClubShop" in body
    assert "StallOwner's stall" in body


# --- Detail page tests ---


def test_detail_notice_shows_when_closes_in_2_days(login, player, club):
    today = timezone.localdate()
    shop = open_shop(club, "ClosingSoon", today, today + timedelta(days=2))
    body = login(player).get(detail_url(club, shop)).content.decode()
    assert "wm-shop-closing-soon" in body
    assert "Leaves the street on" in body
    assert (today + timedelta(days=2)).strftime("%-d %b %Y") in body.replace("'", "'")


def test_detail_notice_hidden_when_closes_in_10_days(login, player, club):
    today = timezone.localdate()
    shop = open_shop(club, "NotClosingSoon", today, today + timedelta(days=10))
    body = login(player).get(detail_url(club, shop)).content.decode()
    assert "wm-shop-closing-soon" not in body


def test_detail_notice_hidden_when_undated_rotation(login, player, club):
    today = timezone.localdate()
    shop = open_shop(club, "AlwaysOpen", today, close_date=None)
    body = login(player).get(detail_url(club, shop)).content.decode()
    assert "wm-shop-closing-soon" not in body


def test_detail_notice_uses_latest_close_date(login, player, club):
    today = timezone.localdate()
    shop = Shop.objects.create(club=club, name="TwoRotations")
    make_rotation(club, shop, today, today + timedelta(days=2), "Soon")
    make_rotation(club, shop, today, today + timedelta(days=20), "Later")
    body = login(player).get(detail_url(club, shop)).content.decode()
    assert "wm-shop-closing-soon" not in body


def test_detail_notice_shows_latest_of_1_and_3_days(login, player, club):
    today = timezone.localdate()
    shop = Shop.objects.create(club=club, name="TwoSoon")
    make_rotation(club, shop, today, today + timedelta(days=1), "VerySoon")
    make_rotation(club, shop, today, today + timedelta(days=3), "JustInTime")
    body = login(player).get(detail_url(club, shop)).content.decode()
    assert "wm-shop-closing-soon" in body
    assert (today + timedelta(days=3)).strftime("%-d %b %Y") in body.replace("'", "'")


def test_closed_shop_detail_no_notice_for_admin(login, club_admin, club):
    today = timezone.localdate()
    shop = open_shop(club, "WasOpen", today - timedelta(days=10), today - timedelta(days=1))
    body = login(club_admin).get(detail_url(club, shop)).content.decode()
    assert "wm-shop-closing-soon" not in body
    # Should show "Closed" badge
    assert "wm-shop-closed" in body


def test_past_rotation_plus_undated_no_ribbon(login, player, club):
    today = timezone.localdate()
    shop = Shop.objects.create(club=club, name="PastAndUndated")
    make_rotation(club, shop, today - timedelta(days=10), today - timedelta(days=1), "Past")
    make_rotation(club, shop, today, None, "Forever")
    body = login(player).get(street_url(club)).content.decode()
    assert "wm-closing-ribbon" not in body
    detail_body = login(player).get(detail_url(club, shop)).content.decode()
    assert "wm-shop-closing-soon" not in detail_body


# --- Boundary tests ---


@pytest.mark.parametrize("days_ahead", [0, 1, 2, 3])
def test_boundary_days_inclusive_show_ribbon(login, player, club, days_ahead):
    today = timezone.localdate()
    open_shop(club, f"Boundary{days_ahead}", today, today + timedelta(days=days_ahead))
    body = login(player).get(street_url(club)).content.decode()
    assert "wm-closing-ribbon" in body, f"Day {days_ahead} should show ribbon"


@pytest.mark.parametrize("days_ahead", [4, 5, 10])
def test_boundary_days_exclusive_hide_ribbon(login, player, club, days_ahead):
    today = timezone.localdate()
    open_shop(club, f"Boundary{days_ahead}", today, today + timedelta(days=days_ahead))
    body = login(player).get(street_url(club)).content.decode()
    assert "wm-closing-ribbon" not in body, f"Day {days_ahead} should not show ribbon"
