## Plan Complete — Ready for Implementation

### Summary
Created implementation plan for adding personal access token expiration and audit logging to the agent_access app.

### Key Decisions
1. **Expiration setting**: `AGENT_TOKEN_EXPIRY_DAYS` (default 365) in `config/settings.py`
2. **Model changes**: 
   - Add `expires_at` DateTimeField to `AgentConnection` (nullable for backward compatibility)
   - New `TokenAuditLog` model with actions: created, used, revoked, expired
3. **Backward compatibility**: Existing tokens without `expires_at` never expire (null = no expiry)
4. **Audit logging points**:
   - Create: in `connection_list` view after `create_token()`
   - Use: in `authenticate_bearer()` on successful auth
   - Revoke: in `connection_revoke` view
   - Expire: in `authenticate_bearer()` when expired token presented
5. **Admin**: Register `TokenAuditLogAdmin` with filtering by action, club, date

### Files to Modify (in order)
1. `config/settings.py` — Add `AGENT_TOKEN_EXPIRY_DAYS`
2. `agent_access/models.py` — Add `expires_at` field + `TokenAuditLog` model
3. `agent_access/tokens.py` — Set `expires_at` on token creation
4. `agent_access/auth.py` — Filter expired tokens + log usage/expiry
5. `agent_access/views/connections.py` — Log create/revoke
6. `agent_access/admin.py` — Register `TokenAuditLogAdmin`
7. `agent_access/templates/agent_access/connections/list.html` — Show expiration column

### Next Steps for Code Stage
1. Implement settings change
2. Create models and generate migration
3. Update token creation, auth, and views
4. Update template and admin
5. Run tests and verify all acceptance criteria pass

### Acceptance Criteria
All 10 items defined and assigned to `code` (4) and `verify` (6) stages.