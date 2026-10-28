## Why

Staff and managers can see full IBANs and signed SEPA mandates of all organizations in their scope. Their accounts are protected by a password only: two-factor authentication is available but optional. A leaked password exposes bank data of many organizations.

## What Changes

- Users with `is_staff` and users with a manager profile must set up two-factor authentication (authenticator app or passkey). Until they have, every page redirects them to the two-factor setup, except account pages, logout and static files.
- Nobody else is affected.
- The setting `REQUIRE_STAFF_MFA` (default on) switches enforcement off, for example in tests or local development.
- While staff impersonate a user, the impersonated session is not blocked.

### Non-goals

- Requiring two-factor authentication for organizations or individual users.
- Remembering devices beyond what allauth offers.

## Capabilities

### New Capabilities
- `staff-mfa`: two-factor authentication required for staff and managers.

### Modified Capabilities
