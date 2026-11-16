## code
- [ ] `DashboardProvider` protocol defined in `accounts/dashboard_providers.py`
- [ ] Provider registry in `accounts/apps.py` `ready()`
- [ ] `_get_dashboard_context()` refactored to use providers
- [ ] HTMX partial endpoint pattern implemented (`dashboard/<slug>/partial/<key>/`)
- [ ] Character preview endpoint (`characters/<slug>/preview/<pk>/`) returns JSON
- [ ] `dashboard.html` renders providers dynamically in order
- [ ] Character selector dropdown options show Bootstrap tooltip on hover/focus
- [ ] Tooltip fetches `/characters/<slug>/preview/<pk>/` via HTMX on `shown.bs.tooltip`
- [ ] Preview JSON: `{name, level, class, species, coins_available, junk_count, junk_value, downtime, open_trades}`
- [ ] Tooltip renders as small card with avatar, key stats
- [ ] Works on mobile (tap to show, tap elsewhere to dismiss)
- [ ] Ruff clean, unit + browser tests pass

## verify
- [ ] All existing dashboard functionality preserved (tests pass)
- [ ] Ruff clean, 1942+ tests pass
