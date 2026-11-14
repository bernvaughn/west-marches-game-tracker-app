# Design system (U35)

Parchment and ink. Warm off-white surfaces, dark ink text, one accent colour, serif headings, a plain sans-serif for data. Light only. One primary action per page.

## Files and load order

`base.html` loads, in this order: Journal, `tokens.css`, `components.css`, `app.css`, `coins.css`, `areas/accounts.css`, `areas/characters.css`, `areas/catalogue.css`, `areas/agent.css`, then `print.css`.

- `tokens.css`: every `--wm-*` token, the `@font-face` rules and the `--bs-*` bridge.
- `components.css`: Bootstrap overrides and one class block per component. Tokens only, no raw hex.
- `areas/*.css`: one file per sweep story. Put area-only rules here, with tokens. Do not edit `components.css` in a sweep.
- Vendored: Bootstrap Icons 1.11.3 sprite and Source Serif 4 (600, 700). Nothing loads from a CDN.

Journal compiles hex values into `.btn-*` and the headings. The `--bs-*` root variables do not reach them, so `components.css` overrides them. Use the `wm-*` classes and tokens; do not fight Journal in a page.

The live reference is `/site/design/` (site admin only).

## Tokens

### Spacing
`--wm-space-1..7` = 4, 8, 12, 16, 24, 32, 48 px. **Do** use these for every gap and padding. **Don't** write raw px values.

### Type
`--wm-font-heading` (Source Serif 4) for headings and the brand. `--wm-font-body` (system sans) for everything else. `--wm-text-xs..3xl` and `--wm-leading-tight/normal`. h1 is clearly larger than h2. **Don't** pick sizes by hand.

### Colour
Roles: `surface`, `surface-raised`, `surface-sunken`, `border`, `text`, `text-muted`, `accent`, `accent-hover`, `on-accent`, `success`, `warning`, `danger`, `info` (each with a `-bg` pale variant) and `neutral-bg`. Every text pair is 4.5:1 or better, and a test enforces it. The accent is Journal's red hue, darkened. **Do** pair danger with an icon or text: it looks close to the accent. **Don't** convey meaning by colour alone.

### Coins
`--wm-coin-cp/sp/gp/pp` (and `pp-bg`) are the text colours, unchanged from U31. `--wm-coin-dot-*` colour a small metal dot before each amount (copper, silver, gold, platinum), so gold reads as gold. Platinum is light text on a dark chip (8:1, and the chip is 8:1 against the page). Print stays black with no dots.

### Shop presets
`--wm-shop-<preset>-deep` and `--wm-shop-<preset>-soft` for parchment, forest, ember, ocean, violet and slate. Deep reads with light text (`--wm-on-accent`), soft reads with dark text (`--wm-text`); a test enforces AA for both. Use them with `banner`.

### Radii
`--wm-radius-sm/md/lg` = 4, 8, 12 px.

### Shadows
`--wm-shadow-1` (cards) and `--wm-shadow-2` (menus, modals). Two levels only.

### Focus ring
`--wm-focus-ring` (a 3 px accent halo) plus `--wm-focus-outline` (a solid 2 px outline, kept for forced-colours mode). Never remove the focus indicator.

### Sizes
`--wm-size-touch` (2.75rem, the phone tap target), `--wm-size-form` (40rem, a form column) and `--wm-size-narrow` (28rem, a narrow card). Use them instead of raw `44px`, `40rem` or `28rem`.

## Components

All live in `templates/components/`. Each file starts with a `{% comment %}` block that lists its context and an example.

**Wrapper pattern.** A part that repeats in a page and wraps content uses an include pair: `card_open.html` and `card_close.html`, `section_open.html` and `section_close.html` (a card footer uses `card_footer.html` and `card_footer_close.html`). A part that wraps a whole HTMX response is a template that the partial extends: `modal_frame.html` has blocks `title`, `subtitle`, `body`, `footer` and an outer `content` block. A form partial wraps `{{ block.super }}` in a `<form>`.

