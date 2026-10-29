# agreement-collections Specification

## Purpose
TBD - created by archiving change organization-agreements. Update Purpose after archive.
## Requirements
### Requirement: Fee collections are created per billing period

A daily command SHALL create a fee collection for every active agreement whose next due date lies within the configured lookahead. Monthly kinds SHALL bill calendar months due on the kind's collection day; yearly kinds SHALL bill calendar years due on one fixed collection month and day for all agreements of the kind. The collection SHALL copy the agreement's amount, SHALL reference the agreement's active mandate, SHALL receive a generated collection reference, and SHALL have status `Planned`. Creation SHALL be idempotent per agreement, kind and period start. No collection SHALL be created for periods starting after the agreement's end date.

#### Scenario: Monthly fee collection

- **WHEN** the command runs on 2027-02-20 with a lookahead of 45 days for a monthly agreement of 120 € with collection day 5
- **THEN** a fee collection for period 2027-03-01 to 2027-03-31 with amount 120 € and due date 2027-03-05 exists
- **AND** running the command again creates no second collection for that period

#### Scenario: Yearly fee collection

- **WHEN** the command runs on 2027-02-01 with a lookahead of 45 days for a member agreement of 60 € started in 2026, whose kind collects on 15 March
- **THEN** one fee collection for 2027-01-01 to 2027-12-31 with amount 60 € and due date 2027-03-15 exists

#### Scenario: Amount frozen at creation

- **WHEN** an agreement's amount is changed after a collection was created
- **THEN** the existing collection keeps its amount and only later collections use the new amount

#### Scenario: No collection after end date

- **WHEN** an agreement ends on 2027-03-31
- **THEN** no fee collection with a period start after 2027-03-31 is created

### Requirement: First period is prorated from the start date

On approval of an agreement whose start date lies within a billing period instead of on its first day, the system SHALL create one prorated fee collection for the rest of that period, calculated from the agreement's start date and never from the signing or decision date, rounded to the cent. For yearly kinds it SHALL be one twelfth of the amount for each full month after the start month up to December, for the period from the first day of the following month to 31 December; no collection SHALL be created when no full month remains. For monthly kinds it SHALL be the amount times the days from the start date to the end of the month, both included, divided by the days of that month, for the period from the start date to the end of the month. Its due date SHALL be the later of the period's regular due date and the decision date plus the configured pre-notification days. It SHALL be created as `Notified` without a pre-notification email; the decision email SHALL state its amount and due date. The daily command SHALL NOT create a full-period collection for the start period. Agreements entered in the admin SHALL get no first-period collection.

#### Scenario: Joining in October

- **WHEN** a membership of 60 € starting 2027-10-10 is approved on 2027-10-12, with the fixed date 15 March and 14 pre-notification days
- **THEN** a fee collection of 10 € for 2027-11-01 to 2027-12-31 with due date 2027-10-26 and status `Notified` exists
- **AND** no pre-notification email is sent
- **AND** the decision email states 10 € and 2027-10-26

#### Scenario: Joining before the fixed date

- **WHEN** a membership of 60 € starting 2027-01-20 is approved on 2027-02-01
- **THEN** a fee collection of 55 € for 2027-02-01 to 2027-12-31 with due date 2027-03-15 exists
- **AND** the daily command creates no full-year collection for 2027

#### Scenario: Joining in December

- **WHEN** a membership starting 2027-12-03 is approved
- **THEN** no fee collection for 2027 exists
- **AND** the daily command creates the full-year collection for 2028

#### Scenario: Starting on 1 January

- **WHEN** a membership starting 2028-01-01 is approved in December 2027
- **THEN** no first-period collection is created
- **AND** the daily command creates the full-year collection for 2028

#### Scenario: Coworking starting mid-month

- **WHEN** a coworking agreement of 120 € with collection day 5 and start date 2027-03-20 is approved on 2027-03-10, with 14 pre-notification days
- **THEN** a fee collection of 46.45 € (12 of 31 days) for 2027-03-20 to 2027-03-31 with due date 2027-03-24 and status `Notified` exists
- **AND** the daily command creates no full-month collection for March 2027 and creates the one for April 2027

