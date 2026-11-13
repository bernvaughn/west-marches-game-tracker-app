# Audit walk: game master (GM)

Scratch findings for the game master walk of the U84 UI audit. Tmp ids use the prefix `GM`.

## Scope and method

- Main at `b0b2bb1` (the audit tooling merge). Roles: `gm_only` where the page allows it, else `gm` (club admin and game master). `gm_only` gets a 403 on club-admin views (inbox, shop and quest management, item create, edit and references, agenda, downtime actions). Those rows use role `gm`.
- Capture: `scripts/screenshots.py --audit --pages '<glob>'` for every owned page at 1920, 1280, 768 and 390 px. This gave 487 screenshots of 122 page names (owned pages plus a few neighbours). `scripts/console_sweep.py --widths 1920,1280,768,390` ran over the same globs: 0 problems.
- Review: I read every owned page at 1280 and 390 px. At 1920 and 768 px I read inbox, agenda, shop edit and quest list by eye. For the other pages the 768 px OVERFLOW and CLIPPED checks and the 1920 px capture stood in for a full read. The tables below list only what I saw.
- Walks: six workflows on a scratch SQLite database, driven by a throwaway Playwright script (not in the repo). Steps are named `walk-<workflow>-<step>@<width>.png`: `catalogue`, `quests`, `shops`, `awards`, `agenda`, `inbox`, plus `chars` for the adjust, consume and handover submit results.
- Screenshots are attached to the task as `gm-shots.zip`. None are in the repo.
- The sandbox has no emoji font. Empty emoji boxes are ignored (A-37). Themed pages keep their theme.
- Rules cited: `DESIGN_SYSTEM.md` (Components, Rules), `AUDIT.md` ids, WCAG 2.1 AA, or "Best existing example".

## Findings

