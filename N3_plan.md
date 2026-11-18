# Implementation Plan: N3 Character Sheet: Quick "Sell Junk" Button

## Goal
Add a "Sell junk" button in the character sheet's inventory card. Clicking it opens a modal to pick a shop (if multiple open), then the selected shop's sell-junk modal pre-filled with the character's junk.

## User Flow
1. Player views character sheet → Inventory card shows "Sell junk" button (only if character has junk marked)
2. Click "Sell junk" → HTMX GET to shop picker view → shop picker modal opens listing all open shops
3. If only one shop is open → skip picker, go directly to that shop's sell-junk modal
4. If multiple shops → player picks one → that shop's sell-junk modal opens, pre-filled with character's junk
5. If no shops open → show "no shops available" message

## Files to Create/Modify

### 1. `shops/views/sell_junk.py` (modify)
Add `pick_shop` view function:
- `@club_member_required` decorator
- GET only
- Get selected character via `selected_character(request)`; raise Http404 if None
- Get open shops via `open_shops(club, today)`
- If no open shops → render modal with "no shops available" message
- If exactly one open shop → redirect (HX-Redirect or HttpResponseRedirect) to `shops:sell_junk` for that shop
- If multiple open shops → render shop picker modal template
- Context: `club`, `character`, `open_shops`

### 2. `shops/urls.py` (modify)
Add URL pattern:
```python
(path("sell-junk-pick/", sell_junk.pick_shop, name="sell_junk_pick"),)
```

### 3. `shops/templates/shops/sell/_shop_picker_modal.html` (new)
Modal template extending `components/modal_frame.html`:
- Title: "Sell junk — pick a shop"
- Body: list of open shops, each as a button:
  - `hx-get="{% url 'shops:sell_junk' club.slug shop.pk %}"`
  - `hx-target="#app-modal .modal-content"`
  - `data-app-modal`
  - `hx-swap="innerHTML"`
  - Button text: shop name + " (" + shop keeper name + ")" if keeper exists
- If no open shops → empty state: "No shops are open right now."
- Footer: Cancel button

### 4. `player_characters/templates/player_characters/characters/detail.html` (modify)
Add "Sell junk" button in the inventory card:
- Inside the `wm-sheet-shop` div, after the shop toggle form
- Only shown when `{% if junk %}` (character has junk marked)
- Button: `hx-get="{% url 'shops:sell_junk_pick' club.slug %}"`, `hx-target="#app-modal .modal-content"`, `hx-swap="innerHTML"`, `data-app-modal`
- Text: "Sell junk" with bag icon
- Tooltip: "Sell your marked junk items to an open shop"

## Technical Details

### Shop picker view logic
```python
@club_member_required
def pick_shop(request, club_slug):
    character = selected_character(request)
    if character is None:
        raise Http404("No character selected.")
    today = timezone.localdate()
    open_shop_qs = list(open_shops(request.club, today).order_by("street_position", "name"))
    if not open_shop_qs:
        # Render "no shops" modal
        ...
    if len(open_shop_qs) == 1:
        # Redirect to that shop's sell_junk
        shop_url = reverse("shops:sell_junk", args=[club_slug, open_shop_qs[0].pk])
        if is_htmx(request):
            response = HttpResponse(status=204)
            response["HX-Redirect"] = shop_url
            return response
        return redirect(shop_url)
    # Render shop picker modal
    return render_modal_or_page(
        request,
        "shops/sell/_shop_picker_modal.html",
        ...,
        {"character": character, "open_shops": open_shop_qs},
    )
```

### Button on character sheet
Placed in the inventory card's `wm-sheet-shop` section, next to the "Sell my junk in my shop" toggle. Only visible when the character has at least one junk-marked item.

## Acceptance Criteria Mapping
| Criteria | Proof Stage |
|----------|-------------|
| "Sell junk" button appears on character sheet inventory card when character has junk | code (unit test + browser test) |
| Button opens shop picker modal when multiple shops are open | code (browser test) |
| Single open shop goes directly to sell-junk modal | code (unit test) |
| No open shops shows "no shops available" message | code (unit test) |
| Selected shop's sell-junk modal is pre-filled with character's junk | code (browser test) |
| Ruff clean, unit + browser tests pass | verify |

## Test Strategy
- Unit tests for `pick_shop` view (0 shops, 1 shop, multiple shops, no character)
- Browser test: character sheet → click "Sell junk" → shop picker → select shop → sell junk modal
- Ruff check on all new/modified files