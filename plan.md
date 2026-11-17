# Implementation Plan: Add Rate Limiting to Authentication Endpoints

## Overview
Implement rate limiting on authentication and OAuth endpoints as specified in the acceptance criteria:
- Login: 5 attempts per minute per IP
- Password change/reset: 3 attempts per hour per user
- OAuth token endpoint: 10 requests per minute per IP
- MCP endpoints: 60 requests per minute per connection
- Rate limits configurable via settings

## Files to Modify

### 1. config/settings.py
- Add cache configuration (Redis for production, locmem for development)
- Add rate limit settings (configurable via environment variables)
  - `RATELIMIT_LOGIN_ATTEMPTS` (default: 5)
  - `RATELIMIT_LOGIN_WINDOW` (default: 60 seconds)
  - `RATELIMIT_PASSWORD_ATTEMPTS` (default: 3)
  - `RATELIMIT_PASSWORD_WINDOW` (default: 3600 seconds)
  - `RATELIMIT_OAUTH_TOKEN_ATTEMPTS` (default: 10)
  - `RATELIMIT_OAUTH_TOKEN_WINDOW` (default: 60 seconds)
  - `RATELIMIT_MCP_ATTEMPTS` (default: 60)
  - `RATELIMIT_MCP_WINDOW` (default: 60 seconds)

### 2. accounts/views/passwords.py
- Apply rate limiting to `ClearFlagPasswordChangeView` (password change)
- Apply rate limiting to `reset_password` function (password reset)
- Use per-user rate limiting (by user ID)

### 3. agent_access/oauth/urls.py
- Apply rate limiting to TokenView (oauth/token/)
- Use per-IP rate limiting

### 4. agent_access/oauth/views.py
- Apply rate limiting to `mcp_entry` view (MCP endpoint)
- Use per-connection rate limiting (by AgentConnection)

## Implementation Approach

### Cache Configuration
Add Django cache backend configuration to settings.py:
- Production: Redis cache backend
- Development: LocMemCache (in-memory)
- Tests: DummyCache (already in test_settings.py)

### Rate Limiting Strategy
Use Django's cache framework with custom decorators/middleware:
- For Django class-based views: Create a `RateLimitMixin` or use decorators
- For function-based views: Use decorators
- For OAuth token endpoint: Wrap the view with rate limiting
- For MCP endpoint: Add rate limiting in the view function

### Key Design Decisions
1. **Per-IP rate limiting** for login and OAuth token endpoints (anonymous users)
2. **Per-user rate limiting** for password change/reset (authenticated users)
3. **Per-connection rate limiting** for MCP endpoints (authenticated connections)
4. All rate limits configurable via environment variables with sensible defaults

## Acceptance Criteria Mapping

| Criterion | Stage | Proof |
|-----------|-------|-------|
| Login: 5 attempts per minute per IP | code | Unit test verifying rate limit on LoginView |
| Password change/reset: 3 attempts per hour per user | code | Unit test verifying rate limit on password views |
| OAuth token endpoint: 10 requests per minute per IP | code | Unit test verifying rate limit on TokenView |
| MCP endpoints: 60 requests per minute per connection | code | Unit test verifying rate limit on mcp_entry |
| Rate limits configurable via settings | code | Verify settings are read from environment |

## Test Strategy
- Add unit tests for each rate-limited endpoint
- Test rate limit exceeded responses (HTTP 429)
- Test rate limit windows reset correctly
- Test configuration via environment variables