## Hand-off: Plan Stage Complete for C4 (Remove Open Trades from Dashboard Header Provider)

### What Was Done
- Verified the implementation plan matches the completed work on this branch (commit 66d9da6).
- Confirmed `accounts/dashboard_providers.py` already has no Trade import, OPEN constant, or open_trades logic (cleaned in round 1, commit 7c964bb).
- Confirmed test files on this branch already have open_trades assertions removed.
- All 12 accounts dashboard tests pass.

### Key Decisions
- The dashboard_providers.py did not need changes — it was already clean from round 1 trading removal.
- Only test files needed updates to remove Trade imports and open_trades assertions.

### Verification
- `grep -i trade accounts/dashboard_providers.py` returns only "open_shops" (shop feature, not trades).
- `grep -i "OPEN" accounts/dashboard_providers.py` returns only `Message.Status.OPEN` (message status).
- All 12 dashboard tests pass: 7 in test_dashboard_header.py + 5 in test_dashboard_context_standardization.py.

### Next Steps for Code Stage
The code changes are already committed on this branch. The code stage should verify the changes are correct and the tests pass (already done). No further edits needed.