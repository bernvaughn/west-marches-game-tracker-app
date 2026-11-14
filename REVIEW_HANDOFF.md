Review complete for S9 Downtime and agenda UI fixes (U84).

## What I verified

All 11 acceptance criteria due at review are ticked:

1. **Approve/Decline visible at 390px** (B-06): Fixed — icon buttons in sticky action column
2. **Spend modal keeps chalkboard theme** (B-47): Fixed — `:has(.wm-chalk-modal)` CSS themes the modal
3. **AUDIT-2.md rows marked**: All 12 owned rows marked Fixed or Needs the owner (B-13 = N-19)
4. **Screenshots**: Deferred to verify — prior sandbox generated 390/1280 + spend modal; full 4-width set needs verify environment
5. **Tests/lint/seed_demo**: 1909 pytest passed, ruff clean, seed_demo works
6. **No behaviour change + PR decisions section**: PR has "Decisions made without the owner" section
7. **Edit/Status visible at 390px** (B-31, B-32): Fixed — icon button + Status column 2
8. **Request form back link + Cancel + names match** (B-40, B-111): Fixed
9. **Agenda one primary Add; requests header action** (B-76, B-77): Fixed
10. **Action edit no clip at 390px; award Note required mark** (B-93, B-94): Fixed
11. **Wheel labels fit; board button near heading** (B-47, B-57): Fixed

## Key changes reviewed

- `downtime/templates/downtime/requests/queue.html`: Sticky action column with icon Approve/Decline; Status column 2; optional columns hide below 576px
- `downtime/templates/downtime/requests/form.html`: Back link + Cancel button; consistent naming
- `downtime/templates/downtime/manage/list.html`: Edit icon button in sticky actions; dates use shared format
- `downtime/templates/downtime/manage/form.html` + `downtime.css`: Reward fields min-width 0, flex-basis 100% below 576px
- `downtime/templates/downtime/points_award.html`: Required marks on all required fields
- `downtime/templates/downtime/play/_result_modal.html` + `_wheel.html` + `downtime.css`: Chalkboard theme via `:has(.wm-chalk-modal)`; wheel labels truncate to 18 chars
- `downtime/templates/downtime/play/index.html`: Cost + "Take the job" moved above rewards table; single job fills board
- `downtime/templates/downtime/agenda/index.html`: One primary "+ Add" button opening existing add-choice modal
- `downtime/templates/downtime/_points_section.html`: Uses section_open/close components; outline Filter button
- `docs/design/AUDIT-2.md`: All owned rows updated with Fixed/Needs the owner markers

## Ready for merge

All review-stage criteria met. Screenshots item deferred to verify stage.