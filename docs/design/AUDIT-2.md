# UI audit 2 (U84)

This document lists the UI consistency problems found on every page and main workflow of the app. It covers players, game masters, club admins and the site admin, at 1920, 1280, 768 and 390 px. The fix epics of U84 plan from it. The first audit is `docs/design/AUDIT.md` (U35); its `A-` ids still appear as rules here.

No app look or behaviour changed in this audit.

## Method

- Revision walked: `main` at `b0b2bb1` (the audit tooling merge). Four walks ran in parallel, one per role group. The walk stories are listed under Screenshots.
- Rows were merged when they were the same problem on the same page or the same shared component. A merged row takes the highest severity of its sources. The Source column lists every scratch id.
- Rank: High first, then Medium, then Low. Inside a severity: theme order, then page name. `B-01` is the first row.
- Rule broken: a `DESIGN_SYSTEM.md` section, a `/site/design/` pattern, an `AUDIT.md` id that regressed, WCAG 2.1 AA, or "Best existing example: <page>" when no written rule exists.
- Themed pages (shop street and banner, quest board, chalkboard Downtime page, stalls) keep their theme. Only the consistency problems around the theme are listed.
- The sandbox has no emoji font. Empty emoji boxes in screenshots are not problems (`AUDIT.md` A-37).

Severity:

- **High**: a broken layout, an unreadable or unusable page at a width, or a contrast failure (WCAG 2.1 AA).
- **Medium**: a visible inconsistency with the design system on a common page.
- **Low**: minor polish.

Roles (the password is `demo-password` for all of them). `gm_only` gets a 403 on club-admin views, so those pages were captured as `gm` or `club_admin`.

| Role | Login | What it is |
|---|---|---|
| `site_admin` | `admin@example.com` | Site admin |
| `gm` | `gm@example.com` | Club admin and game master |
| `alice` | `alice@example.com` | Player (Aria Windrunner) |
| `bob` | `bob@example.com` | Player (Borin Stonefist) |
| `gm_only` | `gm-only@example.com` | Game master, not club admin |
| `club_admin` | `clubadmin@example.com` | Club admin, not game master |
| `anon` | none | Not logged in |

Capture commands (browser setup without root: wiki page `testing/browser-checks-without-root`):

```bash
# Every page at 1920, 1280, 768 and 390 px. Prints OVERFLOW and CLIPPED lines.
uv run python scripts/screenshots.py --audit --out <scratch>/audit
# One area only.
uv run python scripts/screenshots.py --audit --pages 'shops-*' --out <scratch>/audit
# The console sweep at the audit widths.
uv run python scripts/console_sweep.py --widths 1920,1280,768,390
```

Never commit screenshots. Attach them to the story task.

## Screenshots

Screenshots are not in the repo. Each walk story holds its zips as task attachments. A screenshot name in this document is `<page>@<width>.png` for tool shots and `walk-<workflow>-<step>@<width>.png` for walk steps. Find it in the zip of the walk that owns the row (Source prefix: PS, PP, GM or AD).

