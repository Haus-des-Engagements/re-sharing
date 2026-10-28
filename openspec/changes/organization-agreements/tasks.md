## 1. Shared accounting client

- [ ] 1.1 Add tests in `re_sharing/utils/tests/test_buchhaltungsbutler.py` (mocking `requests`) for a client with `create_invoice`, `create_draft_invoice`, `create_einvoice`, `get_receipts`, `get_transactions`: auth header and api key in payload, parsed JSON on success, one `BuchhaltungsButlerError` on HTTP error, timeout and `success: false`, paging of `get_transactions` with `date_since_last_modified`
- [ ] 1.2 Implement `re_sharing/utils/buchhaltungsbutler.py` with settings-based configuration
- [ ] 1.3 Refactor the four tasks in `bookings/tasks.py` to use the client, keeping task names and return values; existing task tests pass unchanged
- [ ] 1.4 Add settings `SEPA_CREDITOR_ID`, `SEPA_CREDITOR_NAME`, `SEPA_CREDITOR_IBAN`, `SEPA_CREDITOR_BIC`, `SEPA_MANDATE_PREFIX`, `SEPA_MANDATE_FORM_URL`, `PRE_NOTIFICATION_DAYS`, `COLLECTION_LOOKAHEAD_DAYS`, `COLLECTION_RETURN_WINDOW_DAYS`, `SEPA_RETURN_FEE` with env defaults; document them in the README and `.envs` templates

## 2. App skeleton and data model

- [ ] 2.1 Create the `agreements` app (apps.py, admin, models, selectors, services, forms, views, urls, mails, tests package, factories) and register it in `LOCAL_APPS` and the root urls under `/agreements/`
- [ ] 2.2 Add `AgreementKind` with the fields from design D2 including `accepting_applications`, `notification_mode` and `collection_month`; `clean()` requires a collection day, and a collection month for yearly kinds only; add migration
- [ ] 2.3 Add `Agreement` with status choices (`Submitted`, `Active`, `Rejected`, `Ended`), `amount`, `deposit_amount`, dates, `details` JSONField, `signed_document` in private storage with the PDF validator, `signed_on`, `decided_at`, `decided_by`, `permanent_code` (nullable, SET_NULL), `history`; `clean()` requires an amount above zero and rejects a deposit on kinds without one; partial unique constraint on (`organization`, `kind`) for submitted and active; add migration
- [ ] 2.4 Add `SepaMandate` with reference (unique), bank fields, `signed_on` and `signed_document` (nullable), `revoked_on`, an `is_active` property (signed document present, not revoked); partial unique constraint on `agreement` where `revoked_on` is null; register with auditlog excluding `iban`; add migration
- [ ] 2.5 Add `Collection` (kind, period, due date, amount, mandate nullable for deposit refunds, status, reference, run, notified_at, collected_at, returned_at, return_text, invoice_number, invoice_amount, paid_at, status_note) with unique constraint on (`agreement`, `kind`, `period_start`) and unique `reference`; add `CollectionRun` (collection date, xml file in private storage, created_by, uploaded_at, uploaded_by, total amount, count); add migration
- [ ] 2.6 Add factories for kind, agreement, mandate, collection and run in `agreements/tests/factories.py`
- [ ] 2.7 Add model tests: defaults, `clean()` rules, partial unique constraints, IBAN excluded from audit log, `__str__`
- [ ] 2.8 Register all models in the admin with list filters for status and kind; IBAN masked in list display; collections and mandates inline on the agreement; an admin test that creating an active agreement with a mandate sends no email and touches no group or code

## 3. References and bank data (red, then green)

- [ ] 3.1 Add tests for `generate_mandate_reference(agreement)` (first, after revocation, skipping an existing hand-entered reference) and `generate_collection_reference(collection)`
- [ ] 3.2 Add tests for IBAN validation and normalisation (spaces removed, checksum) and `masked_iban()`
- [ ] 3.3 Implement the generators and IBAN helpers in `agreements/services.py` and a `MandateForm` with the validation
- [ ] 3.4 Add tests and implementation for `create_mandate(user, agreement, form)` with or without signed PDF, `upload_signed_mandate(user, mandate, form)` and `revoke_mandate(manager, mandate, revoked_on)`: refused when a non-revoked mandate exists, a mandate without signed PDF is not active, uploading the PDF with its signature date makes it active, permission checks

## 4. Agreement lifecycle services (red, then green)

- [ ] 4.1 Add tests for `create_agreement(user, organization, kind, form)`: admin permission required, confirmed organization required (pending, rejected and deactivated denied), kind must be active and accepting applications, duplicate kind refused, details stored, application emails enqueued
- [ ] 4.2 Add tests and implementation for `upload_signed_document(user, agreement, form)` by an admin or manager
- [ ] 4.3 Add an `accesses` parameter to `create_permanent_code_for_organization` defaulting to the current hardcoded set, with a test that the default is unchanged and a test for custom accesses
- [ ] 4.4 Add tests for `approve_agreement(manager, agreement, decided_at)`: refused without signed document, refused without active mandate (including a mandate without signed PDF), refused outside scope, refused when not submitted; on success the organization status is unchanged, group added, permanent code with kind accesses created and stored or none when the kind has no accesses, deposit collection created when required, first-period collection created from the start date (5.1), decision email enqueued stating amount, interval and collection day for once-at-approval kinds
- [ ] 4.5 Add tests for `reject_agreement(manager, agreement, decided_at)`: status, email, organization status unchanged, no side effects
- [ ] 4.6 Add tests for `end_agreement(manager, agreement, end_date=None)`: end date defaulting to today, group removed, group kept when another active agreement grants it, code validity end set when the agreement has a code and nothing touched otherwise, later planned collections cancelled, deposit refund created when a paid deposit exists, ended email enqueued
- [ ] 4.7 Implement the lifecycle services and a `manager_can_manage_agreement(manager, agreement)` selector following the organization scoping rule
- [ ] 4.8 Add the management command `end_expired_agreements` with a test

