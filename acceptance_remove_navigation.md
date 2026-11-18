## code
- [ ] Navigation entries for "trades" group removed from player_characters/apps.py ("My trades", "Propose trade")
- [ ] Navigation entry for "Move items" (characters:transfer_start) removed from player_characters/apps.py
- [ ] TradesDashboardProvider import and registration removed from accounts/apps.py
- [ ] open_trades_needing_action import and registration removed from accounts/apps.py
- [ ] open_trades_needing_action function removed from accounts/approval_providers.py
- [ ] TradesDashboardProvider class removed from accounts/dashboard_providers.py
- [ ] OPEN import from player_characters.trade_services removed from accounts/dashboard_providers.py
- [ ] test_approvals_indicator.py updated: trade-related tests removed, registry test updated
- [ ] test_navigation_menus.py updated: trade/transfer links removed from expected navigation

## verify
- [ ] All existing tests pass (excluding deleted trade/transfer test files)
- [ ] No "Trades" link in top bar or side menu
- [ ] No "Move items" button on character sheet
- [ ] No "Propose trade" link in character directory
- [ ] Player shops still work: "Sell my junk in my shop" toggle unchanged
- [ ] Ledger history still shows old TRANSFER/TRADE entries