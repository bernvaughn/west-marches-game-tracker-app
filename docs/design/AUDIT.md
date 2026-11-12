# Design audit (U35, story 1)

This audit lists the design problems of every page that a demo role can reach.
The "before" screenshots come from `uv run python scripts/screenshots.py --out <dir>`.
Each screenshot name is `<page>@1280.png` or `<page>@390.png`. The set is attached to the task.
Each problem has an id (`A-01`, ...). The sweeps cite the ids.

Categories: Hierarchy, Spacing, Typography, Tables and lists, Forms, Colour and contrast,
Mobile, Consistency.

## Tool findings

- No page scrolls sideways at 390 px (`OVERFLOW` count: 0).
- The tool also prints `CLIPPED` where a container hides content. At 390 px these pages clip:
  `accounts-index`, `accounts-message-inbox`, `inbox-grant-modal`, `shops-detail-lantern`,
  `shops-detail-caravan`, `shops-buy-modal`, `shops-manage-edit`, `shops-rotation-list`,
  `map-requests`, `quests-manage`, `agent-connections`, `agent-batches`,
  `agent-batch-detail` (the source notes box), `agent-proposed-items`.
  Each is a `.table-responsive` that cuts the last columns (A-20).
- The sandbox has no emoji font. Shop symbols show as empty boxes in the screenshots (A-37).
  Check this on a real device before you act on it.

## Cross-cutting problems

### Hierarchy
- **A-01** No shared page header. Each page starts with a very large title. Actions follow as
  bare links in a row ("New item | Show retired", "Edit Transfer Print History").
  The main action is not clear on any page.
- **A-02** `h1` and `h2` look alike. Both are heavy and large. Sections such as "Notes",
  "Stats" and "Details" on the character sheet are empty headings with no card or divider.

### Spacing
- **A-03** No page container. Content sits 12 px from the screen edge. At 1280 px forms and
  tables use the full width, so lines run 1250 px long.
- **A-04** Vertical rhythm is uneven. A heading, a link row and a table are separated by
  different gaps on each page. The "Save" button touches the heading below it (`shops-manage-edit`).

### Typography
- **A-05** Headings fall back to Arial Narrow or the system bold sans. The Journal CSS has no
  font import. The app has no type scale.
- **A-06** Body text is plain 16 px with no secondary text style. Help and meta text look like body text.

### Tables and lists
- **A-07** Tables are striped grey with bold headers. Numbers are left-aligned. Action
  columns differ per page ("Edit" link plus "Remove" button).
- **A-08** Empty states are one bare line in a table row ("Nothing confirmed yet.") or plain text.
- **A-09** Lists are plain bullets (`characters-index-*`, `trades-detail-*`). They carry no
  secondary data, avatar or status.
- **A-10** The coin list on the character sheet is a bullet list, one line per denomination.

### Forms
- **A-11** Every field is full width and stacked. There is no grouping and little help text.
  Short fields such as quantity and percent are as wide as the name field.
- **A-12** Errors and required marks are not visible in the demo shots. The form templates
  render labels with a bare colon in some forms ("Character:") and without it in others.

### Colour and contrast
- **A-13** Journal primary `#eb6864` is about 3.2:1 on white. It fails AA for links and button
  labels. Links, "Save" and "Switch" use it.
- **A-14** Secondary buttons use Journal warning orange (`Remove`, `Discard`, `Cancel trade`).
  Orange on white is low contrast and looks like a warning even for neutral actions.
- **A-15** Coin colours: gold and copper look olive and brown. The platinum label is a dark pill,
  and the others are coloured text. The set looks uneven (see `characters-detail-alice`).
- **A-16** Greyed top-bar controls ("Demo Marc…", "Log out") have low contrast.

### Mobile
- **A-17** The top bar wraps to three rows at 390 px. The menu toggler sits alone on its own
  row, and the open menu pushes the page down (`topbar-menu-open@390`).
- **A-18** The character selector and the club name truncate in the top bar at both widths
  ("Demo Marc…", "Aria Windrun", "No charact…").
