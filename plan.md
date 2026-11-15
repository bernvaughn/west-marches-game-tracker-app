# Implementation Plan: Double-check Player Dashboard with Contextual Quick Actions

## Task Summary
Review PR #211 (Player Dashboard with Contextual Quick Actions) for correctness, side effects, and adherence to acceptance criteria.

## Acceptance Criteria Analysis

| # | Criterion | Status | Notes |
|---|-----------|--------|-------|
| 1 | Dashboard shows right quick actions for player with character, sensible state for player without one | ✅ PASS | Two templates: `dashboard.html` (with character) and `dashboard_no_character.html` (without) |
| 2 | Each quick action goes to right page/does right thing | ✅ PASS | All 6 sections link to correct URLs (shops, quests, trades, downtime, map, messages) |
| 3 | Dashboard works at 390px, 768px, 1280px with no sideways scroll | ✅ PASS | CSS grid with `minmax(280px, 1fr)`; single column ≤575px; screenshot tests at 390px & 1280px |
| 4 | Test suite and CI pass on main | ✅ PASS | 1942 tests pass, 2 skipped |
| 5 | No page outside dashboard changed behavior by accident | ⚠️ NEEDS VERIFICATION | 29 files changed across 7 dirs; many test files updated to follow redirects (expected) |
| 6 | Anything wrong fixed in this story, or filed as own bug | ⚠️ NEEDS FIX | Linting issues in new `dashboard.py`: unused imports, unused variable, import sorting |

## Issues Found

### 1. Linting Issues in New Code (Must Fix)
File: `accounts/views/dashboard.py`
- Unused imports: `ledger.services.coin_balance`, `player_characters.inventory.inventory_rows`, `player_characters.models.Character`
- Unused variable: `junk_val_formatted` (line 111)
- Import block un-sorted/un-formatted

### 2. Potential hx-swap Issue (Investigate)
File: `templates/accounts/_dashboard_header.html`
- Character switch button uses `hx-post` + `hx-target="body"` + `hx-swap="outerHTML"`
- Per workspace knowledge: hx-swap on container can break modal triggers inside it
- **Mitigation**: Button is not a container; no modal triggers inside dashboard header. Likely safe.

### 3. Test Coverage Gap
- No dedicated unit tests for dashboard view logic
- Screenshot tests cover rendering at 390px/1280px for alice/bob roles
- Consider adding unit tests for context building logic

## Plan

### Phase 1: Fix Linting Issues (Required)
1. Fix imports in `accounts/views/dashboard.py`:
   - Remove unused imports
   - Remove unused variable `junk_val_formatted`
   - Sort imports properly
2. Run ruff to verify fixes

### Phase 2: Verify No Accidental Behavior Changes
1. Review all 29 changed files from PR #211
2. Confirm test file changes are only redirect-following updates
3. Verify no functional changes to non-dashboard pages

### Phase 3: Verify Responsive Design
1. Confirm CSS grid behavior at 390px, 768px, 1280px
2. Run screenshot tests to verify rendering

### Phase 4: Final Verification
1. Run full test suite
2. Confirm all acceptance criteria met
3. Document any remaining issues as follow-up bugs if needed

## Files to Modify
- `accounts/views/dashboard.py` - Fix linting issues

## Proof Stages
- **review**: All acceptance criteria verified
- **verify**: Linting clean, tests pass, no regressions