## Why

Membership, coworking and leases run on paper forms, hand-written mandate references and manual bank uploads. No system knows who holds which agreement, what it owes, or whether a debit succeeded. From 2027 the free-bookings quota makes membership relevant for booking, so re-sharing must know who is a member and keep the OrganizationGroups in sync.

## What Changes

- A new `agreements` app. An agreement kind is configuration: the OrganizationGroup it grants, billing interval (yearly, monthly), deposit, notice period, entrances, pre-notification mode, and whether applications are open. Initial kinds: membership (includes lending), coworking, office lease and cellar lease; the last two stay hidden.
- A confirmed organization applies for a kind from its organization page. Registration and the manager's confirmation stay as they are. Amount, start date, signed contract and kind-specific details are stored per agreement.
- The board decides outside the system; a manager records the decision and its date. Approval adds the kind's group and creates a permanent code with the kind's entrances. Ending removes the group and ends the code.
- Payment is SEPA direct debit only. Every agreement carries one mandate: bank details, signed PDF, generated reference, revocation.
- Collections are created per billing period with the amount frozen from the agreement. Deposits are one-off debits under the same mandate.
- A manager builds a SEPA XML run and marks it uploaded. A collection counts as collected when no return appears within the return window. A nightly job scans BuchhaltungsButler bank transactions for returns, identified by mandate and collection reference.
- A manager can invoice a returned collection in BuchhaltungsButler for the amount plus the return fee; its payment status is synced until paid.
- The BuchhaltungsButler client inlined in the bookings tasks moves to a shared module.
- ADRs for the agreements app and the shared accounting client.

### Non-goals

- Room usage. Registration keeps its signed document and its confirmation; the room terms become click-accepted terms in the separate change `organization-terms`.
- Individuals joining as supporting members. Only organizations apply.
- Bank transfer as a regular payment method, or executing debits automatically.
- Pre-filled contract PDFs. The signed document is uploaded.
- Physical key management, deposit refunds through SEPA, dunning beyond the return invoice.

## Capabilities

### New Capabilities
- `organization-agreements`: agreement kinds, application per kind, recording the board decision, lifecycle and its effect on groups and permanent codes.
- `sepa-mandates`: capturing, referencing, storing and revoking one mandate per agreement.
- `agreement-collections`: fee and deposit collections, pre-notification, SEPA XML runs, return detection through BuchhaltungsButler, return invoices.

### Modified Capabilities

None. Organization registration, confirmation and status are unchanged.

## Impact

- New app `agreements` with models, services, forms, views, admin, mails, three commands and tests.
- `organizations`: links to agreements on the organization page and the manager list. No form or model change.
- `bookings/tasks.py`: uses the shared BuchhaltungsButler client.
- `resources/services_permanent_code.py`: accesses passed in instead of hardcoded IDs.
- New dependency for SEPA XML. New settings: creditor data, mandate prefix, pre-notification days, return window, return fee.
- Sensitive data: IBAN and signed documents in private storage, IBAN excluded from audit log diffs.
