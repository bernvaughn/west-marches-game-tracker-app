## code
- [ ] New middleware file `config/middleware.py` created with `SecurityHeadersMiddleware` class
- [ ] Middleware adds `Referrer-Policy: strict-origin-when-cross-origin` header
- [ ] Middleware adds `Permissions-Policy` header with restrictive defaults
- [ ] Middleware adds `Cross-Origin-Opener-Policy: same-origin` header
- [ ] Middleware adds `Cross-Origin-Embedder-Policy: require-corp` header
- [ ] Middleware added to `MIDDLEWARE` list in `config/settings.py` after `SecurityMiddleware`

## review
- [ ] Code follows project conventions (class-based middleware with `__init__` and `__call__`)
- [ ] No linting errors (ruff)
- [ ] No type errors

## verify
- [ ] Unit tests pass for the middleware
- [ ] Integration test confirms headers present on all responses
- [ ] Headers present on HTML responses
- [ ] Headers present on API/JSON responses
- [ ] Headers present on error responses (404, 500)
- [ ] Test settings don't break the middleware (headers still added in test mode)