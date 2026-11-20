"""Tests for stacked items in adjust, consume, and bulk award."""

import re

import pytest
from django.urls import reverse

from items.models import Item
from ledger.services import Line, available_items, record
from player_characters.models import Character


@pytest.fixture
def parchment(club):
    """Stacked item: 100 cp per 10 sheets."""
    return Item.objects.create(
        club=club,
        name="Parchment",
        is_stacked=True,
        unit_name="sheet",
        value_cp=100,
        value_units=10,
    )


@pytest.fixture
def rope(club):
    """Stacked item: 100 cp per 50 ft."""
    return Item.objects.create(
        club=club,
        name="Rope",
        is_stacked=True,
        unit_name="ft",
        value_cp=100,
        value_units=50,
    )


@pytest.fixture
def sword(club):
    """Normal item."""
    return Item.objects.create(club=club, name="Longsword", value_cp=1500)


@pytest.mark.django_db
class TestAdjustStacked:
    """Tests for the adjust view with stacked items."""

    def test_give_stacked_units_names_unit_in_note(self, login, game_master, character, parchment):
        c = login(game_master)
        url = reverse("characters:adjust", args=["club-a", character.pk])
        r = c.post(
            url,
            {
                "direction": "give",
                "kind": "award",
                "date": "2024-01-15",
                "note": "Quest reward",
                "items-0-item": parchment.pk,
                "items-0-quantity": "7",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
            },
            follow=True,
        )
        assert r.status_code == 200
        # Check ledger note contains unit name
        from ledger.models import LedgerEntry

        entry = LedgerEntry.objects.filter(character=character, kind="award").latest("date")
        assert "7 sheet Parchment" in entry.note

    def test_take_stacked_units_names_unit_in_note(self, login, game_master, character, parchment):
        # First give some
        record(character, "award", [Line(item=parchment, quantity=10)], note="Initial")
        c = login(game_master)
        url = reverse("characters:adjust", args=["club-a", character.pk])
        r = c.post(
            url,
            {
                "direction": "take",
                "kind": "adjustment",
                "date": "2024-01-15",
                "note": "Lost some",
                "items-0-item": parchment.pk,
                "items-0-quantity": "3",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
            },
            follow=True,
        )
        assert r.status_code == 200
        from ledger.models import LedgerEntry

        entry = LedgerEntry.objects.filter(character=character, kind="adjustment").latest("date")
        assert "-3 sheet Parchment" in entry.note
        # Balance should be 7
        assert available_items(character)[parchment.pk] == 7

    def test_take_more_than_owned_fails(self, login, game_master, character, parchment):
        # Character has 0
        c = login(game_master)
        url = reverse("characters:adjust", args=["club-a", character.pk])
        r = c.post(
            url,
            {
                "direction": "take",
                "kind": "adjustment",
                "date": "2024-01-15",
                "note": "Lost some",
                "items-0-item": parchment.pk,
                "items-0-quantity": "5",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
            },
            follow=True,
        )
        # Should fail with form error
        assert r.status_code == 200
        assert "has 0 x Parchment available but needs 5" in r.content.decode()
        # No ledger entry should be created
        from ledger.models import LedgerEntry

        assert LedgerEntry.objects.filter(character=character, kind="adjustment").count() == 0

    def test_normal_item_note_unchanged(self, login, game_master, character, sword):
        c = login(game_master)
        url = reverse("characters:adjust", args=["club-a", character.pk])
        r = c.post(
            url,
            {
                "direction": "give",
                "kind": "award",
                "date": "2024-01-15",
                "note": "Found sword",
                "items-0-item": sword.pk,
                "items-0-quantity": "1",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
            },
            follow=True,
        )
        assert r.status_code == 200
        from ledger.models import LedgerEntry

        entry = LedgerEntry.objects.filter(character=character, kind="award").latest("date")
        # Normal item note should not have unit summary
        assert entry.note == "Found sword"

    def test_permissions_player_forbidden(self, login, player, character, parchment):
        c = login(player)
        url = reverse("characters:adjust", args=["club-a", character.pk])
        r = c.post(
            url,
            {
                "direction": "give",
                "kind": "award",
                "date": "2024-01-15",
                "note": "Test",
                "items-0-item": parchment.pk,
                "items-0-quantity": "1",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
            },
        )
        assert r.status_code in (302, 403)

    def test_permissions_other_club_404(self, login, other_club, character, parchment):
        # Create a GM in other club
        from accounts.models import Membership, User

        other_user = User.objects.create_user(
            "other@example.com", password="pw", display_name="Other"
        )
        Membership.objects.create(user=other_user, club=other_club, is_game_master=True)
        c = login(other_user)
        url = reverse("characters:adjust", args=["club-b", character.pk])
        r = c.post(
            url,
            {
                "direction": "give",
                "kind": "award",
                "date": "2024-01-15",
                "note": "Test",
                "items-0-item": parchment.pk,
                "items-0-quantity": "1",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
            },
        )
        assert r.status_code == 404


@pytest.mark.django_db
class TestConsumeStacked:
    """Tests for the consume view with stacked items."""

    def test_consume_stacked_units_names_unit_in_note(
        self, login, game_master, character, parchment
    ):
        record(character, "award", [Line(item=parchment, quantity=10)], note="Initial")
        c = login(game_master)
        url = reverse("characters:consume", args=["club-a", character.pk])
        r = c.post(
            url,
            {
                "date": "2024-01-15",
                "note": "Used for spell",
                "items-0-item": parchment.pk,
                "items-0-quantity": "3",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
            },
            follow=True,
        )
        assert r.status_code == 200
        from ledger.models import LedgerEntry

        entry = LedgerEntry.objects.filter(character=character, kind="consumed").latest("date")
        assert "-3 sheet Parchment" in entry.note

    def test_consume_to_zero_removes_item(self, login, game_master, character, parchment):
        record(character, "award", [Line(item=parchment, quantity=5)], note="Initial")
        c = login(game_master)
        url = reverse("characters:consume", args=["club-a", character.pk])
        r = c.post(
            url,
            {
                "date": "2024-01-15",
                "note": "Used all",
                "items-0-item": parchment.pk,
                "items-0-quantity": "5",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
            },
            follow=True,
        )
        assert r.status_code == 200
        assert available_items(character).get(parchment.pk, 0) == 0


