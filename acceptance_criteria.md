## code
- [ ] Message.Kind.STARTING_REQUEST added to accounts/models.py
- [ ] KIND_FILTERS in accounts/views/inbox.py includes starting_request
- [ ] Inbox template shows kind filter pills (All, Messages, Stock requests, Starting requests)
- [ ] Inbox template shows Grant/Decline buttons on starting-request messages for admin/GM
- [ ] Starting request buttons hidden from regular members
- [ ] URL route for decide confirm (starting_equipment:request_decide_confirm)
- [ ] URL route for decide action (starting_equipment:request_decide)

## review
- [ ] Code follows project conventions (HTMX patterns, permissions, club scoping)
- [ ] No duplicate code or unnecessary complexity
- [ ] Templates use consistent styling (badges, buttons, icons)

## verify
- [ ] test_starting_request_kind_filter passes (kind filter works)
- [ ] test_starting_request_shows_grant_decline_buttons passes (buttons visible to admin/GM)
- [ ] test_starting_request_buttons_hidden_from_regular_member passes (403 for regular members)
- [ ] test_starting_request_grant_approves_and_marks_message_handled passes (approve flow)
- [ ] test_starting_request_decline_sets_declined_and_marks_message_handled passes (decline flow)
- [ ] All 31 starting_equipment request tests pass
- [ ] All 23 accounts inbox tests pass