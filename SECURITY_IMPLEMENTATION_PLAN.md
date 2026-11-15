# Security Enhancements Implementation Plan

Based on comprehensive review of the West Marches Game Tracker app and Django's `check --deploy` output (13 warnings), here is the implementation plan organized by priority.

## Priority Breakdown

| Priority | Area | Django Warnings |
|----------|------|-----------------|
| HIGH | Production Security Settings | 6 (security.W004, W008, W009, W012, W016, W018) |
| HIGH | CORS Restriction for MCP/OAuth | Custom (Access-Control-Allow-Origin: *) |
| MEDIUM | OAuth RFC 9700 Compliance | 8 (oauth2_provider.W001-W008) |
| MEDIUM | Rate Limiting | None (missing entirely) |
| MEDIUM | Content Security Policy | None (missing entirely) |
| LOW | Security Logging | None (missing entirely) |
| LOW | Secure Defaults | Part of security.W009, W018 |

---

## Task 1: Production Security Settings (HIGH)

**Files to modify:** `config/settings.py`

**Changes:**
- Add environment-driven security settings that activate when `DEBUG=False`
- `SECURE_SSL_REDIRECT = not DEBUG`
- `SESSION_COOKIE_SECURE = not DEBUG`
- `CSRF_COOKIE_SECURE = not DEBUG`
- `SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG`
- `SECURE_HSTS_PRELOAD = not DEBUG`
- `SECURE_CONTENT_TYPE_NOSNIFF = True`
- `SECURE_REFERRER_POLICY = "same-origin"`
- `SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"`
- `SESSION_COOKIE_HTTPONLY = True`
- `X_FRAME_OPTIONS = "DENY"`

**Testing:** Run `./manage.py check --deploy` — all 6 security warnings should be resolved.

---

## Task 2: CORS Restriction for MCP/OAuth (HIGH)

**Files to modify:** 
- `config/settings.py` (add `ALLOWED_MCP_ORIGINS` setting)
- `agent_access/oauth/views.py` (update `CORS_HEADERS` and `cors` decorator)

**Changes:**
- Add `ALLOWED_MCP_ORIGINS` env var (comma-separated, defaults to `http://localhost:3000,http://127.0.0.1:3000` for dev)
- In `DEBUG=True`, allow `*` for local development
- In `DEBUG=False`, validate `Origin` header against allowed list
- Return appropriate `Access-Control-Allow-Origin` (specific origin or empty)
- Handle preflight OPTIONS correctly

**Testing:** Verify MCP endpoint rejects requests from unauthorized origins in production mode.

---

## Task 3: OAuth RFC 9700 Compliance (MEDIUM)

**Files to modify:** `config/settings.py` (update `OAUTH2_PROVIDER` dict)

**Changes:**
```python
OAUTH2_PROVIDER = {
    # ... existing settings ...
    "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT": True,
    "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT": True,
    "COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT": True,
    "COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS": True,
    "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,
    "REFRESH_TOKEN_REUSE_PROTECTION": True,
    "COMPLIANT_BCP_RFC9700_REDIRECT_URI_SCHEME": True,  # Requires HTTPS in production
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"] if not DEBUG else ["http", "https"],
}
```

**Note:** `COMPLIANT_BCP_RFC9700_TOKEN_STORAGE=True` requires a migration to hash stored tokens.

**Testing:** Run `./manage.py check --deploy` — all 8 oauth2_provider warnings should be resolved.

---

## Task 4: Rate Limiting (MEDIUM)

**Files to modify:**
- `config/settings.py` (add `REST_FRAMEWORK` with throttle classes)
- `agent_access/oauth/views.py` (add throttle to MCP and OAuth views)
- `agent_access/auth.py` (optional: custom throttle for token auth)

**Changes:**
- Add DRF throttling configuration:
  ```python
  REST_FRAMEWORK = {
      "DEFAULT_THROTTLE_CLASSES": [
          "rest_framework.throttling.AnonRateThrottle",
          "rest_framework.throttling.UserRateThrottle",
      ],
      "DEFAULT_THROTTLE_RATES": {
          "anon": "100/minute",
          "user": "1000/minute",
          "auth": "20/minute",      # Login, password reset
          "oauth": "30/minute",     # OAuth authorize, token
          "mcp": "60/minute",       # MCP tool calls
          "dcr": "10/hour",         # Dynamic client registration
      }
  }
  ```
- Apply `@throttle_classes([AnonRateThrottle])` with custom scopes to:
  - MCP entry point (`mcp_entry`)
  - OAuth authorization (`ConsentView`)
  - OAuth token endpoint (django-oauth-toolkit built-in)
  - DCR endpoint (`PublicClientRegistrationView`)
  - Login/password reset views

