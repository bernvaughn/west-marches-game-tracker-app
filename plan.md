# Implementation Plan: S2 - Menu Icons and Categories (U167)

## Overview
Add icons to every hamburger-menu link and category heading, and regroup links by the approved Round 24 categories. The entry set, URLs, order within categories, and permission checks remain unchanged.

## Files to Modify

### 1. accounts/navigation.py
- **MENU_GROUPS**: Replace with new 7 categories, each with (key, heading, icon):
  - `("character", "Character", "person")`
  - `("town", "Town", "shop")`
  - `("map", "Map", "map")`
  - `("club", "Club", "people")`
  - `("account", "Account", "gear")`
  - `("gm", "Game Master", "person-gear")`
  - `("admin", "Club Admin", "gear-fill")`
- Keep `GROUPS` unchanged for backward compatibility (includes "gm", "admin")
- Update `menu_sections` filter (in accounts_tags.py) to return category icon

### 2. accounts/templatetags/accounts_tags.py
- Update `menu_sections` filter to return `(key, heading, icon, links)` tuples

### 3. App registrations (apps.py files) - Add icons and move entries to new categories

| App | Changes |
|-----|---------|
| **accounts/apps.py** | Add icons to club/admin entries; register footer links (Your clubs, Change password, Donate) in "account" group with icons |
| **player_characters/apps.py** | Add icons to all character/gm entries; "The Fallen" already has flower1 |
| **shops/apps.py** | Add icons to admin entries (Manage shops, Rotations) |
| **quests/apps.py** | Add icon to Manage quests |
| **map/apps.py** | Add icons to gm entries (Map requests, New map); XP table needs icon |
| **downtime/apps.py** | Add icons to gm/admin entries |
| **ledger/apps.py** | Add icons to Ledger (character) and Club ledger (gm) |
| **agent_access/apps.py** | Add icons to all gm entries |
| **starting_equipment/apps.py** | Add icon to Starting Equipment Templates |
| **character_options/apps.py** | Add icon to Character options |
| **items/apps.py** | Add icons to Items (club) and Item catalogue (admin) |
| **player_items/apps.py** | Add icon to Review player items |
| **play_sessions/hooks_calendar.py** | Sessions already has calendar-date icon |
| **play_sessions/hooks_schedule.py** | Add icon to New session (gm) |
| **play_sessions/hooks_settings.py** | Add icon to Session settings (admin) |
| **play_sessions/hooks_report.py** | Add icon to Attendance report (admin) |

### 4. templates/partials/side_menu.html
- Render category heading with icon from menu_sections
- Render each link with its icon (from NavEntry.icon)
- Keep Account section but use category icon from menu_sections
- Remove special-case gm/admin sections (now handled via menu_sections)

### 5. templates/club_home.html
- Use category icon from menu_sections for section headings
- Pass icon to _area_card.html

### 6. accounts/templates/accounts/_area_card.html
- Accept and render link icon

### 7. Tests (accounts/tests/test_navigation_menus.py)
- Add test: every registered entry is in exactly one MENU_GROUPS category
- Add test: each role sees exactly the same set of links as before regrouping
- Add test: every link and heading has an icon
- Add test: link order inside categories is stable (order, then label)

## Icon Assignments (Bootstrap Icons 1.11.3)

### Character category (person)
- Dashboard: `speedometer2` (existing)
- My character: `person` (existing)
- Character directory: `people`
- New character: `person-plus`
- Character slips: `file-earmark-text`
- Archived characters: `archive`
- Ledger: `journal-text`

### Town category (shop)
- Shops: `shop` (existing)
- Quests: `journal-text` (existing)
- Downtime: `hourglass-split` (existing)

### Map category (map)
- All maps: `map` (existing)
- XP table: `table`
- Map requests: `pin-map`

### Club category (people)
- People: `people` (existing)
- Message the admins: `chat-left-text`
- Request stock: `box-arrow-up`
- Sessions: `calendar-date` (existing)
- The Fallen: `flower1` (existing)
- Items: `box-seam`

### Account category (gear)
- Your clubs: `houses`
- Change password: `key`
- Donate: `heart`

### Game Master category (person-gear)
- All characters: `people`
- Award Loot to Party: `cash-stack`
- Map requests: `pin-map`
- New map: `map-plus` (or `plus-circle`)
- Downtime points: `coin`
- Agent access: `person-gear`
- Agent connections: `link-45deg`
- Agent batches: `boxes`
- Proposed items: `box-seam`
- Downtime point requests: `hourglass-split`
- New session: `calendar-plus`
- Club ledger: `journal-text`

### Club Admin category (gear-fill)
- Members: `people`
- Whitelist: `person-check`
- Inbox: `inbox`
- Club settings: `gear`
- Manage shops: `shop`
- Rotations: `arrow-repeat`
- Manage quests: `journal-text`
- Item catalogue: `box-seam`
- Starting Equipment Templates: `box`
- Agenda: `calendar-event`
- Downtime actions: `list-task`
- Attendance report: `clipboard-data`
- Session settings: `gear-wide`
- Character options: `sliders`
- Review player items: `eye`

## Acceptance Criteria Mapping

| Criterion | Proof Stage |
|-----------|-------------|
| MENU_GROUPS carries category icon per group; every entry in exactly one category | code |
| Moving links between categories doesn't change URL/permission | code (test) |
| Every link and heading renders Bootstrap Icons icon | code (visual) |
| Each role sees same links as before (regression test) | code (test) |
| Link order inside categories stable | code (test) |
| apps.py registrations updated for icons and group moves | code |
| menu_sections returns category icon; club_home.html uses it | code |
| Every entry without icon gets sensible Bootstrap Icons id | code (validated) |
| pytest, ruff check, ruff format pass | verify |
| Screenshots for player, GM, club admin at 1280px and 390px | verify |