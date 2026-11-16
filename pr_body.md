## Summary
Show player shop status (open/closed, items listed, sales) with manage link on dashboard.

## Changes
- Created `accounts/views/dashboard_shop.py` with `PlayerShopDashboardProvider`
- Added provider registration in `accounts/apps.py` (order 7)
- Updated `accounts/views/dashboard.py` to remove duplicate `PlayerShopProvider` class
- Updated `accounts/urls.py` import formatting (ruff fix)
- Updated template `templates/accounts/_dashboard_player_shop.html` to display: 'Your Stall: Open · X items listed · Y sales today'
- Added unit tests in `accounts/tests/test_dashboard_player_shop.py`

## Acceptance Criteria
- [x] Player Shop section (provider order 7) shows only if `character.shop_open = True`
- [x] Displays: 'Your Stall: Open · X items listed · Y sales today'
- [x] Manage link → character sheet (where junk toggle lives)
- [x] Ruff clean (no new errors), unit tests pass (1791 tests)

## Testing
- 5 new unit tests added for the provider
- All 1791 existing tests pass
- No new ruff errors introduced

Closes: https://app.codeherder.com/vaughnjbernards-account/vaughnjbernards-workspace/-/tasks/01a1e1d0-2c35-78af-bdc2-2a87edf94b9a