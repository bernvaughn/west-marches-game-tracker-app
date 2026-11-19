# Implementation Plan: S10 Batch Print for Session

## Overview
Add a "Print Session Pack" feature that combines character sheet, item cards, ready quests, and map into a single printable document. The feature includes a button on the dashboard header and a print dialog with options.

## Files to Create/Modify

### 1. `player_characters/views/character_print.py` (modify)
Add new `print_session_pack` view function:
- Accepts `club_slug`, `pk` (character), and query parameters for print options
- Options: `sheet`, `items`, `quests`, `map` (all default to true except map)
- Gathers data from existing sources:
  - Character sheet data (like `characters.detail` view)
  - Item cards grid (reuse `print_items` logic)
  - Ready quests (reuse `QuestsProvider` logic from dashboard)
  - Map data (reuse `map.views.print` logic if selected)
- Renders `print_session_pack.html` template

### 2. `templates/player_characters/characters/print_session_pack.html` (new)
New template combining all sections:
- Extends `base.html`
- Includes `print.css` for print styling
- Sections (each wrapped in conditional blocks based on query params):
  - Character sheet (simplified from `characters/detail.html`)
  - Item cards grid (reuse `characters/print.html` structure)
  - Ready quests (include `quests/_notice.html` for each)
  - Map (include `map/views/print.html` structure if enabled)
- Print dialog options form at top (no-print)
- Uses existing `.wm-card-print` and print CSS classes

### 3. `player_characters/urls_characters.py` (modify)
Add URL pattern:
```python
(
    path(
        "<int:pk>/print-session-pack/",
        character_print.print_session_pack,
        name="print_session_pack",
    ),
)
```

### 4. `templates/accounts/_dashboard_header.html` (modify)
Add "Print Session Pack" button in header (top-right):
- Button opens modal with print options (HTMX partial)
- Or links directly to print page with default options
- Uses existing modal pattern (`data-app-modal`, `hx-get`)

### 5. `templates/accounts/_dashboard_header.html` partial for print options modal (new)
- Modal with checkboxes for: Character Sheet, Item Cards, Ready Quests, Map
- Submit button goes to `print_session_pack` URL with query params

## Print CSS
- Reuses existing `static/css/print.css`
- Ensures `.no-print`, `.wm-toolbar`, buttons, modals, nav are hidden
- Page breaks between major sections
- Fits Letter/A4 paper

## Testing
- Unit tests for view (data gathering, permissions, query params)
- Browser test for print dialog and output
- Ruff lint check

## Acceptance Criteria Mapping

| Criterion | Implementation |
|-----------|----------------|
| "Print Session Pack" button on dashboard (top-right of header) | Added to `_dashboard_header.html` |
| Print dialog options: ☑ Character Sheet, ☑ Item Cards (all, grid), ☑ Ready Quests, ☐ Map | Modal with checkboxes in `_dashboard_header.html` |
| Generates combined print layout using existing print templates | `print_session_pack` view + `print_session_pack.html` template |
| Print CSS hides nav, actions, modals; fits Letter/A4 | Uses existing `print.css` |
| Ruff clean, unit + browser tests pass | Tests in `player_characters/tests/characters/test_print.py` |

## Proof Stages

- **code**: Unit tests pass, view renders correctly, template includes all sections
- **review**: Code review passes
- **verify**: Browser test confirms print output looks correct on Letter/A4, all options work