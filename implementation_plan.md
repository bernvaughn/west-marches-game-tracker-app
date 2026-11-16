# Implementation Plan: S5 Downtime Spend from Dashboard

## Overview
Add "Spend on [Action]" buttons for available downtime actions that open the spinning wheel modal directly via HTMX from the dashboard.

## Files to Create/Modify

### 1. New Provider: `accounts/dashboard_providers.py`
- Add `DowntimeDashboardProvider` class that extends the provider pattern
- Reuse existing downtime action detection logic from `dashboard.py`
- Return context with actions, costs, and affordability

### 2. New View: `accounts/views/dashboard_downtime.py`
- Create partial endpoint for wheel modal: `/dashboard/<slug>/partial/downtime_spend/<action_pk>/`
- Handle HTMX GET to return wheel modal partial
- Handle POST to spend points and return result modal
- Reuse existing `downtime.services.spend()` function

### 3. New Template: `templates/accounts/_dashboard_downtime.html`
- Replace existing template with new version that has "Spend on [Action]" buttons
- Buttons use HTMX (`hx-get` + `data-app-modal`) to open wheel modal
- Disabled with reason if not enough points
- Wheel result toast + dashboard downtime balance refresh

### 4. URL Configuration: `accounts/urls.py`
- Add partial endpoint for downtime spend: `dashboard/partial/downtime_spend/<int:action_pk>/`

### 5. Register Provider: `accounts/apps.py`
- Register `DowntimeDashboardProvider` in `ready()` method

## Acceptance Criteria Mapping

| AC | Implementation |
|----|----------------|
| "Downtime" section (provider order 4) shows "Spend on [Action]" per affordable action | `DowntimeDashboardProvider` with order=4, template renders spend buttons |
| Button opens spinning wheel modal (D3) directly via HTMX | `hx-get` to `/dashboard/<slug>/partial/downtime_spend/<action_pk>/` with `data-app-modal` |
| Disabled with reason if not enough points | Provider context includes `reason` for each action, button disabled if reason exists |
| Wheel result toast + dashboard downtime balance refresh | View returns result modal on POST, dashboard refreshed via HX-Redirect |

## Implementation Steps

1. **Create `accounts/views/dashboard_downtime.py`** - new view for the partial endpoint
2. **Update `accounts/dashboard_providers.py`** - add `DowntimeDashboardProvider` class
3. **Update `templates/accounts/_dashboard_downtime.html`** - new template with spend buttons
4. **Update `accounts/urls.py`** - add the partial endpoint URL
5. **Update `accounts/apps.py`** - register the new provider
6. **Run tests** - verify Ruff clean, unit tests pass

## Key Technical Details

- The wheel modal is rendered by `downtime/play/_result_modal.html` which includes `_wheel.html`
- The `downtime.views.play.spend()` function handles the spend logic - we'll reuse it
- HTMX partial should return the wheel modal on GET, and result modal on POST
- Need to handle HTMX vs full page requests properly using `render_modal_or_page`

## Testing

- Unit test for provider `get_context` and `should_show`
- Unit test for partial view GET and POST
- Browser test for full spend flow from dashboard