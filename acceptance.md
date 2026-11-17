## code
- [ ] Create `starting_equipment/services.py` with `apply_starting_equipment()` function
- [ ] Function handles class equipment (case-insensitive class match, level range filter)
- [ ] Function handles background equipment (case-insensitive background match)
- [ ] Function handles level-based coins (for level > 1)
- [ ] Function handles approved magic item requests (status=APPROVED only)
- [ ] Function uses ledger's `record()` to create a single "award" ledger entry
- [ ] Function returns the LedgerEntry or None if no lines to grant
- [ ] Create `starting_equipment/tests/test_services.py` with unit tests
- [ ] Tests cover class match (case-insensitive), background match, level coins, magic requests, empty template
- [ ] All tests pass

## review
- [ ] Code follows project conventions (type hints, docstrings, error handling)
- [ ] No console errors when running tests
- [ ] Service integrates correctly with ledger's record() function

## verify
- [ ] apply_starting_equipment() works end-to-end with real data
- [ ] Ledger entries are created correctly with all equipment types
- [ ] No regressions in existing ledger tests