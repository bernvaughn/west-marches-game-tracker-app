## code
- [ ] Create `starting_equipment/services.py` with `apply_starting_equipment()` function
- [ ] Function handles class equipment (case-insensitive class match, level range filter)
- [ ] Function handles background equipment (case-insensitive background match)
- [ ] Function handles level-based coins (for level > 1)
- [ ] Function handles approved magic item requests (status=APPROVED only)
- [ ] Function uses ledger's `record()` to create a single "award" ledger entry
- [ ] Function returns the LedgerEntry or None if no lines to grant
- [ ] Create `starting_equipment/tests/test_services.py` with unit tests
- [ ] Tests cover class match (case-insensitive), background match, level coins, magic requests, empty template
- [ ] All tests pass

## review
- [ ] Code follows project conventions (type hints, docstrings, error handling)
- [ ] No console errors when running tests
- [ ] Service integrates correctly with ledger's record() function

## verify
- [ ] apply_starting_equipment() works end-to-end with real data
- [ ] Ledger entries are created correctly with all equipment types
- [ ] No regressions in existing ledger tests

## code — Delete Trade Views, Forms, Services, URLs, Templates
- [ ] Delete player_characters/trade_forms.py
- [ ] Delete player_characters/trade_services.py
- [ ] Delete player_characters/trade_status_line.py
- [ ] Delete player_characters/urls_trades.py
- [ ] Delete player_characters/views/trades.py
- [ ] Delete player_characters/views/trade_detail.py
- [ ] Delete player_characters/views/trade_sides.py
- [ ] Delete player_characters/views/trade_poll.py
- [ ] Delete player_characters/views/trade_status.py
- [ ] Delete player_characters/templates/player_characters/trades/ directory
- [ ] Delete templates/accounts/_dashboard_trades.html
- [ ] Delete templates/partials/trade_poll.html
- [ ] Delete player_characters/tests/trades/ directory
- [ ] Remove trades URL include from config/urls.py
- [ ] Remove trades navigation entries from player_characters/apps.py
- [ ] Remove Trade/OPEN imports and trade logic from player_characters/views/characters.py
- [ ] Remove Trade/OPEN imports and trade logic from player_characters/views/character_print.py
- [ ] Remove Trade/OPEN imports and trade logic from player_characters/selector_context.py
- [ ] Remove "Move items" button and trades references from characters/detail.html
- [ ] Remove trades column and "Propose trade" link from characters/directory.html
- [ ] Remove trades badge from characters/_selector.html
- [ ] Remove trades option from print_session_pack.html
- [ ] Remove trade_poll include from side_menu.html
- [ ] Remove TradesDashboardProvider from accounts/apps.py
- [ ] Remove open_trades_needing_action from accounts/apps.py
- [ ] Remove open_trades_needing_action from accounts/approval_providers.py
- [ ] Remove TradesDashboardProvider from accounts/dashboard_providers.py
- [ ] Remove trade references from accounts/views/dashboard.py
- [ ] Remove trade references from scripts/screenshot_pages.py

## verify — Delete Trade Views, Forms, Services, URLs, Templates
- [ ] Trade pages (/c/<club>/trades/) return 404
- [ ] No "Move items" button on character sheet toolbar
- [ ] No "Trades" link in top bar or side menu
- [ ] No "Propose trade" link in character directory
- [ ] Player shops still work: "Sell my junk in my shop" toggle unchanged
- [ ] All existing tests pass (excluding deleted trade tests)
- [ ] No console errors
