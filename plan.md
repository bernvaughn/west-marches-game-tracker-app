# Implementation Plan: Bulk Map Credit Approval (M1)

## Overview
Add bulk approval functionality to the Map Requests page (M12). GMs can select multiple pending requests via checkboxes, click "Approve selected", and approve all in one modal with tabs for Discovery/Exploration/Found mark kinds.

## Files to Modify

### 1. `map/views/requests.py`
- Add new view `bulk_approve` (GET: renders modal with tabs, POST: processes approvals)
- Reuse `_decide` logic but handle multiple requests grouped by kind
- Need to handle: DISCOVERED, EXPLORED, FOUND kinds (VISIT may be excluded per spec)
- Each tab shows characters from selected requests of that kind

### 2. `map/urls_requests.py`
- Add URL patterns:
  - `requests/bulk-approve/` (GET/POST) → `bulk_approve`

### 3. `map/templates/map/requests/queue.html`
- Add checkbox column to table (only for `is_editor` / GM view)
- Add "Approve selected" button in bulk actions bar (hidden until checkboxes checked)
- Use existing `check_all.js` for select-all/clear
- Button opens modal via `data-app-modal` + `hx-get`

### 4. `map/templates/map/requests/bulk_approve_modal.html` (NEW)
- Extends `components/_confirm_modal.html`
- Tabs for: Discovery, Exploration, Found
- Each tab: table of requests (location, characters) with checkboxes per character? Or just list?
- Per spec: "each listing picked characters" — show which characters from which requests
- Single confirm button submits all approvals

### 5. `map/forms_requests.py` (maybe)
- May need a form for bulk approve confirmation

## Data Flow

1. GM checks boxes on queue page → "Approve selected" button enables
2. Click button → HTMX GET to `bulk_approve` with selected request IDs
3. View groups requests by kind (discovered/explored/found)
4. Modal renders with tabs, each tab showing: request location, characters
5. GM clicks "Approve all" → POST to `bulk_approve` with selected request IDs
6. View processes each request: calls appropriate service (add_to_credit / add_found_marks / record_visits)
7. Updates MapRequest status to APPROVED, sets decided_by/decided_at
8. Returns HX-Trigger to close modal and refresh queue

## Key Considerations

- **Permission**: Only GMs/admins (use `@admin_or_gm_required`)
- **Validation**: Only approve requests with `status=REQUESTED` and `can_approve=True`
- **Atomicity**: Use `transaction.atomic` for all approvals
- **Feedback**: Show success message with count, or partial failure details
- **HTMX**: Modal uses `data-app-modal` pattern; on success trigger queue refresh

## Acceptance Criteria Mapping

| AC | Proof Stage |
|----|-------------|
| Checkboxes appear per request on map requests page (GM view) | verify |
| "Approve selected" button appears when checkboxes checked | verify |
| Modal opens with tabs for Discovery/Exploration/Found | verify |
| Each tab lists picked characters from selected requests | verify |
| Single confirm approves all selected requests | verify |
| Requests marked approved, credits/marks created | verify |

## Dependencies

- Depends on "Shared: Top-bar & Modal Utilities" (already done)
- Uses existing: `modal_frame.html`, `_confirm_modal.html`, `check_all.js`, `modal.js`
- Uses existing services: `add_to_credit`, `add_found_marks`, `record_visits`

## Implementation Order

1. Add `bulk_approve` view and URL
2. Update queue template with checkboxes and bulk button
3. Create bulk approve modal template with tabs
4. Test end-to-end