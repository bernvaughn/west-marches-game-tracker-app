"""Tests for core service base classes."""

import pytest
from django.db.models import QuerySet

from core.services import BaseService, ClubScopedService
from items.models import Item
from ledger.models import LedgerEntry, LedgerLine
from player_characters.models import Character

pytestmark = [pytest.mark.django_db]


class TestBaseService:
    """Tests for BaseService transaction handling."""

    def test_atomic_commits_on_success(self, character):
        """Atomic block commits changes when no exception occurs."""

        class TestService(BaseService):
            def validate(self, *args, **kwargs):
                pass

        service = TestService()

        with service.atomic():
            LedgerEntry.objects.create(
                club=character.club,
                character=character,
                kind="award",
                note="test",
            )

        assert LedgerEntry.objects.filter(note="test").exists()

    def test_atomic_rolls_back_on_exception(self, character):
        """Atomic block rolls back changes when an exception is raised."""

        class TestService(BaseService):
            def validate(self, *args, **kwargs):
                pass

        service = TestService()

        with pytest.raises(ValueError):
            with service.atomic():
                LedgerEntry.objects.create(
                    club=character.club,
                    character=character,
                    kind="award",
                    note="should-rollback",
                )
                raise ValueError("intentional")

        assert not LedgerEntry.objects.filter(note="should-rollback").exists()

    def test_nested_atomic_blocks_use_savepoints(self, character):
        """Nested atomic blocks use savepoints (inner rollback doesn't affect outer)."""

        class TestService(BaseService):
            def validate(self, *args, **kwargs):
                pass

        service = TestService()

        with service.atomic():
            LedgerEntry.objects.create(
                club=character.club,
                character=character,
                kind="award",
                note="outer",
            )
            try:
                with service.atomic():
                    LedgerEntry.objects.create(
                        club=character.club,
                        character=character,
                        kind="award",
                        note="inner",
                    )
                    raise ValueError("inner rollback")
            except ValueError:
                pass

        # Outer entry should still exist
        assert LedgerEntry.objects.filter(note="outer").exists()
        # Inner entry should be rolled back
        assert not LedgerEntry.objects.filter(note="inner").exists()

    def test_lock_for_update_returns_locked_queryset(self, character):
        """lock_for_update returns a queryset with select_for_update applied."""

        class TestService(BaseService):
            def validate(self, *args, **kwargs):
                pass

        service = TestService()

        entry = LedgerEntry.objects.create(
            club=character.club,
            character=character,
            kind="award",
            note="lock-test",
        )

        with service.atomic():
            locked_qs = service.lock_for_update(LedgerEntry.objects.filter(pk=entry.pk))
            assert isinstance(locked_qs, QuerySet)
            assert locked_qs.query.select_for_update
            locked_entry = locked_qs.get()
            assert locked_entry.pk == entry.pk

    def test_validate_is_abstract(self):
        """BaseService.validate is abstract and must be implemented."""

        class IncompleteService(BaseService):
            pass

        with pytest.raises(TypeError):
            IncompleteService()


