"""Tests for player_items models."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from accounts.models import Club, Membership, User
from ledger.models import AppendOnlyError
from player_characters.models import Character
from player_items.models import PlayerItem, PlayerItemChange, PlayerNotice, normalize_name_key


@pytest.mark.django_db
class TestNormalizeNameKey:
    def test_lowercases(self):
        assert normalize_name_key("Magic Sword") == "magic sword"

    def test_collapses_spaces(self):
        assert normalize_name_key("  Magic   Sword  ") == "magic sword"

    def test_handles_tabs_and_newlines(self):
        assert normalize_name_key("Magic\t\tSword\n") == "magic sword"

    def test_empty_string(self):
        assert normalize_name_key("") == ""

    def test_already_normalized(self):
        assert normalize_name_key("magic sword") == "magic sword"


@pytest.mark.django_db
class TestPlayerItem:
    def setup_method(self):
        self.club = Club.objects.create(name="Test Club", slug="test-club")
        self.user = User.objects.create_user("owner@example.com", password="pw")
        self.membership = Membership.objects.create(user=self.user, club=self.club)
        self.character = Character.objects.create(
            club=self.club, owner=self.membership, name="Hero"
        )

    def test_name_key_computed_on_save(self):
        item = PlayerItem.objects.create(
            club=self.club,
            character=self.character,
            name="  Magic   Sword  ",
            quantity=1,
        )
        assert item.name_key == "magic sword"

    def test_name_key_indexed(self):
        # name_key has db_index=True and is in a composite index; verify it exists
        indexes = [idx.fields for idx in PlayerItem._meta.indexes]
        assert any("name_key" in fields for fields in indexes)

    def test_quantity_min_1(self):
        with pytest.raises(ValidationError):
            PlayerItem.objects.create(
                club=self.club,
                character=self.character,
                name="Potion",
                quantity=0,
            ).full_clean()

    def test_name_max_80(self):
        item = PlayerItem.objects.create(
            club=self.club,
            character=self.character,
            name="a" * 80,
            quantity=1,
        )
        assert len(item.name) == 80

    def test_name_not_empty_constraint(self):
        with pytest.raises(IntegrityError):
            PlayerItem.objects.create(
                club=self.club,
                character=self.character,
                name="",
                quantity=1,
            )

    def test_review_choices(self):
        item = PlayerItem.objects.create(
            club=self.club,
            character=self.character,
            name="Sword",
            quantity=1,
        )
        assert item.review == PlayerItem.Review.OPEN
        item.review = PlayerItem.Review.LEFT_AS_IS
        item.save()
        assert item.review == PlayerItem.Review.LEFT_AS_IS
        item.review = PlayerItem.Review.RESOLVED
        item.save()
        assert item.review == PlayerItem.Review.RESOLVED


@pytest.mark.django_db
class TestPlayerItemLimit:
    def setup_method(self):
        self.club = Club.objects.create(name="Test Club", slug="test-club")
        self.user = User.objects.create_user("owner@example.com", password="pw")
        self.membership = Membership.objects.create(user=self.user, club=self.club)
        self.character = Character.objects.create(
            club=self.club, owner=self.membership, name="Hero"
        )
        self.other_character = Character.objects.create(
            club=self.club, owner=self.membership, name="Sidekick"
        )

    def test_50_item_limit_per_character(self):
        # Create 50 items
        for i in range(50):
            PlayerItem.objects.create(
                club=self.club,
                character=self.character,
                name=f"Item {i}",
                quantity=1,
            )
        assert PlayerItem.objects.for_club(self.club).filter(character=self.character).count() == 50

        # 51st should raise ValidationError
        with pytest.raises(ValidationError) as exc:
            PlayerItem.objects.create(
                club=self.club,
                character=self.character,
                name="Item 50",
                quantity=1,
            )
        assert "50" in str(exc.value)

    def test_limit_is_per_character_not_per_club(self):
        # Create 50 items for first character
        for i in range(50):
            PlayerItem.objects.create(
                club=self.club,
                character=self.character,
                name=f"Item {i}",
                quantity=1,
            )
        # Create 50 items for second character - should work
        for i in range(50):
            PlayerItem.objects.create(
                club=self.club,
                character=self.other_character,
                name=f"Item {i}",
                quantity=1,
            )
        qs = PlayerItem.objects.for_club(self.club).filter(character=self.other_character)
        assert qs.count() == 50

    def test_limit_enforced_on_add_not_update(self):
        # Create 50 items
        for i in range(50):
            PlayerItem.objects.create(
                club=self.club,
                character=self.character,
                name=f"Item {i}",
                quantity=1,
            )
        # Updating an existing item should work
        item = PlayerItem.objects.for_club(self.club).filter(character=self.character).first()
        item.quantity = 5
        item.save()
        item.refresh_from_db()
        assert item.quantity == 5


@pytest.mark.django_db
class TestPlayerItemChangeAppendOnly:
    def setup_method(self):
        self.club = Club.objects.create(name="Test Club", slug="test-club")
        self.user = User.objects.create_user("owner@example.com", password="pw")
        self.membership = Membership.objects.create(user=self.user, club=self.club)
        self.character = Character.objects.create(
            club=self.club, owner=self.membership, name="Hero"
        )

    def test_save_existing_raises(self):
        change = PlayerItemChange.objects.create(
            club=self.club,
            character=self.character,
            kind=PlayerItemChange.Kind.ADDED,
            new_name="Sword",
            quantity=1,
        )
        with pytest.raises(AppendOnlyError):
            change.note = "updated"
            change.save()

    def test_delete_existing_raises(self):
        change = PlayerItemChange.objects.create(
            club=self.club,
            character=self.character,
            kind=PlayerItemChange.Kind.ADDED,
            new_name="Sword",
            quantity=1,
        )
        with pytest.raises(AppendOnlyError):
            change.delete()

    def test_queryset_update_raises(self):
        PlayerItemChange.objects.create(
            club=self.club,
            character=self.character,
            kind=PlayerItemChange.Kind.ADDED,
            new_name="Sword",
            quantity=1,
        )
        with pytest.raises(AppendOnlyError):
            PlayerItemChange.objects.for_club(self.club).update(note="updated")

    def test_queryset_delete_raises(self):
        PlayerItemChange.objects.create(
            club=self.club,
            character=self.character,
            kind=PlayerItemChange.Kind.ADDED,
            new_name="Sword",
            quantity=1,
        )
        with pytest.raises(AppendOnlyError):
            PlayerItemChange.objects.for_club(self.club).delete()

    def test_new_row_can_be_created(self):
        # Creating new rows should always work
        PlayerItemChange.objects.create(
            club=self.club,
            character=self.character,
            kind=PlayerItemChange.Kind.ADDED,
            new_name="Sword",
            quantity=1,
        )
        PlayerItemChange.objects.create(
            club=self.club,
            character=self.character,
            kind=PlayerItemChange.Kind.EDITED,
            old_name="Sword",
            new_name="Magic Sword",
            quantity=1,
        )
        assert PlayerItemChange.objects.for_club(self.club).count() == 2


@pytest.mark.django_db
class TestPlayerItemClubScoping:
    def setup_method(self):
        self.club1 = Club.objects.create(name="Club 1", slug="club-1")
        self.club2 = Club.objects.create(name="Club 2", slug="club-2")
        self.user1 = User.objects.create_user("user1@example.com", password="pw")
        self.user2 = User.objects.create_user("user2@example.com", password="pw")
        self.membership1 = Membership.objects.create(user=self.user1, club=self.club1)
        self.membership2 = Membership.objects.create(user=self.user2, club=self.club2)
        self.character1 = Character.objects.create(
            club=self.club1, owner=self.membership1, name="Hero1"
        )
        self.character2 = Character.objects.create(
            club=self.club2, owner=self.membership2, name="Hero2"
        )

    def test_for_club_excludes_other_club(self):
        PlayerItem.objects.create(
            club=self.club1, character=self.character1, name="Sword", quantity=1
        )
        PlayerItem.objects.create(
            club=self.club2, character=self.character2, name="Axe", quantity=1
        )

        club1_items = PlayerItem.objects.for_club(self.club1)
        club2_items = PlayerItem.objects.for_club(self.club2)

        assert club1_items.count() == 1
        assert club1_items.first().name == "Sword"
        assert club2_items.count() == 1
        assert club2_items.first().name == "Axe"

    def test_player_item_change_for_club_excludes_other_club(self):
        PlayerItemChange.objects.create(
            club=self.club1,
            character=self.character1,
            kind=PlayerItemChange.Kind.ADDED,
            new_name="Sword",
            quantity=1,
        )
        PlayerItemChange.objects.create(
            club=self.club2,
            character=self.character2,
            kind=PlayerItemChange.Kind.ADDED,
            new_name="Axe",
            quantity=1,
        )

        club1_changes = PlayerItemChange.objects.for_club(self.club1)
        club2_changes = PlayerItemChange.objects.for_club(self.club2)

        assert club1_changes.count() == 1
        assert club1_changes.first().new_name == "Sword"
        assert club2_changes.count() == 1
        assert club2_changes.first().new_name == "Axe"

    def test_player_notice_for_club_excludes_other_club(self):
        PlayerNotice.objects.create(
            membership=self.membership1,
            club=self.club1,
            kind=PlayerNotice.Kind.ITEM_PROMOTED,
            text="Your item was promoted",
        )
        PlayerNotice.objects.create(
            membership=self.membership2,
            club=self.club2,
            kind=PlayerNotice.Kind.ITEM_PROMOTED,
            text="Your item was promoted",
        )

        club1_notices = PlayerNotice.objects.for_club(self.club1)
        club2_notices = PlayerNotice.objects.for_club(self.club2)

        assert club1_notices.count() == 1
        assert club2_notices.count() == 1


@pytest.mark.django_db
class TestPlayerNotice:
    def setup_method(self):
        self.club = Club.objects.create(name="Test Club", slug="test-club")
        self.user = User.objects.create_user("owner@example.com", password="pw")
        self.membership = Membership.objects.create(user=self.user, club=self.club)
        self.character = Character.objects.create(
            club=self.club, owner=self.membership, name="Hero"
        )

    def test_kind_choices(self):
        for kind in PlayerNotice.Kind:
            notice = PlayerNotice.objects.create(
                membership=self.membership,
                club=self.club,
                kind=kind,
                text=f"Notice: {kind}",
            )
            assert notice.kind == kind

    def test_dismiss_sets_dismissed_at(self):
        notice = PlayerNotice.objects.create(
            membership=self.membership,
            club=self.club,
            kind=PlayerNotice.Kind.GENERIC,
            text="Test notice",
        )
        assert notice.dismissed_at is None
        notice.dismiss()
        notice.refresh_from_db()
        assert notice.dismissed_at is not None

    def test_dismiss_is_idempotent(self):
        notice = PlayerNotice.objects.create(
            membership=self.membership,
            club=self.club,
            kind=PlayerNotice.Kind.GENERIC,
            text="Test notice",
        )
        notice.dismiss()
        first_dismiss = notice.dismissed_at
        notice.dismiss()
        notice.refresh_from_db()
        assert notice.dismissed_at == first_dismiss


@pytest.mark.django_db
class TestPlayerItemDeletePermission:
    def setup_method(self):
        self.club = Club.objects.create(name="Test Club", slug="test-club")
        self.user = User.objects.create_user("owner@example.com", password="pw")
        self.membership = Membership.objects.create(user=self.user, club=self.club)
        self.character = Character.objects.create(
            club=self.club, owner=self.membership, name="Hero"
        )

    def test_can_delete_when_allowed(self):
        # character_can_change_items returns True by default
        item = PlayerItem.objects.create(
            club=self.club,
            character=self.character,
            name="Sword",
            quantity=1,
        )
        item.delete()
        assert PlayerItem.objects.for_club(self.club).count() == 0