| Tmp id | Page | Width | Role | Screenshot | Theme | Rule broken | Severity | Notes |
|---|---|---|---|---|---|---|---|---|
| GM-01 | accounts-message-inbox | 1920 | gm | accounts-message-inbox@1920.png | tables | DESIGN_SYSTEM.md data_table (`td.actions`); AUDIT.md A-20 residual | High | The Actions column is wider than the page cap. "Give map credit" is cut off inside `wm-table-scroll`. The GM must scroll the table to reach it. |
| GM-02 | accounts-message-inbox | 1280 | gm | accounts-message-inbox@1280.png | tables | DESIGN_SYSTEM.md data_table; AUDIT.md A-20 residual | High | Same cut-off at 1280. Tool: `CLIPPED accounts-message-inbox (div.wm-table-scroll)`. |
| GM-03 | accounts-message-inbox | 768 | gm | accounts-message-inbox@768.png | tables | DESIGN_SYSTEM.md data_table; AUDIT.md A-20 residual | High | "Mark handled" is cut off; Close and all three Give buttons are out of view. |
| GM-04 | accounts-message-inbox | 390 | gm | accounts-message-inbox@390.png | tables | AUDIT.md A-20 residual | High | Message text and every action are off screen. Only From, Character and half the Message show. The inbox is the GM's action list, so this hides its purpose. |
| GM-05 | accounts-message-inbox | 1280 | gm | walk-inbox-13-all-final@1280.png | tables | DESIGN_SYSTEM.md data_table | Low | Button groups sit at different offsets per row (first row: "Reopen" right-aligned; second row: left). Rows with and without Give buttons look unaligned. |
| GM-06 | accounts-message-give-map | 390 | gm | accounts-message-give-map@390.png | layout and widths | DESIGN_SYSTEM.md Rules (no horizontal overflow at 390) | High | The "Kind of map credit" button group is wider than the column. "Found mark" runs off the right edge and the page scrolls sideways. Tool: `OVERFLOW accounts-message-give-map`. |
| GM-07 | downtime-requests-gm-only | 390 | gm_only | downtime-requests-gm-only@390.png | tables | AUDIT.md A-20 residual | High | Approve and Decline sit in the last column, off screen. The long note wraps to six lines in a narrow column, so the row is tall and the buttons stay hidden. |
| GM-08 | downtime-requests-gm-only | 768 | gm_only | downtime-requests-gm-only@768.png | tables | AUDIT.md A-20 residual | Medium | Tool: `CLIPPED downtime-requests-gm-only@768 (div.wm-table-scroll)`. The Decided and action columns need a scroll. |
| GM-09 | map-requests | 390 | gm | map-requests@390.png | tables | AUDIT.md A-20 residual | High | Approve and Decline are off screen. Only Kind, Map and part of Location show. The row is 180 px tall for one line of content. |
| GM-10 | map-requests | 768 | gm | map-requests@768.png | tables | AUDIT.md A-20 residual | Medium | Tool: `CLIPPED map-requests@768 (span.visually-hidden, div.wm-table-scroll)`. Actions need a scroll. |
| GM-11 | quests-manage | 390 | gm | quests-manage@390.png | tables | AUDIT.md A-20 residual | Medium | Edit and Delete are off screen. The quest name wraps to three lines. |
| GM-12 | quests-manage | 768 | gm | quests-manage@768.png | tables | AUDIT.md A-20 residual | Medium | Tool: `CLIPPED quests-manage@768`. Last columns need a scroll. |
| GM-13 | downtime-actions | 390 | gm | downtime-actions@390.png | tables | AUDIT.md A-20 residual | Medium | The Edit button is cut at the right edge ("Ed"). |
| GM-14 | items-edit | 390 | gm | items-edit@390.png | forms | DESIGN_SYSTEM.md form_layout; Best existing example: shops-manage-edit (no cramped inputs) | Medium | The four coin inputs share one row. The gp box shows "5(" for 50. Tool: `CLIPPED items-edit (input.form-control)`. `items-create` uses the same value field. |
| GM-15 | quests-edit | 390 | gm | quests-edit@390.png | forms | DESIGN_SYSTEM.md form_layout | Medium | The reward coin row has the same cramped inputs. Tool: `CLIPPED quests-edit (input.form-control)`. |
| GM-16 | downtime-action-edit | 390 | gm | downtime-action-edit@390.png | forms | DESIGN_SYSTEM.md form_layout | Low | Tool: `CLIPPED downtime-action-edit (input.form-control)`. A text input is wider than its box. |
| GM-17 | quests-edit | 1280 | gm | quests-edit@1280.png | forms | Best existing example: shops-manage-edit | Low | Four blank requirement forms and four blank reward forms show by default. Each has a "Delete" tick box that does nothing for an unsaved row. The page is more than 2,000 px tall. `quests-create` has the same. |
| GM-18 | characters-adjust | 390 | gm | characters-adjust@390.png | forms | DESIGN_SYSTEM.md form_layout | Low | The Kind select cuts its text: "Default (award for give, adjustment for tak". |
| GM-19 | characters-adjust | 390 | gm | characters-adjust@390.png | forms | DESIGN_SYSTEM.md form_layout | Low | The Item and Quantity labels are lighter than the bold labels above them. The same formset in the `inbox-give-items-modal@390.png` modal has bold grey labels. The formset label style differs by page. |
| GM-20 | downtime-points-award (walk: no note) | 390 | gm | walk-awards-9-award-validation@390.png | forms | DESIGN_SYSTEM.md form_layout (required mark) | Low | Note is required, but its label has no `*`. The user finds out from the browser tip "Please fill out this field". Date and Points have no mark either. |
| GM-21 | downtime-requests-gm-only | 1280 | gm_only | downtime-requests-gm-only@1280.png | buttons and actions | DESIGN_SYSTEM.md page_header (one primary action, in the header); AUDIT.md A-01 residual | Low | "Request points" sits below the title as a small button. Other list pages (`quests-manage`, `characters-index-gm`) put the primary action beside the title. The page title ("Downtime point requests") also differs from the award page ("Downtime points"). |
| GM-22 | downtime-agenda | 1920 | gm | downtime-agenda@1920.png | layout and widths | DESIGN_SYSTEM.md Rules (page width) | Medium | The agenda fills the full 1920 px. Its title and calendar edge sit at the page gutter. Inbox, manage lists and forms are in a centred column. A wide calendar may be on purpose, so the owner should decide. |
| GM-23 | downtime-agenda | 1280 | gm | downtime-agenda@1280.png | layout and widths | DESIGN_SYSTEM.md Rules (page width) | Medium | The title starts at about 32 px, other GM pages at 96 px. The left edge jumps when the GM moves between pages. |
| GM-24 | downtime-agenda | 1280 | gm | downtime-agenda@1280.png | buttons and actions | DESIGN_SYSTEM.md page_header (one primary action) | Low | "Add rotation", "Add quest" and "Add downtime action" are three equal outline buttons. Manage pages use one red "+ New x" button. |
| GM-25 | map-edit | 1280 | gm | map-edit@1280.png | forms | DESIGN_SYSTEM.md form_layout (forms stop at 40 rem; no nested card) | Medium | The form sits in a card whose header repeats the h1 ("Rename or archive map"). The input fills the card, about 50 rem. Shop, item and quest forms have no card and stop at 40 rem. |
| GM-26 | map-edit | 390 | gm | map-edit@390.png | forms | Best existing example: shops-manage-edit | Low | The card header repeats the title, so the first screen shows the same words twice. |
| GM-27 | catalogue walk: item detail | 1280 | gm | walk-catalogue-5-detail@1280.png | spacing | AUDIT.md A-04 | Low | The "Description" heading sits against the Value row. Retire and Delete sit outside the card, left-aligned, while Edit is in the header. The Delete hint text is grey and small. |
| GM-28 | catalogue walk: item detail (retired) | 390 | gm | walk-catalogue-9-after-retire@390.png | buttons and actions | DESIGN_SYSTEM.md Rules (touch targets) | Low | Restore and Delete stack at different widths. The hint sits under them. The retired badge floats above the card. |
| GM-29 | shops-manage-list | 390 | gm | shops-manage-list@390.png | layout and widths | DESIGN_SYSTEM.md section | Low | The Street settings card (three number fields) comes before the shop list. At 390 px the list starts after about 650 px. The street settings form is a rarely used control above the main task. |
| GM-30 | shops-manage-list | 1280 | gm | shops-manage-list@1280.png | forms | DESIGN_SYSTEM.md form_layout | Low | The street settings fields are 12 rem wide, but the card is full width. The fields look lost in the card. |
| GM-31 | ledger-index | 390 | gm | ledger-index@390.png | forms | Best existing example: accounts-message-inbox (filter pills) | Low | The filter form is about 600 px tall: seven fields, a tick box and two buttons, mixed one and two per row. Rows start below the fold. The "Downtime only" tick box sits between buttons. |
| GM-32 | shops-manage-edit | 390 | gm | shops-manage-edit@390.png | layout and widths | Best existing example: items-edit | Low | The silhouette and building pickers each take three tiles per row. The form is about 2,700 px tall before the Stock section. |

