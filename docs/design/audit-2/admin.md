# Audit 2: club admin, site admin, navigation, print, accessibility (prefix `AD`)

Walk of `club_admin` (`clubadmin@example.com`) and `site_admin` (`admin@example.com`), plus the cross-cutting checks. Main was at b0b2bb1. Screenshots are attached to the walk task as `u84-admin-shots.zip` (folders `audit2` for tool shots, `walk` for walk and print shots, `pdf` for A4 print PDFs, `axe` for axe-core JSON). None are in the repo.

Coverage notes:

- All owned pages were captured at 1920, 1280, 768 and 390 px with `scripts/screenshots.py --audit`. `accounts-whitelist` and `accounts-reset-password` exist in the tool only as `gm`; the walk shots `walk-admin-*` cover them as `club_admin`.
- `shops:street_settings` is POST only. The form is on `shops-manage-list-club-admin`.
- Workflows walked at all four widths: members list, whitelist (native validation error, valid add with temporary password, duplicate), reset password (confirm and result), street settings (invalid and saved), site clubs, new club (empty and valid), site settings save, `/site/design/`.
- Top bar: six roles (anon, alice, gm, gm_only, club_admin, site_admin) at four widths, closed, menu open and each dropdown open (`walk-topbar-<role>-<state>@<width>.png`). No horizontal overflow at any width, and the bar is one row (53 px high) for every role and width.
- Print: seven print pages in print emulation at 1280 plus A4 PDF. Nav, buttons and footers hide, each prints on one A4 page, and nothing clips in print.
- axe-core 4.10.2 (WCAG 2.0/2.1 A and AA tags) on 23 pages at 1280 and 390. Only the rows below failed. Colour contrast failed only on `site-design`.
- Keyboard: Tab through whitelist, members, shops manage, new club and `/site/design/`. Every stop had a visible focus ring, there was no trap, and focus returned to the menu toggle after the menu closed with Escape. The modal focus return was not checked on an admin page: none of them opens a modal.
- Icon-only buttons: the character sheet icon buttons all have hidden text and a tooltip. Only the close buttons (menu and modal) have an `aria-label` without a tooltip.

