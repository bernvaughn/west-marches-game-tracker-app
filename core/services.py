"""
Core service base classes for standardized transaction handling and club-scoped operations.

This module provides two base classes that can be combined via multiple inheritance:

- ``BaseService``: Abstract base class providing database transaction utilities.
  Subclasses must implement ``validate()`` for domain-specific validation.

- ``ClubScopedService``: Mixin providing club-scoping utilities for validating
  that objects belong to the same club and filtering querysets by club.

Usage::

    from core.services import BaseService, ClubScopedService

    class MyService(BaseService, ClubScopedService):
        def validate(self, *args, **kwargs):
            # Custom validation logic
            pass

        def do_something(self, obj1, obj2):
            self.ensure_same_club(obj1, obj2)
            with self.atomic():
                # ... transactional work ...
                pass
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, TypeVar

from django.db import models, transaction
from django.db.models import QuerySet

ModelT = TypeVar("ModelT", bound=models.Model)


class BaseService(ABC):
    """
    Abstract base class for services that need transaction handling.

    Provides consistent transaction management with support for nested
    transactions via savepoints. Subclasses must implement ``validate()``.

    Example::

        class LedgerService(BaseService):
            def validate(self, *args, **kwargs):
                # Domain-specific validation
                pass

            def record(self, ...):
                self.validate(...)
                with self.atomic():
                    # ... write to database ...
                    pass
    """

    @contextmanager
    def atomic(self):
        """
        Context manager for database transactions.

        Wraps ``django.db.transaction.atomic()`` to provide consistent
        error handling and rollback behavior. Supports nested transactions
        via savepoints.

        Yields:
            None: Control returns to the caller within the transaction block.

        Raises:
            Any exception raised within the block causes a rollback.
        """
        with transaction.atomic():
            yield

    def lock_for_update(self, queryset: QuerySet[ModelT]) -> QuerySet[ModelT]:
        """
        Return a queryset that locks selected rows for update.

        Uses ``select_for_update()`` to acquire row-level locks within
        a transaction. Must be called inside an ``atomic()`` block.

        Args:
            queryset: The queryset to lock.

        Returns:
            A queryset with ``select_for_update()`` applied.

        Example::

            with self.atomic():
                locked = self.lock_for_update(MyModel.objects.filter(pk=pk))
                obj = locked.get()
                # ... modify obj ...
                obj.save()
        """
        return queryset.select_for_update()

    @abstractmethod
    def validate(self, *args: Any, **kwargs: Any) -> None:
        """
        Validate inputs before performing an operation.

        Subclasses must implement this method to enforce domain-specific
        validation rules. Called automatically by service methods before
        executing transactional work.

        Args:
            *args: Positional arguments for validation.
            **kwargs: Keyword arguments for validation.

        Raises:
            ValidationError: If validation fails (or any custom exception).
        """
        ...


class ClubScopedService:
    """
    Mixin providing club-scoping utilities for services.

    Provides methods to validate that objects belong to the same club,
    extract the club from a model instance, and filter querysets by club.
    Designed to be combined with ``BaseService`` via multiple inheritance.

    All club-owned models in this project define a ``club_path`` class
    attribute indicating the field path to their club (e.g., ``"club"``,
    ``"character__club"``, ``"entry__club"``).
    """

    def get_club(self, obj: models.Model) -> models.Model | None:
        """
        Extract the club from a club-owned model instance.

        Follows the ``club_path`` attribute on the model to traverse
        relationships. Returns ``None`` if the path cannot be resolved.

        Args:
            obj: A model instance with a ``club_path`` attribute.

        Returns:
            The related Club instance, or ``None`` if not found.

        Example::

            club = self.get_club(character)  # character.club
            club = self.get_club(ledger_line)  # ledger_line.entry.club
        """
        if not hasattr(obj, "club_path"):
            return None

        path = obj.club_path
        current = obj
        for part in path.split("__"):
            current = getattr(current, part, None)
            if current is None:
                return None
        return current

    def ensure_same_club(self, *objects: models.Model) -> models.Model:
        """
        Validate that all objects belong to the same club.

        Args:
            *objects: One or more model instances with ``club_path``.

        Returns:
            The common Club instance.

        Raises:
            ValueError: If no objects provided, any object lacks ``club_path``,
                or objects belong to different clubs.

        Example::

            club = self.ensure_same_club(character, item, action)
            # All three belong to the same club
        """
        if not objects:
            raise ValueError("At least one object must be provided.")

        clubs = []
        for obj in objects:
            club = self.get_club(obj)
            if club is None:
                raise ValueError(
                    f"Object {obj!r} (type {type(obj).__name__}) "
                    f"does not have a resolvable club_path."
                )
            clubs.append(club)

        first_club = clubs[0]
        for club in clubs[1:]:
            if club.pk != first_club.pk:
                raise ValueError(f"Objects belong to different clubs: {[c.pk for c in clubs]}")

        return first_club

    def for_club(self, queryset: QuerySet[ModelT], club: models.Model) -> QuerySet[ModelT]:
        """
        Filter a queryset to a specific club.

        Uses the model's ``club_path`` to construct the filter. The queryset's
        model must have a ``club_path`` attribute.

        Args:
            queryset: The queryset to filter.
            club: The Club instance to filter by.

        Returns:
            A filtered queryset containing only objects belonging to the club.

        Raises:
            ValueError: If the queryset's model lacks ``club_path``.

        Example::

            entries = self.for_club(LedgerEntry.objects.all(), club)
        """
        model = queryset.model
        if not hasattr(model, "club_path"):
            raise ValueError(f"Model {model.__name__} does not have a club_path attribute.")
        return queryset.filter(**{model.club_path: club})

    def get_club_queryset(self, model: type[ModelT], club: models.Model) -> QuerySet[ModelT]:
        """
        Get a queryset for a model filtered by club.

        Convenience method combining ``model.objects.all()`` with ``for_club()``.

        Args:
            model: The model class (must have ``club_path`` and a manager).
            club: The Club instance to filter by.

        Returns:
            A queryset filtered to the given club.
        """
        return self.for_club(model.objects.all(), club)

    def get_club_object_or_404(
        self, model: type[ModelT], club: models.Model, **kwargs: Any
    ) -> ModelT:
        """
        Get a single object by club and lookup kwargs, or raise 404.

        Combines club filtering with ``get_object_or_404``.

        Args:
            model: The model class (must have ``club_path``).
            club: The Club instance to filter by.
            **kwargs: Additional lookup parameters for ``get_object_or_404``.

        Returns:
            The matching model instance.

        Raises:
            Http404: If no matching object exists.
            ValueError: If the model lacks ``club_path``.
        """
        from django.shortcuts import get_object_or_404

        return get_object_or_404(self.get_club_queryset(model, club), **kwargs)
