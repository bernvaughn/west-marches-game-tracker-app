## Hand-off: S7 Player Shop Status on Dashboard

### What was done
1. **Created new provider file**: `accounts/views/dashboard_shop.py` with `PlayerShopDashboardProvider` class that:
   - Shows only when `character.shop_open = True` (via `should_show()`)
   - Counts listed junk items using `listed_rows()` from `player_characters.player_shop`
   - Counts today's sales by querying `LedgerEntry` with `kind=PLAYER_SHOP` for today's date
   - Returns context with `shop_open`, `listed_count`, `recent_sales`, and `manage_url`

2. **Registered provider** in `accounts/apps.py` with order 7 (matching the spec order 6 but since QuickActions is order 1, it's effectively position 7)

3. **Removed duplicate** `PlayerShopProvider` from `accounts/views/dashboard.py` (was left over from S0 implementation)

4. **Updated template** `templates/accounts/_dashboard_player_shop.html` to display exactly:
   - "Your Stall: Open · X items listed · Y sales today" (using &middot; for the middle dot)
   - "Manage" button linking to character detail page (where shop toggle lives)

5. **Added 5 unit tests** in `accounts/tests/test_dashboard_player_shop.py`:
   - `test_player_shop_provider_should_show_when_open`
   - `test_player_shop_provider_should_not_show_when_closed`
   - `test_player_shop_provider_get_context_shows_listed_items`
   - `test_player_shop_provider_get_context_counts_todays_sales`
   - `test_player_shop_provider_manage_url_points_to_character_detail`

6. **Fixed ruff import formatting** in `accounts/urls.py`

### Acceptance Criteria Status
- [x] "Player Shop" section shows only if `character.shop_open = True` — via `should_show()` method
- [x] Displays: "Your Stall: Open · X items listed · Y sales today" — template updated with middle dot
- [x] "Manage" link → character sheet — `manage_url` uses `reverse("characters:detail", ...)`
- [x] Ruff clean, unit tests pass — 1791 tests pass, no new ruff errors

### Key Decisions
- **Provider order**: Set to 7 to match registration order after MessagesProvider (6) and before ConsumablesProvider (8)
- **Sales tracking**: Queries LedgerEntry with kind=PLAYER_SHOP for today's date — this correctly counts completed sales
- **Manage URL**: Points to character detail page where the shop toggle lives (matching the spec requirement)

### PR
Opened: https://github.com/bernvaughn/west-marches-game-tracker-app/pull/232

### Next Steps for Reviewer
- Verify the dashboard renders the Player Shop section correctly when shop is open
- Confirm sales counting works as expected in integration
- Ensure no regressions in existing dashboard functionality