- **A-19** Touch targets are small. Inline links, `btn-sm` buttons and radio buttons are well
  below 44 px.
- **A-20** `.table-responsive` clips columns instead of showing a clear scroll cue (list in "Tool findings").

### Consistency
- **A-21** Buttons: solid primary, outline orange and plain red links all appear for similar
  actions. "Cancel" is a grey button in the buy modal and a link in the adjust form.
- **A-22** Navigation links back ("All quests", "Back to shops", "All maps") are in a different
  place on each page. Some pages have none.
- **A-23** Modals have no common look. The buy modal, tile modal and grant modal differ in
  header, body spacing and footer. The grant modal is a very long form that scrolls inside the
  dialog (`inbox-grant-modal`).
- **A-24** Two top bars exist. Site admin pages show a small bar with the name and "Log out".
  Club pages show a two-row bar.

## Pages

Screenshot names are the page name plus `@1280.png` and `@390.png`.

### Sign-in and home
- **login**: Hierarchy: the card is small, and the page has no wordmark or text. Colour: A-13.
  Mobile: the card fills the width at 390 px (acceptable).
- **home-alice, home-site-admin, club-home-alice, club-home-gm**:
  **A-25** The home pages are nearly empty ("Pick an area from the menu."). There are no cards
  for the main areas. Hierarchy: A-01. The site admin home has no link to the site pages.
- **topbar-menu-open** (390 only): A-17. The toggler sits below the user controls. The open
  menu is a plain list with no dividers.
- **password-change**: Forms: A-11. No password rules shown as help text.

### Accounts
- **accounts-index**: Tables: A-07, A-20 (email clipped). **A-26** Roles and characters wrap
  into tall cells at 390 px.
- **accounts-whitelist**: Forms: A-11. Tables: A-08.
- **accounts-reset-password**: Hierarchy: the warning about the action is plain text. A-21.
- **accounts-message-new**: Forms: A-11, no help for the message box.
- **accounts-message-inbox, inbox-grant-modal, accounts-message-grant**: **A-27** The inbox
  row packs status, a select and two buttons in one cell. The message text is clipped at 1280.
  A-23 for the modal. The grant form has bare `q` and `r` labels and no grouping of coins, items
  and map fields. The item rows have no labels.

### Site admin
- **site-clubs, site-club-new, site-settings**: A-24, A-11. The settings page shows help below
  the field in body text (A-06).

### Characters
- **characters-index-alice, characters-index-gm**: Tables and lists: A-09. No coins or
  owner column. Hierarchy: A-01 ("New character" is a bare link).
- **characters-detail-alice, characters-detail-gm**: A-10, A-15. **A-28** The sheet is a
  long single column. Empty sections "Notes", "Stats" and "Details" show only headings (A-02).
  Held and available coins are one sentence.
- **characters-create, characters-edit, characters-handover**: Forms: A-11.
- **characters-adjust, characters-consume**: Forms: A-11. **A-29** The item rows are an
  unlabelled select over an unlabelled quantity. "Cancel" is a link next to "Save" (A-21).
- **characters-transfer, characters-print-items**: Forms: A-11. The print page uses the full
  app top bar (A-24 inverse: no print-only layout).

### Trades
- **trades-index**: Tables and lists: A-09, A-08.
- **trades-propose**: Forms: A-11, A-29.
- **trades-detail-alice, trades-detail-bob**: **A-30** Status and approvals are plain text lines.
  The two sides are stacked sections with bullet lists, not two columns. The status has no
  badge (A-13 for contrast of the cancel button, A-14).

### Items
- **items-index, items-index-gm**: A-07 (the Value column is left-aligned; the Traits column is
  empty and wide). Hierarchy: A-01.
- **items-detail**: Hierarchy: A-02. **items-create, items-edit**: Forms: A-11.

### Shops
- **shops-index**: **A-31** The tinted cards use each shop's colour. Text on them has uneven
  contrast (the link colour on violet and orange). **A-37** The symbol shows as an empty box in the sandbox (no emoji font). Check on a real device.
