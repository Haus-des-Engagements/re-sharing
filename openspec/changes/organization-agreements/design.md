## Context

Four paper processes exist today, each ending in a signed contract:

| Kind | Interval | Deposit | Notice | Entrance code | Kind-specific data | Visible |
|---|---|---|---|---|---|---|
| Member | yearly | no | per statutes | no | representative's function, solidarity amount | yes |
| Coworker | monthly | yes | 4 weeks to month end | yes | desks, hours per week | yes |
| Office tenant | monthly | 3 months' rent | 3 months to month end | per kind configuration | room, fixed end date | later |
| Cellar tenant | monthly | no | not stated | per kind configuration | area in m² | later |

Members and coworkers already pay by direct debit with hand-written mandate references; tenants currently transfer. The stakeholder decided that all payments go through SEPA direct debit, and that a failed debit is followed by an invoice carrying the return fee.

Organization registration, the signed document it collects and the manager's confirmation stay as they are: a confirmed organization receives the default group and may book rooms. Agreements start from there. Room and lending terms as click-accepted, versioned documents are the subject of the separate change `organization-terms`; they are accepted at the first booking, not when applying.

BuchhaltungsButler (API v1.9.1) can create invoices, list receipts with a `payment_status`, and list bank transactions with `amount`, `purpose`, `booking_text`, `type` and `payment_reference`. It cannot store mandates, execute debits or push webhooks. Its client is inlined four times in `bookings/tasks.py`.

`OrganizationGroup` already expresses "may book rooms", "is a member" and so on, and drives permissions, pricing and the free-bookings quota. `PermanentCode` grants entrance codes with a hardcoded access set. Managers are scoped by groups (ADR 21). Emails go through `django-tasks` from `mails.py`, periodic work runs as management commands.

Constraints: HackSoft style, coverage above 95 percent, one outward relation per app (ADR 9), private storage (ADR 20), audit log (ADR 13).

## Goals / Non-Goals

**Goals:**

- One place that knows which organization holds which agreement, at what price, and whether each period was collected.
- Group membership follows agreements; entrance codes follow the agreements whose kind grants them.
- Direct debit end to end except the bank upload: mandate, pre-notification, XML file, return detection, return invoice.
- The accounting client shared between bookings and agreements.

**Non-Goals:**

- See the proposal. Additionally: encrypting bank data at rest, and reconstructing past payments.

## Decisions

### D1: A new `agreements` app with one outward relation

Models live in `re_sharing/agreements/`. The only foreign key out of the app points to `Organization`; `AgreementKind` references `OrganizationGroup` and `Access` as configuration, like `Compensation` references groups. Applicant views under `/agreements/`, manager views under `/agreements/manage/` with `manager_required`.

Alternative: extend `organizations`. Rejected, that models file is already the largest and membership is a separate lifecycle.

### D2: Kinds are configuration, agreements are one model

`AgreementKind`: `name`, `slug`, `organization_group`, `billing_interval` (yearly, monthly), `requires_deposit`, `notice_period_weeks`, `requires_end_date`, `accesses` (M2M, empty for kinds without an entrance code such as membership), `notification_mode` (each collection, once at approval), `collection_day`, `collection_month` (yearly kinds only), `intro_text` (shown on the application page, links the contract to download), `is_active`, `accepting_applications`. Every kind is paid: an agreement always has an amount, a mandate and collections. `accepting_applications` hides a kind from applicants while managers can still create agreements of it in the admin.

`Agreement`: `organization`, `kind`, `status`, `amount`, `deposit_amount`, `start_date`, `end_date`, `contact_person_function`, `details` (JSONField for the kind-specific values), `signed_document` (private storage, PDF validated), `signed_on`, `decided_at`, `decided_by`, `permanent_code`, `notes`, `history`. The application form per kind writes its fields into `details`; a fifth kind is a form change, not a migration. `clean()` rejects a deposit on kinds without one and requires an amount above zero.

Alternative: four models with inheritance. Rejected, every workflow would exist four times for a handful of fields.

### D3: Agreement lifecycle

```
 submitted ──approve──▶ active ──end──▶ ended
     │
     └──reject──▶ rejected
```

A confirmed organization's admin may apply. Pending, rejected and deactivated organizations may not. Approval requires `decided_at`, a complete signed document and an active mandate; an uploaded document is complete. A manager enters the board's decision date. `approve_agreement`:

1. adds the kind's group,
2. creates a `PermanentCode` with the kind's accesses when the kind has any, through `create_permanent_code_for_organization`, which gains an `accesses` parameter with the current hardcoded set as default,
3. creates the deposit collection when the kind requires one,
4. creates the first-period fee collection when the start date lies within a period (D5),
5. sends the decision email.

