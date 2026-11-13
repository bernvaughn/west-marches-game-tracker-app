# Audit 2: player play walk (PP)

Role `alice` (and `anon` for login). Tool: `scripts/screenshots.py --audit` on main at b0b2bb1, plus a throwaway Playwright walk. Widths 1920, 1280, 768 and 390 were captured for every owned page. Themed pages (quest board, chalkboard Downtime page) keep their theme.

Pages `characters-create`, `characters-slips-print*`, `characters-print-item*` and `map-print` run as `alice` and were checked on screen only. Print emulation belongs to the admin walk.

## Findings

| Tmp id | Page | Width | Role | Screenshot | Theme | Rule broken | Severity | Notes |
|---|---|---|---|---|---|---|---|---|
| PP-01 | password-reset, password-reset-done, password-reset-complete, password-reset-confirm-invalid | 1920, 1280, 768, 390 | anon | password-reset@1280.png, password-reset-confirm-invalid@1280.png | layout and widths | `DESIGN_SYSTEM.md` "Files and load order" (all pages extend `base.html`); AUDIT.md A-24 (two bars) | High | All four pages show the stock Django admin chrome (blue "Django administration" header, breadcrumb, unstyled form). No brand, no parchment, no app header. The login and password-change pages use the auth card. |
| PP-02 | quests-detail | 1280 | alice | quests-detail@1280.png | layout and widths | `back_link` pattern ("Back to <parent>", above the title); `page_header` has one `h1` | Medium | Back link reads "All quests" as a red underlined link, not "Back to quests" with an arrow. There is no page header; the quest title is inside the pinned note. The 40 rem note and turn-in card are centred while the back link sits at the left edge, so the page looks misaligned. Same at 1920 and 768. |
| PP-03 | quests-detail | 1280, 390 | alice | quests-detail@1280.png, quests-detail@390.png | tables | `data_table` ("Do: wrap in wm-table-scroll"); A-07 | Low | The turn-in table shrinks to its content (about 230 px) in a 320 px card. The status badge has no column header. The "Needed" and "Has" numbers are left-aligned, not `td.num`. The card title "Turn in" is a small `h4`, not the `card` header style. |
| PP-04 | walk-turnin-3-submitted | 1280, 390 | alice | walk-turnin-3-submitted@1280.png, walk-turnin-3-submitted@390.png | wording | `alert` pattern; "Best existing example: points-3-submitted (flash then list)" | Medium | After a successful turn-in the page stays on the quest. The success flash is at the top and pushes the content down. The turn-in card now shows "Missing 3 x Wolf pelt" and a faded button, as if it had failed. The flash text "Aria Windrunner completed Pelts for the Tanner." has no reward summary (coins and potion). |
| PP-05 | quests-index | 1280 | alice | quests-index@1280.png | layout and widths | `page_header` (one h1, subtitle); "Best existing example: downtime-play" | Low | Title has no subtitle, unlike Downtime, Items, Message and Slips. The board is one card in a full-width frame and leaves a large empty page below. |
| PP-06 | characters-detail-alice | 1280, 1920, 768, 390 | alice | characters-detail-alice@1280.png | layout and widths | `page_header` and `back_link`; AUDIT.md A-01, A-22 | Medium | The sheet has its own header. A breadcrumb "Characters / Aria Windrunner" replaces the back link. Six buttons sit above the title, not in the header actions. The header is a box with a heavy black border, unlike the `card` surface. At 390 the buttons wrap into three rows. |
| PP-07 | characters-detail-alice | 1280, 390 | alice | characters-detail-alice@1280.png | buttons and actions | `DESIGN_SYSTEM.md` "One primary action per page"; AUDIT.md A-21 | Medium | "Print sheet" is the red primary and the only primary. "Spend" and "Request points" next to Downtime points are bold red underlined text links, not buttons. Row actions in the inventory are three icon-only buttons with no visible label (tooltip only). |
| PP-08 | characters-detail-alice | 1280, 768 | alice | characters-detail-alice@1280.png | spacing | `DESIGN_SYSTEM.md` "Spacing" tokens | Low | The helper text "Earned downtime during a session? Ask your game master for the points." is bold, so it reads like a value. The label and the value in the Combat box sit on one baseline but "Spend Request points" wraps at 768 and 390. |
| PP-09 | characters-detail-alice | 390 | alice | characters-detail-alice@390.png | tables | A-20; `data_table` | Medium | The inventory table loses its "Available" column and the action column at 390. The scroll cue is a faint edge shadow only. Item names wrap in a 60 px column. The "Sell my junk in my shop" switch is off-centre. |
| PP-10 | characters-detail-alice | 1280 | alice | characters-detail-alice@1280.png | wording | "Best existing example: club-home-alice labels" | Low | Four names for one area: top bar "Character", home tile "My character", breadcrumb "Characters", page "Aria Windrunner". The sheet button says "Transfer"; the page it opens says "Move loot"; the home tile says "Move items". |
| PP-11 | characters-edit, characters-create | 1280, 768 | alice | characters-edit@1280.png, characters-create@1280.png | forms | `form_layout` ("forms stop at 40 rem"); `back_link` | Medium | The form is 72 rem wide with six fields in a row. A breadcrumb replaces the back link. The page title sits inside a black-bordered box together with the first fields. Help text "Optional. Whole number from 1 to 30." is repeated six times. |
| PP-12 | characters-transfer | 1280, 390 | alice | characters-transfer@1280.png | forms | A-09 (plain bullet lists); `form_layout` | Medium | The item list is a plain bullet list. The "pp" chip is a dark pill and the gp, sp and cp labels are plain text. The destination select shows Django's "---------". The four coin inputs and chips run into each other at 1280. Three empty item rows look the same as filled rows. "Change" is a second button next to a select. |
| PP-13 | characters-consume-player | 1280, 390 | alice | characters-consume-player@1280.png | forms | `form_layout`; A-09 | Low | The quantity input sits inside a sentence. "Recent changes (last 30 days)" is a bullet list that wraps in a 450 px column inside a 1090 px card. There is no Cancel button. The page title "Consume item" has no item name. |
| PP-14 | characters-junk | 1280 | alice | characters-junk@1280.png | buttons and actions | `form_layout` ("a primary Save and a secondary Cancel") | Low | The form has Save and no Cancel. Compare characters-edit. |
| PP-15 | characters-directory-alice | 1280 | alice | characters-directory-alice@1280.png | tables | `status_badge`; A-07 | Low | "Requested" and "Accepted" badges sit with no gap, and "Propose trade" is a plain link in the same cell. The header "Trades with Aria Windrunner" is long. The page has no subtitle. |
| PP-16 | characters-slips-alice | 390 | alice | characters-slips-alice@390.png | tables | A-20; touch targets (`DESIGN_SYSTEM.md` "Rules") | Medium | The tick boxes are 18 px, below the 44 px phone target. The Species column is cut off and needs a sideways scroll. There is no select-all. |
| PP-17 | walk-slips-3-print-screen | 390 | alice | walk-slips-3-print-screen@390.png, characters-print-items@390.png | layout and widths | OVERFLOW tool line; "Best existing example: characters-print-items" | High | On a phone the screen view of the print page scrolls sideways (page 765 px wide at 390). The slip card is wider than the screen. The same overflow is on `characters-print-items`, `characters-print-item-full`, `characters-print-item-grid` and `characters-slips-print-aria`. |
| PP-18 | characters-print-items, characters-slips-print | 390 | alice | characters-print-items@390.png | buttons and actions | AUDIT.md A-19; icon spacing | Low | The "Print" button icon touches its label. The back link and the Print button share one row, and the instruction text below is in muted grey at body size. The app top bar stays on a page made for print. |
| PP-19 | downtime-requests-alice | 390 | alice | downtime-requests-alice@390.png | tables | A-20; `data_table` | Medium | Status is the last visible meaning of the page and sits off screen at 390. The first row is cut at "Requested". The Note column wraps one word per line. |
| PP-20 | downtime-requests-alice | 1280 | alice | downtime-requests-alice@1280.png | wording | `page_header` | Low | Page title "Downtime point requests"; button "Request points"; the form page title "Request downtime points" and its cancel button "Point requests". The "Decided" column is empty for pending rows. Primary action sits under the title, not in the header actions. |
| PP-21 | downtime-request-new | 1280 | alice | downtime-request-new@1280.png | forms | `form_layout` ("secondary Cancel"); `back_link` | Medium | The secondary button is labelled "Point requests" and not "Cancel". There is no back link. The card has no title. Compare accounts-message-new, which has a card title. |
| PP-22 | downtime-play, walk-downtime-2-spend-modal | 390 | alice | downtime-play@390.png, walk-downtime-2-spend-modal@390.png | modals | `modal_frame`; "Best existing example: shops-buy-modal" | Medium | The spend result opens a white modal on the chalkboard page, so the theme breaks. Wheel slice labels are cut ("A loaf of b…", "The golden…"). The footer has two buttons, "Back to Downtime" and "Close", that do the same thing. The previous page shows through below the footer. |
| PP-23 | downtime-play | 1280, 768 | alice | downtime-play@1280.png | layout and widths | `section`; chalkboard theme | Low | The reward list of one job runs 10 lines, so "Take the job" sits far from the heading. With one job the board is half empty. The "has 2 downtime points" line is small and right-aligned. |
| PP-24 | accounts-message-new, accounts-stock-request-new | 1280, 1920 | alice | accounts-message-new@1280.png | layout and widths | `main_class` `wm-main--narrow`; "Best existing example: downtime-request-new" | Low | The form card is a half-width block (`wm-narrow-block`) while the table below is full width. Other forms are a full card in the narrow column. |
| PP-25 | accounts-message-new, accounts-stock-request-new | 390 | alice | accounts-message-new@390.png | tables | A-20 | Low | The message table scrolls sideways at 390 (CLIPPED line). Date and Character come before the message and status, so the status is the column that moves out of view. |
| PP-26 | walk-inbox-9-alice-status-after-give | 1280 | alice | walk-inbox-9-alice-status-after-give@1280.png | wording | `status_badge` | Medium | After a give the message changes to "Handled" and nothing says what was given. There is no link to the ledger or sheet, and the player gets no notice. Two messages with the same text look the same. |
| PP-27 | walk-inbox-2-sent, walk-inbox-4-stock-sent | 1280, 390 | alice | walk-inbox-2-sent@1280.png | forms | `alert` | Low | After a send the page reloads on the same form with a flash at the top and the new row far below. Focus is not moved to the flash. The button says "Send as Aria Windrunner", the page title says "Message the club admins". |
| PP-28 | items-index | 1280, 1920 | alice | items-index@1280.png | tables | `data_table`, `empty_state`; AUDIT.md A-08 | Medium | The "Traits" column is empty on every row. Value is right-aligned and Rarity is left-aligned with no gap. The where-to-buy column is an icon button with no header. There is no subtitle. |
| PP-29 | items-index | 390 | alice | items-index@390.png | tables | A-20 | Low | Names wrap to two lines and the where-to-buy buttons make each row 46 px high while the others are 30 px. |
| PP-30 | walk-catalogue-3-search-none | 1280, 390 | alice | walk-catalogue-3-search-none@1280.png | empty states | `empty_state` | Medium | The page has no search box and no filter, so the "no hit" empty state cannot be shown (`?q=zzz` returns the full list). See "Needs the owner". |
| PP-31 | items-detail | 1280, 390 | alice | items-detail@1280.png | spacing | `definition_list`; `section` | Medium | The "Description" heading touches the Value row with no gap above it. Rarity and Value labels are muted small caps while the heading is a serif h2. The page has no where-to-buy action although the index has one. |
| PP-32 | ledger-character-history | 390 | alice | ledger-character-history@390.png | tables | A-20 | Medium | Dates break across two lines ("2026-" "11-13"). All five columns squeeze, so lines wrap to 3 lines. |
| PP-33 | ledger-character-history | 1280 | alice | ledger-character-history@1280.png | spacing | `section`; `form_layout` | Low | "Page 1 of 1" is plain text with no pager style. The "Downtime points" heading is a small serif h3, not the `section` bar used on message-new. The filter has a red primary "Filter" button, which is a second primary action. |
| PP-34 | map-index-alice | 1280 | alice | map-index-alice@1280.png | layout and widths | `page_header` actions; `card` | Low | "XP table" and "Map requests" are outline buttons below the title, not header actions. The map list is one link in a 260 px card. |
| PP-35 | map-tile | 1280, 390 | alice | map-tile@1280.png | layout and widths | `back_link` ("above the title"); AUDIT.md A-22 | Medium | The back link "Back to the map" sits on the same row as the "Request a visit" button, below the title, and not above it. The "Show the map for" block repeats the whole selector for one tile. |
| PP-36 | map-detail-alice | 1280, 390 | alice | map-detail-alice@1280.png, map-detail-alice@390.png | layout and widths | `wm-main--narrow` rule; "Best existing example: map-xp" | Low | The map page is full width (U80), so its left edge (32 px) differs from the other pages (96 px at 1280). At 390 the map shrinks to about 330 px wide and the NW to SE buttons take more room than the map controls need. |
| PP-37 | map-request-visit, map-request-credit | 1280 | alice | map-request-visit@1280.png | forms | `back_link`; `form_layout` | Low | No back link. Fields "Column (q)" and "Row (r)" show internal names. The cancel button is "Map requests". |
| PP-38 | map-tile-modal | 390 | alice | map-tile-modal@390.png | modals | `modal_frame` ("below sm the modal is full screen") | Low | The modal is full screen but the body is a big empty block, and the page below shows through at the bottom. |
| PP-39 | home-alice | 1280, 1920 | alice | home-alice@1280.png | layout and widths | `page_header`; A-24 | Low | The top bar shows only a menu toggler and the user name, with no club link or area links, so the page is a dead end if the card is missed. The hamburger is also shown at 1280 on every page (admin walk owns the bar). |
| PP-40 | club-home-alice | 1280 | alice | club-home-alice@1280.png | wording | "Best existing example: club-home-alice sections" | Low | The "Trades" area has two tiles named "Trades" and "Propose trade". "Map" holds "Map", "Map requests", "XP table". Section names repeat tile names. |
| PP-41 | login, password-change | 1280 | anon, alice | login@1280.png, password-change@1280.png | wording | `form_layout` | Low | The login page has no "Forgot your password?" link. The password-change page has no Cancel or back link, and its help list is a plain bullet list. |

