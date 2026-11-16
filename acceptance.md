## plan
- [x] Implementation plan written and stored in task plan field

## code
- [ ] "My Trades" section on dashboard (provider order 2)
- [ ] Lists each open trade with: other character, status badge, primary action button
- [ ] Status badges match U78 wording: "Waiting for X to accept", "Both can change. Approve when ready", etc.
- [ ] "Act Now" button links to correct page: `trades:detail` (accepted) or `trades:edit_side` (propose)
- [ ] HTMX poll refreshes widget every 10s (`hx-trigger="every 10s"`)
- [ ] Only shows for player with open trades

## verify
- [ ] Ruff clean
- [ ] Unit tests pass
- [ ] Browser tests pass