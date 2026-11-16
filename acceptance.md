## code
- [ ] Login: 5 attempts per minute per IP
- [ ] Password change: 3 attempts per hour per user
- [ ] Password reset: 3 attempts per hour per user
- [ ] OAuth token endpoint: 10 requests per minute per IP
- [ ] MCP endpoints: 60 requests per minute per connection
- [ ] Rate limits configurable via settings

## review
- [ ] Code follows project conventions and style
- [ ] Rate limit logic is correct and handles edge cases
- [ ] Configuration via environment variables works correctly
- [ ] No performance regression on non-rate-limited endpoints

## verify
- [ ] Login rate limit enforced (5/min per IP) - test with multiple rapid requests
- [ ] Password change rate limit enforced (3/hour per user) - test with multiple rapid requests
- [ ] Password reset rate limit enforced (3/hour per user) - test with multiple rapid requests
- [ ] OAuth token endpoint rate limit enforced (10/min per IP) - test with multiple rapid requests
- [ ] MCP endpoint rate limit enforced (60/min per connection) - test with multiple rapid requests
- [ ] Rate limit headers present in responses (Retry-After, X-RateLimit-Limit, X-RateLimit-Remaining)
- [ ] Rate limits configurable via environment variables
- [ ] Cache backend works correctly (Redis in production, LocMem in dev)