- **page_header**: the one `h1`, subtitle, one primary action, secondary actions, breadcrumbs. Do: one primary action. Don't: add a second `h1`.
- **card**: raised surface with header, body, optional footer. Don't nest cards.
- **section**: titled `h2` block with a rule. Use to group a page; don't use for one-off spacing.
- **data_table**: CSS classes, not an include. Markup: `<div class="wm-table-scroll"><table class="table table-sm table-striped wm-data-table">`, numbers in `td.num`, buttons in `td.actions`, and `data_table_empty.html` in `{% empty %}`. Do: wrap in `wm-table-scroll`. Don't: clip columns. Row actions (U84): an actions cell that holds icon buttons in `<div class="wm-row-actions btn-group btn-group-sm">` (or has class `wm-row-actions-cell`) sticks to the right edge of `.wm-table-scroll`, so the row's buttons stay visible at 390 px with no sideways scroll. Give each button `aria-label`, `title` and `data-wm-tooltip` (model: `characters/detail.html`). Sticky is opt-in: a `td.actions` of text buttons scrolls as before, because a wide sticky cell would cover the row. Swap text buttons to icons to get the sticky column. `.wm-date` keeps a date cell on one line. `.wm-col-optional` (on th and td) hides a low-value column below 576 px. A themed table sets `--wm-table-sticky-bg` so the sticky cell matches its background.
- **banner**: `banner_open.html` and `banner_close.html`. A full-width coloured band outside the card, tinted by a shop preset. Do: put it first in the page. Don't: fill a whole card with the preset colour.
- **stat**: label and value. **definition_list**: `(term, value)` pairs.
- **back_link**: the one "back to the parent" link: muted, arrow icon, a gap, a phone touch target. Pass `back_url` and `back_label` to `page_header` to render it above the title. Do: use it for every back link, above the title, with the label "Back to <parent>". Don't: use an outline button or a plain `<a>`.
- **page_header_open / page_header_close**: a page header whose actions are template markup (POST forms, partials, several buttons). Put the markup between the two includes. They sit in `.wm-page-actions`, which hides itself when empty.
- **status_badge**: a badge with the tone chosen from one status vocabulary. warning: pending, open, requested, accepted. success: approved, confirmed, completed, handled. danger: declined. info: reversed. Anything else is neutral. Do: use it for every status. Don't: write an if/elif chain.
- **Shared layout classes** (in `components.css`; see the "Shared layout classes" section of `/site/design/`): `.wm-toolbar`, `.wm-inline-form`, `.wm-card-grid`, `.wm-fieldset` with `.wm-form-row`, `.wm-check-list` (`--inline`), `.wm-filter-pills`, `.wm-section-bar`, `.wm-code-wrap` and `.wm-dl--grid`. An area stylesheet must not repeat them.
- **badge**: status pill; `text` is required. Don't: a coloured dot without a word.
- **coins**: wraps the `coins` filter in `.wm-coins`. Don't recolour it. The coin *input* widget (`CoinsField`, `.wm-coin-input`) shows four cells in a row, a 2 x 2 grid below 576 px, and four plain labels with a dot. Platinum has no dark pill on input labels (`--wm-coin-pp-text`); the display pill is unchanged.
- **character_chip**: name with an initial avatar; optional link.
- **empty_state**: icon, one line, one action. Use instead of a blank list.
- **alert**: level (success, info, warning, danger), icon per level. Flash messages (`components/messages.html`) render once, below the page header (`flash_slot` and `flash_messages` tags in `accounts_tags`), or at the top of `main` when the page has no header. They never show in a modal or htmx partial.
- **Dates**: one format, `13 Nov 2026` (`j M Y`), set in `config/formats/en/formats.py` (`FORMAT_MODULE_PATH`). Write `{{ d|date }}`, or `{{ dt|date:"DATETIME_FORMAT" }}` (`13 Nov 2026, 09:05`). Never write an inline format string. HTML date inputs keep ISO.
- **icon**: `{% include "components/icon.html" with name="plus-lg" label="Add" %}`. Icons support labels, never replace them (use a label only for icon-only buttons, via visually-hidden text).
- **form_layout**: the whole form with a primary Save and a secondary Cancel. Fields render through `templates/forms/` (required mark, help, errors with an icon, no stray colon in labels). Short inputs (number, date) stop at 12 rem; forms stop at 40 rem.
- **modal_frame**: header, body, footer for `#app-modal`. Below `sm` the modal is full screen.

### Rules
- Top bar: one row on desktop for every role, the full user name at 1400 px and wider, an initials chip below that (tooltip and screen-reader name carry the full name). The character dropdown submits on change (a `<noscript>` Switch button is the fallback). On a phone the club name hides and the menu has a link to Your clubs.
- Touch targets: below 576 px every `.btn`, input, select, `.nav-link` and `.dropdown-item` is at least 44 px high. Desktop stays compact.
- Page width: `{% block main_class %}wm-main--narrow{% endblock %}` caps a page at 72 rem. The default is full width with token gutters.
- The top bar must fit at 390 px with no horizontal overflow. Check it with `scripts/screenshots.py`.

## Audit top ten and the answer to each

| Audit id | Problem | Answer |
|---|---|---|
| A-36 | Batch review page is hard to use | Built from `page_header`, `card`, `data_table`, `badge`, `character_chip` and grouped buttons. Story 7 migrates it; the owner-approved sample is in the task. |
| A-01 | No shared page header | `page_header` |
| A-13 | Primary colour fails AA | `--wm-accent`, darkened (5.6:1), with `.btn-primary` overrides |
| A-17 | Top bar wraps to three rows at 390 px | Top bar: brand and toggler on row 1, controls on row 2 |
| A-11 | Forms are unstructured full-width stacks | `templates/forms/`, `form_layout`, `.wm-form`, `.wm-field` |
| A-07 | Tables have no alignment or empty state | `data_table` classes, `.num`, `.actions`, `data_table_empty` |
| A-03 | No page container | `wm-main` gutters and `wm-main--narrow` |
| A-05 | Fallback heading font, no type scale | Source Serif 4 and `--wm-text-*` |
| A-23 | Modals differ | `modal_frame` and shared `.modal-*` styles; full screen below `sm` |
| A-20 | Tables clip columns at 390 px | `wm-table-scroll` with an edge shadow and a hint |
