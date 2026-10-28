# 0024. Agreements App and Manual SEPA Export

Date: 2026-10-28

## Status

Accepted

## Context

Memberships, coworking and leases ran on paper forms, hand-written mandate references and manual bank uploads. Nothing recorded who holds which agreement, what it costs or whether a debit succeeded. With the free bookings quota (ADR 23), membership matters for booking, so the organization groups have to follow the agreements. All agreements are paid by SEPA direct debit. The accounting system can create invoices and list bank transactions, but it cannot hold mandates, run debits or notify us.

## Decision

### A separate app with one outward relation

`re_sharing/agreements/` holds `AgreementKind`, `Agreement`, `SepaMandate`, `Collection` and `CollectionRun`. The only foreign key to another app's data is `Agreement.organization`. Kinds point at an `OrganizationGroup` and at `Access` objects as configuration, like `Compensation` does.

### Kinds are configuration, agreements are one model

A kind defines the group it grants, yearly or monthly billing, deposit, notice period, end date requirement, the accesses of a permanent code, the pre-notification mode, the collection day (and month for yearly kinds), an intro text that links the contract, and whether applications are open. `form_type` picks the application form, whose kind-specific fields are stored in `Agreement.details`. A new kind with the same fields is configuration, a new set of fields is a form, never a migration.

### Lifecycle

`submitted → active → ended`, or `submitted → rejected`. Only confirmed admins of confirmed organizations apply. The board decides outside the system; a manager in scope records approval or rejection with the decision date. Approval requires an uploaded signed contract and an active mandate, adds the kind's group, creates a permanent code with the kind's accesses when it has any, creates the deposit and the first-period collection, and sends the decision email. Ending removes the group unless another active agreement grants it, sets the code's validity end, cancels later collections and records a deposit refund. Agreement actions never change the organization's status. Existing agreements are entered in the admin, which runs none of these side effects.

### One mandate per agreement

A mandate holds bank details, a generated reference (`<prefix>-<running number>`, e.g. `HDE-VM-009`, continuing after the highest existing number so that paper mandates entered in the admin keep their place), the signed PDF and a revocation date. It may be saved before the signed PDF exists and only counts as active with the PDF and without revocation. The IBAN is validated, masked outside the manager's mandate page, excluded from the audit log and never put into an email context.

### Collections per period, prorated from the start date

Monthly kinds bill calendar months, yearly kinds calendar years on one fixed date per kind. A daily command creates full-period collections within a lookahead, with the amount frozen. A start within a period is prorated from the agreement's start date, never the signing or decision date: twelfths per full month after the start month for yearly kinds, days for monthly kinds. That collection is created at approval without its own pre-notification, because the approval email states amount and due date, and its due date lies at least the pre-notification period after the decision.

### Manual export, collected by absence of return

A manager builds a pain.008.001.08 CORE file with batch booking off and the collection reference as end-to-end id, uploads it to the bank by hand and marks the run uploaded. A collection counts as collected once the return window has passed without a return. A nightly command scans the accounting system's bank transactions for returns, matched by collection reference, or by mandate reference plus amount. Unmatched negative transactions that look like returns are listed for managers. A returned debit can be invoiced in the accounting system for amount plus return fee; the invoice's payment status is synced.

Alternatives: matching positive credits per debit (rejected, a bank may book a batch as one credit); executing debits through an API (rejected, no such access and no need for it).

## Consequences

- The bank upload stays manual; a run not marked uploaded never turns collected and is listed for attention.
- The wording of return transactions has to be confirmed with the first real return; matching and the keyword list in `services_collections` may need adjusting.
- Agreement emails use `EmailTemplate` rows like all other emails and send nothing until those templates exist and are active.
- Signing documents online is a separate change; uploads stay possible.
