## Why

A collection keeps the mandate that was active when it was created. When a member has no mandate yet, or replaces a revoked one, their waiting collections never enter a run, contrary to the revocation requirement, and their pre-notification names no mandate reference.

Existing memberships and their paper mandates have to be entered one by one in the admin. With dozens of members, a spreadsheet import is faster and less error-prone.

## What Changes

- Planned and notified collections use the agreement's mandate that is active when they are notified and when a run is built. A collection's mandate is fixed only once it is submitted in a run. Collections whose agreement has no active mandate are listed as needing attention.
- The admin offers spreadsheet import and export for agreements: organization by id, kind by slug, status, amounts, dates, function, details and notes, without files. The export adds the organization's name for orientation.
- The admin offers spreadsheet import for mandates: agreement by id, reference, account holder, IBAN, BIC, bank, signature and revocation date, without files. No export, so full IBANs do not end up in files.
- Imports are validated like the admin form, including the unique constraints; the admin imports only after a preview without errors. Imports trigger nothing: no emails, groups, codes or collections for past periods.
- In German, "Agreement" in the agreements app reads "Vereinbarung" instead of the room usage agreement's "Nutzungsvereinbarung".

### Non-goals

- Importing signed PDFs.
- Matching organizations by name.

## Capabilities

### New Capabilities

### Modified Capabilities
- `agreement-collections`: "SEPA collection runs" and "Pre-notification" use the active mandate at that time.
- `sepa-mandates`: adds "Mandate import".
- `organization-agreements`: "Existing agreements entered in the admin" adds the spreadsheet import.