## Coverage

Each page was captured at 1920, 1280, 768 and 390 px for the role named. "Read" means I viewed it at 1280 and 390 px. "Tool" means the tool checks ran (OVERFLOW, CLIPPED, console sweep) and showed no problem I could confirm.

| Area | Pages | Result |
|---|---|---|
| Shops | shops-manage-list, shops-manage-edit | Read. GM-29, GM-30, GM-32. |
| Shops | shops-manage-create, shops-stock-add, shops-stock-edit, shops-rotation-list, shops-rotation-create, shops-rotation-edit, shops-manage-list-club-admin | Read at 1280 and 390 for create, stock and rotation list. No problems beyond the table notes below. |
| Items | items-create, items-edit, items-references, items-index-gm, items-index-gm-only, items-detail-gm-only | items-edit: GM-14. items-detail-gm-only: GM-27, GM-28. Others: Tool, no problems. |
| Quests | quests-manage, quests-create, quests-edit, quests-index-gm-only, quests-detail-gm-only | GM-11, GM-12, GM-15, GM-17. Index and detail: Tool, no problems. |
| Downtime | downtime-actions, downtime-action-new, downtime-action-edit | GM-13, GM-16. `downtime-action-new`: no problems. |
| Downtime | downtime-agenda, downtime-agenda-add, downtime-agenda-action-new, downtime-agenda-action-edit, downtime-agenda-add-modal (no 390 shot by design) | GM-22 to GM-24. The add modal is clean at 1920, 1280 and 768 (`walk-agenda-3-modal-action-form@1280.png`). |
| Downtime | downtime-requests-gm-only, downtime-points-award, downtime-play-gm-only | GM-07, GM-08, GM-20, GM-21. `downtime-play-gm-only`: Tool, no problems. |
| Characters | characters-index-gm, characters-index-gm-only, characters-detail-gm, characters-detail-gm-only, characters-handover, characters-slips-gm | Read: index and handover. No problems. Detail and slips: Tool, no problems. |
| Characters | characters-adjust, characters-consume | GM-18, GM-19. |
| Map | map-index-gm, map-detail-gm, map-create, map-edit, map-location-create, map-location-edit, map-location-delete, map-encounter-create, map-encounter-edit, map-encounter-delete, map-requests, map-visits, map-found, map-credit | GM-09, GM-10, GM-25, GM-26. Others: Tool, no problems. |
| Inbox | accounts-message-inbox, accounts-message-grant, accounts-message-give-items, accounts-message-give-map, accounts-message-status-confirm, inbox-give-items-modal, inbox-grant-modal, inbox-status-modal | GM-01 to GM-06, GM-19. The modals read well at 1280 and 390 (full screen at 390). |
| Agent | agent-index, agent-connections, agent-batches, agent-batch-detail, agent-proposed-items, agent-proposed-item-detail, plus the `-gm-only` variants | Tool, no problems. |
| Ledger | ledger-index, ledger-index-gm-only | GM-31. |
| Landing | home-gm-only, club-home-gm-only | Tool, no problems. |

