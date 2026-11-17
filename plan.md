# Implementation Plan: Security Headers Middleware

## Overview
Add middleware to include additional security headers on all HTTP responses:
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: restrictive defaults
- Cross-Origin-Opener-Policy: same-origin
- Cross-Origin-Embedder-Policy: require-corp

## Files to Create/Modify

### 1. New File: `config/middleware.py`
Create a new middleware class `SecurityHeadersMiddleware` that adds the required security headers to all responses.

### 2. Modify: `config/settings.py`
Add the new middleware to the `MIDDLEWARE` list. It should be placed after `SecurityMiddleware` but before other middleware to ensure headers are set on all responses.

## Implementation Details

### SecurityHeadersMiddleware Class
- Uses Django's middleware `__call__` pattern (same as `ClubMiddleware`)
- In `__call__`, call `self.get_response(request)` to get the response
- Add the four security headers to the response
- Return the modified response

### Header Values
```python
# Referrer-Policy
response["Referrer-Policy"] = "strict-origin-when-cross-origin"

# Permissions-Policy (restrictive defaults - disable most features)
response["Permissions-Policy"] = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), payment=(), usb=(), "
    "interest-cohort=()"
)

# Cross-Origin-Opener-Policy
response["Cross-Origin-Opener-Policy"] = "same-origin"

# Cross-Origin-Embedder-Policy
response["Cross-Origin-Embedder-Policy"] = "require-corp"
```

### Middleware Order
In `config/settings.py`, add `"config.middleware.SecurityHeadersMiddleware"` after `"django.middleware.security.SecurityMiddleware"` and before `"csp.middleware.CSPMiddleware"`.

## Testing Strategy
- Unit tests for the middleware to verify headers are added
- Integration test to verify headers present on actual responses
- Test with test settings (which disable other security features) to ensure middleware still adds headers

## Rollback Plan
- Remove middleware from MIDDLEWARE list
- Delete config/middleware.py