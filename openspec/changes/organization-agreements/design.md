## Context

Four paper processes exist today, each ending in a signed document and a manual payment arrangement:

| Kind | Interval | Pays by | Deposit | Notice | Kind-specific data |
|---|---|---|---|---|---|
| Member | yearly | direct debit | no | per statutes | representative's function, solidarity amount |
| Coworker | monthly | direct debit | yes | 4 weeks to month end | desks, hours per week |
| Office tenant | monthly | bank transfer | 3 months' rent | 3 months to month end | room, fixed end date |
| Cellar tenant | monthly | bank transfer | no | not stated | area in m² |

Mandate references are written by hand, the yearly or monthly debit is uploaded to the bank manually, and nobody can see in one place who owes what. The accounting system (BuchhaltungsButler) is already used for booking invoices through a client that is inlined four times in `bookings/tasks.py`. Its API (v1.9.1) can create invoices, list receipts with a `payment_status` of paid or unpaid, and list bank transactions. It cannot store mandates, execute direct debits, or push webhooks.

In the codebase, `OrganizationGroup` already expresses "is a member", "is a coworker" and so on, and drives permissions, pricing and the free-bookings quota. `PermanentCode` grants entrance codes per organization with a hardcoded set of accesses. Managers are scoped by organization groups (ADR 21). Emails are sent through `django-tasks` from `mails.py` modules, periodic work runs as management commands.

Constraints: HackSoft style (services, selectors, thin views), coverage above 95 percent, one outward relation per app (ADR 9), private storage for signed documents (ADR 20), audit log on business models (ADR 13).

## Goals / Non-Goals

**Goals:**

- One place that knows which organization holds which agreement, at what price, paid how, and whether each period was paid.
- Group membership and entrance codes follow the agreement, never the other way round.
- Direct debit handled end to end except for the bank upload: mandate, pre-notification, XML file, result.
- Bank transfer handled with the same collection records and the same paid signal.
- The accounting client shared between bookings and agreements.

**Non-Goals:**

- Individuals as members, automatic debit execution, contract PDF generation, key inventories, dunning, changes to registration (see proposal).
- Encrypting bank data at rest (see risks).
- Historic reconstruction of past payments. The system starts with the first collection it creates.

## Decisions

### D1: A new `agreements` app with one outward relation

Models live in `re_sharing/agreements/`. The only foreign key out of the app points to `Organization`. `AgreementKind` references `OrganizationGroup` and `Access` as configuration, which is the same kind of relation `Compensation` already has to groups. Views for applicants sit under `/agreements/`, manager views under `/agreements/manage/`, using `manager_required`.

Alternative: extend `organizations`. Rejected, the models file there is already the largest in the project and membership is a different lifecycle from the organization itself.

### D2: Kinds are configuration, agreements are one model

`AgreementKind` is a model edited in the admin: `name`, `slug`, `organization_group`, `billing_interval` (yearly, monthly), `allowed_payment_methods` (direct debit, bank transfer, both), `requires_deposit`, `notice_period_weeks`, `requires_end_date`, `accesses` (M2M to `Access`), `notify_each_collection`, `collection_day` (day of month for monthly, month and day for yearly), `intro_text`, `is_active`.

`Agreement` carries what every kind shares: `organization`, `kind`, `status`, `payment_method`, `amount`, `deposit_amount`, `start_date`, `end_date`, `contact_person_function`, `details` (JSONField), `signed_document` (private storage, PDF validated as for the usage agreement), `decided_at`, `decided_by`, `notes`, `history`.

`details` holds the kind-specific values from the paper forms: desks and hours per week for coworkers, room for office tenants, area for cellar tenants, solidarity amount for members. The application form per kind is a form class per kind that writes into `details`; the model does not know the keys. This keeps a fifth kind a form change, not a migration.

Alternative: four models with multi-table inheritance. Rejected, every workflow, listing and permission check would be written four times for a handful of differing fields.

### D3: Agreement lifecycle

```
 submitted ──approve──▶ active ──end──▶ ended
     │
     └──reject──▶ rejected
```

