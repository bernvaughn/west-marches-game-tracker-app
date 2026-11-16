# Implementation Plan: Restrict OAuth Dynamic Client Registration

## Overview
Replace `AllowAllDCRPermission` with a custom permission class that only allows authenticated club admins and game masters to register OAuth clients.

## Files to Modify

### 1. Create `agent_access/oauth/permissions.py` (new file)
Create a custom DCR permission class that:
- Checks if the user is authenticated
- Checks if the user is a club admin or game master in at least one club
- Returns `True` only for authorized users, `False` otherwise (which results in 403/401)

### 2. Update `config/settings.py`
- Change `OAUTH2_PROVIDER["DCR_REGISTRATION_PERMISSION_CLASSES"]` from `("oauth2_provider.dcr.AllowAllDCRPermission",)` to the new custom permission class

## Implementation Details

### Custom Permission Class: `ClubAdminOrGameMasterDCRPermission`

```python
# agent_access/oauth/permissions.py
from accounts.models import Membership
from oauth2_provider.dcr import enforce_csrf
from oauth2_provider.utils import parse_bearer_token


class ClubAdminOrGameMasterDCRPermission:
    """
    Allow OAuth client registration only to authenticated users who are
    club admins or game masters in at least one club.
    """

    def has_permission(self, request) -> bool:
        # Must be authenticated
        if not (request.user and request.user.is_authenticated):
            return False

        # Bearer token requests bypass CSRF (browsers never send cross-site)
        if parse_bearer_token(request.META.get("HTTP_AUTHORIZATION", "")) is not None:
            # Check if user is club admin or GM
            return Membership.objects.filter(
                user=request.user,
                is_club_admin=True
            ).exists() or Membership.objects.filter(
                user=request.user,
                is_game_master=True
            ).exists()

        # Session-authenticated requests need CSRF protection
        if not enforce_csrf(request):
            return False

        # Check if user is club admin or GM
        return Membership.objects.filter(
            user=request.user,
            is_club_admin=True
        ).exists() or Membership.objects.filter(
            user=request.user,
            is_game_master=True
        ).exists()
```

### Settings Change
In `config/settings.py`, update:
```python
"DCR_REGISTRATION_PERMISSION_CLASSES": ("agent_access.oauth.permissions.ClubAdminOrGameMasterDCRPermission",),
```

## Acceptance Criteria Mapping

| Criterion | Implementation |
|-----------|----------------|
| Custom DCR permission class created | `agent_access/oauth/permissions.py` |
| Only club admins/game masters can register clients | Permission checks `Membership.is_club_admin` and `Membership.is_game_master` |
| Unauthenticated registration returns 403 | Returns `False` for unauthenticated users (results in 401/403) |
| Existing public client registration still works for authorized users | Authorized users (club admin/GM) can still register via `PublicClientRegistrationView` |

## Testing Strategy
1. Run existing tests to ensure no regressions
2. Verify the new permission class works correctly by testing:
   - Unauthenticated request → 401/403
   - Authenticated non-admin/non-GM user → 403
   - Authenticated club admin → 201 (success)
   - Authenticated game master → 201 (success)
   - Superuser (should have access to all clubs) → 201 (success)