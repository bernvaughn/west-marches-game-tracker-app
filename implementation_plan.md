## Implementation Plan

### Overview
Set default value of 10 for all six ability score fields (strength, dexterity, constitution, intelligence, wisdom, charisma) on the Character model. This ensures new characters start with standard D&D ability scores that players can adjust up or down.

### Files to Change

1. **player_characters/models.py** - Add `default=10` to all six ability field definitions
2. **Generated migration** - Django will create a migration to add the defaults

### Detailed Steps

#### 1. Update Character Model
Modify the `_ability_field()` helper function in `player_characters/models.py` to include `default=10`. This will apply to all six ability fields since they all use this helper.

Current code:
```python
def _ability_field():
    return models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text="Optional. Whole number from 1 to 30.",
    )
```

New code:
```python
def _ability_field():
    return models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text="Optional. Whole number from 1 to 30.",
    )
```

Note: Keeping `null=True, blank=True` allows existing characters with NULL abilities to remain unchanged, while new characters get the default of 10.

#### 2. Generate and Apply Migration
Run `python manage.py makemigrations player_characters` to create the migration, then `python manage.py migrate` to apply it.

#### 3. Verify Behavior
- Test character creation via UI shows 10 for all abilities
- Test character detail view displays "10 (+0)" for all abilities
- Test existing characters with NULL abilities still show "—" 
- Run existing test suite to ensure no regressions

### Testing Strategy
- Existing tests in `player_characters/tests/characters/` cover character creation and editing
- Key tests to verify: `test_create_with_level`, `test_player_owner_fixed`, `test_privileged_create_for_member`
- The `test_create_page_has_no_current_column` test verifies the create form has no "Current" column (expected for new characters)
- After change, the form should show 10 as the input value (not blank)

### Rollback Plan
If issues arise, revert the model change and run `python manage.py migrate player_characters <previous_migration>` to rollback.