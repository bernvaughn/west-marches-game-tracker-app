# Implementation Plan: S0 Dashboard Extension Contract

## Overview
Establish the dashboard provider system, HTMX partial endpoints, character preview API, and template patterns that all other workflow enhancement stories depend on.

## Files to Create/Modify

### 1. New File: `accounts/dashboard_providers.py`
- Define `DashboardProvider` protocol (TypedDict or Protocol class)
- Define registry functions: `register_provider()`, `get_providers()`, `get_provider(key)`
- Each provider has: `key`, `order`, `template`, `get_context()`, `should_show()`

### 2. Modify: `accounts/apps.py`
- Import and register built-in providers in `ready()`
- Register providers in priority order matching spec (Quick Actions, Trades, Quests, Downtime, Map, Messages, Player Shop, Consumables)

### 3. Modify: `accounts/views/dashboard.py`
- Refactor `_get_dashboard_context()` to iterate over registered providers
- Each provider's `should_show()` determines inclusion
- Each provider's `get_context()` returns context for its template
- Build combined context with `dashboard_providers` list
- Add new HTMX partial endpoint views: `dashboard_partial(request, club_slug, provider_key)`
- Add character preview endpoint: `character_preview(request, club_slug, pk)`

### 4. Modify: `accounts/urls.py`
- Add pattern: `dashboard/<slug:club_slug>/partial/<str:provider_key>/` → `dashboard_partial`
- Add pattern: `characters/<slug:club_slug>/preview/<int:pk>/` → `character_preview`

### 5. Modify: `templates/accounts/dashboard.html`
- Replace static section includes with dynamic loop over `dashboard_providers`
- Each provider renders its template with its context

### 6. New Templates (built-in providers)
Create provider templates for each built-in section:
- `_dashboard_quick_actions.html` (order 1)
- `_dashboard_trades.html` (order 2)
- `_dashboard_quests.html` (order 3)
- `_dashboard_downtime.html` (order 4)
- `_dashboard_map.html` (order 5)
- `_dashboard_messages.html` (order 6)
- `_dashboard_player_shop.html` (order 7)
- `_dashboard_consumables.html` (order 8)

## Provider Structure

```python
# accounts/dashboard_providers.py
from typing import Protocol, Optional
from django.http import HttpRequest

class DashboardProvider(Protocol):
    key: str
    order: int
    template: str
    
    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        ...
    
    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        return True

# Registry
_providers: dict[str, DashboardProvider] = {}

def register_provider(provider: DashboardProvider) -> None:
    _providers[provider.key] = provider

def get_providers() -> list[DashboardProvider]:
    return sorted(_providers.values(), key=lambda p: p.order)

def get_provider(key: str) -> Optional[DashboardProvider]:
    return _providers.get(key)
```

## Built-in Providers (in dashboard.py)

Each section from current `_get_dashboard_context()` becomes a provider:
1. **Quick Actions** - Town items (sell junk, buy potions) - NEW section
2. **Trades** - Open trades with status
3. **Quests** - Ready quests with turn-in
4. **Downtime** - Available actions
5. **Map** - Visible maps
6. **Messages** - Message admins
7. **Player Shop** - Shop status (conditional)
8. **Consumables** - Quick consume items (conditional)

## HTMX Partial Endpoint

`dashboard/<slug>/partial/<provider_key>/`:
- Returns rendered provider template fragment
- Used for: character switch preview, trade status poll, quick-action modals
- Requires `@club_member_required` and character selection
- Returns 404 if provider not found or `should_show()` is False

## Character Preview Endpoint

`characters/<slug>/preview/<pk>/`:
- Returns JSON: `{name, level, class, species, coins_available, junk_count, junk_value, downtime, open_trades}`
- Used by character selector tooltip (hover/focus)

## Acceptance Criteria Mapping

