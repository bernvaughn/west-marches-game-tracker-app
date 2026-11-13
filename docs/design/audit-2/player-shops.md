# Audit 2: player shops, stalls and trades (U84, walk S2)

Walk owner: player shops and trades. Roles: `alice` (player) and `bob` (the other side of a trade and the stall owner). Revision walked: `origin/main` at b0b2bb1 (the tooling merge). Screenshots are attached to the CodeHerder task, not to the repo.

Method: `scripts/screenshots.py --audit` for the owned pages, `scripts/console_sweep.py --audit` for the console, and a throwaway Playwright walk of each workflow at 1920, 1280, 768 and 390 px on a fresh seeded database. Themed pages (street, shop banner, stalls) keep their theme. Empty emoji boxes are ignored (A-37).

## Coverage

- Pages, all at 1920, 1280, 768 and 390 px as `alice` unless noted: `shops-index`, `shops-detail-lantern`, `shops-detail-caravan`, `shops-buy`, `shops-buy-modal`, `shops-sell-modal`, `shops-sell-junk`, `shops-sell-junk-modal`, `shops-stall-borin`, `shops-stall-own` (`bob`), `shops-stall-buy`, `shops-stall-buy-modal`, `characters-junk`, `characters-junk-modal`, `items-where-to-buy`, `items-where-to-buy-modal`, `trades-index`, `trades-propose`, `trades-detail-alice`, `trades-detail-bob` (`bob`), `trades-detail-requested`, `trades-edit-side`. I read all of them at 1280 and 390. I read 1920 and 768 for the street, the shop detail and the stalls. The other 1920 and 768 shots were checked by the OVERFLOW and CLIPPED lines only; they are in the zip.
- Not owned: `shops-manage-*`, `shops-stock-*`, `shops-rotation-*`, `shops-*-gm-only`, `shops-*-club-admin`. They were captured as a by-product and are in the zip. S4 and S5 own them.
- Workflows, each walked at 1920, 1280, 768 and 390 px, files `walk-<workflow>-<step>@<width>.png`:
  - `selling`: street, shop, confirm modal (non-junk item), result.
  - `buying`: modal that cannot be afforded, modal that can, quantity too high, result.
  - `junk`: sheet, Mark junk modal, filled, result, shop shows junk. `sell-junk`: modal, result, the direct page with nothing left to sell.
  - `stalls`: bob's sheet toggle, off, street without the stall, on, own stall, street, alice's view, buy modal, result, bob's sheet after.
  - `trades`: index, propose (empty, filled), proposed, edit too early, bob requested view, bob accept blocked, accepted trade, edit side, after edit, other side sees the edit, each side approves, completed, index after, bob accepts, cancel, decline.
  - `where-to-buy`: item list, modal, link to the shop.
- The walk found no horizontal overflow and no console error at any width.

## Findings

