# S2: Add, edit, remove on the sheet (U159) - Implementation Plan

## Overview
Build forms, views, URLs, and services for players to add, edit, and remove player-written items on their character sheet. Create the sheet partial template `_entries.html` and include it via the sheet sections registry. Tests for permissions, 'Player-written' label, unsellable enforcement, limit error, and history rows.

## Files to Create

### 1. `player_items/forms.py`
- `PlayerItemForm`: Form for adding/editing a player-written item
  - Fields: name (max 80), quantity (>=1), note (optional)
  - Validation: name not empty, quantity >= 1

### 2. `player_items/services.py`
- `add_player_item(club, character, name, quantity, note, by)` -> PlayerItem
  - Creates PlayerItem, writes PlayerItemChange(kind=ADDED)
  - Enforces 50-item limit (raises ValidationError)
  - Checks `character_can_change_items(character)`
- `edit_player_item(player_item, name, quantity, note, by)` -> PlayerItem
  - Updates PlayerItem, writes PlayerItemChange(kind=EDITED) with old_name/new_name
  - Checks `character_can_change_items(character)`
- `remove_player_item(player_item, by)` -> None
  - Deletes PlayerItem, writes PlayerItemChange(kind=REMOVED)
  - Checks `character_can_change_items(character)`

### 3. `player_items/urls.py`
- URL patterns for add, edit, remove views
- Namespace: `player_items`
- Paths:
  - `<int:character_pk>/entries/add/` -> add view
  - `<int:character_pk>/entries/<int:pk>/edit/` -> edit view
  - `<int:character_pk>/entries/<int:pk>/remove/` -> remove view

### 4. `player_items/views/entries.py`
- `add_entry(request, club_slug, character_pk)` - HTMX modal for adding
- `edit_entry(request, club_slug, character_pk, pk)` - HTMX modal for editing
- `remove_entry(request, club_slug, character_pk, pk)` - HTMX modal for removing (confirmation)
- All views use `club_member_required` decorator
- Permission check: owner, GM, or club admin (via `can_view_inventory` + `owns_character` for owner check)
- Use `render_modal_or_page` pattern like `character_notes.py`

### 5. `player_items/templates/player_items/_entries.html`
- Sheet section partial showing player-written items
- Table with columns: Name, Qty, Note, Actions (edit/remove)
- "Player-written" badge on each row
- "Add player-written item" button (opens modal)
- Only shown when `can_view` is True

### 6. `player_items/templates/player_items/_entry_form.html`
- Form partial for add/edit modals
- Reused by both add and edit views

### 6. `player_items/templates/player_items/_remove_confirm.html`
- Confirmation partial for remove modal

### 7. `player_items/apps.py` - Update
- Add `ready()` method to register sheet section
- Context function: returns `{"entries": character.player_items.for_club(club).all()}`
- Visible function: returns `can_view_inventory(request.user, character)`
- Template: `player_items/_entries.html`
- Order: after ledger box (e.g., order 50)

## Files to Modify
- None (all new files except apps.py update)

## Acceptance Criteria (Tests)

### Permission Tests
- [ ] Owner can add, edit, remove
- [ ] Game master can add, edit, remove
- [ ] Club admin can add, edit, remove
- [ ] Another player (non-owner, non-GM, non-admin) cannot add, edit, remove

### Display Tests
- [ ] Items shown with "Player-written" label/badge
- [ ] Items appear in sheet section on character detail page

### Unsellable Enforcement Tests (one test per path)
- [ ] Player-written items do not appear in shops
- [ ] Player-written items do not appear in stalls (player shops)
- [ ] Player-written items do not appear in quests
- [ ] Player-written items do not appear in rewards

### Limit Tests
- [ ] Adding 51st item shows limit error message

### History Tests
- [ ] Add creates PlayerItemChange(kind=ADDED)
- [ ] Edit creates PlayerItemChange(kind=EDITED) with old_name/new_name
- [ ] Remove creates PlayerItemChange(kind=REMOVED)

## Implementation Order
1. Create forms.py
2. Create services.py
3. Create views/entries.py
4. Create urls.py
5. Create templates (_entries.html, _entry_form.html, _remove_confirm.html)
6. Update apps.py with ready() registration
7. Write tests in player_items/tests/test_views.py
8. Run pytest, ruff check, ruff format

## Design Decisions
- Use existing sheet sections registry (no template modification needed)
- Follow HTMX modal pattern from character_notes.py
- Use existing permission helpers (can_view_inventory, owns_character)
- Reuse character_can_change_items from rules.py (placeholder until death/archive epic)
- PlayerItem model already has 50-limit enforcement in save()
- Unsellable by construction (separate model, not in ledger)