Workflows walked step by step at 1280 and 390 px (the agenda and inbox start steps also at 1920 and 768 px):

| Workflow | Steps and result |
|---|---|
| Awards and point requests | Player files two requests (`walk-awards-1-player-request-form`, `-2-player-after-request`). GM queue (`-3`), approve (`-4`), decline (`-5`), tick-box award (`-6`, `-7`, `-8`), award with no note (`-9`), player view (`-10`, `-11`). All steps work. Success messages appear. Findings: GM-07, GM-20, GM-21; the owner questions below. |
| Agenda | Calendar (`walk-agenda-1-calendar`), "+" on a day opens the add modal (`-2`), downtime action form in the modal (`-3`), save (`-4`), mobile add page (`-5`). The modal works and is clean. The calendar becomes a list at 390 px and works. Findings: GM-22 to GM-24. |
| Inbox and gives | Inbox (`walk-inbox-1`), give coins modal, review and confirm (`-2`, `-3`, `-3b`, `-3c`), give items modal and confirm (`-5`, `-5b`), give map (`-7` to `-10`), mark handled modal (`-11`, `-12`), final list (`-13`), player sheet (`-14`). All gives work with a review step before they apply. Findings: GM-01 to GM-06. |
| Item catalogue editing | Index, create (empty, filled), after create, detail, edit, references, retire, restore, delete (`walk-catalogue-1` to `-11`). Findings: GM-14, GM-27, GM-28. No confirm step on retire or delete (see owner list). |
| Shop and rotation management | Create shop, edit, add stock, edit stock, remove stock, create rotation, edit, delete (`walk-shops-1` to `-18`). All steps work with success messages. No layout problems beyond GM-29, GM-30, GM-32. No confirm on remove or delete. |
| Quest management | Create (empty, filled), edit, delete from the edit page and from the list (`walk-quests-1` to `-7`). Findings: GM-11, GM-15, GM-17. No confirm on delete. |
| Character adjust, consume, handover, slips | Submit results only (`walk-chars-1` to `-4`): adjust and consume return to the sheet with a success message; handover without an owner stays on the page with no message beyond the browser tip; slips shows one "Print slips" action. |

## Needs the owner

1. **No confirm before destructive or final actions.** I submitted each with no dialog and no confirm page: item delete (the hint says "Deletes only if unused; otherwise retires", so the result is not clear before the click), item retire, quest delete (on the edit page and in the list row), rotation delete, shop stock remove, request approve and decline. Should any of them ask first?
2. **Decline has no reason field.** The GM declines a point request with one click and the player gets no reason. Is that on purpose?
3. **Map credit is not listed under "Granted".** After "Give map credit" the inbox row lists the coins and items given but not the map credit (`walk-inbox-13-all-final@1280.png`).
4. **Stock requests cannot be filled from the inbox.** Their rows offer only Mark handled and Close, while a plain message also offers Give coins, items and map credit. Should a stock request have a Give items button?
5. **Role split.** A `gm_only` user gets 403 on the inbox, shop and quest management, item create and edit, the agenda and downtime actions. The "Approvals" badge shows 4 for `gm_only` and 6 for `gm`. Should a game master who is not a club admin see these pages?
6. **Agenda page width.** Should the agenda use the full width (as now) or the centred column like the other GM pages (GM-22, GM-23)?
7. **Street settings position.** Should the street settings card stay above the shop list (GM-29)?
8. **Handover with no owner** shows no app message, only the browser tip. Is a server-side error message needed?