## 5. Collections, runs and return handling (red, then green)

- [ ] 5.1 Add tests for `next_billing_periods(agreement, until)` for monthly kinds (collection day) and yearly kinds (fixed collection month and day), honouring start and end dates and skipping a partial start period; add tests for `first_period_collection(agreement, decided_at)`: yearly two twelfths for an October start, eleven twelfths due on the fixed date for a start on 20 January, none for a December start, none for a 1 January start; monthly 12 of 31 days for a start on 20 March, 15 of 30 days due on the collection day for a start on 16 April approved weeks earlier, none for a start on the first; calculated from the start date regardless of signing and decision date; rounding to the cent; due date never before decision date plus pre-notification days; status notified
- [ ] 5.2 Add tests for `create_due_collections(today)`: creation when the due date is within the lookahead, yearly collections due on the fixed date, no full-period collection for a partial start period, idempotence, amount frozen, mandate snapshot, reference generated, none after end date, none for inactive kinds, cancelled period not recreated
- [ ] 5.3 Implement period calculation, `create_due_collections` and the command `create_agreement_collections`
- [ ] 5.4 Add tests for `notify_due_collections(today)`: email for per-collection mode with amount, due date, mandate reference and creditor id; no email for once-at-approval mode; status notified in both cases; first-period collections are never picked up, they are notified at creation
- [ ] 5.5 Implement `notify_due_collections`, wired into the `create_agreement_collections` command after creation
- [ ] 5.6 Add `sepaxml` to the dependencies; add tests for `build_collection_run(manager, collection_date)`: selection of notified collections with active mandate including deposits, exclusion without mandate, XML content (creditor data, batch booking false, RCUR, end-to-end id equals collection reference, mandate id and signature date, amounts), file stored, collections submitted
- [ ] 5.7 Add tests and implementation for `mark_run_uploaded(manager, run)` and `delete_collection_run(manager, run)`: refused when uploaded, otherwise collections back to notified
- [ ] 5.8 Add tests for `mark_collected(today)`: collected after the window for uploaded runs only, untouched inside the window and for runs never uploaded
- [ ] 5.9 Add tests for `detect_returns(since)` with faked transaction payloads: match by collection reference, match by mandate reference plus amount, return after collected, unmatched negative transactions reported, client error changes nothing, last successful run timestamp stored
- [ ] 5.10 Implement `mark_collected`, `detect_returns` and the command `sync_collection_payments`
- [ ] 5.11 Add tests for `invoice_returned_collection(manager, collection)`: payload with amount plus return fee, organization address, 14 days due, invoice number and amount stored, status invoiced, email with invoice number enqueued, refused when not returned, client error leaves it returned
- [ ] 5.12 Implement the return invoice service and extend `sync_collection_payments` to set invoiced collections paid from the receipt payment status, with tests
- [ ] 5.13 Add tests and implementation for `mark_collection_paid(manager, collection, note)` and `cancel_collection(manager, collection, note)` with the refusal rules

## 6. Forms, views and templates

- [ ] 6.1 Add the application form base with start date, amount, deposit amount where required, signed document and signing date, contact person function; one subclass per kind writing the kind-specific fields into `details`; form tests for each kind
- [ ] 6.2 Add applicant views: list of open kinds on the organization page as available actions for confirmed organizations, apply, agreement detail with collections and the signed document download, the kind's intro text with the contract link on the apply page, add mandate with or without signed PDF, mandate detail with reference, link to the blank mandate form, upload of the signed mandate and its download, upload signed document; view tests for permissions, download access and success paths
- [ ] 6.3 Add manager views: agreement list with filters and submitted count linked from the organization list, agreement detail with approve, reject and end actions (decision date input), mandate detail with full IBAN and revoke, collections overview with attention list, filters, manual settle or cancel and return invoice action, run list with build, mark uploaded, delete and XML download; view tests for every action and denial
- [ ] 6.4 Add email templates and `mails.py` tasks: application received (organization and managers), decision (with mandate reference, and amount and due date of a first-period collection), pre-notification, return invoice, agreement ended; tests assert recipients and that no email contains an IBAN
- [ ] 6.5 Translations for all new strings (`makemessages`, German translations)

## 7. Documentation and rollout

- [ ] 7.1 Add an ADR with the next free number, `Agreements-App-and-Manual-SEPA-Export`, covering D1 to D8 and D10
- [ ] 7.2 Add an ADR with the next free number, `Shared-Accounting-Client`
- [ ] 7.3 Add the three cron entries to the deployment documentation and README (create collections daily, sync payments nightly, end expired agreements daily)
- [ ] 7.4 Document the rollout steps from the design's migration plan in the README, including the kinds to create and entering existing agreements with paper mandate references
- [ ] 7.5 Run the full test suite with coverage and confirm it stays above 95 percent; run pre-commit on all changed files
