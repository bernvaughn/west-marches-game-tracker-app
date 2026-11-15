## plan
- [ ] Production security settings configured (SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE, SECURE_HSTS_SECONDS, SECURE_HSTS_INCLUDE_SUBDOMAINS, SECURE_HSTS_PRELOAD, SECURE_CONTENT_TYPE_NOSNIFF, SECURE_REFERRER_POLICY, SECURE_CROSS_ORIGIN_OPENER_POLICY, SESSION_COOKIE_HTTPONLY, X_FRAME_OPTIONS)
- [ ] CORS restricted for MCP/OAuth endpoints (ALLOWED_MCP_ORIGINS setting, validates Origin header, allows * only in DEBUG)
- [ ] OAuth RFC 9700 compliance enabled (COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT, COMPLIANT_BCP_RFC9700_PASSWORD_GRANT, COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT, COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS, COMPLIANT_BCP_RFC9700_TOKEN_STORAGE, REFRESH_TOKEN_REUSE_PROTECTION, COMPLIANT_BCP_RFC9700_REDIRECT_URI_SCHEME)
- [ ] Rate limiting implemented on auth, OAuth, MCP, and DCR endpoints
- [ ] Content Security Policy headers configured (django-csp middleware, appropriate directives for htmx)
- [ ] Security logging configured (login attempts, password changes, OAuth authorizations, MCP access, batch operations)
- [ ] Secure defaults enforced (DEBUG defaults to False, SECRET_KEY required in production, DCR restricted)

## prod_settings
- [ ] config/settings.py updated with production security settings
- [ ] SECURE_SSL_REDIRECT = not DEBUG
- [ ] SESSION_COOKIE_SECURE = not DEBUG
- [ ] CSRF_COOKIE_SECURE = not DEBUG
- [ ] SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
- [ ] SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
- [ ] SECURE_HSTS_PRELOAD = not DEBUG
- [ ] SECURE_CONTENT_TYPE_NOSNIFF = True
- [ ] SECURE_REFERRER_POLICY = "same-origin"
- [ ] SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
- [ ] SESSION_COOKIE_HTTPONLY = True
- [ ] X_FRAME_OPTIONS = "DENY"

## cors_restriction
- [ ] config/settings.py updated with ALLOWED_MCP_ORIGINS setting
- [ ] agent_access/oauth/views.py updated with CORS origin validation
- [ ] CORS allows * only in DEBUG mode
- [ ] CORS validates Origin header against ALLOWED_MCP_ORIGINS in production

## oauth_compliance
- [ ] config/settings.py updated with OAUTH2_PROVIDER RFC 9700 settings
- [ ] COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT = True
- [ ] COMPLIANT_BCP_RFC9700_PASSWORD_GRANT = True
- [ ] COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT = True
- [ ] COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS = True
- [ ] COMPLIANT_BCP_RFC9700_TOKEN_STORAGE = True
- [ ] REFRESH_TOKEN_REUSE_PROTECTION = True
- [ ] COMPLIANT_BCP_RFC9700_REDIRECT_URI_SCHEME = True
- [ ] ALLOWED_REDIRECT_URI_SCHEMES = ["https"] if not DEBUG else ["http", "https"]

## rate_limiting
- [ ] config/settings.py updated with REST_FRAMEWORK throttling configuration
- [ ] agent_access/throttles.py created with custom throttle scopes
- [ ] agent_access/oauth/views.py updated with throttle classes on MCP/OAuth views
- [ ] Throttle scopes: auth (20/min), oauth (30/min), mcp (60/min), dcr (10/hour)
- [ ] Rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining) present

## csp_headers
- [ ] config/settings.py updated with CSP configuration (django-csp added to INSTALLED_APPS)
- [ ] CSP middleware added to MIDDLEWARE
- [ ] CSP directives configured for htmx compatibility
- [ ] CSP headers present in responses
- [ ] No browser console CSP violations

## security_logging
- [ ] config/settings.py updated with LOGGING configuration
- [ ] agent_access/auth.py updated with authentication event logging
- [ ] accounts/views/passwords.py updated with password change/reset logging
- [ ] agent_access/oauth/views.py updated with OAuth authorization logging
- [ ] MCP access (success/failure) logged
- [ ] Batch confirmations/reversals logged

## secure_defaults
- [ ] config/settings.py updated with secure defaults
- [ ] DEBUG defaults to False (DJANGO_DEBUG defaults to "0")
- [ ] SECRET_KEY required in production (raises ImproperlyConfigured if default used)
- [ ] agent_access/oauth/views.py updated with restricted DCR permission class
- [ ] agent_access/permissions.py created with restricted DCR permission

## review
- [ ] Security review of all changes completed
- [ ] HSTS preload risk assessed and documented
- [ ] CSP tested with htmx - no console violations
- [ ] Rate limit thresholds appropriate for expected traffic
- [ ] OAuth token hashing migration tested
- [ ] CORS configuration documented for MCP client developers

## verify
- [ ] ./manage.py check --deploy shows 0 warnings
- [ ] All existing tests pass (pytest)
- [ ] New security tests pass
- [ ] Manual verification: MCP endpoint rejects unauthorized origins in production mode
- [ ] Manual verification: Rate limit headers present, 429 on excess
- [ ] Manual verification: CSP headers present, no browser console violations
- [ ] Manual verification: Security events appear in logs
- [ ] Manual verification: App fails to start without DJANGO_SECRET_KEY when DEBUG=False
- [ ] Manual verification: DEBUG defaults to False
- [ ] Ruff linting passes