## Tool output

Lines from `scripts/screenshots.py --audit` for owned pages. `span.visually-hidden`, `legend.visually-hidden` and `label.visually-hidden` are screen-reader text by design. `div.wm-table-scroll` is the table scroll area. Neither is a fault alone. The faults are in the table above.

```
CLIPPED accounts-message-give-items (span.visually-hidden)
CLIPPED accounts-message-give-items@768 (span.visually-hidden)
CLIPPED accounts-message-give-map (span.visually-hidden)
CLIPPED accounts-message-give-map@768 (span.visually-hidden)
CLIPPED accounts-message-grant (span.visually-hidden)
CLIPPED accounts-message-grant@768 (span.visually-hidden)
CLIPPED accounts-message-inbox (div.wm-table-scroll)
CLIPPED accounts-message-inbox-club-admin (div.wm-table-scroll)
CLIPPED accounts-message-inbox-club-admin@768 (div.wm-table-scroll)
CLIPPED accounts-message-inbox@768 (div.wm-table-scroll)
CLIPPED accounts-message-status-confirm (span.visually-hidden)
CLIPPED accounts-message-status-confirm@768 (span.visually-hidden)
CLIPPED agent-batch-detail (span.visually-hidden, div.wm-table-scroll, input.form-control)
CLIPPED agent-batch-detail@768 (span.visually-hidden, input.form-control)
CLIPPED agent-batches (span.visually-hidden, div.wm-table-scroll)
CLIPPED agent-batches-gm-only (span.visually-hidden, div.wm-table-scroll)
CLIPPED agent-batches-gm-only@768 (span.visually-hidden)
CLIPPED agent-batches@768 (span.visually-hidden)
CLIPPED agent-connections (span.visually-hidden, div.wm-table-scroll)
CLIPPED agent-connections@768 (span.visually-hidden)
CLIPPED agent-proposed-item-detail (span.visually-hidden, input.form-control)
CLIPPED agent-proposed-item-detail@768 (span.visually-hidden)
CLIPPED agent-proposed-items (span.visually-hidden, div.wm-table-scroll)
CLIPPED agent-proposed-items@768 (span.visually-hidden)
CLIPPED characters-consume-modal (div.wm-table-scroll, span.visually-hidden, label.visually-hidden)
CLIPPED characters-consume-modal@768 (span.visually-hidden, label.visually-hidden)
CLIPPED characters-consume-player (span.visually-hidden, label.visually-hidden)
CLIPPED characters-consume-player@768 (span.visually-hidden, label.visually-hidden)
CLIPPED characters-detail-gm (div.wm-table-scroll, span.visually-hidden)
CLIPPED characters-detail-gm-only (div.wm-table-scroll, span.visually-hidden)
CLIPPED characters-detail-gm-only@768 (span.visually-hidden)
CLIPPED characters-detail-gm@768 (span.visually-hidden)
CLIPPED characters-index-gm (div.wm-table-scroll)
CLIPPED characters-index-gm-only (div.wm-table-scroll)
CLIPPED characters-slips-gm (div.wm-table-scroll)
CLIPPED downtime-action-edit (input.form-control)
CLIPPED downtime-actions (div.wm-table-scroll, span.visually-hidden)
CLIPPED downtime-actions@768 (span.visually-hidden)
CLIPPED downtime-agenda-action-edit (span.visually-hidden)
CLIPPED downtime-agenda-action-edit@768 (span.visually-hidden)
CLIPPED downtime-agenda-action-new (span.visually-hidden)
CLIPPED downtime-agenda-action-new@768 (span.visually-hidden)
CLIPPED downtime-agenda-add (span.visually-hidden)
CLIPPED downtime-agenda-add@768 (span.visually-hidden)
CLIPPED downtime-points-award (div.wm-table-scroll)
CLIPPED downtime-requests-gm-only (div.wm-table-scroll)
CLIPPED downtime-requests-gm-only@768 (div.wm-table-scroll)
CLIPPED inbox-give-items-modal (div.wm-table-scroll)
CLIPPED inbox-give-items-modal@768 (div.wm-table-scroll)
CLIPPED inbox-grant-modal (div.wm-table-scroll)
CLIPPED inbox-grant-modal@768 (div.wm-table-scroll)
CLIPPED inbox-status-modal (div.wm-table-scroll)
CLIPPED inbox-status-modal@768 (div.wm-table-scroll)
CLIPPED items-detail-club-admin (span.visually-hidden)
CLIPPED items-detail-club-admin@768 (span.visually-hidden)
CLIPPED items-detail-gm-only (span.visually-hidden)
CLIPPED items-detail-gm-only@768 (span.visually-hidden)
CLIPPED items-edit (input.form-control)
CLIPPED items-index-club-admin (div.wm-table-scroll, span.visually-hidden)
CLIPPED items-index-club-admin@768 (span.visually-hidden)
CLIPPED items-index-gm (div.wm-table-scroll, span.visually-hidden)
CLIPPED items-index-gm-only (div.wm-table-scroll, span.visually-hidden)
CLIPPED items-index-gm-only@768 (span.visually-hidden)
CLIPPED items-index-gm@768 (span.visually-hidden)
CLIPPED ledger-index (div.wm-table-scroll)
CLIPPED ledger-index-club-admin (div.wm-table-scroll)
CLIPPED ledger-index-gm-only (div.wm-table-scroll)
CLIPPED map-credit (span.visually-hidden, legend.visually-hidden)
CLIPPED map-credit@768 (span.visually-hidden, legend.visually-hidden)
CLIPPED map-detail-gm (span.visually-hidden)
CLIPPED map-detail-gm-only (span.visually-hidden)
CLIPPED map-detail-gm-only@768 (span.visually-hidden)
CLIPPED map-detail-gm@768 (span.visually-hidden)
CLIPPED map-found (span.visually-hidden, legend.visually-hidden)
CLIPPED map-found@768 (span.visually-hidden, legend.visually-hidden)
CLIPPED map-requests (span.visually-hidden, div.wm-table-scroll)
CLIPPED map-requests@768 (span.visually-hidden, div.wm-table-scroll)
CLIPPED map-visits (span.visually-hidden, legend.visually-hidden)
CLIPPED map-visits@768 (span.visually-hidden, legend.visually-hidden)
CLIPPED quests-edit (input.form-control)
CLIPPED quests-manage (div.wm-table-scroll, span.visually-hidden)
CLIPPED quests-manage-club-admin (div.wm-table-scroll, span.visually-hidden)
CLIPPED quests-manage-club-admin@768 (div.wm-table-scroll, span.visually-hidden)
CLIPPED quests-manage@768 (div.wm-table-scroll, span.visually-hidden)
CLIPPED shops-manage-edit (div.wm-table-scroll, span.visually-hidden)
CLIPPED shops-manage-edit@768 (span.visually-hidden)
CLIPPED shops-manage-list (div.wm-table-scroll)
CLIPPED shops-manage-list-club-admin (div.wm-table-scroll)
CLIPPED shops-rotation-list (div.wm-table-scroll, span.visually-hidden)
CLIPPED shops-rotation-list@768 (span.visually-hidden)
CLIPPED shops-stock-add (span.visually-hidden)
CLIPPED shops-stock-add@768 (span.visually-hidden)
CLIPPED shops-stock-edit (span.visually-hidden)
CLIPPED shops-stock-edit@768 (span.visually-hidden)
OVERFLOW accounts-message-give-map
```

Console sweep (`scripts/console_sweep.py --widths 1920,1280,768,390`, run on 15 glob groups covering the owned pages): every run ended `Done: 0 problem(s).`

Walk-time server log: no 5xx during the walks. One 403 came from my own script (`alice` opening the club-admin list `/characters/`), not from a page under audit.
