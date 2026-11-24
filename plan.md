# Implementation Plan: Cross-App Template Include Context Verification

## Summary
The bug in PR 530 was fixed: `accounts/clubs/settings.html` includes `mail/_club_contact_card.html` and `mail/_club_test_card.html`, but the `club_settings` view didn't pass the context those partials need. Commit c07f69c fixed this by adding the required context to the view.

This task requires auditing **all** cross-app template includes where a partial has a dedicated HTMX view that supplies extra context, ensuring parent views pass the same context, and adding plain GET tests.

## Findings

### 1. Cross-App Includes with Dedicated HTMX Views (Critical)

| Parent Template | Included Partial | Partial's HTMX View | Status |
|-----------------|------------------|---------------------|--------|
| `accounts/clubs/settings.html` | `mail/_club_contact_card.html` | `mail.views.contact.contact_email` | **FIXED** (c07f69c) |
| `accounts/clubs/settings.html` | `mail/_club_test_card.html` | `mail.views.test_email.send_test_email` | **FIXED** (c07f69c) |
| `templates/accounts/_dashboard_downtime_result_modal.html` | `downtime/play/_result_body.html` | `downtime.views.play.SpendView` | **OK** - context passed via `_result_context` |
| `templates/accounts/_dashboard_downtime_result_modal.html` | `downtime/play/_wheel.html` | `downtime.views.play.SpendView` | **OK** - context passed via `_result_context` |
| `templates/player_characters/characters/print_session_pack.html` | `quests/_notice.html` | `quests.views.play.detail` | **OK** - context passed explicitly |
| `templates/player_characters/characters/print_session_pack.html` | `map/_hexmap.html` | `map.views.*` | **OK** - context built via `character_maps` |
| `items/templates/items/loot_cards_print.html` | `player_characters/characters/_item_card.html` | `player_characters.views.character_print.print_items` | **OK** - context passed explicitly |

### 2. Cross-App Includes of `items/_item_name.html` (24 occurrences)

The `items/_item_name.html` partial is included in 24 templates across 6 apps:
- `downtime` (2): `_result_body.html`, `_jobs.html`
- `player_characters` (2): `detail.html`, `print_session_pack.html`
- `shops` (7): `sell/_junk_body.html`, `player/detail.html`, `player/_your_inventory.html`, `player/_confirm_body.html`, `buy/_confirm_body.html`, `browse/_your_inventory.html`, `browse/_stock.html`, `browse/_sell_confirm_body.html`
- `quests` (3): `play/_turn_in_card.html`, `_notice.html` (2x)
- `ledger` (3): `index.html`, `_recent_changes.html`, `history.html`
- `starting_equipment` (7): `template_detail.html` (2x), `entry_list.html` (2x), `choices.html`, `requests/_status_row.html`

**Context needed**: `item` (required), `info` (optional), `club` (required when `info=True`)

**Status**: The `club` is provided by the `clubs` context processor (`accounts.context_processors.clubs`), which adds `club` from `request.club`. All parent views are club-scoped, so this works correctly. No dedicated HTMX view for `_item_name.html` exists.

### 3. Other Cross-App Includes

| Parent Template | Included Partial | Status |
|-----------------|------------------|--------|
| `player_characters/characters/_open_result_modal.html` | `downtime/play/_result_body.html` | **OK** - same context structure |
| `templates/accounts/_dashboard_downtime_result_modal.html` | `downtime/play/_result_body.html` | **OK** - handled above |
| `shops/templates/shops/player/_banner.html` | `shops/_building.html` | **OK** - simple partial, no extra context |
| `shops/templates/shops/player/_banner.html` | `shops/_memorial.html` | **OK** - same app |

## Test Coverage Analysis

### Existing Tests for Parent Pages (Plain GET)