Organization status is never touched by agreement actions. `end_agreement` sets `end_date` if empty, removes the group unless another active agreement grants it, sets `validity_end` on the agreement's code when it has one, cancels planned collections after the end date, creates a manual deposit refund record when a paid deposit exists. A daily command ends agreements whose `end_date` has passed.

Which groups may book which rooms stays group configuration. Room and lending terms are accepted at the first booking (`organization-terms`), not as part of the application.

### D4: One mandate per agreement

`SepaMandate`: `agreement`, `reference` (unique), `account_holder`, `iban`, `bic`, `bank_name`, `signed_on` and `signed_document` (both nullable), `revoked_on`. Partial unique constraint: one non-revoked mandate per agreement. A mandate is active when it has a signed document and is not revoked.

The applicant may save the bank data before the signed PDF exists. The mandate page then shows the generated reference and the bank data, links the blank mandate form (`SEPA_MANDATE_FORM_URL`) to print, fill in, sign and upload, and offers the upload. A hand-signed form without the reference written on it is accepted, because the reference is also stated on the mandate page and in the approval email. Reference `<prefix>-<agreement id, six digits>-<n>`, generated, never typed, except that existing paper references can be entered in the admin when unique. IBAN validated with checksum, stored without spaces, masked on pages except the manager's mandate page, excluded from audit log diffs, never in emails. The signed mandate PDF carries the full IBAN and is downloadable from the mandate page by the organization's admins and managers in scope. Encryption at rest is deferred.

### D5: Collections and their identifiers

`Collection`: `agreement`, `kind` (fee, deposit, deposit refund), `period_start`, `period_end`, `due_date`, `amount`, `mandate` (empty only for deposit refunds), `status`, `reference`, `run`, `notified_at`, `collected_at`, `returned_at`, `return_text`, `invoice_number`, `invoice_amount`, `paid_at`, `status_note`. Unique on (`agreement`, `kind`, `period_start`). `reference` is `<prefix>-C-<collection id, six digits>` and is the SEPA end-to-end id; the mandate reference is the SEPA mandate id. Both appear on bank statements and on every return.

```
 planned ─▶ notified ─▶ submitted ─▶ collected
                            │
                            └─▶ returned ─▶ invoiced ─▶ paid
 deposit refund: planned ─▶ paid (manual)
 any non-final ─▶ cancelled
```

Billing periods: monthly kinds bill calendar months, due on the kind's `collection_day`. Yearly kinds bill calendar years, due on one fixed date for all agreements of the kind, `collection_month` and `collection_day` (membership: a day in March).

A daily command `create_agreement_collections` creates fee collections for active agreements whose next due date lies within the lookahead (settings, default 45 days), idempotent through the unique constraint, never for periods after the end date. The amount is frozen at creation; changing the agreement affects later collections. Deposits are created at approval with the start date as due date.

First period: when an agreement's start date lies within a billing period instead of on its first day, `approve_agreement` creates one prorated collection for the rest of that period. The start date of the agreement is decisive, never the signing date or the decision date. Amounts are rounded to the cent.

- Yearly kinds, start date not 1 January: one twelfth of the amount for each full month after the start month up to December. A start in October means November and December, two twelfths; the period runs from the first day of the following month to 31 December. A start in December leaves no full month and creates no collection.
- Monthly kinds, start date not the first of the month: the amount times the days from the start date to the end of the month, both included, divided by the days of that month. A start on 20 March means 12 of 31 days; the period runs from the start date to the end of the month.

The due date is the later of the period's regular due date (yearly: the year's fixed date; monthly: the collection day of the start month) and the decision date plus `PRE_NOTIFICATION_DAYS`. The daily command creates full-period collections only for periods starting on or after the start date, so the partial period is never billed twice. Agreements entered in the admin get no first-period collection; they paid on paper.

### D6: Pre-notification

When a planned collection reaches due date minus `PRE_NOTIFICATION_DAYS` (default 14): kinds with mode "each collection" get an email naming amount, due date, mandate reference and creditor identifier; kinds with mode "once at approval" rely on the approval email, which states amount, interval and collection day and is a valid standing pre-notification under SEPA. Either way the collection becomes `notified`.

The first-period collection (D5) gets no pre-notification email, whatever the kind and mode: it is created as `notified`, and the approval email states its amount and due date, which lies at least `PRE_NOTIFICATION_DAYS` after the decision.

### D7: SEPA runs, upload confirmation, collected by absence of return

