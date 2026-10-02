## Why

Memberships, coworking places, office and cellar leases run on paper forms, hand-written mandate references and manual bank uploads. No system knows who holds which agreement, what it owes, or whether the money arrived. From 2027 the free-bookings quota makes membership relevant for booking, so re-sharing must know who is a member and keep that in sync with the OrganizationGroups that drive permissions and pricing.

## What Changes

- A new `agreements` app. An agreement kind (member, coworker, office tenant, cellar tenant) is configuration: the OrganizationGroup it grants, billing interval, allowed payment methods, deposit yes/no, notice period, entrances to grant, and whether every collection is pre-notified.
- A confirmed organization applies for an agreement through a kind-specific form, separate from organization registration. Amount, start date and kind-specific details are stored per agreement.
- The board decides outside the system; a manager records the decision and its date. Approval adds the organization to the kind's group and creates a permanent access code with the kind's entrances. Ending an agreement removes the group and ends the code.
- Direct-debit agreements carry one SEPA mandate each: bank details, signed PDF in private storage, generated reference, revocation. Bank-transfer agreements carry none.
- Collections are created per billing period with the amount snapshotted from the agreement. Deposits are one-off collections without an invoice.
- Each fee collection silently creates an outbound invoice in BuchhaltungsButler. Direct-debit collections are pre-notified by email where the kind requires it and exported as SEPA XML for manual bank upload. Transfer collections get a payment request email naming the invoice number as purpose.
- A scheduled job reads invoice payment status from BuchhaltungsButler and marks collections paid, overdue or returned. Managers see collections and their status per organization.
- The BuchhaltungsButler client inlined in the bookings tasks moves to a shared module.
- ADRs for the agreements app and the shared accounting client.

### Non-goals

- Individuals joining as supporting members. Only organizations apply.
- Executing direct debits automatically; the bank upload stays manual.
- Generating pre-filled contract PDFs. The signed document is uploaded.
- Physical key management beyond the signed handover protocol.
- Dunning beyond one reminder email for overdue transfers.
- Changes to organization registration or lifecycle.

## Capabilities

### New Capabilities
- `organization-agreements`: agreement kinds, application per kind, recording the board decision, lifecycle and its effect on groups and permanent codes.
- `sepa-mandates`: capturing, referencing, storing and revoking one mandate per agreement.
- `agreement-collections`: fee and deposit collections, notification emails, SEPA XML runs, invoice creation and payment status sync with BuchhaltungsButler.

### Modified Capabilities

None. `organization-lifecycle` and `organization-permanent-codes` keep their requirements.

## Impact

- New app `agreements` with models, services, forms, views, admin, mails, two management commands and tests.
- `organizations`: links from the organization page and the manager list to agreements.
- `bookings/tasks.py`: uses the shared BuchhaltungsButler client.
- `resources/services_permanent_code.py`: accesses passed in instead of hardcoded IDs.
- New dependency for SEPA XML. New settings: creditor identifier, pre-notification lead days.
- Sensitive data: IBAN and signed mandates in private storage, excluded from audit log diffs.
