## Why

Membership, coworking and leases run on paper forms, hand-written mandate references and manual bank uploads. No system knows who holds which agreement, what it owes, or whether a debit succeeded. From 2027 the free-bookings quota makes membership relevant for booking, so re-sharing must know who is a member and keep the OrganizationGroups in sync.

## What Changes

- A new `agreements` app. An agreement kind is configuration: the OrganizationGroup it grants, billing interval (yearly, monthly), deposit, notice period, the entrances of a permanent code where the kind grants one, pre-notification mode, and whether applications are open. Initial kinds: membership (includes lending), coworking, office lease and cellar lease; the last two stay hidden.
- A confirmed organization applies for a kind from its organization page. Registration and the manager's confirmation stay as they are. Amount, start date, signed contract and kind-specific details are stored per agreement.
- The board decides outside the system; a manager records the decision and its date. Approval adds the kind's group and, only for kinds that grant entrances such as coworking, creates a permanent code with them; membership grants none. Ending removes the group and ends the code where one exists.
- Payment is SEPA direct debit only. Every agreement carries one mandate: bank details, signed PDF, generated reference, revocation. A mandate can be saved with bank data first; its page shows the reference and offers the blank mandate form for download, and the mandate becomes active once the signed PDF is uploaded. The contract is downloaded from the link in the kind's intro text, signed and uploaded.
- Collections are created per billing period with the amount frozen from the agreement. Yearly kinds collect on one fixed date for all agreements of the kind, for membership in March for the current calendar year. The first, partial period is prorated from the agreement's start date, never the signing or decision date: a yearly agreement starting during the year pays one twelfth of the amount for each full month after its start month, a monthly agreement starting during a month pays that month by day. It is collected once after approval without a separate pre-notification; the approval email states amount and date. Deposits are one-off debits under the same mandate.
- A manager builds a SEPA XML run and marks it uploaded. A collection counts as collected when no return appears within the return window. A nightly job scans BuchhaltungsButler bank transactions for returns, identified by mandate and collection reference.
- A manager can invoice a returned collection in BuchhaltungsButler for the amount plus the return fee; its payment status is synced until paid.
- The BuchhaltungsButler client inlined in the bookings tasks moves to a shared module.
- ADRs for the agreements app and the shared accounting client.

### Non-goals

- Room usage. Registration keeps its signed document and its confirmation; the room terms become click-accepted terms in the separate change `organization-terms`.
- Individuals joining as supporting members. Only organizations apply.
- Bank transfer as a regular payment method, or executing debits automatically.
- Generating contract text from data. This change collects the signed contract and mandate as uploads; `document-signing` adds signing them online.
- Physical key management, deposit refunds through SEPA, dunning beyond the return invoice.

## Capabilities

### New Capabilities
- `organization-agreements`: agreement kinds, application per kind, recording the board decision, lifecycle and its effect on groups and, for kinds that grant entrances, permanent codes.
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
