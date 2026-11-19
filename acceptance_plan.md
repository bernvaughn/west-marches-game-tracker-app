## plan
- [x] Implementation plan written and accepted

## code
- [ ] Remove Trade import, OPEN constant, and open_trades logic from HeaderDashboardProvider.get_context()
- [ ] Remove open_trades assertions from accounts/tests/test_dashboard_header.py
- [ ] Remove open_trades assertions from accounts/tests/test_dashboard_context_standardization.py

## verify
- [ ] accounts dashboard tests pass with no Trade/OPEN/open_trades references remaining in dashboard_providers.py