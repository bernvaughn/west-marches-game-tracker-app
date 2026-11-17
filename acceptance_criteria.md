## plan
- [ ] Define acceptance criteria for all stages
- [ ] Write implementation plan with file list and design decisions

## code
- [ ] Create `core/services.py` with `BaseService` (transaction handling) and `ClubScopedService` (club scoping)
- [ ] Add documentation in module docstring
- [ ] Refactor at least one existing service (ledger/services.py or downtime/services.py) to use base classes
- [ ] Add tests for base class behavior

## review
- [ ] Code review passes
- [ ] All existing tests pass
- [ ] New tests for base classes pass

## verify
- [ ] All tests pass (existing + new)
- [ ] No regressions in ledger, downtime, or trade services