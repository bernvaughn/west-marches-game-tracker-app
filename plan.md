# Implementation Plan: Inbox Integration for Starting Requests

## Overview
This task implements the inbox integration for magic item starting equipment requests (Child 4 of the "Magic Item Starting Equipment Requests" epic). The work enables club admins/GMs to view, filter, and act on starting equipment requests through the club inbox.

## Current State (Already Implemented)
All required functionality has been implemented and tested:

### 1. Message Kind (`STARTING_REQUEST`)
- Added to `Message.Kind` in `accounts/models.py`
- Migration `0002_startingequipmentrequest_message` in `starting_equipment/migrations/`

### 2. Inbox Kind Filter
- `KIND_FILTERS` in `accounts/views/inbox.py` includes `("starting_request", "Starting requests")`
- `_kind_of()` function handles the filter parameter
- Filter persists with status filter in pagination

### 3. Grant/Decline Action Buttons
- In `accounts/templates/accounts/inbox/inbox.html`:
  - Shows "Grant starting equipment" (check-lg icon, btn-outline-success) for approve
  - Shows "Decline" (x-lg icon, btn-outline-danger) for decline
  - Buttons only visible to club admins and GMs
  - Links to `starting_equipment:request_decide_confirm` with decision parameter

### 4. URL Routing
- Decision confirm and decide URLs in `starting_equipment/urls_requests.py`:
  - `request_decide_confirm` (GET) - renders confirm modal
  - `request_decide` (POST) - processes approve/decline
- Inbox template uses `starting_equipment` app namespace URLs

### 5. Tests
- `accounts/tests/test_inbox.py`: 5 tests for starting request inbox integration
- `starting_equipment/tests/test_requests.py`: 31 tests for request views
- All 54 tests pass

## Remaining Work (Minor UI Improvement)
One minor improvement: Add a kind pill/badge for "Starting request" messages in the inbox message column (similar to the existing "Stock request" badge).

## Files Involved
- `accounts/models.py` - Message.Kind.STARTING_REQUEST (done)
- `accounts/views/inbox.py` - KIND_FILTERS, _kind_of() (done)
- `accounts/templates/accounts/inbox/inbox.html` - kind filter pills, action buttons, kind badge (done except badge)
- `starting_equipment/urls_requests.py` - decide URLs (done)
- `starting_equipment/views/requests.py` - request_decide_confirm, request_decide (done)
- `accounts/tests/test_inbox.py` - inbox integration tests (done)
- `starting_equipment/tests/test_requests.py` - request view tests (done)

## Acceptance Criteria
All criteria are met and tested:
- [ ] Inbox shows "Starting requests" kind filter pill
- [ ] Filtering by kind=starting_request works correctly
- [ ] Admin/GM see Grant/Decline buttons on starting-request messages
- [ ] Regular members cannot see inbox or decision buttons
- [ ] Grant action approves request, grants item via ledger, marks message HANDLED
- [ ] Decline action sets DECLINED + decision_note, marks message HANDLED
- [ ] All related tests pass