A manager records the board decision with `decided_at` (date, required on approve and reject). Approval requires a signed document and, for direct debit, an active mandate; both are uploaded by the manager or the applicant before approval. Side effects of approval in one service `approve_agreement`:

1. add the kind's group to the organization,
2. create a `PermanentCode` with the kind's accesses through `create_permanent_code_for_organization`, which gains an `accesses` parameter and keeps the current hardcoded set as default,
3. create the deposit collection when the kind requires one,
4. send the confirmation email.

`end_agreement` sets `end_date` if empty, removes the group unless another active agreement of the organization grants the same group, sets `validity_end` on the code created by this agreement (the agreement stores the code's id for that), and cancels planned collections after the end date. A daily command ends agreements whose `end_date` has passed.

An agreement with a fixed `end_date` in the future stays active until then. Notice periods are informative for the manager; the system does not compute termination dates.

### D4: Payment method on the agreement, one mandate per agreement

`payment_method` is chosen at application from the kind's allowed methods. `SepaMandate` has a foreign key to the agreement, `reference` (unique), `account_holder`, `iban`, `bic`, `bank_name`, `signed_on`, `signed_document`, `revoked_on`. A partial unique constraint allows one non-revoked mandate per agreement; a new bank account means a new mandate and revoking the old one.

The reference is generated, never typed: `<prefix>-<agreement id, zero padded to 6>-<mandate number>`, prefix from settings. The existing handwritten references on paper mandates are entered through the admin for agreements registered after the fact; the generator skips references that already exist.

IBAN is validated (format and checksum) in the form and stored as entered without spaces. It is excluded from audit log diffs, rendered masked (last four characters) everywhere except the manager's mandate detail, and never put into emails. Encrypting it at rest is deferred: the accounting system and the bank hold the same data, and the private media volume already holds the signed mandates with the IBAN in full.

Alternative: mandate per organization reused across agreements. Rejected by the stakeholder; per agreement matches the paper process and makes revocation equal to ending the agreement.

### D5: Collections are the unit of money

`Collection`: `agreement`, `kind` (fee, deposit, deposit refund), `period_start`, `period_end`, `due_date`, `amount`, `payment_method` (snapshot), `mandate` (snapshot, nullable), `status`, `invoice_number`, `run`, `notified_at`, `paid_at`, `status_note`. Unique on (`agreement`, `kind`, `period_start`).

```
 planned ──notify/request──▶ notified ──(direct debit) add to run──▶ submitted ──▶ paid
                                │                                        │
                                │ (transfer)                             └──▶ returned
                                └──────────────────────────────────────────▶ paid | overdue
 any non-final ──cancel──▶ cancelled
```

A daily command `create_agreement_collections` creates fee collections for every active agreement whose next period starts within the lookahead (settings, default 45 days), using the kind's interval and collection day and the agreement's current amount. It is idempotent through the unique constraint. Deposits are created once at approval with `due_date` equal to `start_date`; deposit refunds once at ending, as a negative-direction record that a manager marks settled by hand. Deposits never create invoices.

The amount is copied from the agreement at creation. Changing the agreement's amount affects only collections created afterwards; an existing planned collection can be cancelled and recreated by the manager.

### D6: Invoice-centric reconciliation through the shared accounting client

The inline HTTP code in `bookings/tasks.py` moves to `re_sharing/utils/buchhaltungsbutler.py` with `create_invoice`, `create_draft_invoice`, `create_einvoice`, `get_receipts`, `get_transactions`, each returning parsed JSON or raising one client error. The bookings tasks keep their names and results.

When a fee collection reaches `notified`, a task creates an outbound invoice (`/invoices/create`, not a draft) with the organization as recipient, the agreement kind and period as line item, a due date equal to the collection's due date, and the final provisions text per payment method: the direct debit clause with mandate reference and creditor identifier, or the transfer request. The returned invoice number is stored on the collection and is the payment purpose in the SEPA file and in the payment request email.

A nightly command `sync_collection_payments` lists outbound receipts changed since the last run and sets `paid` on collections whose invoice is paid. Collections still unpaid after `due_date` plus the grace period (settings, default 7 days) become `overdue` for transfers and get one reminder email. For direct debits the same unpaid state after grace is reported as `returned` only when a bank transaction with a negative amount and the invoice number in its purpose exists; otherwise the collection stays `submitted` and appears in the manager's attention list.

Alternative: skipping invoices and scanning bank transactions for mandate references. Rejected, it depends on parsing bank-formatted text and gives the bookkeeper no receipt.

Alternative: BuchhaltungsButler's own recurring invoices. Rejected, re-sharing would not know the invoice numbers it needs for the XML.

### D7: SEPA runs built by a manager, uploaded by hand

`CollectionRun`: `collection_date`, `xml_file` (private storage), `created_by`, `created`, `total_amount`, `count`. A manager builds a run from all `notified` direct-debit collections with a due date up to the chosen collection date. The file is a pain.008 CORE file generated with the `sepaxml` package, sequence type `RCUR` for every transaction (first-use marking has not been required since 2016), end-to-end id equal to the collection id, remittance information equal to the invoice number. Collections in the run become `submitted`. A run can be deleted while none of its collections is paid, which returns them to `notified`.

Pre-notification: when the kind has `notify_each_collection`, the daily command sends the pre-notification email `PRE_NOTIFICATION_DAYS` (settings, default 14) before the due date, naming amount, date, mandate reference and creditor identifier, and moves the collection to `notified`. When the kind does not, the approval email already states the fixed amount, interval and collection day, which SEPA accepts as a standing pre-notification, and the collection moves to `notified` without a mail. Transfer collections always get the payment request email.

### D8: Permissions

Applying requires a confirmed admin booking permission on a confirmed organization. Applicants see their own agreements, mandates and collections. Managers see agreements whose kind's group is within their scope, following `manager_filter_organizations_list`. Only managers approve, reject, end, build runs and mark deposits. The admin exposes everything for corrections.

### D9: Emails and templates

New enqueued mails in `agreements/mails.py`: application received (to the organization and the managers), decision, pre-notification, payment request, overdue reminder, agreement ended. Templates follow the existing `templates/emails/` layout and are translated.

## Risks / Trade-offs

- [BuchhaltungsButler may not flip a receipt to unpaid after a returned debit] → Returned detection also scans transactions; unresolved submitted collections are listed for the manager after the grace period. Verify with one real returned debit in the pilot year.
- [The invoice `email` parameter might send mail from the accounting system] → Never pass it; recipient data goes in the address fields only.
- [IBAN stored in clear text] → Masked rendering, audit log exclusion, private storage, no emails. Revisit encryption if the hosting changes.
- [A run is built but never uploaded] → Runs show their age; collections stay `submitted`; the sync command flags them after grace.
- [Amount changes between pre-notification and run] → Amount is frozen on the collection at creation, and the run uses the collection amount.
- [Hardcoded accesses in the permanent code service] → The parameter keeps the current default, so existing manager actions are unchanged.
- [Two sources of truth for group membership during the transition] → Managers register existing members and tenants through the admin first; until then groups are edited as today.

## Migration Plan

1. Deploy with the new app, settings (`SEPA_CREDITOR_ID`, `SEPA_MANDATE_PREFIX`, `PRE_NOTIFICATION_DAYS`, `COLLECTION_LOOKAHEAD_DAYS`, `COLLECTION_GRACE_DAYS`) and three new cron entries (create collections, sync payments, end expired agreements).
2. Create the four kinds in the admin, pointing at the existing groups and entrances.
3. Managers register existing agreements in the admin with their current amounts, start dates and existing mandate references; no automatic data migration.
4. First collection run for members in the next yearly cycle; monthly runs from the following month.
5. Rollback: disable the cron entries; the app's tables are unused by other apps and can stay.

## Open Questions

- Whether the yearly member fee is collected on one fixed date for everyone or per anniversary. The design assumes one fixed date per kind.
- Whether the accounting side wants an invoice receipt for member fees of a registered association, or a different document type. The design assumes an invoice.
- Behaviour of receipts after a returned debit in BuchhaltungsButler (see risks).
- Whether deposit refunds should ever go through the SEPA credit side. The design marks them by hand.
