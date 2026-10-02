## 1. Shared accounting client

- [ ] 1.1 Add tests in `re_sharing/utils/tests/test_buchhaltungsbutler.py` (mocking `requests`) for a client with `create_invoice`, `create_draft_invoice`, `create_einvoice`, `get_receipts`, `get_transactions`: auth header and api key in payload, parsed JSON on success, one `BuchhaltungsButlerError` on HTTP error, timeout and `success: false`
- [ ] 1.2 Implement `re_sharing/utils/buchhaltungsbutler.py` with settings-based configuration
- [ ] 1.3 Refactor the four tasks in `bookings/tasks.py` to use the client, keeping task names and return values; existing task tests pass unchanged
- [ ] 1.4 Add settings `SEPA_CREDITOR_ID`, `SEPA_MANDATE_PREFIX`, `SEPA_CREDITOR_NAME`, `SEPA_CREDITOR_IBAN`, `SEPA_CREDITOR_BIC`, `PRE_NOTIFICATION_DAYS`, `COLLECTION_LOOKAHEAD_DAYS`, `COLLECTION_GRACE_DAYS` with env defaults; document them in the README and `.envs` templates

## 2. App skeleton and data model

- [ ] 2.1 Create the `agreements` app (apps.py, admin, models, selectors, services, forms, views, urls, mails, tests package, factories) and register it in `LOCAL_APPS` and the root urls under `/agreements/`
- [ ] 2.2 Add `AgreementKind` with the fields from design D2, `__str__`, ordering, and `clean()` requiring a collection day consistent with the interval; add migration
- [ ] 2.3 Add `Agreement` with status choices (`Submitted`, `Active`, `Rejected`, `Ended`), payment method choices, `details` JSONField, `signed_document` in private storage with the PDF validator, `decided_at`, `decided_by`, `permanent_code` (nullable, SET_NULL), `history`; `clean()` rejects a payment method not allowed by the kind and a deposit amount for kinds without deposit; unique constraint on (`organization`, `kind`) for non-final statuses via partial constraint; add migration
- [ ] 2.4 Add `SepaMandate` with reference (unique), bank fields, `signed_on`, `signed_document`, `revoked_on`; partial unique constraint on `agreement` where `revoked_on` is null; register with auditlog excluding `iban`; add migration
- [ ] 2.5 Add `Collection` (kind, period, due date, amount, payment method, mandate, status, invoice number, run, notified_at, paid_at, status_note) with unique constraint on (`agreement`, `kind`, `period_start`) and `CollectionRun` (collection date, xml file in private storage, created_by, total amount, count); add migration
- [ ] 2.6 Add factories for kind, agreement, mandate, collection and run in `agreements/tests/factories.py`
- [ ] 2.7 Add model tests: status defaults, `clean()` rules, partial unique constraints, IBAN excluded from audit log, `__str__`
- [ ] 2.8 Register all models in the admin with list filters for status, kind and payment method; IBAN masked in list display; collections inline on the agreement

## 3. Mandate reference and bank data (red, then green)

- [ ] 3.1 Add tests for `generate_mandate_reference(agreement)`: first reference, second after revocation, skipping an existing reference entered by hand
- [ ] 3.2 Add tests for IBAN validation and normalisation (spaces removed, checksum), `masked_iban()`
- [ ] 3.3 Implement the reference generator and IBAN helpers in `agreements/services.py` and a `MandateForm` with the validation
- [ ] 3.4 Add tests and implementation for `create_mandate(user, agreement, form)` and `revoke_mandate(manager, mandate, revoked_on)`: refused on transfer agreements, refused when an active mandate exists, permission checks

## 4. Agreement lifecycle services (red, then green)

