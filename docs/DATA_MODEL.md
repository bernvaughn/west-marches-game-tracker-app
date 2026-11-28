# Data model outline (draft)

A plain-language outline of the records each app keeps and how they connect, built from `docs/USER_STORIES.md`. Names are tentative. No code is implied.

## How the pieces connect

```mermaid
erDiagram
    CLUB ||--o{ MEMBERSHIP : has
    USER ||--o{ MEMBERSHIP : joins
    CLUB ||--o{ ITEM : catalogues
    MEMBERSHIP ||--o{ CHARACTER : owns
    CHARACTER ||--o{ INVENTORY_ENTRY : carries
    ITEM ||--o{ INVENTORY_ENTRY : "held as"
    CHARACTER ||--o{ LEDGER_ENTRY : "has history"
    LEDGER_ENTRY ||--|{ LEDGER_LINE : contains
    ITEM ||--o{ LEDGER_LINE : "appears in"
    SHOP ||--o{ SHOP_STOCK : stocks
    ITEM ||--o{ SHOP_STOCK : "stocked as"
    ROTATION }o--o{ SHOP : opens
    QUEST ||--o{ QUEST_REQUIREMENT : requires
    QUEST ||--o{ QUEST_REWARD : gives
    QUEST ||--o{ QUEST_COMPLETION : "completed as"
    CHARACTER ||--o{ QUEST_COMPLETION : completes
    HEX_MAP ||--o{ TILE : contains
    TILE ||--o{ LOCATION : holds
    LOCATION ||--o{ ENCOUNTER : "happens at"
    CLUB ||--o{ XP_LEVEL : sets
    CHARACTER ||--o{ MAP_REQUEST : asks
    CHARACTER ||--o{ DOWNTIME_POINT_ENTRY : holds
    CLUB ||--o{ DOWNTIME_ACTION : offers
    DOWNTIME_ACTION ||--o{ DOWNTIME_ENTRY : "rewards with"
    DOWNTIME_ENTRY ||--o{ DOWNTIME_ENTRY_ITEM : gives
    CHARACTER ||--o{ DOWNTIME_RESULT : gets
    CHARACTER }o--o{ DOWNTIME_POINT_REQUEST : "asked for"
    CHARACTER ||--o{ LOCATION_CREDIT : makes
    LOCATION ||--o{ LOCATION_CREDIT : "progress on"
    HEX_MAP ||--o{ TILE_VISIT : records
    CHARACTER ||--o{ TILE_VISIT : makes
    MEMBERSHIP ||--o{ MESSAGE : sends
    CLUB ||--o{ PLAY_SESSION : schedules
    PLAY_SESSION ||--o{ SESSION_RSVP : receives
    CHARACTER ||--o{ SESSION_ATTENDANCE : makes
    PLAY_SESSION ||--o{ SESSION_AWARD : awards
    CHARACTER ||--o{ MESSAGE : "may be about"
    CLUB ||--o{ EMAIL_MESSAGE : "mails"
    USER ||--o{ EMAIL_MESSAGE : receives
    EMAIL_MESSAGE ||--|| EMAIL_PAYLOAD : carries
    MEMBERSHIP ||--o{ EMAIL_PREFERENCE : prefers
    CLUB ||--o| CLUB_MAIL_SETTINGS : configures
    USER ||--o{ ONE_TIME_TOKEN : holds
    CLUB ||--o{ ONE_TIME_TOKEN : "scopes"
    USER ||--o{ NOTICE_SENT : deduplicates
    DO_NOT_EMAIL ||--o{ EMAIL_MESSAGE : suppresses
```

Reading it: a person (user) joins clubs through memberships, and a membership owns characters. Everything else hangs off a club, a character, or the item catalogue.

## Rules that apply everywhere

