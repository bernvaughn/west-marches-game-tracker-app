# Implementation Plan: S12 Consumable Quick-Consume

## Overview
Add a dashboard section for consumable items with "Use 1" confirm buttons that open a modal and record a consume ledger entry.

## Files to Create/Modify

### 1. `accounts/dashboard_providers.py` - Add ConsumablesDashboardProvider
- Add new `ConsumablesDashboardProvider` class with:
  - `key = "consumables"`
  - `order = 8`
  - `template = "accounts/_dashboard_consumables.html"`
  - `get_context()`: Find items where `quantity > 1` OR `traits` contains "consumable" (case-insensitive)
  - `should_show()`: Return True if any consumable items exist
- Register provider in `accounts/apps.py` ready() (replace existing ConsumablesProvider import)

### 2. `accounts/views/dashboard_consumables.py` (NEW)
- Create new view `consumable_consume_partial(request, club_slug, item_pk)`
- Returns HTMX modal fragment for confirm modal
- Uses existing `player_characters.views.consume.player_consume` logic
- Requires `@club_member_required`, character ownership check
- Returns 404 if item not available or not consumable

### 3. `templates/accounts/_dashboard_consumables.html` (MODIFY)
- Update existing template
- Change "Consume" link to "Use 1" button with HTMX attributes:
  - `hx-get="{% url 'accounts:consumable_consume_partial' club.slug item.pk %}"`
  - `hx-target="#app-modal .modal-content"`
  - `data-app-modal`
- Show item name, quantity, and "Use 1" button per row

### 4. `templates/accounts/modals/_consume_confirm.html` (NEW)
- Create confirm modal template extending `components/modal_frame.html`
- Title: "Consume 1 [Item]?"
- Body: Form with quantity (default 1, hidden or shown), note field (optional)
- Uses `PlayerConsumeForm` for validation
- Submit to `characters:player_consume` endpoint
- Footer: Cancel + "Consume" button

### 5. `accounts/urls.py` (MODIFY)
- Add URL pattern:
  ```python
  (
      path(
          "dashboard/partial/consumable_consume/<int:item_pk>/",
          dashboard_consumables.consumable_consume_partial,
          name="consumable_consume_partial",
      ),
  )
  ```

### 6. `accounts/apps.py` (MODIFY)
- Replace import of `ConsumablesProvider` from `accounts.views.dashboard` with `ConsumablesDashboardProvider` from `accounts.dashboard_providers`
- Register the new provider

## Detection Logic
```python
def _is_consumable(self, item, quantity):
    # Item is consumable if:
    # 1. quantity > 1, OR
    # 2. traits contains "consumable" (case-insensitive)
    if quantity > 1:
        return True
    if item.traits and "consumable" in item.traits.lower():
        return True
    return False
```

## Acceptance Criteria Mapping
| Criteria | Proof Stage |
|----------|-------------|
| "Consumables" section (provider order 8) shows items with `quantity > 1` or "consumable" trait | code (unit test) |
| Each row: item name, qty, "Use 1" button | code (browser test) |
| Button opens confirm modal: "Consume 1 [Item]?" + optional note | code (browser test) |
| Confirm records consume ledger entry (player-initiated, U82) | code (unit test) |
| Ruff clean, unit + browser tests pass | verify |

## Test Strategy
- Unit tests for provider detection logic (quantity > 1, traits contains "consumable")
- Unit tests for partial endpoint (GET returns modal, 404 for non-consumable/non-available)
- Browser test for full flow: dashboard → click "Use 1" → modal opens → confirm → ledger entry created
- Ruff check on all new/modified files