#### Scenario: Start date decides, not the signing date

- **WHEN** a coworking agreement of 120 € with start date 2027-04-16 was signed on 2027-02-25 and is approved on 2027-03-01
- **THEN** a fee collection of 60 € (15 of 30 days) for 2027-04-16 to 2027-04-30 with due date 2027-04-05 exists

#### Scenario: Monthly start on the first

- **WHEN** a coworking agreement starting 2027-05-01 is approved
- **THEN** no first-period collection is created
- **AND** the daily command creates the full-month collection for May 2027

### Requirement: Pre-notification

When a planned collection reaches its notification date (due date minus the configured pre-notification days), the system SHALL assign the agreement's active mandate to it when there is one, SHALL send a pre-notification email naming amount, due date, mandate reference and creditor identifier when the kind's notification mode is per collection, and SHALL send nothing when the mode is once at approval. In both cases the collection SHALL become `Notified`. The approval email of a kind with mode once at approval SHALL state amount, interval and collection date. First-year collections of yearly kinds are notified at creation and SHALL NOT receive a pre-notification email.

#### Scenario: Per-collection notification

- **WHEN** the notification date of a collection of a kind with per-collection mode is reached
- **THEN** the organization receives the pre-notification email
- **AND** the collection status is `Notified`

#### Scenario: Mandate added after the collection was planned

- **WHEN** a collection was planned without mandate and the agreement has an active mandate at the notification date
- **THEN** the pre-notification names that mandate's reference

#### Scenario: Once-at-approval mode

- **WHEN** the notification date of a collection of a kind with once-at-approval mode is reached
- **THEN** no email is sent
- **AND** the collection status is `Notified`

#### Scenario: Approval email as standing notification

- **WHEN** an agreement of a kind with once-at-approval mode is approved
- **THEN** the decision email states amount, billing interval and collection date

### Requirement: SEPA collection runs

The system SHALL allow a manager to build a run for a chosen collection date from all notified collections whose agreement has an active mandate at that time and whose due date is up to that date. Each collection in the run SHALL use the agreement's mandate active when the run is built, regardless of the mandate present when the collection was created. The run SHALL produce a pain.008 CORE XML file in private storage with batch booking disabled, sequence type RCUR, the collection reference as end-to-end id, the mandate reference and signature date, and the creditor data from settings. Collections in the run SHALL become `Submitted`. A manager SHALL mark a run as uploaded. A run not marked uploaded SHALL be deletable, returning its collections to `Notified`; an uploaded run SHALL NOT be deletable.

#### Scenario: Build a run

- **WHEN** a manager builds a run for 2027-03-05 and three notified collections are due by then
- **THEN** a run with three transactions and the summed amount exists and its XML file can be downloaded
- **AND** the XML carries each collection's reference as end-to-end id and each mandate's reference
- **AND** the three collections are `Submitted` and reference the run

#### Scenario: Deposit in the run

- **WHEN** a notified deposit collection is due by the collection date
- **THEN** it is included in the run under the agreement's mandate

#### Scenario: Collection without mandate excluded

- **WHEN** the agreement of a notified collection has no active mandate
- **THEN** it is not included in a run and is listed as needing attention

#### Scenario: Mandate added after the collection

- **WHEN** a collection was created while its agreement had no mandate and a signed mandate is added before the run
- **THEN** the run includes the collection with that mandate and it no longer needs attention

#### Scenario: New mandate after revocation

- **WHEN** the mandate of a notified collection is revoked and a new signed mandate is added
- **THEN** the run includes the collection with the new mandate's reference

#### Scenario: Mark uploaded

- **WHEN** a manager marks a run as uploaded
- **THEN** the run stores the upload time and the manager

#### Scenario: Delete a run before upload

- **WHEN** a manager deletes a run that is not marked uploaded
- **THEN** its collections are `Notified` again and no longer reference the run

#### Scenario: Delete an uploaded run

- **WHEN** a manager tries to delete an uploaded run
- **THEN** the action is refused

### Requirement: Collected by absence of return

A nightly command SHALL set submitted collections of uploaded runs to `Collected` when the run's collection date lies more than the configured return window in the past and no return has been recorded. Collections of runs not marked uploaded SHALL stay `Submitted`.

