# Implementation Plan: apply_starting_equipment Service

## Goal
Create `starting_equipment/services.py` with the `apply_starting_equipment()` function that uses the ledger's `record()` function to create starting equipment entries.

## Files to Create/Modify

### 1. Create `starting_equipment/services.py`
New file with the `apply_starting_equipment()` function that:
- Takes `character`, `template`, and `actor` (User) as parameters
- Queries class entries matching character's class and level (case-insensitive, level range)
- Queries background entries matching character's background (case-insensitive)
- Queries level coins for characters above level 1
- Queries approved magic item requests for the character
- Builds lines using the ledger's `Line` dataclass
- Calls `ledger.services.record()` to create a single ledger entry with kind "award"
- Returns the ledger entry or `None` if no lines

### 2. Create `starting_equipment/tests/test_services.py`
Unit tests covering:
- Class equipment matching (case-insensitive char_class, level range)
- Background equipment matching (case-insensitive background)
- Level-based coins for level > 1
- Approved magic item requests only (not pending/declined)
- Empty template (no matching entries)
- No template provided
- Multiple approved magic item requests

## Implementation Details

### Service Function Signature
```python
def apply_starting_equipment(
    character: "Character",
    template: "StartingEquipmentTemplate",
    actor: "User"
) -> "LedgerEntry | None":
```

### Query Logic
1. **Class equipment**: `template.class_entries.filter(char_class__iexact=character.char_class, min_level__lte=level, max_level__gte=level).first()`
2. **Background equipment**: `template.background_entries.filter(background__iexact=character.background).first()`
3. **Level coins**: `template.level_coins.filter(level=character.level).first()` (only if level > 1)
4. **Magic requests**: `StartingEquipmentRequest.objects.filter(character=character, status=StartingEquipmentRequest.Status.APPROVED)`

### Ledger Integration
- Import `Line` from `ledger.services`
- Import `record` from `ledger.services`
- Use `record(character, "award", lines, note="Starting equipment", actor=actor)`

## Dependencies
- SE1 (models) - already done
- SE2 (Character.background field) - already done (field exists in model)
- ledger.services.record() - already exists

## Testing Approach
- Use pytest with Django test database
- Create fixtures for character, template, items, club, user
- Test each equipment type independently and in combination
- Verify ledger entry is created with correct lines

# Plan: Delete Trade Views, Forms, Services, URLs, Templates

## Scope

Remove all trade functionality from the player_characters app while keeping Trade/TradeLine models in the database for ledger history.

## Files to Delete (13 files + 2 directories)

### Python source files:
1. `player_characters/trade_forms.py`
2. `player_characters/trade_services.py`
3. `player_characters/trade_status_line.py`
4. `player_characters/urls_trades.py`
5. `player_characters/views/trades.py`
6. `player_characters/views/trade_detail.py`
7. `player_characters/views/trade_sides.py`
8. `player_characters/views/trade_poll.py`
9. `player_characters/views/trade_status.py`

### Templates:
10. `player_characters/templates/player_characters/trades/` (entire directory, 11 files)
11. `templates/accounts/_dashboard_trades.html`
12. `templates/partials/trade_poll.html`

### Test files:
13. `player_characters/tests/trades/` (entire directory, 9 files)

## Files to Modify

### config/urls.py
- Remove `path("trades/", include("player_characters.urls_trades"))` from club_patterns

### player_characters/apps.py
- Remove "My trades" (trades:index) navigation registration
- Remove "Propose trade" (trades:propose) navigation registration

### player_characters/views/characters.py
- Remove `Trade` import from models
- Remove `OPEN` import from trade_services
- Remove open_trades query and by_other dict from DirectoryView
- Remove trades/propose_url from DirectoryView rows
- Remove `can_transfer` from DetailView context

### player_characters/views/character_print.py
- Remove `Trade` import from models
- Remove `OPEN` import from trade_services
- Remove `club_queryset` import if only used for trades
- Remove `include_trades` parameter handling from print_session_pack
- Remove open_trades_data computation from print_session_pack

### player_characters/selector_context.py
- Remove `Trade` import from models
- Remove `OPEN` import from trade_services
- Remove open_trades count computation

### player_characters/templates/player_characters/characters/detail.html
- Remove "Move items" button (can_transfer)
- Remove "In open trades" coins section (coins.has_holds)
- Remove "In open trades" table column header (show_held)

### player_characters/templates/player_characters/characters/directory.html
- Remove "Trades with" column header
- Remove trades status badges and "Propose trade" link

### player_characters/templates/player_characters/characters/_selector.html
- Remove "Trades" badge (ctx.open_trades)

### player_characters/templates/player_characters/characters/print_session_pack.html
- Remove "Open Trades" print option checkbox
- Remove "In open trades" coins note
- Remove Open Trades section

### templates/accounts/_print_session_pack_modal.html
- Remove "Open Trades" checkbox option

### templates/partials/side_menu.html
- Remove `{% include "partials/trade_poll.html" %}`

### accounts/apps.py
- Remove import of `open_trades_needing_action` from approval_providers
- Remove import of `TradesDashboardProvider` from dashboard_providers
- Remove `approvals.register(open_trades_needing_action)`
- Remove `register_provider(TradesDashboardProvider())`

### accounts/approval_providers.py
- Remove `open_trades_needing_action` function
- Remove `Trade` import from player_characters.models

### accounts/dashboard_providers.py
- Remove `TradesDashboardProvider` class
- Remove `Trade` import from player_characters.models
- Remove `OPEN` import from player_characters.trade_services
- Remove `trade_status_line` import from player_characters.trade_status_line

### accounts/views/dashboard.py
- Remove `Trade` import from player_characters.models
- Remove `OPEN` import from player_characters.trade_services
- Remove open_trades_data computation from _get_dashboard_context
- Remove open_trades_count from character_preview

### scripts/screenshot_pages.py
- Remove `Trade` and `propose_trade` imports
- Remove `_proposed_trade` function

## What to Keep

- `Trade`, `TradeLine`, `JunkMark` models in player_characters/models.py (append-only ledger)
- `LedgerEntry.Kind.TRANSFER` and `Kind.TRADE` in ledger/models.py
- `player_characters/admin.py` Trade/TradeLine admin registrations (models are kept)
- `player_characters/urls_characters.py` (transfer URLs handled by sibling task)
- `player_characters/views/character_transfer.py` (handled by sibling task)
- `player_characters/forms_transfer.py` (handled by sibling task)
- Player shops functionality (shops app, character shop toggle)

## Proof Stages

- **code**: All deletions and modifications complete; app imports without errors
- **verify**: Trade pages return 404, no trade UI elements remain, all tests pass
