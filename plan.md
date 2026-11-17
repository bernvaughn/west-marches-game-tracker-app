# Implementation Plan: apply_starting_equipment Service

## Goal
Create `starting_equipment/services.py` with the `apply_starting_equipment()` function that uses the ledger's `record()` function to create starting equipment entries.

## Files to Create/Modify

### 1. Create `starting_equipment/services.py`
New file with the `apply_starting_equipment()` function that:
- Takes `character`, `template`, and `actor` (User) as parameters
- Queries class entries matching character's class and level (case-insensitive, level range)
- Queries background entries matching character's background (case-insensitive)
- Queries level coins for characters above level 1
- Queries approved magic item requests for the character
- Builds lines using the ledger's `Line` dataclass
- Calls `ledger.services.record()` to create a single ledger entry with kind "award"
- Returns the ledger entry or `None` if no lines

### 2. Create `starting_equipment/tests/test_services.py`
Unit tests covering:
- Class equipment matching (case-insensitive char_class, level range)
- Background equipment matching (case-insensitive background)
- Level-based coins for level > 1
- Approved magic item requests only (not pending/declined)
- Empty template (no matching entries)
- No template provided
- Multiple approved magic item requests

## Implementation Details

### Service Function Signature
```python
def apply_starting_equipment(
    character: "Character",
    template: "StartingEquipmentTemplate",
    actor: "User"
) -> "LedgerEntry | None":
```

### Query Logic
1. **Class equipment**: `template.class_entries.filter(char_class__iexact=character.char_class, min_level__lte=level, max_level__gte=level).first()`
2. **Background equipment**: `template.background_entries.filter(background__iexact=character.background).first()`
3. **Level coins**: `template.level_coins.filter(level=character.level).first()` (only if level > 1)
4. **Magic requests**: `StartingEquipmentRequest.objects.filter(character=character, status=StartingEquipmentRequest.Status.APPROVED)`

### Ledger Integration
- Import `Line` from `ledger.services`
- Import `record` from `ledger.services`
- Use `record(character, "award", lines, note="Starting equipment", actor=actor)`

## Dependencies
- SE1 (models) - already done
- SE2 (Character.background field) - already done (field exists in model)
- ledger.services.record() - already exists

## Testing Approach
- Use pytest with Django test database
- Create fixtures for character, template, items, club, user
- Test each equipment type independently and in combination
- Verify ledger entry is created with correct lines