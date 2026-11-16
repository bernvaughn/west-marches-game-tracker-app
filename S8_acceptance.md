## Plan
- [x] Implementation plan written and saved
- [x] Acceptance criteria defined for each proving stage

## Code
- [ ] New `bulk_award` view in `player_characters/views/character_adjust.py`
- [ ] New form classes in `player_characters/forms_adjust.py`
- [ ] New template `templates/player_characters/characters/bulk_award.html`
- [ ] URL added in `player_characters/urls.py` (club-level, not per-character)
- [ ] GM navigation entry added in `downtime/apps.py` (or `player_characters/apps.py`)
- [ ] Uses `ledger.services.record_many` for atomic entry creation
- [ ] Success toast + redirect to club ledger filtered to new entries
- [ ] Only GM/admin access (`@admin_or_gm_required`)
- [ ] Ruff clean (no linting errors)

## Review
- [ ] Code review passes
- [ ] Unit tests for view and form logic
- [ ] Browser test for full flow

## Verify
- [ ] New "Award Loot to Party" page in GM menu (navigation entry)
- [ ] Form: character checklist (select all/none), per-character coins + item rows, shared note + date
- [ ] Item rows: autocomplete from catalogue, quantity, override value optional
- [ ] Submit creates ledger entries atomically (all or nothing)
- [ ] Success toast + redirect to club ledger filtered to new entries
- [ ] Only GM/admin; players never see
- [ ] Ruff clean, unit + browser tests pass