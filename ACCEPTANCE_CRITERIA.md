## code
- [ ] Custom DCR permission class created in `agent_access/oauth/permissions.py`
- [ ] Only club admins/game masters can register clients
- [ ] Unauthenticated registration returns 403
- [ ] Existing public client registration still works for authorized users

## verify
- [ ] All existing tests pass
- [ ] New permission correctly rejects unauthenticated requests
- [ ] New permission correctly rejects authenticated non-admin/non-GM users
- [ ] New permission allows club admins to register clients
- [ ] New permission allows game masters to register clients
- [ ] New permission allows superusers to register clients