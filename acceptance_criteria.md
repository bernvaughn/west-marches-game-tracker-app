## code
- [ ] Tokens expire after 1 year (configurable via AGENT_TOKEN_EXPIRY_DAYS setting)
- [ ] Expired tokens rejected at authentication (token_authenticator filters by expires_at)
- [ ] Audit log entries for: create (in connection_list view), use (in authenticate_bearer), revoke (in connection_revoke view), expire (on failed auth of expired token)
- [ ] Admin view to see token audit log (TokenAuditLogAdmin registered with list_display, list_filter, search_fields)

## verify
- [ ] Existing tokens without expires_at continue to work (backward compatibility)
- [ ] New tokens have expires_at set to 1 year from creation by default
- [ ] Authentication fails with 401 for expired tokens
- [ ] Audit log shows correct action, user, timestamp, and connection for each event
- [ ] Admin can filter audit log by action, club, date
- [ ] Connection list template shows expiration date and "Expired" status