| Prefix | Walk story | Zip names |
|---|---|---|
| PS | [Audit walk: player shops, stalls and trades (U84)](https://app.codeherder.com/vaughnjbernards-account/vaughnjbernards-workspace/-/tasks/01a1d6fa-9ece-77ff-860c-cd8cd79a0fe5) | the pages zip and the walks zip (see the task attachments) |
| PP | [Audit walk: player sheet, quests, downtime, inbox, catalogue (U84)](https://app.codeherder.com/vaughnjbernards-account/vaughnjbernards-workspace/-/tasks/01a1d6fa-a0c9-73c4-91f4-a33b87515423) | `player-play-shots.zip` |
| GM | [Audit walk: game master (U84)](https://app.codeherder.com/vaughnjbernards-account/vaughnjbernards-workspace/-/tasks/01a1d6fa-a2e2-7bb1-87dc-a324019cadb8) | `gm-shots.zip` |
| AD | [Audit walk: admins, navigation, print, accessibility (U84)](https://app.codeherder.com/vaughnjbernards-account/vaughnjbernards-workspace/-/tasks/01a1d6fa-a4f1-72c1-836e-7bf9867e1681) | `u84-admin-shots.zip` (folders `audit2`, `walk`, `pdf`, `axe`) |

The zips stay on the walk stories because a story may write only its own attachments. This story links them instead of copying them. The page, width, role and screenshot columns locate each problem.

## Summary

117 rows after merging 128 scratch rows.

| Theme | High | Medium | Low | Total |
|---|---|---|---|---|
| layout and widths | 4 | 12 | 11 | 27 |
| spacing | 0 | 2 | 5 | 7 |
| buttons and actions | 0 | 5 | 7 | 12 |
| tables | 3 | 10 | 9 | 22 |
| forms | 0 | 9 | 14 | 23 |
| modals | 0 | 2 | 3 | 5 |
| empty states | 0 | 2 | 2 | 4 |
| tooltips | 0 | 0 | 1 | 1 |
| wording | 0 | 4 | 6 | 10 |
| print | 0 | 0 | 1 | 1 |
| accessibility | 1 | 1 | 3 | 5 |
| **Total** | **8** | **47** | **62** | **117** |

## Problems by theme

Columns: id, page, width, role, screenshot, rule broken, severity, source (scratch ids) and notes.

### Layout and widths

| Id | Page | Width | Role | Screenshot | Rule broken | Severity | Source | Notes |
|---|---|---|---|---|---|---|---|---|
| B-01 | accounts-message-give-map | 390 | gm | accounts-message-give-map@390.png | DESIGN_SYSTEM.md Rules (no horizontal overflow at 390) | High | GM-06 | The "Kind of map credit" button group is wider than the column. "Found mark" runs off the right edge and the page scrolls sideways. |
| B-02 | password-reset, password-reset-done, password-reset-complete, password-reset-confirm-invalid | 1920, 1280, 768, 390 | anon | password-reset@1280.png; password-reset-confirm-invalid@1280.png | `DESIGN_SYSTEM.md` "Files and load order" (all pages extend `base.html`); AUDIT.md A-24 (two bars) | High | PP-01 | All four pages show the stock Django admin chrome (blue "Django administration" header, breadcrumb, unstyled form). No brand, no parchment, no app header. |
| B-03 | shops-detail-caravan (inventory sell table) | 390 | alice | shops-detail-caravan@390.png | A-20 (residual); DESIGN_SYSTEM data_table | High | PS-01 | The "Your inventory" table is wider than its card. The quantity box and "Sell for" button are cut off at the right and only a sideways swipe inside the table shows them. |
| B-04 | walk-slips-3-print-screen; characters-print-items; characters-slips-print-aria | 768, 390 | alice | walk-slips-3-print-screen@390.png; characters-print-items@390.png; characters-slips-print-aria@768.png | OVERFLOW tool line; "Best existing example: characters-print-items"; AUDIT.md A-17 (no overflow at 390); AUDIT.md A-17 | High | PP-17, AD-21, AD-22 | On a phone the screen view of every print page scrolls sideways (765 px wide at 390). The card sheet and the slip have a fixed width. They print correctly on one A4 page. See N-17. |
| B-09 | accounts-whitelist | 390 | club_admin | walk-admin-whitelist-error@390.png | DESIGN_SYSTEM "Rules": the top bar fits at 390 px | Medium | AD-07 | The bar does not overflow but it cuts the club name ("Demo M...") and the character label ("No chara..."), and the Approvals badge loses its word. Same on every club page for GM and admins. |
| B-10 | characters-detail-alice | 1280 | alice | characters-detail-alice@1280.png | AUDIT.md A-01 (no shared page header) | Medium | AD-23 | These templates have an `h1` but do not use `components/page_header`: `characters/detail.html`, `characters/slips.html`, `characters/print.html`, `characters/print_item_choose.html`, `characters/form.html`, `trades/edit_side.html`, `shops/browse/detail.html`, and the `registration/*` pages (login, logout, password change). The swap touches templates owned by E2, E3, E4, E5 and E7. E1 does it in one pass, so those epics do not touch the header lines. |
| B-11 | characters-detail-alice | 1920, 1280, 768, 390 | alice | characters-detail-alice@1280.png | `page_header` and `back_link`; AUDIT.md A-01, A-22 | Medium | PP-06 | The sheet has its own header. A breadcrumb "Characters / Aria Windrunner" replaces the back link. |
| B-12 | club-home-club-admin | 1280 | club_admin | walk-topbar-club_admin-closed@1280.png | DESIGN_SYSTEM "Rules": top bar, initials chip below 1400 px | Medium | AD-06 | The rule says the full name shows at 1400 px and wider, and an initials chip below that. The code hides the name only below 400 px (`.user-name-text` in `components.css`), so the chip and the name show together at 768 and 1280 px, and a long name is cut ("Cleo the Club A..."). |
| B-13 | downtime-agenda | 1920, 1280 | gm | downtime-agenda@1920.png; downtime-agenda@1280.png | DESIGN_SYSTEM.md Rules (page width) | Medium | GM-22, GM-23 | The agenda fills the full width at 1920, and its title starts at 32 px at 1280. Other GM pages use a centred column that starts at 96 px, so the left edge jumps between pages. A wide calendar may be on purpose. |
| B-14 | map-tile | 1280, 390 | alice | map-tile@1280.png | `back_link` ("above the title"); AUDIT.md A-22 | Medium | PP-35 | The back link "Back to the map" sits on the same row as the "Request a visit" button, below the title, and not above it. The "Show the map for" block repeats the whole selector for one tile. |
| B-15 | quests-detail | 1280 | alice | quests-detail@1280.png | `back_link` pattern ("Back to <parent>", above the title); `page_header` has one `h1` | Medium | PP-02 | Back link reads "All quests" as a red underlined link, not "Back to quests" with an arrow. There is no page header; the quest title is inside the pinned note. |
| B-16 | shops-detail-caravan (page heading) | 1280 | alice | shops-detail-caravan@1280.png | DESIGN_SYSTEM page_header ("the one h1") | Medium | PS-04 | The shop name is centred and sits above the banner, while `shops-index`, `shops-stall-*`, `trades-*` and every other page put the h1 on the left or inside the page header. A stray shop symbol sits at the far left of the heading row and is not tied to the title. |
| B-17 | shops-stall-borin | 1280 | alice | shops-stall-borin@1280.png | DESIGN_SYSTEM page_header; banner | Medium | PS-05 | The stall title sits inside the banner on the right of the stall picture, on the ground line. The caravan title is above the banner and centred. |
| B-18 | shops-stall-own | 1280 | bob | shops-stall-own@1280.png | DESIGN_SYSTEM banner ("first in the page") | Medium | PS-06 | The "This is your shop" alert is placed between the banner picture and the ground strip, so the ground line is cut from the picture. Compare `shops-stall-borin@1280.png`. |
| B-19 | trades-detail-alice | 1280 | alice | trades-detail-alice@1280.png | A-22; DESIGN_SYSTEM back_link | Medium | PS-16 | The detail page uses the muted back link "Back to trades". `trades-propose` and `trades-edit-side` use a breadcrumb ("Trades / Trade 1 / Edit my side") in a different place and style. |
| B-20 | trades-propose | 1280 | alice | trades-propose@1280.png | DESIGN_SYSTEM Sizes (`--wm-size-form`, narrow main) | Medium | PS-17 | The propose and edit pages end at x=1120; the index and detail end at x=1184, so the page edge jumps by 64 px when you move between them. The Coins and Note boxes sit side by side with different heights and no grid. |
| B-56 | accounts-message-new, accounts-stock-request-new | 1920, 1280 | alice | accounts-message-new@1280.png | `main_class` `wm-main--narrow`; "Best existing example: downtime-request-new" | Low | PP-24 | The form card is a half-width block (`wm-narrow-block`) while the table below is full width. Other forms are a full card in the narrow column. |
| B-57 | downtime-play | 1280, 768 | alice | downtime-play@1280.png | `section`; chalkboard theme | Low | PP-23 | The reward list of one job runs 10 lines, so "Take the job" sits far from the heading. With one job the board is half empty. |
| B-58 | home-alice | 1920, 1280 | alice | home-alice@1280.png | `page_header`; A-24 | Low | PP-39 | The top bar shows only a menu toggler and the user name, with no club link or area links, so the page is a dead end if the card is missed. The hamburger is also shown at 1280 on every page (admin walk owns the bar). |
| B-59 | map-detail-alice | 1280, 390 | alice | map-detail-alice@1280.png; map-detail-alice@390.png | `wm-main--narrow` rule; "Best existing example: map-xp" | Low | PP-36 | The map page is full width (U80), so its left edge (32 px) differs from the other pages (96 px at 1280). At 390 the map shrinks to about 330 px wide and the NW to SE buttons take more room than the map controls need. |
| B-60 | map-index-alice | 1280 | alice | map-index-alice@1280.png | `page_header` actions; `card` | Low | PP-34 | "XP table" and "Map requests" are outline buttons below the title, not header actions. The map list is one link in a 260 px card. |
| B-61 | quests-index | 1280 | alice | quests-index@1280.png | `page_header` (one h1, subtitle); "Best existing example: downtime-play" | Low | PP-05 | Title has no subtitle, unlike Downtime, Items, Message and Slips. The board is one card in a full-width frame and leaves a large empty page below. |
| B-62 | shops-manage-edit | 390 | gm | shops-manage-edit@390.png | Best existing example: items-edit | Low | GM-32 | The silhouette and building pickers each take three tiles per row. The form is about 2,700 px tall before the Stock section. |
| B-63 | shops-manage-list | 390 | gm | shops-manage-list@390.png | DESIGN_SYSTEM.md section | Low | GM-29 | The Street settings card (three number fields) comes before the shop list. At 390 px the list starts after about 650 px. |
| B-64 | site-design | 1280 | site_admin | site-design@1280.png | DESIGN_SYSTEM "page_header": one `h1` per page | Low | AD-04 | The page has 3 `h1` elements, because the component samples render real `page_header` headings. Use a sample wrapper that demotes them. |
| B-65 | site-settings | 1280 | site_admin | walk-admin-site-settings-saved@1280.png | DESIGN_SYSTEM "Page width" | Low | AD-26 | Site pages (clubs, new club, settings) show a top bar with no club name or area links and a large empty page below. A single-field form is a full card. |
| B-66 | trades-edit-side | 1280 | alice | trades-edit-side@1280.png | DESIGN_SYSTEM page_header | Low | PS-22 | The Coins box has half width and leaves an empty right half. The inventory box below has full width. |

### Spacing

| Id | Page | Width | Role | Screenshot | Rule broken | Severity | Source | Notes |
|---|---|---|---|---|---|---|---|---|
| B-21 | accounts-whitelist | 1280 | club_admin | walk-admin-whitelist-duplicate@1280.png | DESIGN_SYSTEM "alert"; Best existing example: reset password result (alert below the title) | Medium | AD-12 | Flash messages ("already a member", "Site settings saved.") render above the page header. The title drops from y=99 to y=190, so the page jumps after every save. |
| B-22 | items-detail | 1280, 390 | alice | items-detail@1280.png | `definition_list`; `section` | Medium | PP-31 | The "Description" heading touches the Value row with no gap above it. Rarity and Value labels are muted small caps while the heading is a serif h2. |
| B-67 | catalogue walk: item detail | 1280 | gm | walk-catalogue-5-detail@1280.png | AUDIT.md A-04 | Low | GM-27 | The "Description" heading sits against the Value row. Retire and Delete sit outside the card, left-aligned, while Edit is in the header. |
| B-68 | characters-detail-alice | 1280, 768 | alice | characters-detail-alice@1280.png | `DESIGN_SYSTEM.md` "Spacing" tokens | Low | PP-08 | The helper text "Earned downtime during a session? Ask your game master for the points." is bold, so it reads like a value. |
| B-69 | ledger-character-history | 1280 | alice | ledger-character-history@1280.png | `section`; `form_layout` | Low | PP-33 | "Page 1 of 1" is plain text with no pager style. The "Downtime points" heading is a small serif h3, not the `section` bar used on message-new. |
| B-70 | shops-detail-caravan (junk row) | 1280 | alice | shops-detail-caravan@1280.png | DESIGN_SYSTEM tokens: Spacing | Low | PS-03 | The "Sell junk" button touches the table header with no gap. The coin lines above have a different gap from the lines below. |
| B-71 | site-clubs | 390 | site_admin | walk-admin-site-clubs@390.png | DESIGN_SYSTEM "icon"; Best existing example: site-clubs@1280 | Low | AD-16 | At 390 the "+" icon touches the label ("+New club"). At 1280 there is a gap. |

### Buttons and actions

| Id | Page | Width | Role | Screenshot | Rule broken | Severity | Source | Notes |
|---|---|---|---|---|---|---|---|---|
| B-23 | characters-detail-alice | 1280, 390 | alice | characters-detail-alice@1280.png | `DESIGN_SYSTEM.md` "One primary action per page"; AUDIT.md A-21 | Medium | PP-07 | "Print sheet" is the red primary and the only primary. "Spend" and "Request points" next to Downtime points are bold red underlined text links, not buttons. |
| B-24 | shops-buy-modal | 390 | alice | shops-buy-modal@390.png | A-32 (not fixed) | Medium | PS-08 | When the total is more than the coins, the modal says "-1 gp (not enough coins)" but "Buy as Aria Windrunner" stays active. The submit fails after the page reloads (`walk-buying-3-modal-qty3-too-many@390.png`, `walk-buying-4-result@390.png`). |
| B-25 | shops-manage-list-club-admin | 1280 | club_admin | shops-manage-list-club-admin@1280.png | DESIGN_SYSTEM "Light only. One primary action per page" | Medium | AD-15 | Two primary buttons: header "New shop" and the street settings "Save". Make Save secondary or move the street settings to its own page. |
| B-26 | shops-stall-buy-modal | 1280 | alice | walk-stalls-9-result@390.png | Best existing example: walk-buying-4-result (shop buy) | Medium | PS-25 | After a stall purchase the page returns to the street, not to the stall. A shop purchase stays on the shop. |
| B-27 | trades-detail-alice | 1280 | alice | trades-detail-alice@1280.png | DESIGN_SYSTEM page_header ("one primary action") | Medium | PS-15 | The actions are on two rows. "Cancel this trade" (outline red) sits alone above "Change what you give" and "Approve the trade as shown above". |
| B-72 | accounts-index-club-admin | 1280 | club_admin | accounts-index-club-admin@1280.png | DESIGN_SYSTEM "page_header": one primary action | Low | AD-10 | People has no page action, so the Whitelist page is reachable only from the side menu. Best existing example: `site-clubs` (header "New club" action). |
| B-73 | catalogue walk: item detail (retired) | 390 | gm | walk-catalogue-9-after-retire@390.png | DESIGN_SYSTEM.md Rules (touch targets) | Low | GM-28 | Restore and Delete stack at different widths. The hint sits under them. |
| B-74 | characters-junk | 1280 | alice | characters-junk@1280.png | `form_layout` ("a primary Save and a secondary Cancel") | Low | PP-14 | The form has Save and no Cancel. Compare characters-edit. |
| B-75 | characters-print-items, characters-slips-print | 390 | alice | characters-print-items@390.png | AUDIT.md A-19; icon spacing | Low | PP-18 | The "Print" button icon touches its label. The back link and the Print button share one row, and the instruction text below is in muted grey at body size. |
| B-76 | downtime-agenda | 1280 | gm | downtime-agenda@1280.png | DESIGN_SYSTEM.md page_header (one primary action) | Low | GM-24 | "Add rotation", "Add quest" and "Add downtime action" are three equal outline buttons. Manage pages use one red "+ New x" button. |
| B-77 | downtime-requests-gm-only | 1280 | gm_only | downtime-requests-gm-only@1280.png | DESIGN_SYSTEM.md page_header (one primary action, in the header); AUDIT.md A-01 residual | Low | GM-21 | "Request points" sits below the title as a small button. Other list pages (`quests-manage`, `characters-index-gm`) put the primary action beside the title. |
| B-78 | trades-detail-requested | 1280 | bob | walk-trades-6-bob-accept-blocked@1280.png | DESIGN_SYSTEM page_header ("one primary action") | Low | PS-23 | "Accept trade request and propose items" is a long label (about 40 characters) on one button; at 390 it wraps over two lines. The Decline button next to it uses the outline red look of "Cancel this trade", but the result of Cancel and Decline is not explained. |

### Tables

| Id | Page | Width | Role | Screenshot | Rule broken | Severity | Source | Notes |
|---|---|---|---|---|---|---|---|---|
| B-05 | accounts-message-inbox | 1920, 1280, 768, 390 | gm | accounts-message-inbox@1920.png; accounts-message-inbox@1280.png; accounts-message-inbox@768.png; accounts-message-inbox@390.png | DESIGN_SYSTEM.md data_table (`td.actions`); AUDIT.md A-20 residual; DESIGN_SYSTEM.md data_table; AUDIT.md A-20 residual; AUDIT.md A-20 residual | High | GM-01, GM-02, GM-03, GM-04 | The inbox Actions column is wider than the table area at every width. "Give map credit" or "Mark handled" is cut off, and at 390 the message text is off screen too. The inbox is the GM's action list. |
| B-06 | downtime-requests-gm-only | 768, 390 | gm_only | downtime-requests-gm-only@390.png; downtime-requests-gm-only@768.png | AUDIT.md A-20 residual | High | GM-07, GM-08 | Approve and Decline sit in the last column: off screen at 390, behind a scroll at 768. A long note wraps to six lines, so the row is tall and the buttons stay hidden. |
| B-07 | map-requests | 768, 390 | gm | map-requests@390.png; map-requests@768.png | AUDIT.md A-20 residual | High | GM-09, GM-10 | Approve and Decline are off screen at 390 and need a scroll at 768. The row is 180 px tall for one line of content. |
| B-28 | accounts-index-club-admin | 390 | club_admin | walk-admin-members-list@390.png | AUDIT.md A-20 (tables clip columns at 390 px) | Medium | AD-08 | The People table scrolls sideways. The email is cut and the Reset password button (the only action) is off screen. |
| B-29 | characters-detail (shop toggle on the sheet); characters-detail-alice | 390 | bob, alice | walk-stalls-1-sheet-toggle@390.png; characters-detail-alice@390.png | DESIGN_SYSTEM form_layout; A-11; A-20; `data_table` | Medium | PS-26, PP-09 | At 390 the sheet inventory table loses its Available and action columns, and the only scroll cue is a faint edge shadow. The "Sell my junk in my shop" switch is off-centre (centred at 390, left at 1280). |
| B-30 | characters-slips-alice | 390 | alice | characters-slips-alice@390.png | A-20; touch targets (`DESIGN_SYSTEM.md` "Rules") | Medium | PP-16 | The tick boxes are 18 px, below the 44 px phone target. The Species column is cut off and needs a sideways scroll. |
| B-31 | downtime-actions | 390 | gm | downtime-actions@390.png | AUDIT.md A-20 residual | Medium | GM-13 | The Edit button is cut at the right edge ("Ed"). |
| B-32 | downtime-requests-alice | 390 | alice | downtime-requests-alice@390.png | A-20; `data_table` | Medium | PP-19 | Status is the last visible meaning of the page and sits off screen at 390. The first row is cut at "Requested". |
| B-33 | items-index | 1920, 1280 | alice | items-index@1280.png | `data_table`, `empty_state`; AUDIT.md A-08 | Medium | PP-28 | The "Traits" column is empty on every row. Value is right-aligned and Rarity is left-aligned with no gap. |
| B-34 | ledger-character-history | 390 | alice | ledger-character-history@390.png | A-20 | Medium | PP-32 | Dates break across two lines ("2026-" "11-13"). All five columns squeeze, so lines wrap to 3 lines. |
| B-35 | quests-manage | 768, 390 | gm | quests-manage@390.png; quests-manage@768.png | AUDIT.md A-20 residual | Medium | GM-11, GM-12 | Edit and Delete are off screen at 390 and need a scroll at 768. The quest name wraps to three lines. |
| B-36 | shops-detail-caravan (inventory sell rows) | 1280 | alice | shops-detail-caravan@1280.png | Best existing example: trades-propose (inventory table) | Medium | PS-02 | The "Sell for" row has a different shape from every other table. The Quantity box and the button float at the far right under no column header. |
| B-37 | trades-index | 390 | alice | trades-index@390.png | A-07; A-20 | Medium | PS-13 | The date wraps over three lines ("Nov. / 13, / 2026") and the names wrap over two or three lines. The Open table has four columns of equal weight. |
| B-79 | accounts-index-club-admin | 1280 | club_admin | accounts-index-club-admin@1280.png | DESIGN_SYSTEM "data_table" (`td.actions`); Best existing example: characters-detail-alice (row icon buttons with tooltips) | Low | AD-09 | Every row has a text "Reset password" outline button, taller than the row text. The name and email sit at the top of the cell instead of centred against it. |
| B-80 | accounts-message-inbox | 1280 | gm | walk-inbox-13-all-final@1280.png | DESIGN_SYSTEM.md data_table | Low | GM-05 | Button groups sit at different offsets per row (first row: "Reopen" right-aligned; second row: left). Rows with and without Give buttons look unaligned. |
| B-81 | accounts-message-new, accounts-stock-request-new | 390 | alice | accounts-message-new@390.png | A-20 | Low | PP-25 | The message table scrolls sideways at 390 (CLIPPED line). Date and Character come before the message and status, so the status is the column that moves out of view. |
| B-82 | accounts-whitelist | 1280 | club_admin | walk-admin-whitelist-success@1280.png | DESIGN_SYSTEM "data_table" | Low | AD-13 | The "Whitelisted emails" table has one column (email). It has no status (joined or not), no date, and no row action. |
| B-83 | characters-directory-alice | 1280 | alice | characters-directory-alice@1280.png | `status_badge`; A-07 | Low | PP-15 | "Requested" and "Accepted" badges sit with no gap, and "Propose trade" is a plain link in the same cell. The header "Trades with Aria Windrunner" is long. |
| B-84 | items-index | 390 | alice | items-index@390.png | A-20 | Low | PP-29 | Names wrap to two lines and the where-to-buy buttons make each row 46 px high while the others are 30 px. |
| B-85 | quests-detail | 1280, 390 | alice | quests-detail@1280.png; quests-detail@390.png | `data_table` ("Do: wrap in wm-table-scroll"); A-07 | Low | PP-03 | The turn-in table shrinks to its content (about 230 px) in a 320 px card. The status badge has no column header. |
| B-86 | shops-manage-list-club-admin | 390 | club_admin | walk-admin-street-error@390.png | AUDIT.md A-20 | Low | AD-17 | The shops table clips from the Sell % column at 390. The scroll shadow is the only hint. |
| B-87 | shops-stall-borin (Your inventory) | 1280 | alice | shops-stall-borin@1280.png | A-07 | Low | PS-07 | Under the stall the "Available" header is left-aligned but the numbers are right-aligned, far from the header. The Qty column is left-aligned. |

### Forms

| Id | Page | Width | Role | Screenshot | Rule broken | Severity | Source | Notes |
|---|---|---|---|---|---|---|---|---|
| B-100 | trades-propose | 1280 | alice | trades-propose@1280.png | A-15 | Low | PS-18 | In "Coins to give" the platinum label is a dark filled pill with white text, while gp, sp and cp are plain text with a dot. The four fields are 76 px wide with no label above them. The same dark chip appears on `characters-transfer` (B-39). |
| B-101 | walk-inbox-2-sent, walk-inbox-4-stock-sent | 1280, 390 | alice | walk-inbox-2-sent@1280.png | `alert` | Low | PP-27 | After a send the page reloads on the same form with a flash at the top and the new row far below. Focus is not moved to the flash. |
| B-38 | characters-edit, characters-create | 1280, 768 | alice | characters-edit@1280.png; characters-create@1280.png | `form_layout` ("forms stop at 40 rem"); `back_link` | Medium | PP-11 | The form is 72 rem wide with six fields in a row. A breadcrumb replaces the back link. |
| B-39 | characters-transfer | 1280, 390 | alice | characters-transfer@1280.png | A-09 (plain bullet lists); `form_layout` | Medium | PP-12 | The item list is a plain bullet list. The "pp" chip is a dark pill and the gp, sp and cp labels are plain text. |
| B-40 | downtime-request-new | 1280 | alice | downtime-request-new@1280.png | `form_layout` ("secondary Cancel"); `back_link` | Medium | PP-21 | The secondary button is labelled "Point requests" and not "Cancel". There is no back link. |
| B-41 | items-edit | 390 | gm | items-edit@390.png | DESIGN_SYSTEM.md form_layout; Best existing example: shops-manage-edit (no cramped inputs) | Medium | GM-14 | The four coin inputs share one row. The gp box shows "5(" for 50. Shared cause: the coin input widget (see the trades and quests rows). |
| B-42 | map-edit | 1280, 390 | gm | map-edit@1280.png; map-edit@390.png | DESIGN_SYSTEM.md form_layout (forms stop at 40 rem; no nested card); Best existing example: shops-manage-edit | Medium | GM-25, GM-26 | The form sits in a card whose header repeats the h1. The input fills the card (about 50 rem), while shop, item and quest forms have no card and stop at 40 rem. |
| B-43 | quests-edit | 390 | gm | quests-edit@390.png | DESIGN_SYSTEM.md form_layout | Medium | GM-15 | The reward coin row has the same cramped inputs. Tool: `CLIPPED quests-edit (input.form-control)`. Shared cause: the coin input widget. |
| B-44 | site-design | 1280 | site_admin | site-design@1280.png | WCAG 2.1 A 1.3.1 / 4.1.2 (form labels); DESIGN_SYSTEM "form_layout" | Medium | AD-02 | axe: 2 `.form-control` samples have no label (the form-layout sample). The reference page models a pattern it breaks. |
| B-45 | trades-edit-side | 390 | alice | trades-edit-side@390.png | DESIGN_SYSTEM form_layout | Medium | PS-20 | The four coin fields are 40 px wide and the typed value is cut off ("0" is half hidden). The CLIPPED line lists `input.form-control`. Shared cause: the coin input widget. |
| B-46 | trades-edit-side | 1280 | alice | walk-trades-9-after-edit@1280.png | DESIGN_SYSTEM form_layout (errors with an icon) | Medium | PS-21 | A value above the available count shows the browser's own bubble ("Value must be less than or equal to 1.") and not the inline error with an icon that other forms use. The message appears over the next row. |
| B-88 | accounts-whitelist | 390 | club_admin | walk-admin-whitelist-success@390.png | DESIGN_SYSTEM "form_layout" | Low | AD-11 | The "Game master" checkbox is indented about 24 px from the other fields at 390 and 1280. |
| B-89 | characters-adjust | 390 | gm | characters-adjust@390.png | DESIGN_SYSTEM.md form_layout | Low | GM-18 | The Kind select cuts its text: "Default (award for give, adjustment for tak". |
| B-90 | characters-adjust | 390 | gm | characters-adjust@390.png | DESIGN_SYSTEM.md form_layout | Low | GM-19 | The Item and Quantity labels are lighter than the bold labels above them. The same formset in the `inbox-give-items-modal@390.png` modal has bold grey labels. |
| B-91 | characters-consume-player | 1280, 390 | alice | characters-consume-player@1280.png | `form_layout`; A-09 | Low | PP-13 | The quantity input sits inside a sentence. "Recent changes (last 30 days)" is a bullet list that wraps in a 450 px column inside a 1090 px card. |
| B-92 | characters-junk-modal | 390 | alice | characters-junk-modal@390.png | DESIGN_SYSTEM form_layout | Low | PS-29 | "How many are junk?" is a plain input that starts at 0 and the help says "0 removes the junk mark". The modal heading is "Mark junk"; the row button is "Mark as junk". |
| B-93 | downtime-action-edit | 390 | gm | downtime-action-edit@390.png | DESIGN_SYSTEM.md form_layout | Low | GM-16 | Tool: `CLIPPED downtime-action-edit (input.form-control)`. A text input is wider than its box. |
| B-94 | downtime-points-award (walk: no note) | 390 | gm | walk-awards-9-award-validation@390.png | DESIGN_SYSTEM.md form_layout (required mark) | Low | GM-20 | Note is required, but its label has no `*`. The user finds out from the browser tip "Please fill out this field". |
| B-95 | ledger-index | 390 | gm | ledger-index@390.png | Best existing example: accounts-message-inbox (filter pills) | Low | GM-31 | The filter form is about 600 px tall: seven fields, a tick box and two buttons, mixed one and two per row. Rows start below the fold. |
| B-96 | map-request-visit, map-request-credit | 1280 | alice | map-request-visit@1280.png | `back_link`; `form_layout` | Low | PP-37 | No back link. Fields "Column (q)" and "Row (r)" show internal names. |
| B-97 | quests-edit | 1280 | gm | quests-edit@1280.png | Best existing example: shops-manage-edit | Low | GM-17 | Four blank requirement forms and four blank reward forms show by default. Each has a "Delete" tick box that does nothing for an unsaved row. |
| B-98 | shops-manage-list | 1280 | gm | shops-manage-list@1280.png | DESIGN_SYSTEM.md form_layout | Low | GM-30 | The street settings fields are 12 rem wide, but the card is full width. The fields look lost in the card. |
| B-99 | shops-manage-list-club-admin | 390 | club_admin | walk-admin-street-error@390.png | DESIGN_SYSTEM "form_layout" (errors with an icon) | Low | AD-18 | The invalid field gets an amber border and an amber icon, while the message below is red with a red triangle. Two tones for one error. |

### Modals

| Id | Page | Width | Role | Screenshot | Rule broken | Severity | Source | Notes |
|---|---|---|---|---|---|---|---|---|
| B-102 | items-where-to-buy-modal | 390 | alice | items-where-to-buy-modal@390.png | DESIGN_SYSTEM modal_frame | Low | PS-28 | The modal is full screen at 390 for a one-row table, with a large blank area. The "Shops" heading repeats the title. |
| B-103 | map-tile-modal | 390 | alice | map-tile-modal@390.png | `modal_frame` ("below sm the modal is full screen") | Low | PP-38 | The modal is full screen but the body is a big empty block, and the page below shows through at the bottom. |
| B-104 | shops-buy-modal | 390 | alice | shops-buy-modal@390.png | DESIGN_SYSTEM modal_frame | Low | PS-09 | The three coin lines (Total, Coins before, Coins after) are stacked label over value at 390 and in a two-column list at 1280 (`walk-stalls-8-buy-modal@1280.png`). The labels use the muted caps style; the other modals (`shops-sell-modal@390.png`) use the same labels with different spacing. |
| B-47 | downtime-play, walk-downtime-2-spend-modal | 390 | alice | downtime-play@390.png; walk-downtime-2-spend-modal@390.png | `modal_frame`; "Best existing example: shops-buy-modal" | Medium | PP-22 | The spend result opens a white modal on the chalkboard page, so the theme breaks. Wheel slice labels are cut ("A loaf of b…", "The golden…"). |
| B-48 | shops-sell-modal | 390 | alice | shops-sell-modal@390.png | Best existing example: shops-sell-junk-modal | Medium | PS-10 | The sell confirm modal shows the warning "This item isn't marked as junk." with no explanation of why it matters or what happens. The title is "Sell Healing potion" with a raw item icon, the buy modal title is "Buy Healing potion" and repeats the name in the body. |

### Empty states

| Id | Page | Width | Role | Screenshot | Rule broken | Severity | Source | Notes |
|---|---|---|---|---|---|---|---|---|
| B-105 | items-where-to-buy | 1280 | alice | items-where-to-buy@1280.png | DESIGN_SYSTEM empty_state | Low | PS-27 | "Not for sale anywhere today." is one bare line and a plain "Back to items" link. The link is not the `back_link` pattern (no arrow, no gap, below the text) (A-08, A-22). |
| B-106 | trades-index (Closed trades) | 1280 | alice | trades-index@1280.png | DESIGN_SYSTEM empty_state; data_table_empty | Low | PS-12 | "No closed trades." is a table row under a full header, with the column widths changed from the Open table above (FROM, TO, STATUS and DATE sit at different x positions in the two tables). |
| B-49 | shops-sell-junk | 1280 | alice | shops-sell-junk@1280.png | DESIGN_SYSTEM empty_state; "Don't nest cards" | Medium | PS-11 | The empty state is a half-width box inside a card, with white space to its right. The `empty_state` pattern is a full-width block. |
| B-50 | walk-catalogue-3-search-none | 1280, 390 | alice | walk-catalogue-3-search-none@1280.png | `empty_state` | Medium | PP-30 | The page has no search box and no filter, so the "no hit" empty state cannot be shown (`?q=zzz` returns the full list). See "Needs the owner". |

### Tooltips

| Id | Page | Width | Role | Screenshot | Rule broken | Severity | Source | Notes |
|---|---|---|---|---|---|---|---|---|
| B-107 | club-home-club-admin | 1280 | club_admin | walk-topbar-club_admin-menu@1280.png | DESIGN_SYSTEM "icon" (icon-only buttons carry a label) | Low | AD-25 | The menu close button and the modal close button have `aria-label` but no tooltip. The labels are fine; only mouse users get no hint. |

### Wording

| Id | Page | Width | Role | Screenshot | Rule broken | Severity | Source | Notes |
|---|---|---|---|---|---|---|---|---|
| B-108 | accounts-reset-password | 1280 | club_admin | walk-admin-reset-confirm@1280.png | DESIGN_SYSTEM "back_link"; wording | Low | AD-14 | The confirm page has no back link, but the result page has "Back to people". The title changes from "Reset password" to "Password reset". |
| B-109 | characters-detail-alice | 1280 | alice | characters-detail-alice@1280.png | "Best existing example: club-home-alice labels" | Low | PP-10 | Four names for one area: top bar "Character", home tile "My character", breadcrumb "Characters", page "Aria Windrunner". The sheet button says "Transfer"; the page it opens says "Move loot"; the home tile says "Move items". The home tile names live in `club_home.html` (E1); E4 changes only the sheet side. |
| B-110 | club-home-alice | 1280 | alice | club-home-alice@1280.png | "Best existing example: club-home-alice sections" | Low | PP-40 | The "Trades" area has two tiles named "Trades" and "Propose trade". "Map" holds "Map", "Map requests", "XP table". |
| B-111 | downtime-requests-alice | 1280 | alice | downtime-requests-alice@1280.png | `page_header` | Low | PP-20 | Page title "Downtime point requests"; button "Request points"; the form page title "Request downtime points" and its cancel button "Point requests". The "Decided" column is empty for pending rows. |
| B-112 | login, password-change | 1280 | anon, alice | login@1280.png; password-change@1280.png | `form_layout` | Low | PP-41 | The login page has no "Forgot your password?" link. The password-change page has no Cancel or back link, and its help list is a plain bullet list. |
| B-113 | trades-detail-alice | 390 | alice | walk-trades-18-cancelled@390.png | Best existing example: shops-detail-caravan (success alert) | Low | PS-24 | After "Cancel this trade" the page shows the success alert "Trade cancelled." with a green tick, and the banner says the same again. The two lines repeat each other. The shop messages belong to E2, the trade messages to E3. Use one wording rule. |
| B-51 | characters-slips-print | 1280 | alice | characters-slips-print@1280.png | DESIGN_SYSTEM "alert"; Best existing example: whitelist (error only after a submit) | Medium | AD-19 | The picker shows a red "Tick at least one character." alert on first load, before the player did anything. |
| B-52 | trades-detail-alice | 1280 | alice | trades-detail-alice@1280.png | DESIGN_SYSTEM status_badge | Medium | PS-14 | Date formats differ: the index table uses "Nov. 13, 2026", the detail banner uses "13 Nov 2026" (`walk-trades-13-completed@1280.png`). The status reads "Accepted" while the banner says "Both of you need to approve again" and both badges say "not approved". |
| B-53 | walk-inbox-9-alice-status-after-give | 1280 | alice | walk-inbox-9-alice-status-after-give@1280.png | `status_badge` | Medium | PP-26 | After a give the message changes to "Handled" and nothing says what was given. There is no link to the ledger or sheet, and the player gets no notice. |
| B-54 | walk-turnin-3-submitted | 1280, 390 | alice | walk-turnin-3-submitted@1280.png | `alert` pattern; "Best existing example: points-3-submitted (flash then list)" | Medium | PP-04 | After a successful turn-in the page stays on the quest. The success flash is at the top and pushes the content down. |

### Print

| Id | Page | Width | Role | Screenshot | Rule broken | Severity | Source | Notes |
|---|---|---|---|---|---|---|---|---|
| B-114 | characters-slips-print | 1280 | alice | walk-print-characters-slips-print@print.png | Best existing example: map-print (prints only the content) | Low | AD-20 | Print of the picker prints the table with empty tick boxes and the red alert, but no slips. |

### Accessibility

| Id | Page | Width | Role | Screenshot | Rule broken | Severity | Source | Notes |
|---|---|---|---|---|---|---|---|---|
| B-08 | site-design | 1280 | site_admin | site-design@1280.png | WCAG 2.1 AA 1.4.3 contrast | High | AD-01 | axe: 15 inline `code` samples are pink `#e83e8c` on `#fbf8f3`, 3.6:1 (needs 4.5:1). Same at 390. |
| B-115 | accounts-index-club-admin | 1280 | club_admin | accounts-index-club-admin@1280.png | WCAG 2.1 A 2.4.1 bypass blocks | Low | AD-24 | There is no skip link in `base.html`. A keyboard user tabs through the top bar stops on every page before the content. |
| B-116 | map-print | 1280 | alice | map-print@1280.png | WCAG 2.1 A 4.1.2 (axe nested-interactive) | Low | AD-05 | The hex map SVG has focusable descendants. Same at 390. |
| B-117 | trades-propose | 1280 | alice | trades-propose@1280.png | WCAG 2.1 AA 1.4.3 (not measured) | Low | PS-19 | The disabled Rope row (grey text on cream, field grey) looks lighter than 4.5:1. I did not measure it; the admin walk (S5) runs the axe check. |
| B-55 | site-design | 390 | site_admin | site-design@390.png | WCAG 2.1 A 2.1.1 keyboard | Medium | AD-03 | axe: scrollable `pre` code blocks cannot take focus (5 at 1280, 17 at 390). A keyboard user cannot scroll them. |

## Tool findings

### OVERFLOW

`scripts/screenshots.py --audit` printed these OVERFLOW lines. Every other page, in all four walks, had none.

| Line | Width | Problem |
|---|---|---|
| `OVERFLOW accounts-message-give-map` | 390 | B-01 |
| `OVERFLOW characters-print-items`, `characters-print-item-full`, `characters-print-item-grid` | 390 | B-04 |
| `OVERFLOW characters-slips-print-aria` | 390, 768 | B-04 |

The walk also found `walk-slips-3-print-screen@390` at 765 px wide (B-04). The player and admin walks listed the same print lines; they are one set.

### CLIPPED

`span.visually-hidden`, `label.visually-hidden` and `legend.visually-hidden` lines are dropped. They are screen-reader text that the CSS clips on purpose. `div.wm-table-scroll` marks a table that scrolls by design; it is a defect only when the scroll hides the key column or the action.

| Line (pattern) | Pages | Problem |
|---|---|---|
| `input.form-control` | `trades-edit-side` | B-45 |
| `input.form-control` | `items-edit` | B-41 |
| `input.form-control` | `quests-edit` | B-43 |
| `input.form-control` | `downtime-action-edit` | B-93 |
| `input.form-control` | `agent-batch-detail`, `agent-proposed-item-detail` | No row. The GM walk recorded no problem. A fix story for the agent pages should check them. |
| `pre` | `site-design` (768, 1280, 1920) | B-55 |
| `div.wm-table-scroll` | `shops-detail-lantern`, `shops-detail-caravan` | B-03 |
| `div.wm-table-scroll` | `accounts-message-inbox`, `accounts-message-inbox-club-admin` | B-05 |
| `div.wm-table-scroll` | `downtime-requests-gm-only` | B-06 |
| `div.wm-table-scroll` | `map-requests` | B-07 |
| `div.wm-table-scroll` | `quests-manage`, `quests-manage-club-admin` | B-35 |
| `div.wm-table-scroll` | `downtime-actions` | B-31 |
| `div.wm-table-scroll` | `characters-detail-alice`, `characters-detail-gm`, `characters-detail-gm-only` | B-29 |
| `div.wm-table-scroll` | `characters-slips-alice` | B-30 |
| `div.wm-table-scroll` | `downtime-requests-alice` | B-32 |
| `div.wm-table-scroll` | `accounts-message-new`, `accounts-stock-request-new` | B-81 |
| `div.wm-table-scroll` | `accounts-index`, `accounts-index-club-admin` | B-28 |
| `div.wm-table-scroll` | `shops-manage-list`, `shops-manage-list-club-admin` | B-86 |
| `div.wm-table-scroll` | `characters-directory-alice`, `characters-slips-print`, `characters-slips-gm`, `characters-index-gm`, `characters-index-gm-only` | No separate row. The scroll is by design and the walks recorded no hidden key column. |
| `div.wm-table-scroll` | `items-index-gm`, `items-index-gm-only`, `items-index-club-admin`, `ledger-index*`, `shops-rotation-list`, `shops-manage-edit`, `downtime-points-award`, `agent-batches*`, `agent-connections`, `agent-proposed-items`, `agent-batch-detail` | No separate row. Same reason. |
| `div.wm-table-scroll` | `characters-junk-modal`, `characters-consume-modal`, `inbox-*-modal`, `shops-buy-modal`, `shops-sell-modal`, `shops-sell-junk-modal` | The table behind or inside a modal. No separate row. |

### Console sweep

`scripts/console_sweep.py --widths 1920,1280,768,390` ended with `Done: 0 problem(s).` on every run: the shops and trades walk, the player walk, the GM walk (15 glob groups) and the admin walk (12 runs). The walk scripts logged no console error, no page error and no 5xx. One 403 in the GM walk came from the walk script, not from a page.

### axe-core and print emulation

- axe-core 4.10.2 (WCAG 2.0 and 2.1, A and AA) on 23 pages at 1280 and 390. `site-design`: colour-contrast (15, B-08), label (2, B-44), scrollable-region-focusable (5 at 1280, 17 at 390, B-55). `map-print`: nested-interactive (1, B-116). The other 21 pages had no violation.
- Print emulation (1280 and A4 PDF) of the seven print pages: each fits one A4 page, nav, buttons and `.no-print` elements are hidden, the body is black on white, and nothing extends past the page. The print pages fail on screen at 390, not in print (B-04). The slips picker prints with no slips (B-114).
- Keyboard: Tab through the whitelist, members, shop management, new club and `/site/design/` pages showed a visible focus ring everywhere and no trap. The only gap is the missing skip link (B-115).

## Needs the owner

Every fix below needs a feature or behaviour change, or a product decision. The fix epics do not do them. A row that depends on an answer stays out of its epic's first story.

| Id | Question | Related problems | Source |
|---|---|---|---|
| N-01 | **Buy with too few coins (A-32).** The buy modal says "not enough coins" and the button still works. The page then rejects the purchase. Should the modal disable the button? | B-24 | PS Q1 |
| N-02 | **Confirm step before final actions.** These run on one click with no confirm: cancel and decline a trade, item delete and retire, quest delete, rotation delete, stock remove, request approve and decline. Item delete may retire the item instead, and the page does not say so before the click. Should any of them ask first? | B-78, B-67, B-73, B-06, B-07, B-35 | PS Q2, Q3; GM Q1 |
| N-03 | **Decline has no reason.** A GM declines a point request, or a trade request, with no reason field. The player sees no reason. Is that on purpose? | B-06, B-78 | GM Q2 |
| N-04 | **One accepted trade per character.** A character with an accepted trade cannot accept a second request. The Accept button shows as usual and the error appears after the click. Should the button explain this up front? | B-78 | PS Q4 |
| N-05 | **Status "Accepted" with nothing approved.** After a side is edited, the status stays "Accepted" while both approvals reset. Should the badge read "Needs approval"? | B-52 | PS Q5 |
| N-06 | **Where to buy lists shops only.** A player stall that sells the item does not show in "Where to buy". Is that intended? | B-102 | PS Q6 |
| N-07 | **Stall purchase goes to the street.** A shop purchase stays on the shop. A stall purchase returns to the street. Should both stay on the page you bought from? | B-26 | PS Q7 |
| N-08 | **Sell flow warns about non-junk.** The sell confirm modal warns "This item isn't marked as junk." and lets the player sell at the junk price. Should selling non-junk be allowed in this flow? | B-48 | PS Q8 |
| N-09 | **Item search.** U84 names "browse, search, detail" for the catalogue, but `items-index` has no search box or filter. Is search wanted, or is the full list enough? | B-50 | PP Q1 |
| N-10 | **Turn-in feedback.** After a turn-in the player stays on the quest. Should the page show the rewards, and should a finished quest leave the board? | B-54 | PP Q2 |
| N-11 | **Give notice.** After a GM gives coins or items from a message, the player sees only "Handled". Should the player see what arrived and get a notice? | B-53 | PP Q3 |
| N-12 | **Map credit not listed under "Granted".** After "Give map credit" the inbox row lists coins and items but not the map credit. | B-05 | GM Q3 |
| N-13 | **Stock requests cannot be filled from the inbox.** Stock request rows offer only Mark handled and Close. Plain messages also offer the Give buttons. Should a stock request have a Give items button? | B-80 | GM Q4 |
| N-14 | **Password reset entry.** The reset pages use Django admin templates, and the login page has no "Forgot your password?" link. Is a reset link wanted on the login page? | B-02, B-112 | PP Q4 |
| N-15 | **Sheet header.** The sheet, edit and create pages use a boxed header and a breadcrumb. Do they keep their own look, or follow `page_header`? | B-11, B-38, B-10 | PP Q5 |
| N-16 | **Wheel modal theme.** The spend result opens a white modal on the chalkboard page. Should it stay white or take the chalkboard theme? | B-47 | PP Q6 |
| N-17 | **Print pages on a phone.** Should the screen view of the card sheet and slip pages fit a phone, or stay at the print size? | B-04 | PP Q7; AD Q5 |
| N-18 | **Role split.** A `gm_only` user gets 403 on the inbox, shop and quest management, item create and edit, the agenda and downtime actions. The Approvals badge shows 4 for `gm_only` and 6 for `gm`. Should a GM who is not a club admin see these pages? | B-05 | GM Q5 |
| N-19 | **Agenda page width.** Should the agenda use the full width (as now) or the centred column of other GM pages? | B-13 | GM Q6 |
| N-20 | **Street settings position.** Should the street settings card stay above the shop list? It is also a second primary button on that page. | B-63, B-25 | GM Q7 |
| N-21 | **Handover with no owner.** The page shows no app message, only the browser tip. Does it need a server-side error? No problem row: the walk found no layout fault. | None | GM Q8 |
| N-22 | **Temporary password shown once.** The reset result page shows the temporary password once. After a reload it is lost. Is that intended? | B-108 | AD Q1 |
| N-23 | **Whitelist remove or status.** A wrong email stays on the list. Should the page offer a remove action or a status per row? | B-82 | AD Q2 |
| N-24 | **Street settings errors at the POST URL.** Errors render at `/shops/manage/street/`, and a reload re-submits. Redirect with the errors in the session, or keep the page? | B-99 | AD Q3 |
| N-25 | **Top bar name rule.** The doc says an initials chip below 1400 px. The code shows the name down to 400 px. Which one is the rule? | B-12 | AD Q4 |
| N-26 | **Site admin pages without club context.** Should the site admin see a site-level top bar (Clubs, Settings, Design) instead of the menu only? | B-65 | AD Q6 |
| N-27 | **Slips: select all.** The slips picker has no select-all and the tick boxes are small. A select-all is a new control. | B-30 | audit row |
| N-28 | **Quest forms: blank rows.** Four blank requirement forms and four blank reward forms show by default. Showing fewer changes the formset behaviour. | B-97 | audit row |
| N-29 | **Item detail: where-to-buy action.** The index has a where-to-buy button but the detail page has none. Adding it is a new action. | B-22 | audit row |

## Candidate rules

### Rules the audit used without a written rule

Each row cited "Best existing example". These are proposals for `DESIGN_SYSTEM.md`. The example page is the model.

| Proposed rule | Example page | Problems |
|---|---|---|
| A table keeps its key column and its row action visible without a sideways scroll at 390. | `shops-manage-list-club-admin`; row icon buttons with tooltips on `characters-detail-alice`; inventory table on `trades-propose` | B-36, B-28, B-79 |
| A flash message sits below the page title, and a validation alert appears only after a submit. A purchase or action stays on the page it started from. | reset password result; `whitelist`; the `shops-detail-caravan` success alert; `points-3-submitted`; `walk-buying-4-result` | B-21, B-51, B-113, B-54, B-26 |
| A form page has no nested card, stops at 40 rem, hides blank formset rows and keeps coin inputs readable at 390. | `shops-manage-edit`; `items-edit`; `downtime-request-new` | B-41, B-97, B-42, B-62, B-56 |
| The primary action sits in the page header, and an icon keeps a gap to its label. | `site-clubs` (header "New club" action, icon gap at 1280) | B-72, B-71 |
| Modals use one frame: title, short body, footer buttons in one order. | `shops-sell-junk-modal`; `shops-buy-modal` | B-48, B-47 |
| A filter form is compact: pills or one row of fields. | `accounts-message-inbox` (filter pills) | B-95 |
| A page uses the narrow main column and a subtitle in the page header. | `map-xp`; `downtime-play` | B-59, B-61 |
| One name for one area across top bar, home tile, breadcrumb, sheet and button. | `club-home-alice` labels and sections | B-109, B-110 |
| A print page prints only its content, and its screen view fits a phone. | `map-print`; `characters-print-items` | B-114, B-04 |

### Rules a test could check in code

This is a proposal only. No test is added here. File names are suggestions.

| Rule | Check | Test file |
|---|---|---|
| Every page extends `base.html` (B-02). | Render each GET page in the URL resolver. Assert the response has the app top bar and no Django admin header. | `scripts/test_screenshot_pages.py` (reuses the page list) |
| Every page has exactly one `h1`, from `components/page_header` (B-10, B-64). | Parse the HTML of each page. Count `h1`. Flag templates with an `h1` and no `page_header` include. | `accounts/tests/test_design_system.py` |
| Row actions in `td.actions` are icon buttons with a tooltip (B-79). | Template grep: a `td.actions` cell holds `components/icon` buttons with a `title`. | `accounts/tests/test_design_system.py` |
| No page has horizontal overflow at 390 (B-01, B-04). | Run `screenshots.py --audit` and fail on any OVERFLOW line. | `scripts/test_screenshot_pages.py` with the `browser` marker |
| No CLIPPED `input.form-control` at 390 (B-45, B-41). | Same run. Fail on a CLIPPED line that names `input.form-control`. | `scripts/test_screenshot_pages.py` with the `browser` marker |
| One date format filter across pages (B-52). | Template grep: no raw `|date:` formats outside one shared filter. | `accounts/tests/test_design_system.py` |
| Numeric table columns use `td.num` (B-87, B-85). | Template grep of `data_table` headers marked numeric. | `accounts/tests/test_design_system.py` |
| `code` text passes 4.5:1 contrast (B-08). | axe-core run on `/site/design/` in the browser test. | `scripts/test_console_sweep.py` with the `browser` marker |
| Scrollable `pre` blocks take focus (B-55). | Assert `tabindex="0"` on `.wm-code-wrap pre`. | `accounts/tests/test_design_system.py` |
| A primary button appears once per page (B-25, B-69). | Count `btn-primary` per rendered page. | `accounts/tests/test_design_system.py` |

## Proposed fix epics

The epics group problems by the files they touch, so fix stories run in parallel. **E1 goes first.** E2 to E10 depend only on E1. No two epics own the same file, except that E1 does the one cross-template row (B-10).

| Epic | Rows | High | Medium | Low | Blocked by owner questions |
|---|---|---|---|---|---|
| E1 Shared templates and CSS | 17 | 1 | 9 | 7 | N-15, N-25 |
| E2 Shops and stalls | 18 | 1 | 9 | 8 | N-01, N-07, N-08, N-20, N-24 |
| E3 Trades | 11 | 0 | 6 | 5 | N-02, N-03, N-04, N-05 |
| E4 Character sheet, slips (screen), junk, transfer | 16 | 0 | 7 | 9 | N-15, N-27 |
| E5 Print | 2 | 1 | 0 | 1 | N-17 |
| E6 Downtime and agenda | 12 | 1 | 5 | 6 | N-02, N-03, N-16, N-19 |
| E7 Inbox, accounts and auth | 16 | 3 | 2 | 11 | N-11, N-12, N-13, N-14, N-18, N-22, N-23, N-26 |
| E8 Quests | 6 | 0 | 3 | 3 | N-02, N-10, N-28 |
| E9 Map | 8 | 1 | 2 | 5 | N-02 |
| E10 Items and ledger | 11 | 0 | 4 | 7 | N-02, N-06, N-09, N-29 |

### E1: Shared templates and CSS

Owned files:

- `templates/base.html`
- `templates/components/**`
- `templates/forms/**`
- `templates/partials/**`
- `templates/home.html`
- `templates/club_home.html`
- `static/css/tokens.css`
- `static/css/components.css`
- `static/css/coins.css`
- `ledger/templates/ledger/widgets/**` (coin widget)
- `accounts/templates/accounts/design/**` (`/site/design/` page)

Problems (17: 1 High, 9 Medium, 7 Low): B-08, B-09, B-10, B-100, B-107, B-110, B-115, B-12, B-21, B-41, B-43, B-44, B-45, B-55, B-58, B-64, B-71.

Blocked by owner questions: N-15, N-25.

Goes first. Every other epic depends only on E1. B-10 (page header swap) is the one row that edits other epics' templates; E1 does it in one pass. A shared fix to `td.actions` and table scroll in `components.css` may also shrink the A-20 rows in E2, E3, E6, E7, E8, E9 and E10; do it here, then re-check those rows.

### E2: Shops and stalls

Owned files:

- `shops/templates/**`
- `static/css/areas/shops.css`

Problems (18: 1 High, 9 Medium, 8 Low): B-03, B-104, B-16, B-17, B-18, B-24, B-25, B-26, B-36, B-48, B-49, B-62, B-63, B-70, B-86, B-87, B-98, B-99.

Blocked by owner questions: N-01, N-07, N-08, N-20, N-24.

Shop street, shop detail, stalls, buy, sell, sell junk, shop and stock management.

### E3: Trades

Owned files:

- `player_characters/templates/player_characters/trades/**`

Problems (11: 0 High, 6 Medium, 5 Low): B-106, B-113, B-117, B-19, B-20, B-27, B-37, B-46, B-52, B-66, B-78.

Blocked by owner questions: N-02, N-03, N-04, N-05.

Trade index, propose, detail, edit side. No CSS file of its own: reuse E1 classes.

### E4: Character sheet, slips (screen), junk, transfer

Owned files:

- `player_characters/templates/player_characters/characters/**` except the E5 files
- `static/css/areas/characters.css`

Problems (16: 0 High, 7 Medium, 9 Low): B-109, B-11, B-114, B-23, B-29, B-30, B-38, B-39, B-51, B-68, B-74, B-83, B-89, B-90, B-91, B-92.

Blocked by owner questions: N-15, N-27.

Sheet, edit, create, transfer, consume, junk, directory, adjust and the slips picker (`slips.html`).

### E5: Print

Owned files:

- `static/css/print.css`
- `player_characters/templates/player_characters/characters/print.html`
- `.../print_item.html`
- `.../print_item_choose.html`
- `.../slips_print.html`
- `.../_item_card.html`
- `.../_slip.html`
- `map/templates/map/views/print.html`

Problems (2: 1 High, 0 Medium, 1 Low): B-04, B-75.

Blocked by owner questions: N-17.

`_item_card.html` and `_slip.html` are included only by print pages, so they belong here. `map/_hexmap.html` is shared by the screen map and the print page, so E9 owns it.

### E6: Downtime and agenda

Owned files:

- `downtime/templates/**`
- `static/css/areas/downtime.css`
- `static/css/agenda.css`

Problems (12: 1 High, 5 Medium, 6 Low): B-06, B-111, B-13, B-31, B-32, B-40, B-47, B-57, B-76, B-77, B-93, B-94.

Blocked by owner questions: N-02, N-03, N-16, N-19.

Downtime play and the wheel, requests, GM actions, agenda.

### E7: Inbox, accounts and auth

Owned files:

- `accounts/templates/accounts/**` except `design/`
- `templates/registration/**`
- `static/css/areas/accounts.css`

Problems (16: 3 High, 2 Medium, 11 Low): B-01, B-02, B-05, B-101, B-108, B-112, B-28, B-53, B-56, B-65, B-72, B-79, B-80, B-81, B-82, B-88.

Blocked by owner questions: N-11, N-12, N-13, N-14, N-18, N-22, N-23, N-26.

Inbox and gives, message forms, people, whitelist, site pages, login and password pages. B-02 needs new `registration/password_reset_*` templates.

### E8: Quests

Owned files:

- `quests/templates/**`
- `static/css/areas/quests.css`

Problems (6: 0 High, 3 Medium, 3 Low): B-15, B-35, B-54, B-61, B-85, B-97.

Blocked by owner questions: N-02, N-10, N-28.

Quest board, detail, turn-in and quest management.

### E9: Map

Owned files:

- `map/templates/**` except `map/views/print.html`
- `map/static/map/map.css`

Problems (8: 1 High, 2 Medium, 5 Low): B-07, B-103, B-116, B-14, B-42, B-59, B-60, B-96.

Blocked by owner questions: N-02.

Map pages, requests, tile modal, map edit, `_hexmap.html`.

### E10: Items and ledger

Owned files:

- `items/templates/**`
- `static/css/areas/catalogue.css`
- `ledger/templates/**` except `widgets/`

Problems (11: 0 High, 4 Medium, 7 Low): B-102, B-105, B-22, B-33, B-34, B-50, B-67, B-69, B-73, B-84, B-95.

Blocked by owner questions: N-02, N-06, N-09, N-29.

Item catalogue, detail, where-to-buy, ledger history and index.

### Agent access

The `agent-*` pages had no findings. They get no epic. The two `input.form-control` CLIPPED lines on the agent detail pages are open checks (see Tool findings).

### Check list

- Every B-id (B-01 to B-117) is in exactly one epic: 117 rows in 10 epics.
- Rows that wait on an owner answer are marked in the Blocked column. Rows with no epic: none.
- Print files: `_item_card.html` and `_slip.html` are included only by print pages. `map/_hexmap.html` is shared by the screen and print map, so only E9 owns it.
