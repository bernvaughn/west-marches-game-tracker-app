# Implementation Plan: Figure out why worktrees not being cleaned up

## Problem Analysis

The PI device (CodeHerder device "PI DEVICE WSL DESKTOP-KQ4S3ST") has 27 orphaned worktree slots that cannot be cleaned up, preventing new sessions from spawning. The task events show multiple `task.start_refused` with reason `no_placeable_device`.

## Root Cause Hypotheses

1. **Pi coding agent sessions not properly disposing** - If `AgentSession.dispose()` is not called (process crash, SIGKILL, unhandled exception), `cleanupSessionResources()` won't run, leaving resources orphaned.

2. **Missing worktree cleanup registration** - The `registerSessionResourceCleanup()` mechanism exists but no worktree cleanup function appears to be registered in the pi coding agent codebase.

3. **CodeHerder device agent bug** - The device agent that manages worktree slots may have a bug in its cleanup logic (not in this workspace).

4. **Session lifecycle issue** - Sessions may be terminated abnormally (OOM kill, device restart, network partition) without graceful shutdown.

## Investigation Plan

### Stage 1: Plan (Current)
- [x] Analyze task description and acceptance criteria
- [x] Explore pi coding agent codebase for worktree/session cleanup
- [x] Identify key files: `agent-session.js`, `session-manager.js`, `cleanupSessionResources`
- [ ] Write implementation plan (this document)

### Stage 2: Code (Investigation)
- [ ] Search CodeHerder SDK/docs for worktree slot management
- [ ] Check if pi coding agent registers any worktree cleanup via `registerSessionResourceCleanup`
- [ ] Examine session disposal paths in pi coding agent
- [ ] Check for any crash/unhandled exception handlers that might prevent dispose()
- [ ] Look at process signal handling (SIGTERM, SIGINT) in pi agent

### Stage 3: Review
- [ ] Document root cause found
- [ ] Propose specific solutions (code changes or config fixes)
- [ ] Create hand-off comment with findings

## Key Files to Investigate

1. `/opt/pi/node_modules/@earendil-works/pi-coding-agent/dist/core/agent-session.js` - Session disposal and cleanupSessionResources call
2. `/opt/pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/chunks/chunk-USJZMAIR.js` - cleanupSessionResources implementation
3. `/opt/pi/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js` - Session persistence
4. CodeHerder device agent (external - not in workspace)

## Acceptance Criteria Mapping

| Criterion | Proof Stage |
|-----------|-------------|
| Message/comment revealing reason for orphaned worktree slots | review |
| Message/comment proposing solutions | review |

## Next Steps

1. Complete investigation in code stage
2. Post findings as task comment
3. Propose solutions based on root cause
4. Transition to review stage