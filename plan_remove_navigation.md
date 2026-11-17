# Implementation Plan: Remove Trade/Transfer Navigation Entries

## Overview
Remove navigation registrations for trades group and transfer link from player_characters/apps.py and accounts/apps.py. Remove TradesProvider dashboard provider and open_trades_needing_action approval provider.

## Files to Modify

### 1. player_characters/apps.py
Remove navigation registrations:
- "trades" group: "My trades" (trades:index) and "Propose trade" (trades:propose)
- "character" group: "Move items" (characters:transfer_start)

### 2. accounts/apps.py
- Remove import of `open_trades_needing_action` from `.approval_providers`
- Remove import of `TradesDashboardProvider` from `.dashboard_providers`
- Remove `approvals.register(open_trades_needing_action)`
- Remove `register_provider(TradesDashboardProvider())`

### 3. accounts/approval_providers.py
- Remove the `open_trades_needing_action` function (since it's no longer registered)

### 4. accounts/dashboard_providers.py
- Remove the `TradesDashboardProvider` class (since it's no longer registered)
- Remove `OPEN` import from `player_characters.trade_services` (no longer used)

### 5. Update Tests
- **accounts/tests/test_approvals_indicator.py**: Remove tests for `open_trades_needing_action` and update `test_registry_has_real_providers` to remove it from expected providers
- **accounts/tests/test_navigation_menus.py**: Remove checks for `characters:transfer_start`, `trades:index`, `trades:propose` from expected navigation links

## Execution Order
1. Modify player_characters/apps.py
2. Modify accounts/apps.py
3. Modify accounts/approval_providers.py
4. Modify accounts/dashboard_providers.py
5. Update test_approvals_indicator.py
6. Update test_navigation_menus.py
7. Run tests to verify

## Notes
- The Trade and TradeLine models remain in the database (append-only ledger preserves history)
- LedgerEntry.Kind.TRANSFER and Kind.TRADE remain for historical entries
- Player shops remain fully functional
- The trades and transfers views/URLs are handled by other stories (Delete Trade Code, Delete Transfer Code, Update URL Configuration)