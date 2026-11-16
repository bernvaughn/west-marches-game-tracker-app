## Hand-off: S2 Trade Dashboard Widget (Plan Stage Complete)

### What was done
1. **Explored the codebase** to understand the existing dashboard provider system, trade models, and trade status display logic
2. **Created implementation plan** (`plan.md`) detailing:
   - Files to modify: `accounts/views/dashboard.py` (TradesProvider), `templates/accounts/_dashboard_trades.html`
   - URL endpoint already exists: `/dashboard/<slug>/partial/trades/`
   - Provider already registered in `accounts/apps.py` with order=2
3. **Set acceptance criteria** with proof stages (plan → code → verify)

### Key findings
- **TradesProvider already exists** in `accounts/views/dashboard.py` with basic functionality but needs enhancement
- **Template exists** at `templates/accounts/_dashboard_trades.html` but uses simple `trade_items` list instead of detailed trade data
- **Trade status wording** is in `player_characters/trade_status_line.py` - `trade_status_line()` function
- **Trade URLs**: `trades:detail`, `trades:edit_side`, `trades:accept`, `trades:decline`, `trades:cancel`
- **HTMX polling**: Existing `trades:poll` endpoint at `/trades/poll/` polls every 5s for navbar; dashboard widget needs 10s poll to its own partial endpoint

### What the next agent (code stage) should do
1. **Modify `TradesProvider.get_context()`** in `accounts/views/dashboard.py`:
   - Import `trade_status_line` from `player_characters.trade_status_line`
   - Build detailed trade data with status text, action button URL/label per trade state
   - Return `open_trades_data` list with dicts containing: trade, other_character, side, status_display, action_url, action_label

2. **Rewrite `templates/accounts/_dashboard_trades.html`**:
   - Iterate over `provider_context.open_trades_data`
   - Show status badge using U78 wording
   - Show "Act Now" button with correct link per state machine
   - Wrap in container with `hx-get="{% url 'accounts:dashboard_partial' club.slug 'trades' %}" hx-trigger="every 10s" hx-swap="outerHTML"`

3. **Update `TradesProvider.should_show()`** to return True only if user has open trades

### Open questions / decisions
- The `trade_status_line` function needs `viewer_side` parameter ("sender", "receiver", or None) - need to pass user's side
- For REQUESTED status: receiver sees "Accept" → `trades:edit_side`; sender sees "Cancel" → `trades:detail` (or cancel POST)
- For ACCEPTED status: if viewer not approved → "Change" → `trades:edit_side`; if viewer approved but other not → "Approve" → `trades:detail` (approve POST); if both approved → trade completes automatically

### Files to reference
- `accounts/views/dashboard.py` - TradesProvider class
- `templates/accounts/_dashboard_trades.html` - template to rewrite
- `player_characters/trade_status_line.py` - status wording function
- `player_characters/urls_trades.py` - trade URL patterns