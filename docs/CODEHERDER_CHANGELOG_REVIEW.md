# CodeHerder changelog review (2026-11-11 to 2026-11-18)

## Result

No code changes are needed for `west-marches-game-tracker-app`.

All changelog entries in the one-week lookback (2026-11-11 to 2026-11-18) are platform-side changes to CodeHerder itself. This repository is a provider, not a client. It exposes OAuth2 dynamic client registration and an MCP endpoint, and it never calls the CodeHerder platform back.

## Verification checks

I applied the three checks from workspace knowledge `codeherder/telling-a-codeherder-changelog-change-from-a-noise-change`:

1. Grep the repo for `ch` CLI calls — none found (only false positives: variable `ch` for Character).
2. Grep for a CodeHerder API client or webhook consumer — none found (`codeherder.com` appears only as a footer link and in test assertions).
3. Integration protocols are OAuth2 DCR (`agent_access/oauth/`) and the MCP server (`agent_access/mcp/server.py`). The repo never calls the platform back.

## Operational notes for humans

No code change is required for either item. These are deployment, config, or platform notes only.

### 1. Sandbox preview (2026-11-11)

A sandbox can serve the running app at its own URL. That host must be in `DJANGO_ALLOWED_HOSTS` or Django answers 400. The repo already reads `ALLOWED_HOSTS` from the `DJANGO_ALLOWED_HOSTS` env var (default `localhost,127.0.0.1,testserver`) in `config/settings.py`. Add the sandbox host to `DJANGO_ALLOWED_HOSTS` at deployment time.

### 2. Device unlinked (2026-11-15)

A device that loses its workspace link can no longer read session guardrails or workspace knowledge. Platform and device side only; no repo code change.

## Outcome

No implementation tasks were created. Nothing for an agent to change in this repo.

Task: https://app.codeherder.com/vaughnjbernards-account/vaughnjbernards-workspace/-/tasks/01a1ede2-bb53-74ca-9275-77fe550ae25f
