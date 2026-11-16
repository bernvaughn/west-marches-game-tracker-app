# Handoff: S8 Bulk Award for GMs - Plan Complete

## What Was Done

1. **Explored the codebase** to understand existing patterns:
   - `player_characters/views/character_adjust.py` - existing adjust/consume views
   - `player_characters/forms_adjust.py` - AdjustForm, ConsumeForm
   - `player_characters/forms.py` - ItemLineForm and formset utilities
   - `ledger/services.py` - `record_many` for atomic ledger entry creation
   - `downtime/views/points.py` - D5 points award (character checklist pattern)
   - `downtime/templates/downtime/points_award.html` - character checklist UI
   - `accounts/navigation.py` - navigation registration system
   - `downtime/apps.py` - GM navigation registration example

2. **Created implementation plan** (`S8_plan.md`) covering:
   - New `bulk_award` view in `player_characters/views/character_adjust.py`
   - New form classes in `player_characters/forms_adjust.py`
   - New template `templates/player_characters/characters/bulk_award.html`
   - URL in `player_characters/urls.py` (club-level: `/characters/<club_slug>/bulk-award/`)
   - GM navigation entry in `player_characters/apps.py` (or `downtime/apps.py`)

3. **Set acceptance criteria** (`S8_acceptance.md`) with 21 items across plan, code, review, verify stages

## Key Design Decisions

### URL Structure
- Club-level URL: `/characters/<club_slug>/bulk-award/` (not per-character)
- This matches the D5 points award pattern

### Form Design
- Character checklist using `ModelMultipleChoiceField` with `CheckboxSelectMultiple` (like D5)
- Per-character coins input (dynamic fields per selected character)
- Per-character item rows using formsets (autocomplete item select, quantity, optional value override)
- Shared note + date fields

### Atomic Submission
- Use `ledger.services.record_many()` which handles atomic batch creation
- Each selected character gets one LedgerEntry with their coins/items

### Permissions
- `@admin_or_gm_required` decorator (same as existing adjust views)
- Navigation entry uses `is_gm_or_admin` check

### Navigation
- Register in `player_characters/apps.py` (or `downtime/apps.py`) under "gm" group
- Label: "Award Loot to Party"
- Order: ~20 (after Downtime points at 15)

## Files to Create/Modify (for Code Stage)

1. **`player_characters/views/character_adjust.py`** - Add `bulk_award` view
2. **`player_characters/forms_adjust.py`** - Add form classes
3. **`templates/player_characters/characters/bulk_award.html`** - New template
4. **`player_characters/urls.py`** - Add club-level URL pattern
5. **`player_characters/apps.py`** - Register GM navigation entry

## Next Steps for Code Stage

1. Implement the form classes in `forms_adjust.py`
2. Implement the `bulk_award` view in `character_adjust.py`
3. Create the template `bulk_award.html`
4. Add URL in `urls.py`
5. Register navigation in `apps.py`
6. Run ruff and tests to verify