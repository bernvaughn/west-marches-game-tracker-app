# S1: Item weight field and its display (U154) - Implementation Plan

## Overview
Add an optional `weight_hundredth_lb` field to `Item`, a helper module `items/weights.py`, and expose weight on the item form, item detail, item card, shop lines, and agent `search_items`.

## Files to Change

### 1. items/models.py
- Add `weight_hundredth_lb = models.PositiveIntegerField(null=True, blank=True)` to `Item` model
- This stores weight in hundredths of a pound (integer) to avoid float issues
- Null means "not listed", never zero

### 2. Migration (auto-generated)
- Run `makemigrations items` to create migration for the new field

### 3. items/weights.py (NEW FILE)
Create helper module with:
- `format_weight(hundredths: int | None, precision: int = 1) -> str`
  - Returns "not listed" for None
  - Formats with specified decimal places (default 1)
  - For stacked items' totals, caller passes precision=2
- `item_weight_total(item: Item, units: int) -> int | None`
  - Returns total weight in hundredths for `units` of the item
  - For stacked items: `item.weight_hundredth_lb * units`
  - For non-stacked: `item.weight_hundredth_lb` (units ignored, always 1)
  - Returns None if item.weight_hundredth_lb is None

### 4. items/forms.py
- Add `weight` field to `ItemForm` (IntegerField, min_value=0, required=False)
- Label: "Weight (hundredths of lb)"
- Help text: "Weight of one unit in hundredths of a pound. Leave blank if unknown."
- In `__init__`: set initial from `instance.weight_hundredth_lb`
- In `save`: save `weight_hundredth_lb` from cleaned data

### 5. items/templates/items/_details_body.html
- Add weight display row in the definition list
- Use `format_weight` template filter (to be created) or call helper in view
- Show "not listed" when blank

### 6. player_characters/templates/player_characters/characters/_item_card.html
- Add weight pill in the pills section
- For stacked items: show per-unit weight and total for the card's quantity
- Use `format_weight` with appropriate precision

### 7. shops/templates/shops/browse/_stock.html
- Add weight column or inline display in the stock row
- Show per-unit weight for stacked items

### 8. agent_access/mcp/tools_lookup.py
- In `search_items` tool, add weight fields to returned item data:
  - `weight_hundredth_lb` (raw integer or null)
  - `weight` (formatted string, "not listed" or "X.Y lb")
  - For stacked items: `weight_per_unit` and `weight_total_for_bundle` (if bundle_units available)

### 9. Template tags (items/templatetags/weights.py - NEW)
- Create `weight_display` filter that uses `format_weight`
- Allows easy use in templates: `{{ item.weight_hundredth_lb|weight_display }}`

### 10. Tests (items/tests/test_weights.py - NEW)
- Test `format_weight`: None -> "not listed", 125 -> "1.3 lb", 125 with precision=2 -> "1.25 lb"
- Test `item_weight_total`: stacked items scale with units, non-stacked don't
- Test form: blank weight saves as None, not zero
- Test detail template: shows "not listed" when blank
- Test card template: shows weight correctly for stacked/non-stacked
- Test shop template: shows weight
- Test agent search_items: includes weight fields
- Test that weight never blocks buy/sale/award/opening (integration test)

## Acceptance Criteria Mapping

| Criterion | Files | Test |
|-----------|-------|------|
| Blank weight displays as "not listed" and never zero | weights.py, templates | test_format_weight_none, test_form_blank_not_zero |
| Stacked items: weight per unit, totals scale | weights.py, templates | test_item_weight_total_stacked |
| Display format: 1 decimal (2 for stacked totals) | weights.py, templates | test_format_weight_precision |
| Agent search_items includes weight | tools_lookup.py | test_search_items_includes_weight |
| Weight never blocks buy/sale/award/opening | integration test | test_weight_never_blocks_operations |

## Implementation Order
1. Model + migration
2. weights.py helper
3. Template tag for weights
4. Form field
5. Detail template
6. Card template
7. Shop template
8. Agent search_items
9. Tests

## Decisions Made Without Owner
- Weight stored as hundredths (integer) per design doc
- Default precision 1 decimal for per-unit, 2 decimals for stacked totals
- "not listed" string for blank weight
- Weight field optional on form with help text explaining hundredths
- Template tag in items/templatetags/weights.py for reusability