## Plan Complete: Restrict OAuth Dynamic Client Registration

### What was done
- Analyzed the existing OAuth DCR implementation in `agent_access/oauth/views.py`
- Reviewed the `AllowAllDCRPermission` from django-oauth-toolkit
- Examined the `IsAuthenticatedDCRPermission` for reference
- Identified the Membership model with `is_club_admin` and `is_game_master` fields
- Created implementation plan in `IMPLEMENTATION_PLAN.md`
- Set acceptance criteria for code and verify stages

### Key decisions
1. **New permission class location**: `agent_access/oauth/permissions.py` (new file)
2. **Permission logic**: Check if authenticated user has `Membership` with `is_club_admin=True` OR `is_game_master=True`
3. **CSRF handling**: Follow the pattern from `IsAuthenticatedDCRPermission` - Bearer tokens bypass CSRF, session cookies need CSRF validation
4. **Superuser handling**: Superusers should have access (they can be club admin/GM in any club via the existing `game_master_clubs` function logic)

### Files to create/modify
1. **Create**: `agent_access/oauth/permissions.py` - Custom `ClubAdminOrGameMasterDCRPermission` class
2. **Modify**: `config/settings.py` - Update `DCR_REGISTRATION_PERMISSION_CLASSES` to use new permission class

### Next steps for code stage
1. Create the permissions.py file with the custom permission class
2. Update settings.py to use the new permission class
3. Run existing tests to ensure no regressions
4. Verify the implementation works correctly

### Notes
- The `PublicClientRegistrationView` in views.py already restricts to public clients (token_endpoint_auth_method=none) - this should continue to work for authorized users
- The existing `game_master_clubs` function in forms.py shows the pattern for checking GM status
- Superusers are handled by the Membership query (they would need explicit membership, but typically superusers have admin access)