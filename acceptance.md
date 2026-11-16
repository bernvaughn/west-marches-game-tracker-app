## code
- [ ] `DashboardProvider` protocol defined in `accounts/dashboard_providers.py`
- [ ] Provider registry in `accounts/apps.py` `ready()`
- [ ] `_get_dashboard_context()` refactored to use providers
- [ ] HTMX partial endpoint pattern implemented (`dashboard/<slug>/partial/<key>/`)
- [ ] Character preview endpoint (`characters/<slug>/preview/<pk>/`) returns JSON
- [ ] `dashboard.html` renders providers dynamically in order

## verify
- [ ] All existing dashboard functionality preserved (tests pass)
- [ ] Ruff clean, 1942+ tests pass