**Testing:** Verify rate limit headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`) and 429 responses.

---

## Task 5: Content Security Policy (MEDIUM)

**Files to modify:**
- `config/settings.py` (add CSP middleware and settings)
- `config/middleware.py` (new file for CSP middleware) OR use `django-csp` package

**Approach:** Use `django-csp` package (lightweight, well-maintained) for nonce-based CSP.

**Changes:**
- Add `csp` to `INSTALLED_APPS`
- Add `csp.middleware.CSPMiddleware` to `MIDDLEWARE` (after SecurityMiddleware)
- Configure CSP in settings:
  ```python
  CSP_DEFAULT_SRC = ["'self'"]
  CSP_SCRIPT_SRC = ["'self'", "'unsafe-inline'"]  # htmx needs inline scripts
  CSP_STYLE_SRC = ["'self'", "'unsafe-inline'"]   # htmx needs inline styles
  CSP_IMG_SRC = ["'self'", "data:"]
  CSP_FONT_SRC = ["'self'"]
  CSP_CONNECT_SRC = ["'self'"]
  CSP_FRAME_ANCESTORS = ["'none'"]
  CSP_FORM_ACTION = ["'self'"]
  CSP_BASE_URI = ["'self'"]
  ```
- For tighter security: implement nonce-based inline scripts for htmx

**Testing:** Verify CSP headers present; no console CSP violations in browser.

---

## Task 6: Security Logging (LOW)

**Files to modify:**
- `config/settings.py` (add `LOGGING` configuration)
- `agent_access/auth.py` (log authentication events)
- `accounts/views/passwords.py` (log password changes/resets)
- `agent_access/oauth/views.py` (log OAuth authorizations)

**Changes:**
- Configure structured logging to console/file with JSON format
- Log security events:
  - Failed/successful login attempts
  - Password changes and resets
  - OAuth authorization grants/denials
  - MCP authentication (success/failure)
  - Token creation/revocation
  - Batch confirmations/reversals (sensitive operations)

**Testing:** Verify logs appear for security-relevant actions.

---

## Task 7: Secure Defaults (LOW)

**Files to modify:**
- `config/settings.py`
- `agent_access/oauth/views.py` (DCR permission class)

**Changes:**
- `DEBUG = os.environ.get("DJANGO_DEBUG", "0") in ("1", "true", "True")` — default False
- `SECRET_KEY` — raise `ImproperlyConfigured` if default used in production:
  ```python
  SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
  if not SECRET_KEY:
      if DEBUG:
          SECRET_KEY = "dev-only-insecure-key-change-me"
      else:
          from django.core.exceptions import ImproperlyConfigured
          raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production")
  ```
- Restrict DCR: change `DCR_REGISTRATION_PERMISSION_CLASSES` from `AllowAllDCRPermission` to a custom class that requires approval or known clients

**Testing:** Verify app fails to start in production without `DJANGO_SECRET_KEY`; DEBUG defaults to False.

---

## Workflow Composition

This plan requires 7 implementation tasks + review + verify:

1. **Plan** - This document (current stage)
2. **Code** - Task 1: Production Security Settings
3. **Code** - Task 2: CORS Restriction
4. **Code** - Task 3: OAuth RFC 9700 Compliance
4. **Code** - Task 4: Rate Limiting
5. **Code** - Task 5: Content Security Policy
6. **Code** - Task 6: Security Logging
7. **Code** - Task 7: Secure Defaults
8. **Review** - Security review of all changes
9. **Verify** - Run `check --deploy`, tests, manual verification
10. **Done** - Complete

---

## Acceptance Criteria Mapping

| Criterion | Proving Stage |
|-----------|---------------|
| `check --deploy` shows 0 warnings | verify |
| MCP/OAuth CORS rejects unauthorized origins in production | verify |
| OAuth RFC 9700 warnings resolved | verify |
| Rate limiting active on auth, OAuth, MCP endpoints | verify |
| CSP headers present, no console violations | verify |
| Security events logged (login, password, OAuth, MCP, batches) | verify |
| App fails to start without SECRET_KEY in production | verify |
| DEBUG defaults to False | verify |
| All existing tests pass | verify |
| New security tests added for each area | verify |

---

## Dependencies Between Tasks

- Task 1 (Production Settings) is independent
- Task 2 (CORS) should reference DEBUG from Task 1
- Task 3 (OAuth) is independent but needs migration for token hashing
- Task 4 (Rate Limiting) needs DRF config from settings
- Task 5 (CSP) may need adjustment based on htmx usage
- Task 6 (Logging) can be done anytime
- Task 7 (Secure Defaults) should be done after Task 1

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| HSTS preload irreversible | Only enable after confirming HTTPS works; use env var to control |
| CSP breaks htmx | Start with `'unsafe-inline'`, migrate to nonces incrementally |
| OAuth token hashing migration | Test migration on copy of production data first |
| Rate limiting too aggressive | Start with generous limits, tune based on monitoring |
| CORS breaks MCP clients | Document required origins; allow `*` in DEBUG |

---

## Files to Create/Modify Summary

### New Files:
- `config/middleware.py` (CSP middleware, if not using django-csp)
- `agent_access/throttles.py` (custom throttle classes)
- `agent_access/permissions.py` (restricted DCR permission)
- Tests for each security feature

### Modified Files:
- `config/settings.py` (all tasks)
- `agent_access/oauth/views.py` (Tasks 2, 3, 4)
- `agent_access/auth.py` (Task 6)
- `accounts/views/passwords.py` (Task 6)
- `agent_access/models.py` (Task 3 migration may add fields)

---

## Estimated Effort

| Task | Estimate |
|------|----------|
| Task 1: Production Security Settings | 1-2 hours |
| Task 2: CORS Restriction | 1-2 hours |
| Task 3: OAuth RFC 9700 Compliance | 2-3 hours (includes migration) |
| Task 4: Rate Limiting | 2-3 hours |
| Task 5: Content Security Policy | 2-3 hours |
| Task 6: Security Logging | 1-2 hours |
| Task 7: Secure Defaults | 1 hour |
| **Total** | **10-16 hours** |