| Tmp id | Page | Width | Role | Screenshot | Theme | Rule broken | Severity | Notes |
|---|---|---|---|---|---|---|---|---|
| PS-01 | shops-detail-caravan (inventory sell table) | 390 | alice | shops-detail-caravan@390.png | layout and widths | A-20 (residual); DESIGN_SYSTEM data_table | High | The "Your inventory" table is wider than its card. The quantity box and "Sell for" button are cut off at the right and only a sideways swipe inside the table shows them. The main action of the sell flow is half hidden. The same table sits on `shops-detail-lantern@390.png` and in `walk-selling-2-shop@390.png`. |
| PS-02 | shops-detail-caravan (inventory sell rows) | 1280 | alice | shops-detail-caravan@1280.png | tables | Best existing example: trades-propose (inventory table) | Medium | The "Sell for" row has a different shape from every other table. The Quantity box and the button float at the far right under no column header. The Rope row has no action and no explanation. Qty and Available are left-aligned here but right-aligned in the character sheet table (A-07). The qty boxes have three widths (the button text changes the width). |
| PS-03 | shops-detail-caravan (junk row) | 1280 | alice | shops-detail-caravan@1280.png | spacing | DESIGN_SYSTEM tokens: Spacing | Low | The "Sell junk" button touches the table header with no gap. The coin lines above have a different gap from the lines below. |
| PS-04 | shops-detail-caravan (page heading) | 1280 | alice | shops-detail-caravan@1280.png | layout and widths | DESIGN_SYSTEM page_header ("the one h1") | Medium | The shop name is centred and sits above the banner, while `shops-index`, `shops-stall-*`, `trades-*` and every other page put the h1 on the left or inside the page header. A stray shop symbol sits at the far left of the heading row and is not tied to the title. The same at 1920, 768 and 390 (`shops-detail-caravan@390.png`: the title wraps to two lines). |
| PS-05 | shops-stall-borin | 1280 | alice | shops-stall-borin@1280.png | layout and widths | DESIGN_SYSTEM page_header; banner | Medium | The stall title sits inside the banner on the right of the stall picture, on the ground line. The caravan title is above the banner and centred. The two shop types use two different title places. At 390 the title overlaps the ground strip and touches the left edge (`shops-stall-borin@390.png`). The stall has no back link; the shop detail also has none, but the sell-junk page has one. |
| PS-06 | shops-stall-own | 1280 | bob | shops-stall-own@1280.png | layout and widths | DESIGN_SYSTEM banner ("first in the page") | Medium | The "This is your shop" alert is placed between the banner picture and the ground strip, so the ground line is cut from the picture. Compare `shops-stall-borin@1280.png`. |
| PS-07 | shops-stall-borin (Your inventory) | 1280 | alice | shops-stall-borin@1280.png | tables | A-07 | Low | Under the stall the "Available" header is left-aligned but the numbers are right-aligned, far from the header. The Qty column is left-aligned. The card repeats the coin line and "In open trades" with no sell action, so it gives nothing to do. |
| PS-08 | shops-buy-modal | 390 | alice | shops-buy-modal@390.png | buttons and actions | A-32 (not fixed) | Medium | When the total is more than the coins, the modal says "-1 gp (not enough coins)" but "Buy as Aria Windrunner" stays active. The submit fails after the page reloads (`walk-buying-3-modal-qty3-too-many@390.png`, `walk-buying-4-result@390.png`). A-32 was left open on purpose; it is still a visible gap (see "Needs the owner"). |
| PS-09 | shops-buy-modal | 390 | alice | shops-buy-modal@390.png | modals | DESIGN_SYSTEM modal_frame | Low | The three coin lines (Total, Coins before, Coins after) are stacked label over value at 390 and in a two-column list at 1280 (`walk-stalls-8-buy-modal@1280.png`). The labels use the muted caps style; the other modals (`shops-sell-modal@390.png`) use the same labels with different spacing. The footer buttons stack (Cancel above Buy) in the buy modal but sit side by side in the sell junk modal. |
| PS-10 | shops-sell-modal | 390 | alice | shops-sell-modal@390.png | modals | Best existing example: shops-sell-junk-modal | Medium | The sell confirm modal shows the warning "This item isn't marked as junk." with no explanation of why it matters or what happens. The title is "Sell Healing potion" with a raw item icon, the buy modal title is "Buy Healing potion" and repeats the name in the body. Quantity is plain text here but an input in the buy modal. |
| PS-11 | shops-sell-junk | 1280 | alice | shops-sell-junk@1280.png | empty states | DESIGN_SYSTEM empty_state; "Don't nest cards" | Medium | The empty state is a half-width box inside a card, with white space to its right. The `empty_state` pattern is a full-width block. Compare `trades-index@1280.png` where the empty state is a table row instead (two empty state looks on the same owned flow). |
| PS-12 | trades-index (Closed trades) | 1280 | alice | trades-index@1280.png | empty states | DESIGN_SYSTEM empty_state; data_table_empty | Low | "No closed trades." is a table row under a full header, with the column widths changed from the Open table above (FROM, TO, STATUS and DATE sit at different x positions in the two tables). |
| PS-13 | trades-index | 390 | alice | trades-index@390.png | tables | A-07; A-20 | Medium | The date wraps over three lines ("Nov. / 13, / 2026") and the names wrap over two or three lines. The Open table has four columns of equal weight. The "To" name is not a link but "From" is. |
| PS-14 | trades-detail-alice | 1280 | alice | trades-detail-alice@1280.png | wording | DESIGN_SYSTEM status_badge | Medium | Date formats differ: the index table uses "Nov. 13, 2026", the detail banner uses "13 Nov 2026" (`walk-trades-13-completed@1280.png`). The status reads "Accepted" while the banner says "Both of you need to approve again" and both badges say "not approved". |
| PS-15 | trades-detail-alice | 1280 | alice | trades-detail-alice@1280.png | buttons and actions | DESIGN_SYSTEM page_header ("one primary action") | Medium | The actions are on two rows. "Cancel this trade" (outline red) sits alone above "Change what you give" and "Approve the trade as shown above". The buttons are small (`btn-sm` look) and sit left, but "Propose trade" on the index is a large button on the right. The primary action is last, the opposite of the other pages. At 390 the three buttons stack at three widths (`trades-detail-alice@390.png`). |
| PS-16 | trades-detail-alice | 1280 | alice | trades-detail-alice@1280.png | layout and widths | A-22; DESIGN_SYSTEM back_link | Medium | The detail page uses the muted back link "Back to trades". `trades-propose` and `trades-edit-side` use a breadcrumb ("Trades / Trade 1 / Edit my side") in a different place and style. Their header is a boxed sheet card; the detail header is a plain page header. |
| PS-17 | trades-propose | 1280 | alice | trades-propose@1280.png | layout and widths | DESIGN_SYSTEM Sizes (`--wm-size-form`, narrow main) | Medium | The propose and edit pages end at x=1120; the index and detail end at x=1184, so the page edge jumps by 64 px when you move between them. The Coins and Note boxes sit side by side with different heights and no grid. The box style (heavy black outline) is not the `card` pattern used on the detail page. |
| PS-18 | trades-propose | 1280 | alice | trades-propose@1280.png | forms | A-15 | Low | In "Coins to give" the platinum label is a dark filled pill with white text, while gp, sp and cp are plain text with a dot. The four fields are 76 px wide with no label above them. |
| PS-19 | trades-propose | 1280 | alice | trades-propose@1280.png | accessibility | WCAG 2.1 AA 1.4.3 (not measured) | Low | The disabled Rope row (grey text on cream, field grey) looks lighter than 4.5:1. I did not measure it; the admin walk (S5) runs the axe check. |
| PS-20 | trades-edit-side | 390 | alice | trades-edit-side@390.png | forms | DESIGN_SYSTEM form_layout | Medium | The four coin fields are 40 px wide and the typed value is cut off ("0" is half hidden). The CLIPPED line lists `input.form-control`. The same fields are 76 px wide at 1280. |
| PS-21 | trades-edit-side | 1280 | alice | walk-trades-9-after-edit@1280.png | forms | DESIGN_SYSTEM form_layout (errors with an icon) | Medium | A value above the available count shows the browser's own bubble ("Value must be less than or equal to 1.") and not the inline error with an icon that other forms use. The message appears over the next row. |
| PS-22 | trades-edit-side | 1280 | alice | trades-edit-side@1280.png | layout and widths | DESIGN_SYSTEM page_header | Low | The Coins box has half width and leaves an empty right half. The inventory box below has full width. |
| PS-23 | trades-detail-requested | 1280 | bob | walk-trades-6-bob-accept-blocked@1280.png | buttons and actions | DESIGN_SYSTEM page_header ("one primary action") | Low | "Accept trade request and propose items" is a long label (about 40 characters) on one button; at 390 it wraps over two lines. The Decline button next to it uses the outline red look of "Cancel this trade", but the result of Cancel and Decline is not explained. |
| PS-24 | trades-detail-alice | 390 | alice | walk-trades-18-cancelled@390.png | wording | Best existing example: shops-detail-caravan (success alert) | Low | After "Cancel this trade" the page shows the success alert "Trade cancelled." with a green tick, and the banner says the same again. The two lines repeat each other. Messages across the flows end differently: "Sold 2 × Healing potion to Wandering Caravan for 50 gp." has a full stop; "Bought 1 × Torch from Borin Stonefist's shop" has none. |
| PS-25 | shops-stall-buy-modal | 1280 | alice | walk-stalls-9-result@390.png | buttons and actions | Best existing example: walk-buying-4-result (shop buy) | Medium | After a stall purchase the page returns to the street, not to the stall. A shop purchase stays on the shop. The street shows the stall gone and gives no link to the stall. |
| PS-26 | characters-detail (shop toggle on the sheet) | 390 | bob | walk-stalls-1-sheet-toggle@390.png | forms | DESIGN_SYSTEM form_layout; A-11 | Low | "Sell my junk in my shop" switch is centred in the Inventory box at 390 and left at 1280 (`walk-stalls-1-sheet-toggle@1280.png`). The Inventory table on the sheet is cut off at the right at 390 (the Available column). The sheet is owned by the S3 walk; this row covers only the stall toggle. |
| PS-27 | items-where-to-buy | 1280 | alice | items-where-to-buy@1280.png | empty states | DESIGN_SYSTEM empty_state | Low | "Not for sale anywhere today." is one bare line and a plain "Back to items" link. The link is not the `back_link` pattern (no arrow, no gap, below the text) (A-08, A-22). |
| PS-28 | items-where-to-buy-modal | 390 | alice | items-where-to-buy-modal@390.png | modals | DESIGN_SYSTEM modal_frame | Low | The modal is full screen at 390 for a one-row table, with a large blank area. The "Shops" heading repeats the title. Stalls do not appear in the list (see "Needs the owner"). |
| PS-29 | characters-junk-modal | 390 | alice | characters-junk-modal@390.png | forms | DESIGN_SYSTEM form_layout | Low | "How many are junk?" is a plain input that starts at 0 and the help says "0 removes the junk mark". The modal heading is "Mark junk"; the row button is "Mark as junk". |

