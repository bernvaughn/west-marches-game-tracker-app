## Hand-off: S3 Character Switch Preview — Plan Complete

### What was done
- Created implementation plan (`plan.md`) covering all required files and steps
- Set acceptance criteria with all 6 items deferred to `code` stage (where they'll be implemented and proven)
- Analyzed existing codebase: `_selector.html` template, `selection.py` views, `selector_context.py`, `urls_characters.py`, `tooltips.js`

### Key decisions
1. **Native `<select>` → Bootstrap dropdown**: The current character selector uses a native `<select>` which doesn't support tooltips on `<option>` elements. The plan converts it to a Bootstrap dropdown (button + dropdown-menu) so each character item can have a tooltip.

2. **JSON endpoint + JS rendering**: The `character_preview` view returns JSON. JavaScript in `tooltips.js` fetches this on `shown.bs.tooltip`, builds an HTML card, and updates the tooltip content via Bootstrap's `setContent()` API.

3. **Reuse existing logic**: The preview view reuses `selector_context.character_selector_context()` for data fetching (coins, junk, trades, downtime).

### Files to modify (per plan)
1. `player_characters/views/selection.py` — add `character_preview` view
2. `player_characters/urls_characters.py` — add `/preview/<pk>/` URL
3. `templates/player_characters/characters/_selector.html` — convert to Bootstrap dropdown with tooltip attributes
4. `static/js/tooltips.js` — add handler for `shown.bs.tooltip` on `[data-wm-preview-url]`

### Next steps for code stage
1. Implement `character_preview` view in `selection.py`
2. Add URL pattern in `urls_characters.py`
3. Convert `_selector.html` to Bootstrap dropdown
4. Add tooltip fetch handler in `tooltips.js`
5. Write unit tests in `test_selection.py`
6. Write browser tests (Playwright) for tooltip behavior

### Acceptance criteria (all in code stage)
- Character selector dropdown options show Bootstrap tooltip on hover/focus
- Tooltip fetches `/characters/<slug>/preview/<pk>/` via HTMX on `shown.bs.tooltip`
- Preview JSON: `{name, level, class, species, coins_available, junk_count, junk_value, downtime, open_trades}`
- Tooltip renders as small card with avatar, key stats
- Works on mobile (tap to show, tap elsewhere to dismiss)
- Ruff clean, unit + browser tests pass