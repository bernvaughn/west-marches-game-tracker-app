# Implementation Plan: Print Loot Cards (U92)

## Overview
Add a new feature for game masters and club admins to print loot cards from the catalogue. Reuses the item card design from U90 and magic item type from U93.

## Files to Create

### 1. `items/views.py` - Add two new views
- **`loot_cards_picker(request, club_slug)`** - GET only
  - Decorator: `@admin_or_gm_required`
  - Lists club's catalogue items (non-retired) with:
    - Quantity input (number, min=0, default=0) per item
    - Search filter (plain GET, filters by name)
    - Copies choice radio: "One card per item type" / "One card per item"
  - Submits to `loot_cards_print` via GET with query params
  - Template: `items/loot_cards_picker.html`

- **`loot_cards_print(request, club_slug)`** - GET only
  - Decorator: `@admin_or_gm_required`
  - Reads quantities from GET params (e.g., `qty_<pk>=N`)
  - Skips items with quantity 0
  - Validates copies mode (`type` or `item`)
  - Uses `player_characters.item_cards.build_cards`, `chunk`, `too_many`
  - Caps at 90 cards (`CARD_CAP`), shows message if exceeded
  - Renders `items/loot_cards_print.html` with:
    - `sheets` (list of lists of `ItemCard`)
    - `copies` mode
    - `too_many` flag
    - `printed_on` = `timezone.localdate()`
    - `owner=None` (so footer shows "Loot")

### 2. `items/urls.py` - Add two URL patterns
```python
path("loot-cards/", views.loot_cards_picker, name="loot_cards_picker"),
path("loot-cards/print/", views.loot_cards_print, name="loot_cards_print"),
```

### 3. `items/templates/items/loot_cards_picker.html` - New template
- Extends `base.html`
- Page header: title "Print loot cards", back to catalogue
- Search form (GET, `q` param)
- Copies choice: two radio buttons (`copies=type` / `copies=item`)
- Table of catalogue items:
  - Columns: Name, Rarity, Magic Type, Value, Quantity (number input `qty_<pk>`)
  - Pre-filled with search results
- Submit button → `loot_cards_print` with all params
- No-print toolbar with back link

### 4. `items/templates/items/loot_cards_print.html` - New template
- Extends `base.html`
- `main_class = "wm-card-print"`
- Loads `css/print.css`
- No-print: back link to picker, print button, hint
- If `too_many`: include `_too_many.html` (adapted for loot)
- If `layout=full` (default for loot): each card in `.wm-card-page` with `full=True`
- Else (grid): 3×3 sheets using `_item_card.html`, pad with empty cells
- Pass `owner=None` to `_item_card.html` → footer shows "Loot · printed YYYY-MM-DD"

### 5. `items/templates/items/index.html` - Modify
- Add "Print loot cards" action to page header (only for `is_admin` or `is_game_master`)
- Action URL: `items:loot_cards_picker`
- Icon: `printer` (or `box-seam`)

### 6. `items/tests/test_u92_loot_cards.py` - New test file
Tests tagged `@pytest.mark.story("U92")`:
- **Permissions**: player gets 403; GM and club admin get 200
- **Picker**: lists club items with qty=0 default; search filters; copies choice present
- **Print**: qty=0 items skipped; both copies modes; 90-card cap message; footer "Loot · date"
- **No side effects**: no LedgerEntry/LedgerLine created; no inventory changes
- **Cross-club isolation**: another club's items never appear in picker or print

## Reused Components
- `player_characters.item_cards`: `build_cards`, `chunk`, `too_many`, `CARD_CAP`, `CARDS_PER_SHEET`
- `player_characters/templates/player_characters/characters/_item_card.html` (supports `owner=None`)
- `player_characters/templates/player_characters/characters/_too_many.html` (adapt for loot)
- `accounts.permissions.admin_or_gm_required`
- `accounts.scoping.club_queryset`, `club_get_object_or_404`

## Acceptance Criteria Mapping
| Criterion | Stage |
|-----------|-------|
| Catalogue has "Print loot cards" for GM/admin; player 403 | verify |
| Picker: club items, qty box (0), search, copies choice | verify |
| Print page: U90 card design, 3×3, "Loot" + date footer, qty 0 skipped | verify |
| No inventory/ledger changes; cross-club isolation | verify |
| Tests tagged U92 pass; pytest + ruff pass | verify |

## Decisions Made Without Owner
None — all design decisions inherited from epic spec and U90/U93 implementations.