## Needs the owner

1. **Buy with too few coins (A-32).** The modal shows "(not enough coins)" and the button still works, then the page rejects the purchase. Should the button be disabled in the modal? This is a behaviour change, so it waits for a decision.
2. **Cancel has no confirm.** "Cancel this trade" on an accepted trade cancels at once with no confirm step. Both sides lose their work. Should it ask first?
3. **Decline has no confirm and gives no reason.** Same for "Decline this trade request".
4. **One accepted trade per character.** A character with an accepted trade cannot accept a second request ("Aria Windrunner already has another accepted trade"). The request page shows the Accept button as usual, and the error only shows after the click. Should the button explain this up front?
5. **Status "Accepted" with nothing approved.** After a side is edited the status stays "Accepted" and both approvals reset. The banner says so, but the badge could read "Needs approval". Is the word change wanted?
6. **Where to buy lists shops only.** A player stall that sells the item does not show in "Where to buy". Is that intended?
7. **Stall purchase goes to the street.** A shop purchase stays on the shop, a stall purchase leaves it. Should both stay on the page you bought from?
8. **Sell flow warns about non-junk.** The confirm modal warns "This item isn't marked as junk." and lets the player sell it at the junk price. Should selling non-junk be allowed in the same flow?

## Tool output

Console sweep (`scripts/console_sweep.py --audit`), owned pages: `shops-*`, `characters-junk*`, `items-where-to-buy*`, `trades-*`: **0 problems** at 1920, 1280, 768 and 390.
The walk script (all workflows, four widths) logged **no console error and no page error**, and **no horizontal overflow** on any step.

