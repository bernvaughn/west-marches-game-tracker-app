# Implementation Plan: Unified Dashboard Provider System

## Goal
Create a single unified dashboard provider system in `accounts/dashboard_providers.py` that replaces the duplicate implementations in `dashboard_providers.py` and `dashboard.py`.

## Current State Analysis

### Duplicate Providers (to consolidate)
| Provider | Location | Key | Order | Template |
|----------|----------|-----|-------|----------|
| QuickActionsProvider | dashboard_providers.py | quick_actions | 1 | _dashboard_quick_actions.html |
| TradesProvider | dashboard.py (dataclass) | trades | 2 | _dashboard_trades.html |
| QuestsProvider | dashboard.py (dataclass) | quests | 3 | _dashboard_quests.html |
| **DowntimeDashboardProvider** | dashboard_providers.py | downtime | 4 | _dashboard_downtime.html |
| **DowntimeProvider** | dashboard.py (dataclass) | downtime | 4 | _dashboard_downtime.html | **DUPLICATE** |
| MapDashboardProvider | dashboard.py (class) | map | 5 | _dashboard_map.html |
| MessagesProvider | dashboard.py (dataclass) | messages | 6 | _dashboard_messages.html |
| PlayerShopDashboardProvider | dashboard_shop.py (dataclass) | player_shop | 7 | _dashboard_player_shop.html |
| MessagesDashboardProvider | dashboard_messages.py (dataclass) | my_messages | 7 | _dashboard_my_messages.html |
| **ConsumablesDashboardProvider** | dashboard_providers.py | consumables | 8 | _dashboard_consumables.html |
| **ConsumablesProvider** | dashboard.py (dataclass) | consumables | 8 | _dashboard_consumables.html | **DUPLICATE** |

## Implementation Steps

### 1. Update `accounts/dashboard_providers.py`
- Add `BaseDashboardProvider` base class with common utilities (optional but recommended for DRY)
- Move ALL providers from `dashboard.py`, `dashboard_messages.py`, `dashboard_shop.py` into this file
- Rename providers to follow consistent naming: `*DashboardProvider`
  - `TradesProvider` → `TradesDashboardProvider`
  - `QuestsProvider` → `QuestsDashboardProvider`
  - `MapDashboardProvider` → keep name (move from dashboard.py)
  - `MessagesProvider` → `MessagesDashboardProvider` (for admin unread messages)
  - `MessagesDashboardProvider` (from dashboard_messages.py) → `MyMessagesDashboardProvider` (for player's sent messages)
  - `PlayerShopDashboardProvider` → move from dashboard_shop.py
- Keep existing: `DowntimeDashboardProvider`, `QuickActionsProvider`, `ConsumablesDashboardProvider`
- Remove duplicate `DowntimeProvider` and `ConsumablesProvider` from dashboard.py

### 2. Update `accounts/apps.py`
- Update imports to import all providers from `dashboard_providers.py` only
- Remove imports from `dashboard.py`, `dashboard_messages.py`, `dashboard_shop.py`
- Register all providers from the unified module

### 3. Update `accounts/views/dashboard.py`
- Remove ALL inline provider classes (TradesProvider, QuestsProvider, DowntimeProvider, MapDashboardProvider, MessagesProvider, ConsumablesProvider)
- Remove imports for moved providers
- Keep only: `_get_dashboard_context`, `player_dashboard`, `dashboard_partial`, `character_preview`, `print_session_pack_modal`
- Ensure `dashboard_partial` uses `get_provider` from unified system

### 4. Update `accounts/views/dashboard_messages.py`
- Remove `MessagesDashboardProvider` class (moved to dashboard_providers.py as MyMessagesDashboardProvider)
- Keep only the view functions (message_detail, etc.)

### 5. Update `accounts/views/dashboard_shop.py`
- Remove `PlayerShopDashboardProvider` class (moved to dashboard_providers.py)
- Keep only the view functions if any

### 6. Verify Templates
- Templates already use `provider_context.*` variables matching what providers return
- No template changes needed for this story (template standardization is separate bug task)

### 7. Run Tests
- All existing tests should pass
- Fix any test failures due to import changes

## Files to Modify
1. `accounts/dashboard_providers.py` - Main file (add base class + all providers)
2. `accounts/apps.py` - Update registration imports
3. `accounts/views/dashboard.py` - Remove inline providers
4. `accounts/views/dashboard_messages.py` - Remove MessagesDashboardProvider
5. `accounts/views/dashboard_shop.py` - Remove PlayerShopDashboardProvider

## Acceptance Criteria
- Single `DashboardProvider` Protocol with `key`, `order`, `template`, `get_context(request, club, character, membership)`, `should_show(request, club, character, membership)`
- Base class `BaseDashboardProvider` with common utilities
- Registration via `register_provider()` / `get_providers()` / `get_provider(key)`
- All existing providers migrated: Downtime, QuickActions, Consumables
- New providers added: Trades, Quests, Messages (admin), MyMessages, Map, PlayerShop
- `dashboard.py` uses only the unified system
- All existing tests pass