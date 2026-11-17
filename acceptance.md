## code
- [ ] Single `DashboardProvider` Protocol with `key`, `order`, `template`, `get_context(request, club, character, membership)`, `should_show(request, club, character, membership)`
- [ ] Base class `BaseDashboardProvider` with common utilities
- [ ] Registration via `register_provider()` / `get_providers()` / `get_provider(key)`
- [ ] All existing providers migrated: Downtime, QuickActions, Consumables
- [ ] New providers added: Trades, Quests, Messages, MyMessages, Map, PlayerShop
- [ ] `dashboard.py` uses only the unified system
- [ ] All existing tests pass

## verify
- [ ] Run full test suite - all tests pass
- [ ] No duplicate provider classes exist in dashboard.py, dashboard_messages.py, dashboard_shop.py
- [ ] All providers registered in apps.py from dashboard_providers.py only