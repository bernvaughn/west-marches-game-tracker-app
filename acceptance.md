## Acceptance Criteria

### Plan Stage
- [ ] Implementation plan documented with files to change and verification steps

### Code Stage
- [ ] Alpine.js CSP build (v3.13.3) replaces standard build in `static/vendor/alpinejs/alpine.min.js`
- [ ] `config/settings.py` - `'unsafe-eval'` removed from `script-src` CSP directive
- [ ] `config/test_settings.py` - `'unsafe-eval'` removed from `script-src` CSP directive
- [ ] All tests pass (2127 tests)
- [ ] Linting passes (`ruff check`)
- [ ] Formatting passes (`ruff format --check`)

### Review Stage
- [ ] Code review confirms CSP build doesn't use `eval()`/`Function()` constructor
- [ ] CSP policy no longer includes `'unsafe-eval'`
- [ ] Command palette (Cmd/Ctrl+K) works correctly
- [ ] Alpine.js components initialize without CSP errors

### Verify Stage
- [ ] CI pipeline passes on PR
- [ ] Manual verification: command palette opens and functions
- [ ] No `EvalError: call to Function() blocked by CSP` errors in browser console

### Done Stage
- [ ] Merged to main branch