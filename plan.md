# Implementation Plan: S2 Trade Dashboard Widget

## Overview
Enhance the existing "My Trades" dashboard provider to show open trades with status badges matching U78 wording and "Act Now" buttons linking to correct pages. Add HTMX polling every 10s.

## Files to Modify

### 1. `accounts/views/dashboard.py`
- **Modify `TradesProvider` class:**
  - Update `get_context()` to return detailed trade data including:
    - Trade object, other character, user's side (sender/receiver)
    - Status badge text (from `trade_status_line` function)
    - "Act Now" button URL and label based on trade status and user's side
  - Update `should_show()` to return `True` only if user has open trades

### 2. `templates/accounts/_dashboard_trades.html`
- **Rewrite template to:**
  - Show each trade as a list item with:
    - Other character name
    - Status badge (using U78 wording from `trade_status_line`)
    - Primary "Act Now" button linking to correct page:
      - REQUESTED + receiver → `trades:edit_side` (Accept)
      - REQUESTED + sender → `trades:detail` (Cancel)
      - ACCEPTED + not approved → `trades:edit_side` (Change)
      - ACCEPTED + approved, other not → `trades:detail` (Approve)
      - ACCEPTED + both approved → completed (no action)
  - Add HTMX polling: `hx-get` to dashboard partial endpoint, `hx-trigger="every 10s"`, `hx-swap="outerHTML"`

### 3. `accounts/urls.py`
- **Already has** `/dashboard/<slug>/partial/<provider_key>/` endpoint
- The existing `dashboard_partial` view will work for `provider_key="trades"`

### 4. Register provider (already done in `accounts/apps.py`)
- `TradesProvider` is already registered with `order=2`

## Key Logic for "Act Now" Button

| Trade Status | User Side | Button Label | Target URL |
|--------------|-----------|--------------|------------|
| REQUESTED | receiver | "Accept" | `trades:edit_side` |
| REQUESTED | sender | "Cancel" | `trades:detail` (or cancel endpoint) |
| ACCEPTED | viewer (not approved) | "Change" | `trades:edit_side` |
| ACCEPTED | viewer (approved, other not) | "Approve" | `trades:detail` |
| ACCEPTED | both approved | — | — (completed) |

## Testing
- Unit tests for `TradesProvider.get_context()` with various trade states
- Browser test for dashboard display with HTMX polling
- Ruff clean

## Acceptance Criteria Mapping
- [ ] "My Trades" section on dashboard (provider order 2) → `TradesProvider.order = 2`
- [ ] Lists each open trade with: other character, status badge, primary action button → Template + provider context
- [ ] Status badges match U78 wording → Use `trade_status_line` function
- [ ] "Act Now" button links to correct page → Logic in provider
- [ ] HTMX poll refreshes widget every 10s → Template with `hx-trigger="every 10s"`
- [ ] Only shows for player with open trades → `should_show()` checks for open trades
- [ ] Ruff clean, unit + browser tests pass → Run tests