- [ ] 4.1 Add tests for `create_agreement(user, organization, kind, form)`: permission rules (confirmed admin, confirmed organization), duplicate kind refused, details stored, application emails enqueued
- [ ] 4.2 Add an `accesses` parameter to `create_permanent_code_for_organization` defaulting to the current hardcoded set, with a test that the default is unchanged and a test for custom accesses
- [ ] 4.3 Add tests for `approve_agreement(manager, agreement, decided_at)`: refused without signed document, refused without mandate for direct debit, refused outside scope, refused when not submitted; on success group added, permanent code with kind accesses created and stored, deposit collection created when required, decision email enqueued
- [ ] 4.4 Add tests for `reject_agreement(manager, agreement, decided_at)`: status, email, no side effects
- [ ] 4.5 Add tests for `end_agreement(manager, agreement, end_date=None)`: end date defaulting to today, group removed, group kept when another active agreement grants it, code validity end set, later planned collections cancelled, deposit refund created when a paid deposit exists, ended email enqueued
- [ ] 4.6 Implement the lifecycle services and a `manager_can_manage_agreement(manager, agreement)` selector following the organization scoping rule
- [ ] 4.7 Add the management command `end_expired_agreements` with a test (ends agreements with end date before today, leaves others)

## 5. Collections and runs (red, then green)

- [ ] 5.1 Add tests for `next_billing_periods(agreement, until)` for monthly and yearly kinds with a collection day, honouring start and end dates
- [ ] 5.2 Add tests for `create_due_collections(today)`: creation within lookahead, idempotence, amount frozen, mandate snapshot, none after end date, cancelled period not recreated
- [ ] 5.3 Implement period calculation and `create_due_collections` and the command `create_agreement_collections`
- [ ] 5.4 Add tests for `notify_due_collections(today)`: invoice created through the client with due date and payment-method-specific final provisions, invoice number stored, pre-notification email only for kinds with per-collection notification, payment request email for transfers and deposits, deposit creates no invoice, client error leaves the collection planned
- [ ] 5.5 Implement `build_invoice_payload_for_collection` and `notify_due_collections`, wired into the `create_agreement_collections` command after creation
- [ ] 5.6 Add `sepaxml` to the dependencies; add tests for `build_collection_run(manager, collection_date)`: selection of notified direct debit collections with active mandate, exclusion without mandate, XML content (creditor id, RCUR, end-to-end id, remittance information, amounts), file stored, collections submitted
- [ ] 5.7 Add tests for `delete_collection_run(manager, run)`: refused with a paid collection, otherwise collections back to notified
- [ ] 5.8 Implement run building and deletion
- [ ] 5.9 Add tests for `sync_collection_payments(today)`: paid, overdue with single reminder, returned with matching negative transaction, unresolved stays submitted, client error changes nothing
- [ ] 5.10 Implement the sync service and the command `sync_collection_payments`
- [ ] 5.11 Add tests and implementation for `mark_collection_paid(manager, collection, note)` and `cancel_collection(manager, collection, note)` with the refusal rules

## 6. Forms, views and templates

- [ ] 6.1 Add the application form base with kind selection, amount, start date, payment method limited by the kind, deposit amount, contact person function; one subclass per kind writing the kind-specific fields into `details`; form tests for each kind
- [ ] 6.2 Add applicant views: choose kind, apply, agreement detail with collections, add mandate, upload signed document; view tests for permissions and success paths; htmx partials follow the existing booking templates
- [ ] 6.3 Add the organization page link and the manager list link to agreements
- [ ] 6.4 Add manager views: agreement list with filters and submitted count, agreement detail with approve, reject and end actions (decision date input), mandate detail with full IBAN and revoke, collections overview with attention list, filters and manual settle or cancel, run list with build and delete and XML download; view tests for every action and denial
- [ ] 6.5 Add email templates and `mails.py` tasks: application received (organization and managers), decision, pre-notification, payment request, overdue reminder, agreement ended; tests assert recipients and that no email contains an IBAN
- [ ] 6.6 Translations for all new strings (`makemessages`, German translations)

## 7. Documentation and rollout

- [ ] 7.1 Add ADR `0024-Agreements-App-and-Manual-SEPA-Export.md` covering D1 to D7
- [ ] 7.2 Add ADR `0025-Shared-Accounting-Client.md`
- [ ] 7.3 Add the three cron entries to the deployment documentation and README (create collections daily, sync payments nightly, end expired agreements daily)
- [ ] 7.4 Document the rollout steps from the design's migration plan in the README, including entering existing mandate references through the admin
- [ ] 7.5 Run the full test suite with coverage and confirm it stays above 95 percent; run pre-commit on all changed files