| Tmp id | Page | Width | Role | Screenshot | Theme | Rule broken | Severity | Notes |
|---|---|---|---|---|---|---|---|---|
| AD-01 | site-design | 1280 | site_admin | site-design@1280.png | accessibility | WCAG 2.1 AA 1.4.3 contrast | High | axe: 15 inline `code` samples are pink `#e83e8c` on `#fbf8f3`, 3.6:1 (needs 4.5:1). Same at 390. The Bootstrap default `code` colour is not overridden. Other pages that use `code` will fail the same way. |
| AD-02 | site-design | 1280 | site_admin | site-design@1280.png | forms | WCAG 2.1 A 1.3.1 / 4.1.2 (form labels); DESIGN_SYSTEM "form_layout" | Medium | axe: 2 `.form-control` samples have no label (the form-layout sample). The reference page models a pattern it breaks. |
| AD-03 | site-design | 390 | site_admin | site-design@390.png | accessibility | WCAG 2.1 A 2.1.1 keyboard | Medium | axe: scrollable `pre` code blocks cannot take focus (5 at 1280, 17 at 390). A keyboard user cannot scroll them. The tool also reports them as CLIPPED at 768, 1280 and 1920. Fix with `tabindex="0"` on `.wm-code-wrap pre`. |
| AD-04 | site-design | 1280 | site_admin | site-design@1280.png | layout and widths | DESIGN_SYSTEM "page_header": one `h1` per page | Low | The page has 3 `h1` elements, because the component samples render real `page_header` headings. Use a sample wrapper that demotes them. |
| AD-05 | map-print | 1280 | alice | map-print@1280.png | accessibility | WCAG 2.1 A 4.1.2 (axe nested-interactive) | Low | The hex map SVG has focusable descendants. Same at 390. |
| AD-06 | club-home-club-admin | 1280 | club_admin | walk-topbar-club_admin-closed@1280.png | layout and widths | DESIGN_SYSTEM "Rules": top bar, initials chip below 1400 px | Medium | The rule says the full name shows at 1400 px and wider, and an initials chip below that. The code hides the name only below 400 px (`.user-name-text` in `components.css`), so the chip and the name show together at 768 and 1280 px, and a long name is cut ("Cleo the Club A..."). Either the code or the doc is wrong. |
| AD-07 | accounts-whitelist | 390 | club_admin | walk-admin-whitelist-error@390.png | layout and widths | DESIGN_SYSTEM "Rules": the top bar fits at 390 px | Medium | The bar does not overflow but it cuts the club name ("Demo M...") and the character label ("No chara..."), and the Approvals badge loses its word. Same on every club page for GM and admins. |
| AD-08 | accounts-index-club-admin | 390 | club_admin | walk-admin-members-list@390.png | tables | AUDIT.md A-20 (tables clip columns at 390 px) | Medium | The People table scrolls sideways. The email is cut and the Reset password button (the only action) is off screen. The name column wraps to four lines ("Cleo the Club Admin"). Best existing example: `shops-manage-list-club-admin` (shops table keeps its key column visible). |
| AD-09 | accounts-index-club-admin | 1280 | club_admin | accounts-index-club-admin@1280.png | tables | DESIGN_SYSTEM "data_table" (`td.actions`); Best existing example: characters-detail-alice (row icon buttons with tooltips) | Low | Every row has a text "Reset password" outline button, taller than the row text. The name and email sit at the top of the cell instead of centred against it. The row action is a destructive step with no warning on the button. |
| AD-10 | accounts-index-club-admin | 1280 | club_admin | accounts-index-club-admin@1280.png | buttons and actions | DESIGN_SYSTEM "page_header": one primary action | Low | People has no page action, so the Whitelist page is reachable only from the side menu. Best existing example: `site-clubs` (header "New club" action). |
| AD-11 | accounts-whitelist | 390 | club_admin | walk-admin-whitelist-success@390.png | forms | DESIGN_SYSTEM "form_layout" | Low | The "Game master" checkbox is indented about 24 px from the other fields at 390 and 1280. |
| AD-12 | accounts-whitelist | 1280 | club_admin | walk-admin-whitelist-duplicate@1280.png | spacing | DESIGN_SYSTEM "alert"; Best existing example: reset password result (alert below the title) | Medium | Flash messages ("already a member", "Site settings saved.") render above the page header. The title drops from y=99 to y=190, so the page jumps after every save. Also on `site-settings`. |
| AD-13 | accounts-whitelist | 1280 | club_admin | walk-admin-whitelist-success@1280.png | tables | DESIGN_SYSTEM "data_table" | Low | The "Whitelisted emails" table has one column (email). It has no status (joined or not), no date, and no row action. |
| AD-14 | accounts-reset-password | 1280 | club_admin | walk-admin-reset-confirm@1280.png | wording | DESIGN_SYSTEM "back_link"; wording | Low | The confirm page has no back link, but the result page has "Back to people". The title changes from "Reset password" to "Password reset". The subtitle "Confirm the reset." is vague. The alert title is only the name "Alice", with no "Reset the password for" lead. |
| AD-15 | shops-manage-list-club-admin | 1280 | club_admin | shops-manage-list-club-admin@1280.png | buttons and actions | DESIGN_SYSTEM "Light only. One primary action per page" | Medium | Two primary buttons: header "New shop" and the street settings "Save". Make Save secondary or move the street settings to its own page. |
| AD-16 | site-clubs | 390 | site_admin | walk-admin-site-clubs@390.png | spacing | DESIGN_SYSTEM "icon"; Best existing example: site-clubs@1280 | Low | At 390 the "+" icon touches the label ("+New club"). At 1280 there is a gap. Same for "+New shop" on `shops-manage-list-club-admin@390`. |
| AD-17 | shops-manage-list-club-admin | 390 | club_admin | walk-admin-street-error@390.png | tables | AUDIT.md A-20 | Low | The shops table clips from the Sell % column at 390. The scroll shadow is the only hint. The tool reports CLIPPED `div.wm-table-scroll`. |
| AD-18 | shops-manage-list-club-admin | 390 | club_admin | walk-admin-street-error@390.png | forms | DESIGN_SYSTEM "form_layout" (errors with an icon) | Low | The invalid field gets an amber border and an amber icon, while the message below is red with a red triangle. Two tones for one error. |
| AD-19 | characters-slips-print | 1280 | alice | characters-slips-print@1280.png | wording | DESIGN_SYSTEM "alert"; Best existing example: whitelist (error only after a submit) | Medium | The picker shows a red "Tick at least one character." alert on first load, before the player did anything. |
| AD-20 | characters-slips-print | 1280 | alice | walk-print-characters-slips-print@print.png | print | Best existing example: map-print (prints only the content) | Low | Print of the picker prints the table with empty tick boxes and the red alert, but no slips. |
| AD-21 | characters-print-items | 390 | alice | characters-print-items@390.png | layout and widths | AUDIT.md A-17 (no overflow at 390) | Medium | Tool OVERFLOW: the card sheet is a fixed width and scrolls sideways on a phone. It prints correctly (`walk-print-characters-print-items@print.png`). Same for `characters-print-item-full@390` and `characters-print-item-grid@390`. |
| AD-22 | characters-slips-print-aria | 768 | alice | characters-slips-print-aria@768.png | layout and widths | AUDIT.md A-17 | Medium | Tool OVERFLOW at 768 and 390: the slip is fixed width. Prints on one A4 page (`pdf/characters-slips-print-aria.pdf`). |
| AD-23 | characters-detail-alice | 1280 | alice | characters-detail-alice@1280.png | layout and widths | AUDIT.md A-01 (no shared page header) | Medium | These templates have an `h1` but do not use `components/page_header`: `characters/detail.html`, `characters/slips.html`, `characters/print.html`, `characters/print_item_choose.html`, `characters/form.html`, `trades/edit_side.html`, `shops/browse/detail.html`, and the `registration/*` pages (login, logout, password change). Other walks should check the look. |
| AD-24 | accounts-index-club-admin | 1280 | club_admin | accounts-index-club-admin@1280.png | accessibility | WCAG 2.1 A 2.4.1 bypass blocks | Low | There is no skip link in `base.html`. A keyboard user tabs through the top bar stops on every page before the content. |
| AD-25 | club-home-club-admin | 1280 | club_admin | walk-topbar-club_admin-menu@1280.png | tooltips | DESIGN_SYSTEM "icon" (icon-only buttons carry a label) | Low | The menu close button and the modal close button have `aria-label` but no tooltip. The labels are fine; only mouse users get no hint. |
| AD-26 | site-settings | 1280 | site_admin | walk-admin-site-settings-saved@1280.png | layout and widths | DESIGN_SYSTEM "Page width" | Low | Site pages (clubs, new club, settings) show a top bar with no club name or area links and a large empty page below. A single-field form is a full card. Cosmetic. |

