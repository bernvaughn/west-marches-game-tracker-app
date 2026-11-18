## code
- [ ] Add `pick_shop` view to `shops/views/sell_junk.py`
- [ ] Add `sell_junk_pick` URL to `shops/urls.py`
- [ ] Create `shops/templates/shops/sell/_shop_picker_modal.html`
- [ ] Add "Sell junk" button to `player_characters/templates/player_characters/characters/detail.html` inventory card
- [ ] Button only shows when character has junk marked
- [ ] Multiple open shops → shop picker modal
- [ ] Single open shop → direct to that shop's sell-junk modal
- [ ] No open shops → "no shops available" message

## verify
- [ ] "Sell junk" button visible on character sheet when character has junk
- [ ] Button hidden when character has no junk
- [ ] Clicking button with multiple open shops opens shop picker modal
- [ ] Clicking button with single open shop opens that shop's sell-junk modal directly
- [ ] Clicking button with no open shops shows "no shops available"
- [ ] Selected shop's sell-junk modal is pre-filled with character's junk
- [ ] All existing tests pass
- [ ] Ruff clean on all changed files
- [ ] No console errors
