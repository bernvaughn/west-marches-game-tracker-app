## Hand-off: S5 Downtime Spend from Dashboard - Plan Stage Complete

### Summary
Created implementation plan for adding "Spend on [Action]" buttons to the dashboard downtime section that open the spinning wheel modal directly via HTMX.

### Key Decisions
1. **Provider Pattern**: Will extend the existing `DashboardProvider` system with a `DowntimeDashboardProvider` class (order=4)
2. **HTMX Partial Endpoint**: New view at `/dashboard/<slug>/partial/downtime_spend/<action_pk>/` returning wheel modal
3. **Template Reuse**: Will reuse existing `downtime/play/_result_modal.html` and `downtime/play/_wheel.html` templates
4. **Spend Logic**: Will reuse existing `downtime.services.spend()` function

### Files to Create/Modify
1. **NEW**: `accounts/views/dashboard_downtime.py` - partial endpoint view
2. **MODIFY**: `accounts/dashboard_providers.py` - add `DowntimeDashboardProvider` class
3. **MODIFY**: `templates/accounts/_dashboard_downtime.html` - new template with spend buttons
4. **MODIFY**: `accounts/urls.py` - add partial endpoint URL
5. **MODIFY**: `accounts/apps.py` - register the new provider

### Next Steps for Code Stage
1. Implement `DowntimeDashboardProvider` in `dashboard_providers.py`
2. Create `dashboard_downtime.py` view with GET (wheel modal) and POST (spend + result modal)
3. Update `_dashboard_downtime.html` template with HTMX buttons
4. Add URL route in `accounts/urls.py`
5. Register provider in `accounts/apps.py`
6. Run tests to verify

### Acceptance Criteria (deferred to code stage)
- "Downtime" section (provider order 4) shows "Spend on [Action]" per affordable action
- Button opens spinning wheel modal (D3) directly via HTMX
- Disabled with reason if not enough points
- Wheel result toast + dashboard downtime balance refresh
- Ruff clean, unit + browser tests pass