| # | Criteria | Proof Stage |
|---|----------|-------------|
| 1 | `DashboardProvider` protocol defined in `accounts/dashboard_providers.py` | code |
| 2 | Provider registry in `accounts/apps.py` `ready()` | code |
| 3 | `_get_dashboard_context()` refactored to use providers | code |
| 4 | HTMX partial endpoint pattern implemented | code |
| 5 | Character preview endpoint returns JSON | code |
| 6 | `dashboard.html` renders providers dynamically in order | code |
| 7 | All existing dashboard functionality preserved (tests pass) | verify |
| 8 | Ruff clean, 1942+ tests pass | verify |

## Testing Strategy

### Unit Tests (code stage)
- Test provider registration and ordering
- Test `should_show()` logic for each provider
- Test `get_context()` output for each provider
- Test HTMX partial endpoint returns correct fragment
- Test character preview JSON structure

### Integration Tests (verify stage)
- Run full test suite (1942+ tests)
- Verify dashboard renders with all providers
- Verify character switch preview works
- Verify no regressions in existing functionality

### Ruff Check (verify stage)
- Run `uv run ruff check .` and fix any issues

---

# Implementation Plan: S3 Character Switch Preview

## Overview
Add Bootstrap tooltip on character selector dropdown showing character preview (coins, junk, downtime, open trades) fetched via HTMX on hover/focus.

## Files to Modify

### 1. `player_characters/views/selection.py`
Add `character_preview` view:
- Accept `club_slug` and `pk` parameters
- Verify character belongs to current club and user owns it
- Return JSON with: `name`, `level`, `class`, `species`, `coins_available` (int), `coins_formatted` (string), `junk_count`, `junk_value`, `downtime`, `open_trades`
- Reuse logic from `selector_context.character_selector_context()`

### 2. `player_characters/urls_characters.py`
Add URL pattern:
- Path: `<int:pk>/preview/`
- Name: `preview`
- View: `selection.character_preview`

### 3. `templates/player_characters/characters/_selector.html`
Convert native `<select>` to Bootstrap dropdown:
- Replace `<select>` with dropdown button + `<ul class="dropdown-menu">`
- Each character becomes `<a class="dropdown-item">` with:
  - `data-bs-toggle="tooltip"`
  - `data-bs-html="true"`
  - `data-wm-preview-url="{% url 'characters:preview' club.slug c.pk %}"`
  - `title="Loading…"` (placeholder)
  - `onclick` to submit the character switch form
- Keep hidden form for POST submission

### 4. `static/js/tooltips.js`
Add handler for `shown.bs.tooltip` on elements with `data-wm-preview-url`:
- Fetch preview URL via `fetch()` (not HTMX, since we need JSON)
- Build HTML card from JSON response
- Update tooltip content using `tooltip.setContent({ '.tooltip-inner': html })`
- Handle loading/error states
- Ensure tooltip is disposed on `hide.bs.tooltip` or dropdown close

## Testing

### Unit Tests (`player_characters/tests/test_selection.py`)
- Test `character_preview` returns correct JSON structure
- Test 403 for other player's character
- Test 404 for non-existent character
- Test 404 for character not in club

### Browser Tests (Playwright)
- Test tooltip appears on hover/focus
- Test tooltip shows correct data
- Test mobile tap behavior
- Test tooltip dismisses on click elsewhere

## Acceptance Criteria Mapping

| AC | Proof Stage |
|----|-------------|
| Selector dropdown options show Bootstrap tooltip on hover/focus | code (unit + browser) |
| Tooltip fetches `/characters/<slug>/preview/<pk>/` via HTMX on `shown.bs.tooltip` | code (browser) |
| Preview JSON: `{name, level, class, species, coins_available, junk_count, junk_value, downtime, open_trades}` | code (unit) |
| Tooltip renders as small card with avatar, key stats | code (browser) |
| Works on mobile (tap to show, tap elsewhere to dismiss) | code (browser) |
| Ruff clean, unit + browser tests pass | verify |