class TestClubScopedService:
    """Tests for ClubScopedService club-scoping utilities."""

    def test_get_club_from_character(self, character, club):
        """get_club extracts club from character (club_path='club')."""

        class TestService(ClubScopedService):
            pass

        service = TestService()
        assert service.get_club(character) == club

    def test_get_club_from_ledger_entry(self, character, club):
        """get_club extracts club from ledger entry (club_path='club')."""

        class TestService(ClubScopedService):
            pass

        service = TestService()
        entry = LedgerEntry.objects.create(
            club=club,
            character=character,
            kind="award",
        )
        assert service.get_club(entry) == club

    def test_get_club_from_ledger_line(self, character, club):
        """get_club extracts club from ledger line (club_path='entry__club')."""

        class TestService(ClubScopedService):
            pass

        service = TestService()
        entry = LedgerEntry.objects.create(
            club=club,
            character=character,
            kind="award",
        )
        line = LedgerLine.objects.create(entry=entry, coins=100)
        assert service.get_club(line) == club

    def test_get_club_from_item(self, club):
        """get_club extracts club from item (club_path='club')."""

        class TestService(ClubScopedService):
            pass

        service = TestService()
        item = Item.objects.create(club=club, name="Test Item")
        assert service.get_club(item) == club

    def test_get_club_returns_none_for_model_without_club_path(self, club):
        """get_club returns None for models without club_path."""

        class TestService(ClubScopedService):
            pass

        # Create a model without club_path dynamically
        from django.db import models

        class NoClubPath(models.Model):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "core"

            def __str__(self):
                return self.name

        obj = NoClubPath(name="test")
        service = TestService()
        assert service.get_club(obj) is None

    def test_ensure_same_club_single_object(self, character, club):
        """ensure_same_club returns the club for a single object."""

        class TestService(ClubScopedService):
            pass

        service = TestService()
        result = service.ensure_same_club(character)
        assert result == club

    def test_ensure_same_club_multiple_objects_same_club(self, character, other_character, club):
        """ensure_same_club returns club when all objects share the same club."""

        class TestService(ClubScopedService):
            pass

        service = TestService()
        result = service.ensure_same_club(character, other_character)
        assert result == club

    def test_ensure_same_club_raises_on_different_clubs(self, character, other_club_character):
        """ensure_same_club raises ValueError when objects belong to different clubs."""

        class TestService(ClubScopedService):
            pass

        service = TestService()
        with pytest.raises(ValueError, match="different clubs"):
            service.ensure_same_club(character, other_club_character)

    def test_ensure_same_club_raises_on_no_objects(self):
        """ensure_same_club raises ValueError when no objects provided."""

        class TestService(ClubScopedService):
            pass

        service = TestService()
        with pytest.raises(ValueError, match="At least one object"):
            service.ensure_same_club()

    def test_ensure_same_club_raises_on_unresolvable_club_path(self, club):
        """ensure_same_club raises ValueError when club_path cannot be resolved."""

        class TestService(ClubScopedService):
            pass

        from django.db import models

        class NoClubPath(models.Model):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "core"

            def __str__(self):
                return self.name

        service = TestService()
        obj = NoClubPath(name="test")
        with pytest.raises(ValueError, match="does not have a resolvable club_path"):
            service.ensure_same_club(obj)

    def test_for_club_filters_queryset(self, character, other_club_character, club, other_club):
        """for_club filters queryset to the given club."""

        class TestService(ClubScopedService):
            pass

        service = TestService()
        qs = service.for_club(Character.objects.all(), club)
        pks = set(qs.values_list("pk", flat=True))
        assert character.pk in pks
        assert other_club_character.pk not in pks

    def test_for_club_raises_on_model_without_club_path(self, club):
        """for_club raises ValueError for models without club_path."""

        class TestService(ClubScopedService):
            pass

        from django.db import models

        class NoClubPath(models.Model):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "core"

            def __str__(self):
                return self.name

        service = TestService()
        with pytest.raises(ValueError, match="does not have a club_path attribute"):
            service.for_club(NoClubPath.objects.all(), club)

    def test_get_club_queryset_returns_filtered_queryset(
        self, character, other_club_character, club
    ):
        """get_club_queryset returns queryset filtered by club."""

        class TestService(ClubScopedService):
            pass

        service = TestService()
        qs = service.get_club_queryset(Character, club)
        pks = set(qs.values_list("pk", flat=True))
        assert character.pk in pks
        assert other_club_character.pk not in pks

    def test_get_club_object_or_404_returns_object(self, character, club):
        """get_club_object_or_404 returns object when found."""

        class TestService(ClubScopedService):
            pass

        service = TestService()
        obj = service.get_club_object_or_404(Character, club, pk=character.pk)
        assert obj == character

    def test_get_club_object_or_404_raises_404_on_not_found(self, club):
        """get_club_object_or_404 raises Http404 when object not found."""

        class TestService(ClubScopedService):
            pass

        from django.http import Http404

        service = TestService()
        with pytest.raises(Http404):
            service.get_club_object_or_404(Character, club, pk=99999)


class TestCombinedService:
    """Tests for services combining BaseService and ClubScopedService."""

    def test_combined_service_works(self, character, club, item):
        """A service inheriting from both base classes works correctly."""

        class CombinedService(BaseService, ClubScopedService):
            def validate(self, *args, **kwargs):
                pass

            def do_work(self, character, item):
                self.ensure_same_club(character, item)
                with self.atomic():
                    entry = LedgerEntry.objects.create(
                        club=character.club,
                        character=character,
                        kind="award",
                        note="combined",
                    )
                    LedgerLine.objects.create(entry=entry, item=item, quantity=1)
                return entry

        service = CombinedService()
        entry = service.do_work(character, item)

        assert entry.note == "combined"
        assert entry.lines.count() == 1
        assert entry.lines.first().item == item

    def test_combined_service_rolls_back_on_validation_error(self, character, club, item):
        """Validation error in combined service rolls back transaction."""

        class CombinedService(BaseService, ClubScopedService):
            def validate(self, character, item):
                if item.name == "Invalid":
                    raise ValueError("Invalid item")

            def do_work(self, character, item):
                self.validate(character, item)
                with self.atomic():
                    entry = LedgerEntry.objects.create(
                        club=character.club,
                        character=character,
                        kind="award",
                        note="should-fail",
                    )
                    LedgerLine.objects.create(entry=entry, item=item, quantity=1)

        service = CombinedService()
        invalid_item = Item.objects.create(club=club, name="Invalid")

        with pytest.raises(ValueError, match="Invalid item"):
            service.do_work(character, invalid_item)

        assert not LedgerEntry.objects.filter(note="should-fail").exists()