#### Scenario: Collected after the window

- **WHEN** the command runs 8 days after the collection date of an uploaded run with a return window of 7 days and a collection has no return
- **THEN** the collection is `Collected` with the collection date stored

#### Scenario: Inside the window

- **WHEN** the command runs 3 days after the collection date of an uploaded run
- **THEN** its collections stay `Submitted`

#### Scenario: Run never uploaded

- **WHEN** the command runs 30 days after the collection date of a run not marked uploaded
- **THEN** its collections stay `Submitted` and the run is listed as needing attention

### Requirement: Return detection

The nightly command SHALL read bank transactions from the accounting system since the last successful run and SHALL mark a submitted or collected collection `Returned` when a transaction with a negative amount contains the collection reference, or the mandate reference together with the collection amount, in its purpose, booking text or payment reference. The matched text SHALL be stored. Negative direct debit transactions matching no collection SHALL be listed for manager attention. When the accounting system cannot be reached, no status SHALL change and the error SHALL be logged.

#### Scenario: Return matched by collection reference

- **WHEN** a transaction of -60 € whose purpose contains the collection reference exists
- **THEN** the collection is `Returned` with the transaction text stored

#### Scenario: Return matched by mandate reference and amount

- **WHEN** a transaction of -120 € contains only the mandate reference of an agreement with one submitted collection of 120 €
- **THEN** that collection is `Returned`

#### Scenario: Return after collected

- **WHEN** a collected collection's reference appears in a negative transaction five weeks later
- **THEN** the collection is `Returned`

#### Scenario: Unmatched return

- **WHEN** a negative direct debit transaction matches no collection
- **THEN** it appears in the manager's attention list

#### Scenario: Accounting system unreachable

- **WHEN** the accounting system cannot be reached
- **THEN** no collection status changes and the error is logged

### Requirement: Return invoice

A manager SHALL be able to invoice a returned collection. The system SHALL create an outbound invoice in the accounting system for the collection amount plus the configured return fee with the organization's address, SHALL store the invoice number and amount, SHALL set the status to `Invoiced`, and SHALL email the organization with the invoice number as payment purpose. The nightly command SHALL set invoiced collections to `Paid` when the accounting system reports the invoice as paid. Invoicing a collection that is not returned SHALL be refused.

#### Scenario: Invoice a returned collection

- **WHEN** a manager invoices a returned collection of 60 € with a return fee of 5 €
- **THEN** an invoice of 65 € exists in the accounting system, its number is stored, the status is `Invoiced`
- **AND** the organization receives an email naming the invoice number as payment purpose

#### Scenario: Invoice creation fails

- **WHEN** the accounting system returns an error
- **THEN** the collection stays `Returned`, no email is sent, and the error is logged

#### Scenario: Invoice paid

- **WHEN** the nightly command runs and the accounting system reports the invoice as paid
- **THEN** the collection is `Paid`

#### Scenario: Invoice a collected collection

- **WHEN** a manager tries to invoice a collection that is not returned
- **THEN** the action is refused

### Requirement: Manual settlement and overview

A manager SHALL be able to mark any non-final collection as paid or cancelled by hand with a note; deposit refunds SHALL only be settled this way, have no mandate and are never part of a run. Managers SHALL see collections filterable by status, kind and agreement kind within their scope, with an attention list of returned, invoiced-past-due and never-uploaded items first. Organization users SHALL see their own collections with status and amount.

#### Scenario: Deposit refund settled

- **WHEN** a manager marks a deposit refund as paid with a note
- **THEN** the collection is `Paid` and the note is stored

#### Scenario: Cancel a planned collection

- **WHEN** a manager cancels a planned collection
- **THEN** the collection is `Cancelled` and the command does not recreate it for that period

#### Scenario: Paid collection cannot be cancelled

- **WHEN** a manager tries to cancel a paid collection
- **THEN** the action is refused

#### Scenario: Organization sees own collections

- **WHEN** a confirmed user of an organization opens its agreements page
- **THEN** the organization's collections are listed with status and amount and no bank data