- **Every record belongs to a club.** Every lookup is limited to the current club, which is what keeps clubs from seeing each other's data (U12).
- **Coins are whole numbers of copper.** They are shown as copper, silver, gold, and platinum, with no platinum under 10,000 gp (U32).
- **The ledger is the history and the source of truth.** A character's inventory and coin total are the sum of their ledger lines. The app may keep running totals for speed, but the ledger wins if they disagree. Ledger entries are never edited or deleted; a mistake is fixed with a new entry.
- **Holds are not a separate record.** The code returns held_coins=0 and held_items={}, so nothing is held; everything owned is available. The lock on selling, transferring, turning in, and consuming still applies (U16).
- **Dates on manual changes default to today** and can be changed (U14).

## What a new club is seeded with

The site admin "new club" form creates a club and seeds it in one transaction.

### Seeded

| Area | Details |
| --- | --- |
| XP table | Default bands from `map/xp.py` (`copy_default_xp_table`). |
| Character options | Default species (11), classes (12), backgrounds (16) from `character_options/defaults.py`, seeded by `seed_default_options` in `character_options/services.py`. |
| Club admin | First admin from the form. The app sets a temporary password and `must_change_password`. |
| Items | Default item catalogue (167 items) from the starting-equipment data and the General Store gear list. Includes 8 stacked gear items (ammunition and small consumables sold in unit bundles). Item weights from the SRD and gear lists are set on catalogue and General Store items. |
| Starting equipment | Active template named "2024 D&D Default". Holds class entries, background entries, and level coins. Each "X or Y" option of the 2024 PHB is a choice group (see below). |
| Starting packs | The seven standard packs (Explorer's, Priest's, Dungeoneer's, Burglar's, Scholar's, Diplomat's, Entertainer's) are containers with their PHB contents as fixed slots. A character can open them. |
| Shops | General Store run by Mabel Packwell (halfling grocer), sells at 100%/buys at 75%, stocks all Adventuring Gear plus ammunition, unlimited quantity, in "Always open" rotation at street position 0. Stacked ammunition is stocked as bundle lines whose bundle size matches the item's unit size. |

### Not seeded

Characters, quests, hex maps and locations, downtime actions, ledger entries, messages, demo users, play sessions, player-written items, club mail settings. The GM creates these. Other (non-ammunition) stacked items are not seeded for a new club either; the GM converts them on the convert page or with `uv run python manage.py convert_to_stacked --club <slug>`.

### Rules

- Seeding runs in the club-creation transaction. A failure rolls back the whole club.
- Every seeder is idempotent. It never overwrites edited rows.
- Existing clubs are not backfilled. They can run `uv run python manage.py seed_starting_equipment --club <slug>` to get the current catalogue and template, then `uv run python manage.py convert_seeded_bundles --club <slug> --apply` to convert seeded bundle items to stacked items (dry run without `--apply`).
- The sibling `uv run python manage.py rename_seeded_items --club <slug>` command brings an existing club's item names up to the current seed (dry run by default; add `--apply`). It ships in a sibling story; see docs/DEPLOY.md.
- A plain run leaves an existing template unchanged. It still adds missing catalogue items and configures packs that have no slots.
- `--force` upgrades an existing template. It resets entry coins and makes each entry's lines match the default data in order. It deletes stale lines, for example an old fixed line that is now a choice default. A forced run on a template that already matches writes no lines.
- `seed_pack_containers --club <slug>` configures the packs only. It skips a pack that already has slots.
- `seed_general_store --club <slug>` adds the General Store to an existing club. It never runs automatically; a deleted shop does not return on its own.
- `seed_item_weights --club <slug> --apply` backfills SRD and gear-list weights onto seeded items whose weight is blank for an existing club. Dry run without `--apply`; never overwrites an admin-set weight. Idempotent.

### Choice groups in the default template

- Each "X or Y" in the 2024 PHB is one choice group. All its options are `is_choice=True` lines with the same `choice_group` slug (for example `weapon`, `armor`, `ranged`, `focus`, `pack`, `instrument`).
- The default option ("X") is the first line of the group. It is never also a fixed line.
- All 12 classes have choice groups. The backgrounds Artisan (`tools`), Entertainer (`instrument`) and Soldier (`gaming_set`) have one group each. Other backgrounds have no "or" and get no group.
- One option is one line. Compound options are simplified: "light crossbow + 20 bolts" keeps the crossbow in the group and the ammo is a fixed line. "Any martial/simple weapon" is a short list of named catalogue items.

## By app

### accounts

- **User**: a login (email, password, display name, and a flag that the person must choose a new password at next sign-in). Accounts are created by club admins (U20) and passwords reset by them when they administer every club the person belongs to (U21); the app sends no email. One person has one user, even with characters in several clubs. The site admin is a flag on the user.
- **Club**: a name. The unit that separates data. See [What a new club is seeded with](#what-a-new-club-is-seeded-with).
- **Membership**: a user in a club, with two separate yes/no permissions, club admin and game master. Everyone with a membership is also a player and can own characters.
- **Whitelist entry**: an email address allowed to join a club (U1). Belongs to one club; the same email can be whitelisted in several.
- **Message**: from a membership to the club's admins, free text, with an optional character it is about (the sender's selected character, U27), and a handled/closed flag set by an admin (U13). No replies are stored. Grants made from a message (U30) are ordinary ledger entries, visits, credit, or found marks that point back at the message, so the message can list what was granted from it.
- **Site feedback**: a site-level bug report or feature request from any logged-in user, sent to site admins rather than club admins (U114). Records who sent it, the club they were in when they sent it (if any), bug or feature kind, the free-text body, the page they came from, and an open/handled/closed status.

A player's email is shown only to club admins (U17). Email is optional and never carries passwords; it only delivers one-time links.
- **Club** adds `timezone` (IANA string, default from settings).

### items

- **Item**: belongs to a club. Name, description, traits and other details, a value in copper (I1), and an optional emoji symbol shown before the name (U44). Items already held or in the ledger are retired rather than deleted. A "unique" item is just an item a shop stocks one of or a game master gives out once; nothing is tracked individually. New clubs start with the default catalogue (167 items). **`is_container`** (bool, default false) marks an item as openable.
- **Stacked item fields**: **`is_stacked`** (bool, default false) marks an item that is sold in bundles but used one unit at a time; an item is a container or stacked, never both. **`unit_name`** (char, 40, blank) names the unit, such as `sheet`, `ft`, or `arrow`; unit names are never pluralised. **`value_units`** (positive int, default 1) is the number of units that `value_cp` covers (1 for normal items). CHECK rules: a stacked item cannot be a container; `value_units` is at least 1; a stacked item must have a non-blank `unit_name`.
- **Container slot**: belongs to a container item. `chance_pct` (1–100), `unknown` (bool, masks the slot as `???` before opening), `position` (order). At least one slot is required.
- **Container slot option**: one row per possible outcome in a slot. `item` (FK Item, PROTECT), `qty_min`, `qty_max` (range, min≤max), `weight` (≥1). One option = fixed entry; several = weighted "pick one" table. Roll order: chance check, then weighted pick, then uniform quantity in [min, max].
- **Container opening**: links one `opened` ledger entry to the container item, the character, and a JSON `result` (per-slot outcomes in slot order). Write-once; drives the replay and result page.

### character_options

- **Species**: a club-scoped species option (name unique per club, case-insensitive). Is-active flag; sort order.
- **Character class**: a club-scoped class option (name unique per club, case-insensitive). Is-active flag; sort order.
- **Background**: a club-scoped background option (name unique per club, case-insensitive). Is-active flag; sort order.
- Each option belongs to one club and has no default text snapshot; starting-equipment entries link to options by FK only (U97, U98, D1, D2, U104).

### player_characters

- **Character**: belongs to a club and is owned by a membership. Name and an optional level from 1 (U52, not tied to XP). The sheet (U2, U69) adds optional class, species, alignment, pronouns, a description, the six ability scores (1 to 30, with the modifier worked out as (score - 10) // 2), armor class (0 to 40), a Perception bonus (may be negative; passive Perception is 10 plus the bonus, blank shows a dash), and XP. Handing a character to another player changes the owner (U18).
  - **`died_on`** (date, nullable): the date the character died. If set, the character is dead.
  - **`death_note`** (text, blank): optional note about the death.
  - **`archived_at`** (datetime, nullable): when the character was archived. If set, the character is archived.
  - Dead and archived are independent states; each can be set without the other.
  - Properties: `is_dead` (`died_on` is set), `is_archived` (`archived_at` is set), `is_active` (not archived).
  - Queryset methods: `not_archived()`, `living()` (not dead), `dead()`. Lookups by id still find archived characters.
- **Inventory entry**: a character, an item, and a quantity. Visible only to the owner, game masters, and club admins (U19).
- **Junk mark**: a character, an item, and a quantity the player set aside to sell (U47). One per character and item. The quantity is capped at the number owned when read, so it needs no cleanup when items leave. It never touches the ledger.

- **Character status change** (append-only): one row per state change on a character. Fields: `character` (FK), `kind` (died, revived, archived, unarchived), `by` (Membership, nullable), `at` (datetime), `note` (text), `date` (date). Uses `AppendOnlyModel` so rows cannot be updated or deleted. Ordered by `-at, -id`. Index on `(character, at)`.
  - The single guard for all state checks is `player_characters/life.py`: `can_buy`, `can_sell`, `can_act`, `buy_block_reason`, `sell_block_reason`, `require_can_buy`, `require_can_sell`, `require_can_act`, plus service functions `mark_dead`, `undo_death`, `archive`, `unarchive` that write one history row each in a transaction.

### starting_equipment

- **Template**: belongs to a club, name, is-active flag. One active template per club at a time.
- **Class entry** and **background entry**: link a template to a character class / background option by FK only. Min/max level range; coins granted; magic items. The old `char_class` / `background` text columns are gone, so an entry either matches a real club option or it does not exist at all (no free-text snapshot).
- **Choice groups**: a line with `is_choice=True` belongs to a `choice_group`. The player gets one option per group. The default pick is the first line (lowest id) of the group. Lines with `is_choice=False` are always granted.
- **Claim flow**: applying starting equipment returns an entry plus additive reason codes (`no_template`, `empty_template`, `class_missing`, `class_custom`, `class_no_entry`, `class_level_not_covered`, `background_missing`, `background_custom`, `background_no_entry`). Granting anything marks the character claimed; unmatched or custom values surface as warnings instead of blocking the grant. The claim grants all fixed lines plus one picked option per choice group. After a character is saved, the player is sent to a choices page (`starting_equipment:choices`) to pick one option per group when the template has choice groups for the class/background; templates without choice groups grant the default pick immediately. The claimed flag (`starting_equipment_claimed`) tracks whether the single `Starting equipment` ledger entry has been granted, so reloading cannot grant twice. A player who leaves can finish later from the character sheet via the "Choose starting equipment" link.
- Background entries are unique per template + background option per club.

### ledger

- **Ledger entry**: a character, a date, a note ("traded to a character", "awarded by a game master"), and who made it (a person or the system). Notes whether it was recorded through an agent batch. Records what kind of event it was: award, purchase, sale, quest turn-in, quest reward, consumed, manual adjustment, or **opened** (container open).
- **Ledger line**: part of an entry. Either an item with a signed quantity, or a signed amount of coins. A purchase is one entry with a coin line and an item line. An `opened` entry has the container at `-1` and each rolled item at `+qty` (merged by item). For a stacked item the quantity counts units.

### shops

- **Shop**: belongs to a club. Name, description, shopkeeper's name and description, a default sell percentage, a default buy percentage (S1), and its look: a preset colour, a symbol, and a preset shopkeeper silhouette (U10, U36).
- **Shop stock**: a shop, an item, a quantity in stock (empty means unlimited), and optional sell and buy percentage overrides for that item in that shop (U9, S1). **`bundle_units`** (positive int, default 1) is the number of units in one bundle line. Stock lives here and carries over between rotations. Only items with a stock row are purchasable. A shop can still buy items it has no stock row for, using its default buy percentage, and that does not create a stock row. The unique key is now `(shop, item, bundle_units)`, so one shop can stock the same item in several bundle sizes, each with its own stock.
- **Rotation**: a name, an open date, and an optional close date (S2). An empty close date means always open, which is how always-open shops (U5) work. Links to the shops that are open in it; a shop can be in several rotations.

There is no separate purchase record. A purchase or sale changes the stock and writes a ledger entry that points at the shop.

### quests

- **Quest**: belongs to a club. Name, description, start date, end date, a limit on total completions in the club, and a limit on completions per character (Q1-Q3). Empty limits mean no limit.
- **Quest requirement**: an item and a quantity a player must turn in. All requirements must be met in one turn-in, and the items are always used up.
- **Quest reward**: an item and quantity, or an amount of coins. A quest can have several.
- **Quest completion**: a quest, a character, and a date. The limits are counted from these. Completing one writes ledger entries for the turn-in and the reward.

### downtime

- **Downtime point entry**: a character, a change in points (positive or negative), a note, a date, a kind (award, remove, spend, request), who made it, and a free-text source such as "result:12". Append-only. The balance is the sum of the changes and never goes below zero.
- **Downtime action**: belongs to a club. Name, description, a cost in points (at least 1), and a start and end date, with the same live rules as quests.
- **Downtime entry**: one possible reward of an action. A label, a weight (at least 1) that sets its chance, an amount of coins, and an order.
- **Downtime entry item**: an item and a quantity (at least 1) that an entry gives.
- **Downtime result**: a character, the action they spent points on, and the entry that came up.
- **Downtime point request**: a club, the member who asked, the characters, the points (at least 1), a note, a status (pending, approved, declined), and who decided and when.

### agent_access

- **Agent connection**: a user, a club, an agent label, when it was approved, last used, and revoked. Created when a game master signs in and approves an agent (A1). It holds the sign-in grant the agent uses and can be limited to one club where that person is a game master. A fixed personal token for agent software that cannot sign in is the same record with a hashed secret shown once.
- **Proposed batch**: a club, the connection and user that sent it, a date, a key that prevents duplicates when the same batch is sent twice, a status (pending, confirmed, discarded, reversed), and the source notes if the agent sends them (A3, A4).
- **Proposed line**: a batch, a character, either an item with a quantity or an amount of copper, and a note. It points at a catalogue item or a proposed new item. Applying a confirmed batch writes one ledger entry per line, marked as recorded through an agent (A4).
- **Proposed item**: a club, and the details of a new catalogue item waiting for a game master or club admin to approve (A5). It cannot be awarded until approved.
- Reversal writes new ledger entries that undo the batch; it never edits old ones (A6).
- Coming soon: proposed map changes in the same shape (A7).

### map

- **Hex map**: belongs to a club. A name, an archived flag, and no size limit (M1, M2). Safe town sits at position 0,0.
- **Tile**: a map, a position, and an optional color. Only tiles that have a location or encounter are stored; every other position is drawn blank. A tile's location count is counted from its locations (M3).
- **Location**: a tile, a name, a color, a symbol, player notes, GM notes, and a target level (M3-M5, M11). A tile can have several.
- **XP level**: per club, one row per target level band (CR 1-2 to CR 19-20) with the XP for discovering and for exploring. Filled from the default table and editable by a club admin (M13).
- **Encounter**: a location, a date, and a description of what happened (M6). Can be added during play or later.
- **Location credit**: a location, a kind (discovered or explored), a date, and a list of characters. A location has at most one of each kind. Discovery credit goes to the first group, explored credit to one group that may be different. Later characters are never added automatically; a game master or club admin can add or remove characters to correct it (M14). Credited characters also get a visit to the tile. The map marks unexplored locations among those the viewer can see and shows credited characters to everyone who can see the location (M15). A party is not stored: it is just the list of characters chosen when something is recorded.
- **Request**: a character (or several), what is asked for (tile visit, location discovered, location explored, or location found), a status (requested, approved, declined), and a date. Approving creates the visit or adds the characters to the location's credited group or found marks. Nothing is declined automatically (M12).
- **Found mark**: a location and a character that has found it without XP credit, set by a game master or club admin, or granted from a request (M12, M16). A character has found a location if it is in either credited group or has a found mark.
- **Selected character**: per person and club, the character they act as (U24). Pages that act on a character default to it.
- **Tile visit**: a map, a position, and a character that has been there (M7). It stores the position rather than the tile so empty tiles can be visited too.
- **What each person sees.** Game masters and club admins see everything, including GM notes, and can print either the full map or a players' view for a group of characters they pick (M10). A player sees the tiles visited by the characters they pick, and on those tiles the locations those characters have found, with their player notes and encounters, but never GM notes. A location on those tiles that has discovery credit but that the picked characters have not found shows as an unnamed placeholder; undiscovered locations are not shown (M8, M9, M16). The pick starts as the player's selected character (U24).

### play_sessions

- **SessionSeries**: a recurring series of play sessions (weekly or every two weeks). Belongs to a club; created by a membership (GM). Rule is `weekly` or `every_two_weeks`. Only a grouping so "cancel the rest" works.
- **PlaySession**: a single scheduled play session. Club, title, starts_at (aware UTC), ends_at (nullable), game_master (Membership), location, notes, recap (shown to players), gm_notes (GM only), cancelled (bool), series (nullable FK to SessionSeries), created/updated. Ordering by starts_at. Index on (club, starts_at). Check constraint: ends_at >= starts_at.
- **SessionRSVP**: a character's RSVP to a session. Session, character, answer (yes/maybe/no), answered_by (User), answered_at. Unique per session and character.
- **SessionAttendance**: a character's attendance at a session. Session, character, played (bool), confirmed_by (User), confirmed_at. Unique per session and character.
- **AttendanceChange**: append-only history of attendance corrections. Session, character, old_played (nullable), new_played, changed_by (User), changed_at (auto). Extends AppendOnlyModel; update/delete raise error.
- **SessionAward**: downtime points awarded for attending a session. Session, character, points (positive small int). Unique per session and character. Used to compute difference on corrections.
- **SessionSettings**: per-club settings for play sessions. One-to-one with Club. award_points (0-10, default 0), feed_token (64-char, blank until calendar feed creates it). Conditional unique constraint on feed_token where not blank.

All models are club-scoped with `club_path` set and use `ClubScopedManager`. Child tables (RSVP, Attendance, AttendanceChange, Award) use `club_path = "session__club"`.

### mail

- **EmailMessage**: an email queued for delivery. Club (nullable), user (nullable), kind, to_address, subject, status (queued, sending, sent, failed, bounced, complained), provider_id, attempts, last_error, next_attempt_at, created, sent_at. Never stores a body or a link; those live in EmailPayload and are deleted after send or final failure.
- **EmailPayload**: one-to-one with EmailMessage. text, html, reply_to, expires_at. Deleted once the message is sent or failed for good.
- **DoNotEmail**: an address that must never receive email. address (lower case, unique), reason (bounce, complaint, manual), created.
- **OneTimeToken**: a single-use, expiring token. purpose (welcome, password_reset, rsvp, unsubscribe, email_change), user, club (nullable), token_hash (unique, SHA-256), expires_at, used_at, extra (JSON). Only the hash is stored; the raw token is returned once on issue.
- **EmailPreference**: per-membership preference for a kind (reminder, notice, digest). Unique per (membership, kind). No row means default (on for reminders and notices, OFF for digest).
- **ClubMailSettings**: one-to-one with Club. contact_email (blank), reminder_days (JSON list, default [3]).
- **NoticeSent**: deduplication table for notices (reminders, cancel, change, digests). kind, key (string), user. Unique on (kind, key, user). Key holds ids and start time as text, never a link.
- **JobRun**: tracks job executions. name (unique), last_run_at, ok (bool), note.

### player_items

- **PlayerItem**: a player-written inventory entry. Belongs to a club and a character. Fields: `name` (max 80), `name_key` (lowercased, collapsed spaces, indexed), `quantity` (positive integer, at least 1), `note` (text, blank), `review` (open, left_as_is, resolved), `resolved_by_change` (nullable FK to PlayerItemChange). A character can have at most 50 PlayerItem rows. The `name_key` is computed on save from `name` for grouping and search.
- **PlayerItemChange** (append-only): history of every add, edit, remove, promote, merge, or match. Extends `AppendOnlyModel` so rows cannot be updated or deleted. Fields: `club`, `character`, `kind` (added, edited, removed, promoted, merged, matched), `old_name`, `new_name`, `quantity`, `item` (nullable FK to items.Item), `by` (nullable FK to User), `at`, `note`. Ordered by `-at, -id`.
- **PlayerNotice**: a notice for a membership (player) about item resolution. Fields: `membership` (FK), `club`, `character` (nullable), `kind` (item_promoted, item_merged, item_matched, generic), `text`, `created`, `dismissed_at` (nullable). A notice can be dismissed once; dismissing is idempotent.

All three models are club-scoped via `club_path` and `ClubScopedManager` (or `AppendOnlyManager` for PlayerItemChange).

## Settled since the first draft

1. Memberships are created when an email is whitelisted, so characters can be assigned before first sign-in.
2. Shops can buy items they do not sell, but only items they stock are purchasable.
3. Always-open shops are in a rotation with no close date.
4. Quests have no partial turn-ins.
5. Turned-in quest items are always used up.
6. No individually tracked items; a unique item is a catalogue item with a quantity of 1.
7. Messages are only marked handled or closed.
8. Map visits are per character.
9. The game master's players-only map is for a group of characters they pick.
10. Each location has one credited discovery group (the first) and one credited explored group (may differ); a game master or club admin can correct either, and everyone sees the credited characters. A party is just a list of characters, not a stored record.
11. Players can request visits, discovered, or explored credit, and a game master or club admin grants them.

## Still open

Nothing right now.

## Decisions: containers

1. Any item can become a container via `is_container`; no separate type.
2. Slot chance is 1–100; quantity is a range with min≤max.
3. Weighted "pick one" via multiple slot options; weight ≥ 1.
4. Unknown slots show `???` to players; GMs/admins see contents via `loot_preview(viewer_can_see_unknown=True)`.
5. Nesting allowed, no cycles, max depth 3 (A in B in C). Opening is one level only.
6. `opened` ledger kind: container −1, rolled items +qty (merged). One entry per open.
7. Opening only from inventory (owner, GM, or club admin). Not from shops.
8. Server-only roll; result stored in `ContainerOpening.result` and ledger lines. No reroll.
9. Player-facing previews always go through `loot_preview()`; never read slots directly.
10. Existing packs migrated by idempotent `seed_pack_containers` command; no ledger rewrite.
11. Agent/MCP output calls `loot_preview(..., viewer_can_see_unknown=False)`. Unknown items never leak.
12. Residual: an unknown slot's content item is a normal catalogue item; its name may appear elsewhere (shops, catalogue) without revealing it is in a box.
13. Default starting equipment seeding configures the seven standard packs as containers on every run (`items/pack_seeding.py`). The `seed_pack_containers` command uses the same service.

## Decisions: stacked items

1. Pool model: one inventory row per character and stacked item; quantity counts units and combining is automatic (no split or combine button).
2. Bundle size lives on the shop line (`ShopStock.bundle_units`), not on the item, so one shop can stock several bundle sizes with separate stock.
3. Buying uses `bundle_price`: `ceil(value_cp * bundle_units * sell_pct / (100 * value_units))`, integer math, no 1 cp minimum.
4. Selling uses `sale_price`: `floor(value_cp * units * buy_pct / (100 * value_units))`, integer math once from the total units sold, never per unit; a 0 cp sale is refused by slices (the function itself returns 0).
5. Unit names are never pluralised: "bundle of 100 arrow", "40 ft Rope", "1 sheet Parchment", "105 arrow Arrows".
6. `value_cp` keeps its name: it is the value that `value_units` units cover (1 for normal items).
7. `bundle_price` uses ceil with no 1 cp minimum; `percent_price` for normal items is unchanged and keeps its 1 cp minimum.
8. Non-stacked items keep `bundle_units = 1` on shop lines; a non-stacked item with `bundle_units > 1` is not enforced in the DB (forms/services enforce it).
9. CHECK `bundle_units >= 1` added on ShopStock; unique constraint renamed `unique_shop_item_bundle`.
