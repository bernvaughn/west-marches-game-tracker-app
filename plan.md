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