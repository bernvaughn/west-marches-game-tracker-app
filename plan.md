# Implementation Plan: Add or change my email (E9)

## Files to Create

### 1. `mail/views/change_email.py`
Two views:
- **Club view** `change_email` (requires sign-in, club member): Shows form to enter new email. On POST: validates new email is not the same as current, not already used by another account (case-insensitive). Issues a 24-hour `email_change` token via `mail.tokens.issue()`, queues confirmation email to the new address with the link. Shows success message that link was sent. Old address stays active until link is used.
- **Public view** `ConfirmEmailView` (GET/POST at `/mail/email/confirm/<token>/`): GET shows confirm page with new email address. POST consumes token, changes user's email (which is also their sign-in name), sends "email changed" notice to old address, logs out other sessions. Handles: token invalid/expired, address already in use by another account (neutral answer like E4), wrong signed-in user.

### 2. `mail/urls_change_email.py`
- `club_urlpatterns`: `path("change-email/", change_email, name="change_email")`
- `public_urlpatterns`: `path("email/confirm/<str:token>/", ConfirmEmailView.as_view(), name="confirm_email")`

### 3. `mail/hooks_change_email.py`
- `register()`: Registers nav entry in "account" group with label "My email address", URL name `mail:change_email`, check `is_member`, order 10.

### 4. `mail/builders_email_change.py`
- `build_confirm_email(context)`: Renders text and HTML for the confirmation email sent to the new address. Context: user, club, new_email, confirm_url, site_url. Uses base templates.

### 5. Templates
- `mail/templates/mail/change_email.html`: Club page with form for new email, shows current email, note that changing email changes sign-in name.
- `mail/templates/mail/confirm_email.txt` / `confirm_email.html`: Email templates for the confirmation link.
- `mail/templates/mail/email_changed.txt` / `email_changed.html`: Email templates for the "email changed" notice sent to the old address after confirmation.

### 6. `mail/tests/test_change_email.py`
Tests covering:
- Old address works until confirmed
- Old address gets notice after change
- Neutral answer for address in use (no email sent)
- Token single use and expiry (24 hours)
- Whitelist entries unchanged (test that Whitelist email is not modified)
- Case-insensitive duplicates caught

## Key Implementation Details

### Token Extra Data
When issuing the token, include in `extra`:
- `new_email`: the new email address
- `old_email`: the current email address (for the notice)

### Email Change Flow
1. User visits `/c/<club_slug>/mail/change-email/`, enters new email
2. View validates: not same as current, not in use by another User (case-insensitive), not in DoNotEmail
3. Issue `email_change` token (24h TTL) with extra={new_email, old_email}
4. Build confirm URL: `/mail/email/confirm/<token>/`
5. Queue email to new address using `queue_email(kind="email_change", ...)`
6. Show success message

### Confirmation Flow
1. GET `/mail/email/confirm/<token>/`: peek token, show confirm page with new email
2. POST: consume token, validate not expired/used
3. Check if new_email is already used by another User (case-insensitive) → neutral answer, no email
4. Change user.email = new_email, save
5. Sign out other sessions (like password reset)
6. Send "email changed" notice to old_email via `queue_email(kind="email_change", ...)`
7. Show success page

### Neutral Answer for Address in Use
Same behavior as E4 (forgot password): if the new email belongs to another account, show the same generic success message but send nothing. This prevents email enumeration.

### Whitelist Entries Unchanged
The whitelist in `accounts/views/people.py` stores email addresses separately. Changing the user's email should not modify any WhitelistEntry records.

### Sign-in Name Change
Since `User.email` is the sign-in name, changing it changes how the user signs in. The page must say so.

## Acceptance Criteria Mapping

| Criterion | Proof Stage |
|-----------|-------------|
| Changing the address sends a link to the new address; the old address stays active until it is used | review (tests) |
| Old address gets a notice after the change | review (tests) |
| An address used by another account gets the neutral answer and no email | review (tests) |
| Whitelist entries are unchanged | review (tests) |
| Tests pass; ruff clean; screenshots at 1280 and 390 | verify |

## Proof Stages
All acceptance items are deferred to `review` stage. The `code` stage implements the feature, `review` stage runs tests and verifies behavior.