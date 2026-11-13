# Audit 2 scratch notes (U84)

These files hold the raw findings of the UI audit. Each walk story fills one file. The final story merges them into `docs/design/AUDIT-2.md` and deletes this folder.

Read `docs/design/AUDIT.md` (the first audit), `docs/design/DESIGN_SYSTEM.md` and `/site/design/` before you start.

## Files

| File | Owner |
|---|---|
| `player-shops.md` | Walk: player shops and trades |
| `player-play.md` | Walk: player sheet, quests, downtime, inbox, catalogue |
| `gm.md` | Walk: game master |
| `admin.md` | Walk: club admin, site admin, navigation, print, accessibility |

No two walks edit the same file.

## Table header

```
| Tmp id | Page | Width | Role | Screenshot | Theme | Rule broken | Severity | Notes |
```

## Column rules

- **Tmp id**: the file prefix and a number: `PS-01`, `PP-01`, `GM-01`, `AD-01`. The final story maps them to `B-01`, and so on.
- **Page**: the page name from `scripts/screenshot_pages.py`, or the workflow step.
- **Width**: 1920, 1280, 768 or 390.
- **Role**: `anon`, `site_admin`, `gm`, `gm_only`, `club_admin`, `alice` (player) or `bob` (player).
- **Screenshot**: `<page-name>@<width>.png`, as the tool names it. A walk step that is not in the page list uses `walk-<workflow>-<step>@<width>.png`.
- **Theme**: one of layout and widths, spacing, buttons and actions, tables, forms, modals, empty states, tooltips, wording, print, accessibility.
- **Rule broken**: a `DESIGN_SYSTEM.md` section, a `/site/design/` pattern, an `AUDIT.md` id that regressed, or WCAG 2.1 AA for contrast and focus. If no written rule exists, write "Best existing example: <page>". The final story lists these as candidate rules.
- **Severity**: see below.

## Severity

- **High**: a broken layout, an unreadable or unusable page at a width, or a contrast failure (WCAG 2.1 AA).
- **Medium**: a visible inconsistency with the design system on a common page.
- **Low**: minor polish.

## Other rules

- Themed pages (shop street and banner, quest board, chalkboard Downtime page, stalls) keep their theme. Report only the consistency problems around the theme.
- Empty emoji boxes in sandbox screenshots are not a problem. The sandbox has no emoji font (`AUDIT.md` A-37).
- Do not change the app in a walk. Put anything that needs a product decision under "Needs the owner".

## Sections of each file

Each file ends with these two sections:

- **Needs the owner**: questions that only the owner can decide.
- **Tool output**: the OVERFLOW, CLIPPED and console sweep lines for the pages that the walk owns.

## Roles

`extra_fixtures()` in `scripts/screenshot_pages.py` creates the last two roles. `seed_demo` does not.

| Role | Login | What it is |
|---|---|---|
| `site_admin` | `admin@example.com` | Site admin |
| `gm` | `gm@example.com` | Club admin and game master |
| `alice` | `alice@example.com` | Player (Aria Windrunner) |
| `bob` | `bob@example.com` | Player (Borin Stonefist) |
| `gm_only` | `gm-only@example.com` | Game master, not club admin |
| `club_admin` | `clubadmin@example.com` | Club admin, not game master |

The password is `demo-password` for all of them.

`gm_only` gets a 403 on every view that needs a club admin: the inbox, shop and quest management, item create, edit and references, the agenda and the downtime actions. Capture those pages as `gm` or `club_admin`.

## Capture commands

```bash
# Every page at 1920, 1280, 768 and 390 px. Prints OVERFLOW and CLIPPED lines.
uv run python scripts/screenshots.py --audit --out <scratch>/audit
# One area only.
uv run python scripts/screenshots.py --audit --pages 'shops-*' --out <scratch>/audit
# The console sweep at the audit widths.
uv run python scripts/console_sweep.py --widths 1920,1280,768,390
```

Browser setup without root: see the wiki page `testing/browser-checks-without-root`. Attach screenshots to the story task with `ch task attach`. Never commit them.
