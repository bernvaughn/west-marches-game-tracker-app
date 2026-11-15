# Security Enhancement Plan

Based on comprehensive review of the West Marches Game Tracker app, here are the security issues found and recommended fixes.

## Summary of Issues

### HIGH Priority

1. **Missing Production Security Settings** (Django security check: 6 warnings)
   - `SECURE_SSL_REDIRECT` not set
   - `SESSION_COOKIE_SECURE` not set  
   - `CSRF_COOKIE_SECURE` not set
   - `SECURE_HSTS_SECONDS` not set
   - `SECURE_HSTS_INCLUDE_SUBDOMAINS` not set
   - `SECURE_HSTS_PRELOAD` not set

2. **CORS Too Permissive on MCP/OAuth Endpoints**
   - `Access-Control-Allow-Origin: *` allows any origin

### MEDIUM Priority

3. **OAuth RFC 9700 Compliance** (8 warnings from django-oauth-toolkit)
   - Implicit grant enabled
   - Password grant enabled
   - Access tokens accepted in URI query string
   - Missing `iss` parameter in auth response
   - Tokens stored in plaintext
   - Refresh token replay detection disabled
   - HTTP redirect URIs allowed

4. **No Rate Limiting**
   - No throttling on auth endpoints
   - No throttling on MCP endpoint
   - No throttling on OAuth endpoints

5. **No Content Security Policy**
   - No CSP headers configured

### LOW Priority

6. **No Security Logging/Audit Trail**
   - No logging configuration for security events
   - No audit trail for sensitive operations

7. **Insecure Defaults**
   - `DEBUG` defaults to True via env var
   - `SECRET_KEY` default is "dev-only-insecure-key-change-me"
   - OAuth DCR allows all registrations

## Recommended Task Breakdown

### Task 1: Production Security Settings (HIGH)
Add environment-driven security settings to `config/settings.py`:
- `SECURE_SSL_REDIRECT = True` (when not DEBUG)
- `SESSION_COOKIE_SECURE = True` (when not DEBUG)
- `CSRF_COOKIE_SECURE = True` (when not DEBUG)
- `SECURE_HSTS_SECONDS = 31536000` (1 year, when not DEBUG)
- `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- `SECURE_HSTS_PRELOAD = True`
- `SECURE_CONTENT_TYPE_NOSNIFF = True`
- `SECURE_REFERRER_POLICY = "same-origin"`
- `SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"`
- `SESSION_COOKIE_HTTPONLY = True`
- `X_FRAME_OPTIONS = "DENY"`

### Task 2: CORS Restriction for MCP/OAuth (HIGH)
- Restrict `Access-Control-Allow-Origin` to specific allowed origins
- Add `ALLOWED_MCP_ORIGINS` setting
- Only allow `*` in DEBUG mode for local development

### Task 3: OAuth RFC 9700 Compliance (MEDIUM)
Update `OAUTH2_PROVIDER` settings:
- `COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT = True`
- `COMPLIANT_BCP_RFC9700_PASSWORD_GRANT = True`
- `COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT = True`
- `COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS = True`
- `COMPLIANT_BCP_RFC9700_TOKEN_STORAGE = True`
- `REFRESH_TOKEN_REUSE_PROTECTION = True`
- `COMPLIANT_BCP_RFC9700_REDIRECT_URI_SCHEME = True` (requires HTTPS in production)

### Task 4: Rate Limiting (MEDIUM)
- Add DRF throttling for auth endpoints
- Add throttling for MCP endpoint
- Add throttling for OAuth endpoints
- Configure appropriate rates (e.g., 100/min for auth, 60/min for MCP)

### Task 5: Content Security Policy (MEDIUM)
- Add CSP middleware or headers
- Configure CSP for inline scripts/styles needed by htmx
- Add nonce-based CSP for inline scripts

### Task 6: Security Logging (LOW)
- Configure Django logging for security events
- Log: login attempts, password changes, OAuth authorizations, MCP access
- Add audit trail for sensitive operations (password resets, batch confirmations)

### Task 7: Secure Defaults (LOW)
- Change `DEBUG` default to False
- Require `DJANGO_SECRET_KEY` env var in production (fail if default used)
- Restrict OAuth DCR to known clients or require approval

## Workflow Composition

This plan requires multiple implementation tasks. The workflow should include:
1. **Planning** - Detail each task (this document)
2. **Code** - Implement production security settings
3. **Code** - Implement CORS restrictions
4. **Code** - Implement OAuth RFC 9700 compliance
5. **Code** - Implement rate limiting
6. **Code** - Implement CSP
7. **Code** - Implement security logging
8. **Code** - Fix secure defaults
9. **Review** - Security review of changes
10. **Verify** - Run security checks and tests
11. **Done** - Complete