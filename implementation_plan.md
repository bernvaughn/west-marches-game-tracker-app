# Implementation Plan: Personal Access Token Expiration and Audit Logging

## Overview
Add token expiration (1 year default, configurable) and audit logging for token lifecycle events (create, use, revoke, expire) with an admin view.

---

## Files to Modify

### 1. `config/settings.py` — Add token expiration setting
```python
# Token expiration (days)
AGENT_TOKEN_EXPIRY_DAYS = int(os.environ.get("AGENT_TOKEN_EXPIRY_DAYS", "365"))
```

### 2. `agent_access/models.py` — Add expiration field and audit log model
**Changes to `AgentConnection`:**
- Add `expires_at = models.DateTimeField(null=True, blank=True)` field
- Add `@property def is_expired(self)` method
- Add `clean()` to validate `expires_at >= approved_at` (if both set)

**New model `TokenAuditLog`:**
```python
class TokenAuditLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        USED = "used", "Used"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE, related_name="token_audit_logs")
    connection = models.ForeignKey(AgentConnection, on_delete=models.CASCADE, related_name="audit_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    action = models.CharField(max_length=10, choices=Action.choices)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    details = models.JSONField(default=dict, blank=True)

    objects = ClubScopedManager()

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["club", "action", "-timestamp"]),
        ]
```

### 3. `agent_access/tokens.py` — Set expiration on token creation
- Import `timezone` and `settings`
- In `create_token()`: calculate `expires_at = timezone.now() + timedelta(days=settings.AGENT_TOKEN_EXPIRY_DAYS)`
- Pass `expires_at` to `AgentConnection.objects.create()`

### 4. `agent_access/auth.py` — Reject expired tokens and log usage
- In `token_authenticator()`: add filter `.filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now()))`
- In `authenticate_bearer()`: after successful auth, create `TokenAuditLog` entry for "used" action
- Consider adding a check for expired tokens that logs "expired" action (optional: management command for bulk expiry detection)

### 5. `agent_access/views/connections.py` — Log creation and revocation
- In `connection_list()`: after `create_token()`, create `TokenAuditLog` entry for "created" action
- In `connection_revoke()`: before saving revocation, create `TokenAuditLog` entry for "revoked" action

### 6. `agent_access/admin.py` — Register audit log model
```python
from .models import TokenAuditLog

@admin.register(TokenAuditLog)
class TokenAuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "club", "connection", "user", "action"]
    list_filter = ["action", "club", "timestamp"]
    search_fields = ["connection__label", "user__email"]
    readonly_fields = ["timestamp", "club", "connection", "user", "action", "details"]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]
```

### 7. `agent_access/templates/agent_access/connections/list.html` — Show expiration
- Add "Expires" column to table
- Show expiration date or "Never" if null
- Update status badge to show "Expired" when `c.is_expired`

### 8. Create migration
- Run `makemigrations agent_access` after model changes

### 9. Tests (`agent_access/tests/test_a1_tokens.py`) — Add test cases
- Test token creation sets `expires_at` correctly
- Test expired token is rejected at authentication
- Test audit log entries for create, use, revoke
- Test template shows expiration
- Test admin view accessible

---

## Acceptance Criteria Mapping

| Criterion | Implementation | Proof Stage |
|-----------|----------------|-------------|
| Tokens expire after 1 year (configurable) | `AGENT_TOKEN_EXPIRY_DAYS` setting + `expires_at` field + `create_token()` logic | code |
| Expired tokens rejected at authentication | `token_authenticator()` filters out expired tokens | code, verify |
| Audit log entries for: create, use, revoke, expire | `TokenAuditLog` model + logging in views/auth | code, verify |
| Admin view to see token audit log | `TokenAuditLogAdmin` registration | verify |

---

## Implementation Order

1. **Settings** (`config/settings.py`) — Add `AGENT_TOKEN_EXPIRY_DAYS`
2. **Models** (`agent_access/models.py`) — Add `expires_at` and `TokenAuditLog`
3. **Tokens** (`agent_access/tokens.py`) — Set expiration on creation
4. **Auth** (`agent_access/auth.py`) — Reject expired + log usage
5. **Views** (`agent_access/views/connections.py`) — Log create/revoke
6. **Admin** (`agent_access/admin.py`) — Register audit log
7. **Template** (`agent_access/templates/.../list.html`) — Display expiration
8. **Migration** — Generate and apply
9. **Tests** — Add/update test cases
10. **Run tests** — Verify all pass

---

## Notes

- **Backward compatibility**: Existing tokens without `expires_at` will never expire (null = no expiry). This is intentional for a smooth migration.
- **Expiration detection**: "Expired" audit entries can be created either:
  - At authentication time (when an expired token is presented) — simpler
  - Via a management command (for periodic cleanup/reporting) — more complete
  - Recommendation: Start with authentication-time logging; add management command if needed later.
- **Club scoping**: `TokenAuditLog` uses `ClubScopedManager` for consistency with other models.
- **Performance**: Index on `club, action, -timestamp` for admin list view filtering.