| Parent View | Test File | Test Function | Asserts Partial Content? |
|-------------|-----------|---------------|--------------------------|
| `club_settings` | `accounts/tests/test_club_timezone_ui.py` | `test_settings_page_mail_cards_get_context_on_plain_load` | **Yes** - checks "Email is disabled" banner |
| `club_settings` | `accounts/tests/test_club_timezone_ui.py` | `test_settings_page_shows_disabled_reason_when_mail_off` | **Yes** - checks disabled reason |
| `dashboard_downtime_spend_partial` | `accounts/tests/test_dashboard_downtime_browser.py` | `test_dashboard_downtime_spend_reloads_card_and_wheel_spins` | Browser test, not plain GET |
| `print_session_pack` | `player_characters/tests/characters/test_print_session_pack.py` | `test_owner_sees_pack`, `test_pack_includes_item_cards`, `test_pack_options_exclude_quests`, `test_map_option_prints_character_view` | **Partial** - checks for class names, not specific partial content |
| `loot_cards_print` | `items/tests/test_u92_loot_cards.py` | `test_print_copies_type`, `test_print_copies_item` | **Partial** - checks for `wm-item-card` class |
| `downtime:play` | `downtime/tests/test_d8_d9_d10.py` | `test_rewards_table` | **No** - doesn't check item names |
| `shops:detail` | `shops/tests/test_u63_shop_page.py` | `test_inventory_row_sells_through_sell_item` | **No** - doesn't check item names |
| `quests:index` | `quests/tests/test_notice_progress.py` | `test_short_quest_shows_have_of_need_and_more` | **Partial** - checks progress text |
| `quests:detail` | `quests/tests/test_turn_in_card.py` | `test_card_lists_counts_and_missing` | **Partial** - checks item symbol |

### Gaps
- No plain GET tests for `downtime:play` asserting `items/_item_name.html` content
- No plain GET tests for `shops:detail` asserting `items/_item_name.html` content
- No plain GET tests for `quests:index`/`quests:detail` asserting `items/_item_name.html` content
- No plain GET tests for `ledger:index`/`ledger:history` asserting `items/_item_name.html` content
- No plain GET tests for `starting_equipment` views asserting `items/_item_name.html` content
- No plain GET tests for `player_characters:detail` asserting `items/_item_name.html` content

## Implementation Plan

### Phase 1: Verify Context Passing (Read-Only)
- [ ] Confirm all parent views in Section 1 pass required context (already verified)
- [ ] Confirm `items/_item_name.html` works via context processor (already verified)

### Phase 2: Add Plain GET Tests for Missing Coverage
For each parent view that includes a cross-app partial, add a plain GET test asserting the partial's key content:

1. **`downtime:play`** (`downtime/tests/test_d8_d9_d10.py`)
   - Add test: `test_play_page_shows_item_names_in_rewards`
   - Assert: Item names from `items/_item_name.html` appear in reward table

2. **`shops:detail`** (`shops/tests/test_u63_shop_page.py`)
   - Add test: `test_detail_page_shows_item_names_in_inventory`
   - Assert: Item names from `items/_item_name.html` appear in inventory rows

3. **`quests:index`** (`quests/tests/test_notice_progress.py` or new file)
   - Add test: `test_index_page_shows_item_names_in_notices`
   - Assert: Item names from `items/_item_name.html` appear in quest notices

4. **`quests:detail`** (`quests/tests/test_turn_in_card.py` or new file)
   - Add test: `test_detail_page_shows_item_names_in_requirements_rewards`
   - Assert: Item names from `items/_item_name.html` appear in requirements/rewards

5. **`ledger:index`** and **`ledger:history`** (new test file if needed)
   - Add test: `test_ledger_pages_show_item_names_in_entries`
   - Assert: Item names from `items/_item_name.html` appear in ledger lines

6. **`starting_equipment` views** (new test file if needed)
   - Add test: `test_template_detail_shows_item_names`
   - Assert: Item names from `items/_item_name.html` appear in template entries

7. **`player_characters:detail`** (`player_characters/tests/characters/test_*.py`)
   - Add test: `test_detail_page_shows_item_names_in_inventory`
   - Assert: Item names from `items/_item_name.html` appear in inventory rows

### Phase 3: Consider Context Processor/Template Tag Refactor (Optional)
- The mail context (`email_on`, `disabled_reason`, `settings`, `admins`, `recent_tests`) is currently duplicated in `club_settings` view and mail HTMX views. Consider moving to a context processor or template tag for reuse.
- The `items/_item_name.html` partial's `club` dependency is already handled by the `clubs` context processor.

### Phase 4: Report Findings
- Document all cross-app includes found
- Document which were fixed, which were already correct, which need tests
- Recommend any refactoring (context processor for mail context)

## Acceptance Criteria Mapping

| Acceptance Item | Proving Stage |
|-----------------|---------------|
| List every template that includes a partial whose own view supplies extra context | **plan** (this document) |
| Check that parent view passes same context | **plan** (verified in findings) |
| Add plain GET test of each parent page asserting partial's key content | **code** (Phase 2) |
| Report what was found | **verify** (Phase 4) |

## Next Steps
1. Transition to `code` stage
2. Implement Phase 2 tests
3. Optionally implement Phase 3 refactor
4. Write final report in `verify` stage