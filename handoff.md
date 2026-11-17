Hand-off to review for task "Remove Trade/Transfer Navigation Entries" (01a1e7c9-f1d3-7186-bab0-e9718150b902).

## What the change does
The change removes all trade and transfer navigation entries. It also removes the trade dashboard and approval providers.

## Key files and decisions
- player_characters/apps.py: removed the "trades" group ("My trades", "Propose trade") and the "Move items" (characters:transfer_start) entry.
- accounts/apps.py: removed the TradesDashboardProvider and open_trades_needing_action imports and their registrations.
- accounts/approval_providers.py: removed the open_trades_needing_action function.
- accounts/dashboard_providers.py: removed the TradesDashboardProvider class and the OPEN import from trade_services.
- accounts/navigation.py: removed "trades" from GROUPS and MENU_GROUPS.
- Tests updated: test_approvals_indicator.py, test_navigation_menus.py, test_u60_top_bar.py, test_u61_top_bar.py.

## Decisions and rationale
I merged origin/main into the branch. Main had already merged "Delete Trade Code" (#262), so the trade test files were gone and the downtime test now asserts Trades is absent. The transfers deletion story is not merged, so main still had the "Move items" entry. My task owns removing "Move items" from navigation, so I removed it and kept the matching test update. I resolved a conflict in accounts/approval_providers.py and test_navigation_menus.py in favour of my version.

## Verification
The full non-browser suite passes: 1780 passed in about 93 seconds. Ruff passes across the repo. CI pipeline #44161523295 is green (pytest, ruff, pip-audit). Re-recorded test and lint verifications against this green state. typecheck stays pass because the project has no typecheck tool.

## What is open
Nothing is open at the code stage. All 9 code acceptance items are ticked. Items 10 to 15 are deferred to the verify stage.

## What the next stage should do first
Review PR #260. It targets main. Confirm the diff is limited to the navigation and provider removals plus test updates. The non-browser suite and CI already pass, so the risk is low.

## Links
- MR: https://github.com/bernvaughn/west-marches-game-tracker-app/pull/260
- Branch: task/e9718150b902
- Artifact recorded on the task.