@pytest.mark.django_db
class TestBulkAwardStacked:
    """Tests for bulk award with stacked items."""

    def test_bulk_award_different_unit_counts(self, login, game_master, club, parchment, rope):
        from accounts.models import Membership

        owner = Membership.objects.get(user=game_master, club=club)
        char1 = Character.objects.create(club=club, owner=owner, name="Char1")
        char2 = Character.objects.create(club=club, owner=owner, name="Char2")
        c = login(game_master)
        url = reverse("characters:bulk_award", args=["club-a"])
        r = c.post(
            url,
            {
                "date": "2024-01-15",
                "note": "Party loot",
                "characters": [char1.pk, char2.pk],
                f"coins_{char1.pk}": "0",
                f"coins_{char2.pk}": "0",
                f"items_{char1.pk}-TOTAL_FORMS": "1",
                f"items_{char1.pk}-INITIAL_FORMS": "0",
                f"items_{char1.pk}-0-item_id": parchment.pk,
                f"items_{char1.pk}-0-quantity": "10",
                f"items_{char2.pk}-TOTAL_FORMS": "1",
                f"items_{char2.pk}-INITIAL_FORMS": "0",
                f"items_{char2.pk}-0-item_id": rope.pk,
                f"items_{char2.pk}-0-quantity": "20",
            },
            follow=True,
        )
        assert r.status_code == 200
        from ledger.models import LedgerEntry

        entries = LedgerEntry.objects.filter(kind="award").order_by("date")
        assert entries.count() == 2
        # Check notes contain unit names
        assert "10 sheet Parchment" in entries[0].note
        assert "20 ft Rope" in entries[1].note

    def test_non_integer_quantity_rejected(self, login, game_master, character, parchment):
        c = login(game_master)
        url = reverse("characters:adjust", args=["club-a", character.pk])
        r = c.post(
            url,
            {
                "direction": "give",
                "kind": "award",
                "date": "2024-01-15",
                "note": "Test",
                "items-0-item": parchment.pk,
                "items-0-quantity": "1.5",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
            },
            follow=True,
        )
        assert r.status_code == 200
        # Should show form error
        assert "quantity" in r.content.decode().lower() or "invalid" in r.content.decode().lower()

    def test_zero_quantity_rejected(self, login, game_master, character, parchment):
        c = login(game_master)
        url = reverse("characters:adjust", args=["club-a", character.pk])
        r = c.post(
            url,
            {
                "direction": "give",
                "kind": "award",
                "date": "2024-01-15",
                "note": "Test",
                "items-0-item": parchment.pk,
                "items-0-quantity": "0",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
            },
            follow=True,
        )
        assert r.status_code == 200
        # Should show form error (min_value=1)
        assert "quantity" in r.content.decode().lower()

    def test_negative_quantity_rejected(self, login, game_master, character, parchment):
        c = login(game_master)
        url = reverse("characters:adjust", args=["club-a", character.pk])
        r = c.post(
            url,
            {
                "direction": "give",
                "kind": "award",
                "date": "2024-01-15",
                "note": "Test",
                "items-0-item": parchment.pk,
                "items-0-quantity": "-5",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
            },
            follow=True,
        )
        assert r.status_code == 200
        # Should show form error (min_value=1)
        assert "quantity" in r.content.decode().lower()


@pytest.mark.django_db
class TestAdjustPermissions:
    """Permission tests for adjust, bulk_award, consume."""

    def test_player_cannot_adjust(self, login, player, character, parchment):
        c = login(player)
        url = reverse("characters:adjust", args=["club-a", character.pk])
        r = c.get(url)
        assert r.status_code in (302, 403)

    def test_player_cannot_bulk_award(self, login, player):
        c = login(player)
        url = reverse("characters:bulk_award", args=["club-a"])
        r = c.get(url)
        assert r.status_code in (302, 403)

    def test_player_cannot_consume(self, login, player, character, parchment):
        c = login(player)
        url = reverse("characters:consume", args=["club-a", character.pk])
        r = c.get(url)
        assert r.status_code in (302, 403)

    def test_other_club_gm_404(self, login, other_club, game_master, character, parchment):
        from accounts.models import Membership, User

        other_user = User.objects.create_user(
            "other@example.com", password="pw", display_name="Other"
        )
        Membership.objects.create(user=other_user, club=other_club, is_game_master=True)
        c = login(other_user)
        url = reverse("characters:adjust", args=["club-b", character.pk])
        r = c.get(url)
        assert r.status_code == 404

    def test_club_admin_ok(self, login, club_admin, character, parchment):
        c = login(club_admin)
        url = reverse("characters:adjust", args=["club-a", character.pk])
        r = c.get(url)
        assert r.status_code == 200


@pytest.mark.django_db
def test_bulk_award_datalist_shows_unit_price_once(login, game_master, parchment, sword):
    r = login(game_master).get(reverse("characters:bulk_award", args=["club-a"]))
    body = r.content.decode()
    assert re.search(r"Parchment \((<[^>]+>)?[^<]+(</span>)? per 10 sheet\)", body)
    assert body.count("per 10 sheet") == 1
    assert "per 1 " not in body
