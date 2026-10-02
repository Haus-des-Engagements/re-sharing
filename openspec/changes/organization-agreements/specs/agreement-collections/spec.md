## ADDED Requirements

### Requirement: Fee collections are created per billing period

A daily command SHALL create a fee collection for every active agreement whose next billing period starts within the configured lookahead. The collection SHALL copy the agreement's amount and payment method, SHALL reference the agreement's active mandate for direct debit, SHALL have the kind's collection day of the period as due date, and SHALL have status `Planned`. Creation SHALL be idempotent per agreement, kind and period start. No collection SHALL be created for periods starting after the agreement's end date.

#### Scenario: Monthly fee collection

- **WHEN** the command runs on 2027-02-20 with a lookahead of 45 days for a monthly agreement of 120 € with collection day 5
- **THEN** a fee collection for period 2027-03-01 to 2027-03-31 with amount 120 € and due date 2027-03-05 exists
- **AND** running the command again creates no second collection for that period

#### Scenario: Yearly fee collection

- **WHEN** the command runs within the lookahead of the yearly collection date for a member agreement of 60 €
- **THEN** one fee collection for the calendar year with amount 60 € exists

#### Scenario: Amount frozen at creation

- **WHEN** an agreement's amount is changed after a collection was created
- **THEN** the existing collection keeps its amount and only later collections use the new amount

#### Scenario: No collection after end date

- **WHEN** an agreement ends on 2027-03-31
- **THEN** no fee collection with a period start after 2027-03-31 is created

### Requirement: Notification and invoice creation

When a planned fee collection reaches the notification date (due date minus the configured pre-notification days), the system SHALL create an outbound invoice in the accounting system with the collection's due date and store the invoice number on the collection, SHALL send a pre-notification email for direct debit when the kind requires it, SHALL send a payment request email naming the invoice number as purpose for bank transfer, and SHALL set the status to `Notified`. Deposit collections SHALL NOT create invoices.

#### Scenario: Direct debit with per-collection notification

- **WHEN** the notification date of a direct debit fee collection of a kind with per-collection notification is reached
- **THEN** an invoice exists in the accounting system and its number is stored on the collection
- **AND** the organization receives an email naming amount, due date, mandate reference and creditor identifier
- **AND** the collection status is `Notified`

#### Scenario: Direct debit without per-collection notification

- **WHEN** the notification date of a direct debit fee collection of a kind without per-collection notification is reached
- **THEN** the invoice is created and the status is `Notified`
- **AND** no email is sent

#### Scenario: Bank transfer payment request

- **WHEN** the notification date of a bank transfer fee collection is reached
- **THEN** the organization receives an email with amount, due date, the creditor's bank account and the invoice number as payment purpose
- **AND** the collection status is `Notified`

#### Scenario: Invoice creation fails

- **WHEN** the accounting system returns an error on invoice creation
- **THEN** the collection stays `Planned`, no email is sent, and the error is logged

#### Scenario: Deposit has no invoice

- **WHEN** a deposit collection reaches its notification date
- **THEN** the organization receives the payment request email
- **AND** no invoice is created

### Requirement: SEPA collection runs

The system SHALL allow a manager to build a collection run for a chosen collection date from all notified direct debit collections with an active mandate and a due date up to that date. The run SHALL produce a pain.008 CORE XML file stored in private storage, with sequence type RCUR, the collection id as end-to-end id, the invoice number as remittance information, and the creditor identifier from settings. Collections in the run SHALL become `Submitted`. A manager SHALL be able to delete a run while none of its collections is paid, returning them to `Notified`.

#### Scenario: Build a run

- **WHEN** a manager builds a run for 2027-03-05 and three notified direct debit collections are due by then
- **THEN** a run with three transactions and the summed amount exists and its XML file can be downloaded
- **AND** the three collections are `Submitted` and reference the run

#### Scenario: Collection without mandate excluded

- **WHEN** a notified direct debit collection's mandate was revoked
- **THEN** it is not included in a run and is listed as needing attention

#### Scenario: Delete an unpaid run

- **WHEN** a manager deletes a run none of whose collections is paid
- **THEN** its collections are `Notified` again and no longer reference the run

#### Scenario: Delete a run with a paid collection

- **WHEN** a manager deletes a run with at least one paid collection
- **THEN** the action is refused

### Requirement: Payment status synchronisation

A nightly command SHALL read outbound receipts from the accounting system and set collections with a paid invoice to `Paid` with the payment date. Collections still unpaid after due date plus the grace period SHALL become `Overdue` for bank transfer, with one reminder email. Submitted direct debit collections unpaid after the grace period SHALL become `Returned` when a negative bank transaction carrying the invoice number exists, and otherwise SHALL be listed for manager attention.

#### Scenario: Paid invoice

- **WHEN** the sync runs and the accounting system reports the collection's invoice as paid
- **THEN** the collection is `Paid`

#### Scenario: Overdue transfer

- **WHEN** the sync runs 8 days after the due date of an unpaid bank transfer collection with a grace period of 7 days
- **THEN** the collection is `Overdue`
- **AND** the organization receives exactly one reminder email across later runs

#### Scenario: Returned debit

- **WHEN** the sync runs after the grace period for a submitted direct debit collection whose invoice is unpaid and a negative bank transaction with the invoice number exists
- **THEN** the collection is `Returned`

#### Scenario: Unresolved debit

- **WHEN** the sync runs after the grace period for a submitted direct debit collection whose invoice is unpaid and no matching transaction exists
- **THEN** the collection stays `Submitted` and appears in the manager's attention list

#### Scenario: Accounting system unreachable

- **WHEN** the accounting system cannot be reached
- **THEN** no collection status changes and the error is logged

### Requirement: Manual settlement and overview

A manager SHALL be able to mark a deposit, deposit refund or any collection as paid or cancelled by hand with a note. Managers SHALL see collections filterable by status, kind and payment method within their scope. Organization users SHALL see their own collections with status and amount.

#### Scenario: Deposit marked received

- **WHEN** a manager marks a deposit collection as paid with a note
- **THEN** the collection is `Paid` and the note is stored

#### Scenario: Cancel a planned collection

- **WHEN** a manager cancels a planned collection
- **THEN** the collection is `Cancelled` and the command does not recreate it for that period

#### Scenario: Paid collection cannot be cancelled

- **WHEN** a manager tries to cancel a paid collection
- **THEN** the action is refused

#### Scenario: Attention list

- **WHEN** a manager opens the collections overview
- **THEN** overdue, returned, and submitted-past-grace collections are shown first