## Needs the owner

- **Reset password has no per-row confirm on the list.** The list button goes to a confirm page, so a mistake is guarded. But the confirm page shows the temporary password once, on the result page only. If the admin reloads, the password is lost with no way to see it. Is that intended?
- **Whitelist has no remove or edit.** A wrong email stays on the list. Should the page offer a remove action, or a status per row (invited, joined)?
- **Street settings errors render at the POST URL** (`/shops/manage/street/`). A reload re-submits the form. Redirect with the errors in the session, or keep the page?
- **Top bar name rule.** AD-06: decide whether the doc (initials chip below 1400 px) or the code (name shown down to 400 px) is the rule.
- **Print pages on a phone.** AD-21 and AD-22: should the card sheet and slip pages scale to the screen, or stay fixed at the print size?
- **Site admin pages without club context.** Should the site admin see a site-level top bar (Clubs, Settings, Design) instead of the menu only?

## Tool output

`scripts/screenshots.py --audit` (OVERFLOW and CLIPPED lines for the owned pages; `span.visually-hidden` clips are expected):

```
OVERFLOW characters-print-items
OVERFLOW characters-print-item-full
OVERFLOW characters-print-item-grid
OVERFLOW characters-slips-print-aria
OVERFLOW characters-slips-print-aria@768
CLIPPED accounts-index (div.wm-table-scroll, span.visually-hidden)
CLIPPED accounts-index@768 (span.visually-hidden)
CLIPPED accounts-index-club-admin (div.wm-table-scroll, span.visually-hidden)
CLIPPED accounts-index-club-admin@768 (span.visually-hidden)
CLIPPED shops-manage-list-club-admin (div.wm-table-scroll)
CLIPPED site-design (pre, span.visually-hidden)
CLIPPED site-design@768 (pre, span.visually-hidden)
CLIPPED characters-slips-print (div.wm-table-scroll)
CLIPPED characters-print-items, -item-choose, -item-full, -item-grid, characters-slips-print-aria, map-print (span.visually-hidden, at 390 and 768)
```

`scripts/console_sweep.py --audit` on the same page globs: `Done: 0 problem(s).` for all 12 runs.

axe-core 4.10.2 (1280 and 390): `site-design` color-contrast (15), label (2), scrollable-region-focusable (5 at 1280, 17 at 390); `map-print` nested-interactive (1). No violations on the other 21 pages.

Print emulation (1280, A4 PDF): every print page fits one A4 page, no visible nav, buttons or `.no-print` elements, body is black on white, no element extends past the page width.

Walk log:

```
whitelist bad email: native validation blocks submit (no server message)
whitelist empty:     native validation blocks submit
whitelist ok:        temporary password alert, new row
whitelist duplicate: info flash above the title
street invalid:      field error under "Maximum", page at /shops/manage/street/
street saved:        redirect to /shops/manage/
club new ok:         "Club created" with temporary password
settings saved:      success flash above the title
```