`scripts/screenshots.py --audit` printed **0 OVERFLOW** and **0 failed** for every owned page. CLIPPED lines (owned pages only; `span.visually-hidden` is the clip pattern for hidden labels and is not a defect):

```
CLIPPED shops-detail-lantern (span.visually-hidden, div.wm-table-scroll)
CLIPPED shops-detail-caravan (span.visually-hidden, div.wm-table-scroll)
CLIPPED shops-buy (span.visually-hidden)
CLIPPED shops-buy-modal (span.visually-hidden, div.wm-table-scroll)
CLIPPED shops-stall-borin (span.visually-hidden)
CLIPPED shops-stall-own (span.visually-hidden)
CLIPPED shops-stall-buy (span.visually-hidden)
CLIPPED shops-stall-buy-modal (span.visually-hidden)
CLIPPED shops-sell-junk (span.visually-hidden)
CLIPPED shops-sell-junk-modal (span.visually-hidden, div.wm-table-scroll)
CLIPPED shops-sell-modal (span.visually-hidden, div.wm-table-scroll)
CLIPPED characters-junk (span.visually-hidden)
CLIPPED characters-junk-modal (div.wm-table-scroll, span.visually-hidden)
CLIPPED items-where-to-buy-modal (span.visually-hidden)
CLIPPED trades-propose (label.visually-hidden)
CLIPPED trades-detail-alice (span.visually-hidden)
CLIPPED trades-detail-bob (span.visually-hidden)
CLIPPED trades-detail-requested (span.visually-hidden)
CLIPPED trades-edit-side (input.form-control, label.visually-hidden)
```

The same pages at 768 px print the same CLIPPED lines with an `@768` suffix. The `div.wm-table-scroll` lines at 1280 are the sell table (PS-01) and the buy and sell modals' page behind the modal. `trades-edit-side (input.form-control)` is PS-20.