- **shops-detail-lantern, shops-detail-caravan**: A-37. A-20 (the Quantity column is cut at
  390 px). The "Buy" link is a plain link in a table (A-21). The empty Description column is wide.
- **shops-buy, shops-buy-modal**: A-23. The summary rows are separate paragraphs with equal
  weight. **A-32** "Not enough coins" shows in orange next to the number. The buy button stays
  active. "Cancel" is grey (A-21).
- **shops-sell**: Forms: A-11, A-29.
- **shops-manage-list, shops-manage-create, shops-manage-edit**: A-04 (Save touches "Stock").
  Forms: A-11 for "Sell percent" and "Buy percent" (no help on what blank means; the table
  shows "default").
- **shops-stock-add, shops-stock-edit, shops-rotation-list, shops-rotation-create,
  shops-rotation-edit**: A-07, A-11, A-20.

### Ledger
- **ledger-index, ledger-character-history**: Tables: A-07 (the amount columns are
  left-aligned, with no sign or colour for debit and credit), A-08.

### Map
- **map-index-alice, map-index-gm**: A-09, A-01.
- **map-detail-alice, map-detail-gm**: **A-33** Controls are a stack of bare links ("Rename or
  archive map", "Request a visit", "Full map | Players' view", "Print", "E W NE NW SE SW").
  There is no legend and no frame around the map. Forms: the "Show" button and the character
  checkboxes are small (A-19).
- **map-tile, map-tile-modal**: A-23. The modal body is a link and one line of text. The footer
  has only "Open full page".
- **map-create, map-edit, map-location-create, map-location-edit, map-encounter-create,
  map-encounter-edit**: Forms: A-11.
- **map-location-delete, map-encounter-delete**: Hierarchy: a destructive confirm with the
  same weight as a normal page (A-21).
- **map-requests, map-request-visit, map-request-credit**: A-07, A-20, A-11.
- **map-xp**: A-07 (the numbers are left-aligned and have no thousands separator).
- **map-print**: not reviewed for print layout. The screenshot uses the screen layout.

### Quests
- **quests-index**: A-09. **quests-detail**: **A-34** "Needs", "Reward" and "Turn in" use
  mixed bold inline labels and a heading. There is no card or progress cue.
- **quests-manage, quests-create, quests-edit**: A-07, A-11, A-20.

### Agent access
- **agent-index**: A-01, A-09.
- **agent-connections, agent-proposed-items**: A-07, A-20, A-08.
- **agent-proposed-item-detail**: Hierarchy: A-02. Actions: A-21.
- **agent-batches**: **A-35** The "Pending" and "Recent" tables use different column sets and
  different column widths. "Nothing confirmed yet." sits inside a table row.
- **agent-batch-detail**: **A-36** The worst page. Each line is a full edit form of seven stacked
  fields, so two lines fill two screens. The reader cannot see what the batch does at a glance.
  There is no summary table of characters, items and coins. "Save line", "Remove line",
  "Confirm batch" and "Discard batch" stack in one column with the same weight, so the main
  action, "Confirm batch", is easy to confuse with a line action. The status, date and source are
  one run-on sentence with a double full stop. The source notes use a clipped monospace box at 390 px.
  Also A-02 ("Lines" over "Line 1").
- **agent-batch-line-edit**, confirm, discard and reverse are POST-only and not in the page list.

## Top ten by impact

1. **A-36** The batch review page is the hardest page to use, and it controls real coins and items.
2. **A-01** No shared page header. Every page loses its main action. One component fixes all pages.
3. **A-13** Primary colour fails AA on links and buttons. This affects every page.
4. **A-17** The top bar wraps to three rows on a phone and pushes content down.
5. **A-11** Forms are unstructured, full-width stacks. Most pages in the app are forms.
6. **A-07** Tables have no alignment, actions or empty-state pattern. Tables hold most of the data.
7. **A-03** No page container. Lines run too long at 1280 px and touch the edge at 390 px.
8. **A-05** Headings use a fallback font and there is no type scale. The app has no voice.
9. **A-23** Modals differ. Buy, tile and grant are the daily actions on a phone.
10. **A-20** Tables clip columns at 390 px with no scroll cue. Players lose price and quantity.

## Story 8: consistency pass

The last story compared every area side by side and promoted what two or more areas had built alike.

### Fixed

| Item | What changed |
| --- | --- |
| A-01 residual | `page_header` takes `back_url` and `back_label`; `page_header_open` and `page_header_close` hold template-built actions. Ledger history and trade detail use them. |
| Back links | One `back_link` component replaces four patterns: the agent link, the map `btn-link`, the plain `<p><a>` and the outline button. It has a gap after the arrow and a 44 px tap target on phones. |
| Status badges | One `status_badge` component holds the status-to-tone map. Trades, batches, inbox, proposed items and map requests use it. A declined trade is now red. |
| Shared layout classes | `.wm-toolbar`, `.wm-inline-form`, `.wm-card-grid`, `.wm-fieldset`, `.wm-form-row`, `.wm-check-list`, `.wm-filter-pills`, `.wm-section-bar`, `.wm-code-wrap` and `.wm-dl--grid` live in `components.css`. The area copies are gone. |
| A-20 residual | `.wm-table-scroll` carries `position: relative` once, in `components.css`. |
| Mobile targets | `.btn-close` and `.form-check` are 44 px high below sm. The map-local `.form-check` rule is gone. |
| Sizes | New tokens `--wm-size-touch`, `--wm-size-form` and `--wm-size-narrow` replace every raw `44px`, `2.75rem`, `40rem` and `28rem`. |
| Retired items | One badge text, "Retired", on the item pages, the shop manager and the sheet. |
| Dead CSS | `static/css/app.css` is deleted. The live top-bar rules and `.donate` moved to `components.css`. `.notice`, `.temp-password`, the old map SVG block, `.area-nav`, `.map-toolbar` and the agent-local `:root` variables are gone. |
| Dead templates | `accounts/index.html` and `accounts/stub.html` are deleted. |
| Map | The "!" in an unexplored hex no longer has an underline. |

### Left or explained

- **A-32**: Buy stays active with too few coins. Fixing it changes behaviour; the view still rejects the purchase.
- **A-11 residual**: The percent help text needs form `help_text`, which is Python.
- **A-37**: The sandbox has no emoji font. Check shop symbols on a real device.
- **Kept area-local** (one area uses each, so no promotion): the auth card, the temp-secret block, the soft shop banner with its figure slot, the silhouette radio grid, the decision bar, the line-edit disclosure, the map legend, the sheet box and grid, the trade sides, signed amounts, the agent line grid and the agent batch grid.
- `main table { margin-bottom }` from `app.css` was dropped; tables sit in `.wm-table-scroll` or a card.

### Top ten

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 1 | A-36 | Fixed | `agent-batch-detail` screenshots (story 7); line editor and decision bar. |
| 2 | A-01 | Fixed | `page_header`, `page_header_open` and `back_link` on every page. |
| 3 | A-13 | Fixed | Darkened accent token; a test enforces 4.5:1. |
| 4 | A-17 | Fixed | Top bar: `narrow-menu` screenshots. |
| 5 | A-11 | Fixed, one residual | `form_layout`, `.wm-fieldset` and `.wm-form-row`. Percent help text stays (see above). |
| 6 | A-07 | Fixed | `data_table` classes and `data_table_empty` on every list. |
| 7 | A-03 | Fixed | `.wm-main` and `.wm-main--narrow` containers. |
| 8 | A-05 | Fixed | Vendored serif headings and the type scale in `tokens.css`. |
| 9 | A-23 | Fixed | `modal_frame` for buy, tile and grant; `.btn-close` is 44 px on phones. |
| 10 | A-20 | Fixed | `.wm-table-scroll` on every table; see the CLIPPED note below. |
