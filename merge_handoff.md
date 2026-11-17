# Merge Stage Hand-off: Orphaned Worktree Slots Investigation Complete

## Summary
The investigation into why worktrees are not being cleaned up on the PI device is complete. Both acceptance criteria have been satisfied:

1. ✅ **Message/comment revealing reason for orphaned worktree slots** - Posted in code stage (comment `01a1e6c7-fbc4-75d1-bd27-6078836680aa`)
2. ✅ **Message/comment proposing solutions** - Posted in code stage (same comment) and reviewed in review stage (comment `01a1e6cd-a46a-79f0-b3b1-e0553dd80271`)

## Root Cause
The **CodeHerder device agent** (not the pi coding agent) manages git worktree slots. The pi coding agent's lifecycle gaps prevent the device agent from detecting session end and cleaning up worktrees:

- **No worktree cleanup registered** - Pi coding agent has `registerSessionResourceCleanup()` mechanism but only registers WebSocket cleanup, not worktree cleanup
- **Signal handling gaps** - SIGKILL uncaught, uncaught exceptions call `emergencyTerminalExit()` without `dispose()`, crashes bypass graceful shutdown
- **Device agent detection issues** - Device agent monitors pi process via exit codes/pipes/heartbeats; abnormal exits may not trigger cleanup

## Key Evidence
- 27 orphaned worktree slots on device "PI DEVICE WSL DESKTOP-KQ4S3ST"
- Device health: `unhealthy: worktree_slots (staffable: no)`
- `task.start_refused` with `no_placeable_device`
- `ch device reclaim` returned exit code 1 (didn't resolve)

## Proposed Solutions
1. **Register worktree cleanup in pi agent** - Requires device agent API (may not exist)
2. **Fix device agent reclaim logic** - Periodic orphan scan, auto-cleanup, handle restarts/partitions
3. **Improve pi agent graceful shutdown** - More signal handlers, `uncaughtException` calls `dispose()`, `process.on('exit')`
4. **Session shutdown event for extensions** - Requires device agent cooperation

## Recommendation
The root cause is **in the CodeHerder device agent**, not the pi coding agent. The device agent is responsible for creating and cleaning up worktree slots. The pi coding agent cannot fix this alone because:
1. It doesn't create the worktrees
2. It doesn't have access to the device agent's worktree management
3. Even with perfect pi shutdown, device agent bugs or crashes can leave worktrees orphaned

**Next steps (outside this workspace):**
1. Investigate CodeHerder device agent worktree management code
2. Check if `ch device reclaim` has a known bug
3. Consider filing a bug against the CodeHerder device agent
4. As a mitigation, the pi coding agent could register a "session end" notification that the device agent listens for (requires device agent changes)

## For Verify Stage
No code changes in this workspace were required or made. The investigation is complete. The verify stage should confirm the findings are documented and close the task.