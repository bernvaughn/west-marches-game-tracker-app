# Implementation Plan: Remove Open Trades from Dashboard Header Provider

## Overview
This task (C4) removes open_trades logic from the dashboard header provider and its tests. The Trade/TradeLine models were already removed in C1 (commit 4a559c3). The dashboard_providers.py was already cleaned of trade logic in round 1 (commit 7c964bb). This task only needs to update the test files to remove open_trades assertions.

## Current State
- `accounts/dashboard_providers.py`: Already clean — no Trade import, no OPEN constant, no open_trades logic in HeaderDashboardProvider.get_context()
- `accounts/tests/test_dashboard_header.py`: On main, has Trade import and open_trades assertions; on this branch (HEAD), already cleaned
- `accounts/tests/test_dashboard_context_standardization.py`: On main, has test_header_provider_includes_trades_data_flat_context; on this branch (HEAD), already cleaned

## Plan
1. **Verify dashboard_providers.py is clean** — Confirm no Trade, OPEN, or open_trades references remain
2. **Update test_dashboard_header.py** — Remove Trade/Character import, remove "open_trades" assertion from test_provider_get_context_returns_expected_keys, delete test_provider_context_open_trades
3. **Update test_dashboard_context_standardization.py** — Delete test_header_provider_includes_trades_data_flat_context
4. **Run tests** — Verify all 12 accounts dashboard tests pass

## Acceptance Criteria Mapping
- Plan: Implementation plan written and accepted
- Code: Three edit items above
- Verify: Accounts dashboard tests pass with no Trade/OPEN/open_trades references in dashboard_providers.py

## Notes
- The work is already complete on this branch (commit 66d9da6). This plan documents the completed changes.
- Peer task C2 (ledger services) must land first for full test suite to pass, but accounts dashboard tests are self-contained and pass now.