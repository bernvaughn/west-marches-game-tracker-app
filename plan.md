# Implementation Plan: Common Service Base Classes

## Overview
Create `core/services.py` with base service classes to standardize transaction handling and club-scoped operations across ledger, downtime, and trade services.

## Files to Create
1. `core/services.py` - New module with base classes

## Files to Modify (Refactor)
1. `ledger/services.py` - Refactor to use `BaseService` and `ClubScopedService`
2. `ledger/tests/test_services.py` - Add tests for base class behavior (or create new test file)

## Implementation Steps

### 1. Create `core/services.py`
Create a new `core` app directory with `services.py` containing:

**`BaseService`** - Abstract base class providing:
- `atomic()` - Context manager for database transactions (wraps `transaction.atomic()`)
- `lock_for_update(queryset)` - Helper for `select_for_update()` locking
- `validate()` - Abstract method for validation logic

**`ClubScopedService`** - Mixin/class providing:
- `ensure_same_club(*objects)` - Validate all objects belong to same club
- `get_club(object)` - Extract club from model instance
- Club-scoped queryset filtering utilities

### 2. Refactor `ledger/services.py`
- Import `BaseService` and `ClubScopedService` from `core.services`
- Refactor `record()` and `record_many()` to use base class transaction handling
- Use club-scoping utilities for validation

### 3. Add Tests
- Create `core/tests/test_services.py` with tests for:
  - `BaseService.atomic()` transaction behavior
  - `BaseService.lock_for_update()` locking behavior
  - `ClubScopedService.ensure_same_club()` validation
  - Club-scoped queryset filtering

## Design Decisions

### BaseService as Abstract Base Class
Using ABC (Abstract Base Class) rather than Protocol because:
- Can provide default implementations for transaction handling
- Can enforce validation contract via abstract method
- Better for runtime checking

### ClubScopedService as Mixin
Using a mixin class because:
- Can be combined with BaseService via multiple inheritance
- Provides reusable club-scoping utilities without forcing inheritance hierarchy
- Follows Django's mixin patterns

### Transaction Handling
- `atomic()` wraps `django.db.transaction.atomic()`
- Provides consistent error handling and rollback behavior
- Supports nested transactions via savepoints

## Testing Strategy
- Unit tests for base class methods in isolation
- Integration tests showing refactored ledger service works identically
- Ensure all existing ledger tests still pass