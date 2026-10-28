## Context

allauth 65 provides the two-factor setup and login steps (`/accounts/2fa/`) but no way to require them.

## Decisions

- **Middleware.** `RequireStaffMFAMiddleware` runs after authentication and hijack. For an authenticated user who must use two-factor authentication and has no authenticator, it redirects to `mfa_index` with a message; htmx requests get an `HX-Redirect` header instead.
- **Who.** `is_staff`, `is_superuser` or a `Manager` row. Checked on every request, so granting or removing the role takes effect immediately.
- **Exempt paths.** `/accounts/` (setup, reauthentication, logout, email confirmation), static and media files and hijack release. The admin is not exempt.
- **Setting.** `REQUIRE_STAFF_MFA` defaults to on; the test settings switch it off so existing tests that log in as managers keep working, and the middleware tests switch it on.

## Risks / Trade-offs

- A manager who loses their device is locked out. → Recovery codes; staff can delete the authenticator in the admin so the manager sets it up again.