`CollectionRun`: `collection_date`, `xml_file`, `created_by`, `uploaded_at`, `uploaded_by`, `total_amount`, `count`. A manager builds a run from notified collections with an active mandate and due date up to the collection date. The XML is a pain.008 CORE file generated with `sepaxml`, sequence type RCUR, batch booking false so the bank books one line per debit, end-to-end id equal to the collection reference, mandate id and signature date from the mandate, remittance information naming the kind and period. Collections become `submitted`.

The manager marks the run uploaded after the bank accepted the file. A run that is not marked uploaded can be deleted, returning its collections to `notified`; its collections never become `collected`. A nightly command `sync_collection_payments` sets `collected` on submitted collections of uploaded runs whose collection date lies more than `COLLECTION_RETURN_WINDOW_DAYS` (default 7) in the past and that have no return.

Alternative: positive confirmation by matching credit transactions. Rejected, a bank may book the batch as one aggregated credit, and the absence-of-return rule is what SEPA direct debit gives you anyway.

### D8: Return detection and return invoices

The nightly command lists BuchhaltungsButler transactions since the last run and marks a submitted or collected collection `returned` when a transaction with negative amount contains the collection reference or, failing that, the mandate reference plus the amount, in `purpose`, `booking_text` or `payment_reference`. The matched text is stored as `return_text`. Collected collections can therefore still turn returned, since a debtor refund is possible for eight weeks.

For a returned collection the manager triggers `invoice_returned_collection`: an outbound invoice in BuchhaltungsButler for the collection amount plus `SEPA_RETURN_FEE`, due in 14 days, with the organization address and a transfer request; the invoice number and amount are stored and the status becomes `invoiced`, and an email with the invoice number as payment purpose goes to the organization. The nightly command then reads the receipt by invoice number and sets `paid`. Managers can also mark any collection paid or cancelled by hand with a note.

### D9: Shared accounting client

`re_sharing/utils/buchhaltungsbutler.py` with `create_invoice`, `create_draft_invoice`, `create_einvoice`, `get_receipts`, `get_transactions`, raising one `BuchhaltungsButlerError`. The bookings tasks keep names and results.

### D10: Existing agreements

Existing members and coworkers are entered in the admin as active agreements with their paper mandate references, signed contracts and signing dates; no data migration is needed because nothing about them exists in the database today. Groups and codes they already hold are left alone; the admin form does not call the approval service. Tenants are entered the same way once their kinds open and their mandates exist.

### D11: Permissions and emails

Applicants need a confirmed admin booking permission on a confirmed organization. They see their own agreements, mandates and collections. Managers see agreements whose kind's group is within scope, following `manager_filter_organizations_list`, and alone approve, reject, end, build runs, invoice returns and settle by hand. New enqueued mails: application received, decision, pre-notification, return invoice, agreement ended.

## Risks / Trade-offs

- [Bank books the batch as one aggregated credit despite batch booking false] → Irrelevant for collected detection, which needs no credit matching; returns are always booked individually.
- [Return text format differs from expectations] → Match on collection reference first, mandate reference plus amount second; unmatched negative direct debit transactions are listed for the manager. Verify with one real return in the pilot cycle.
- [A run built but never uploaded] → Collections of runs without `uploaded_at` never become collected and the run list shows its age.
- [Debtor refund after collected] → Collected is not final; the sync keeps scanning and flips to returned.
- [IBAN in clear text] → Masked rendering, audit exclusion, private storage, no emails.
- [Existing tenants have no mandate] → Their kinds stay hidden; when opened, each tenant signs a mandate and a contract amendment before a manager creates the agreement in the admin.
- [Admin-created agreements drift from approved ones] → Both end up in the same status with the same fields; only the side effects of approval are skipped, and the admin shows whether group and code are present.

## Migration Plan

1. Deploy with the app, settings (`SEPA_CREDITOR_ID`, `SEPA_CREDITOR_NAME`, `SEPA_CREDITOR_IBAN`, `SEPA_CREDITOR_BIC`, `SEPA_MANDATE_PREFIX`, `SEPA_MANDATE_FORM_URL`, `PRE_NOTIFICATION_DAYS`, `COLLECTION_LOOKAHEAD_DAYS`, `COLLECTION_RETURN_WINDOW_DAYS`, `SEPA_RETURN_FEE`) and three cron entries.
2. Create the kinds in the admin: membership (yearly, collection date in March) and coworking open; office and cellar with applications closed. Only coworking gets accesses; membership grants no code.
3. Enter existing member and coworker agreements with their paper mandate references in the admin.
4. First yearly member run in the next cycle; monthly runs from the following month.
5. Rollback: disable the cron entries; the tables stay and the registration flow was never touched.

## Open Questions

- The exact wording of return transactions from the bank in BuchhaltungsButler (see risks).
