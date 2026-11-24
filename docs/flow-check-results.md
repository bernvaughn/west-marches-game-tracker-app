# Flow check verification results

## Summary

A flow check verification was run against the running app, walking real user
flows and clicking every control to find buttons that do nothing.

- **Total controls tested: 45**
- **Passed: 45**
- **Failed: 0**
- **Bugs found: 0** (no child tasks needed)

All server responses were 200 OK or 302 redirect. No 4xx or 5xx errors. No
console errors or warnings.

## Test script

The test script is preserved in this repository at `scripts/flow_check.py`. It
can be re-run for future regression checks against a running dev server.

See the script header for prerequisites and usage.

## Flows tested

| Flow | Description | Controls |
|------|-------------|----------|
| 1 | New character → choices → gear reveal → sheet | 6 |
| 2 | Buy at a shop → sell junk | 3 |
| 9 | Switch character from top bar → use dashboard | 34 |
| Mobile | Dashboard → hamburger menu → character dropdown (390px) | 2 |
| **Total** | | **45** |

### Flow 1: New character, choices, gear reveal, sheet

Login as alice → club home → hamburger menu → "New character" → fill form →
submit → confirm choices. Controls tested: 6.

### Flow 2: Buy at a shop, then sell junk

Shops index → click shop → buy button (modal) → sell junk button (modal).
Controls tested: 3.

### Flow 9: Switch character from top bar, use dashboard

Dashboard → character Switch button → character dropdown → 8 navbar shortcuts →
Print Session Pack modal → hamburger menu → 22 side menu links.
Controls tested: 34.

### Mobile width (390px)

Dashboard → hamburger menu → character dropdown. Controls tested: 2.

## Server responses

- All navigation: 200 OK or 302 redirect
- No 4xx or 5xx errors during the test run

## Console output

- No console errors or warnings

## Browser used

- Chromium (headless) via Playwright
- Firefox not available in the sandbox; Chromium used instead
- Browser checks run without root: see the wiki page `testing/browser-checks-without-root`

## Product decisions for children

N/A — no bugs found, no child tasks needed.