## Needs the owner

1. **Item search.** The user story names "browse, search, detail" for the catalogue. `items-index` has no search box and no filter. Is search wanted, or is the full list enough?
2. **Turn-in feedback.** After a turn-in the player stays on the quest. Should the page show the rewards, and should a completed quest leave the board?
3. **Give notice.** When a game master gives coins or items from a message, the player only sees "Handled". Should the player see what arrived and get a notice?
4. **Password reset.** The reset pages use Django admin templates. Is there a login link to start a reset? The login page has none.
5. **Sheet header.** The sheet, edit and create pages use a boxed header and breadcrumbs. Do these keep their own look, or follow `page_header`?
6. **Wheel modal.** Should the spend result stay a white modal, or take the chalkboard theme?
7. **Print pages on a phone.** Should the screen view of print pages fit a phone, or is it desktop only?

## Tool output

Capture: `uv run python scripts/screenshots.py --audit --keep-db --out <scratch>` (673 shots, 0 failed). OVERFLOW lines for owned pages:

```
OVERFLOW characters-slips-print-aria@768
OVERFLOW characters-print-items            (390)
OVERFLOW characters-slips-print-aria       (390)
OVERFLOW characters-print-item-full        (390)
OVERFLOW characters-print-item-grid        (390)
```

CLIPPED lines for owned pages. Every `span.visually-hidden` and `label.visually-hidden` entry is expected (screen-reader text). The `div.wm-table-scroll` entries are tables that scroll by design, but the scroll hides columns:

```
CLIPPED accounts-message-new (div.wm-table-scroll)            (390)
CLIPPED accounts-stock-request-new (div.wm-table-scroll)      (390)
CLIPPED characters-directory-alice (div.wm-table-scroll)      (390)
CLIPPED characters-slips-alice (div.wm-table-scroll)          (390)
CLIPPED characters-detail-alice (div.wm-table-scroll)         (390)
CLIPPED characters-slips-print (div.wm-table-scroll)          (390)
CLIPPED characters-junk-modal (div.wm-table-scroll)           (390)
CLIPPED characters-consume-modal (div.wm-table-scroll)        (390)
CLIPPED downtime-requests-alice (div.wm-table-scroll)         (390)
```

Walk-only check: `walk-slips-3-print-screen@390` also overflows (page 765 px wide).

Console sweep (`scripts/console_sweep.py --widths 1920,1280,768,390`):

```
Done: 0 problem(s).
```

The sweep covered every demo page and modal trigger at the four audit widths. It found no console error for the owned pages.
