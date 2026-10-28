## Why

Applicants download a blank contract from a link in the kind's intro text and fill in by hand what re-sharing already knows: organization name, address, phone, email, website, representative, function and amount. The SEPA mandate is a second page of the same paper form, blank as well, although the mandate's reference and bank data are already in the system. Retyping invites mistakes, and a mandate without its reference has to be matched by hand.

## What Changes

- An agreement kind can carry a contract template: a fillable PDF uploaded in the admin. Its form fields are filled by name from the agreement: organization data, representative, function, amount, start and end date, deposit, kind name and the answers of the kind's application fields. Fields with other names stay empty and editable.
- The admin shows which fields an uploaded template contains and which of them re-sharing fills.
- The agreement page offers the prefilled contract for download to the organization's admins and managers in scope, as long as the agreement is open. It is generated on request and not stored.
- The representative is the person who applied, stored as the agreement's contact person; for agreements entered by a manager it is the organization admin who downloads.
- The SEPA mandate becomes a separate, generated document: creditor name, address and identifier, mandate reference, the standard recurring core direct debit wording, debtor organization and address, account holder, bank, IBAN and BIC, place, date and signature lines. The mandate page offers it for download instead of a blank form. It carries the full IBAN, so it is only downloadable by those who may see the mandate and is never emailed.
- **BREAKING** The setting `SEPA_MANDATE_FORM_URL` is removed; a new setting `SEPA_CREDITOR_ADDRESS` is printed on the mandate.
- A fillable version of the current membership form, simplified to one amount field, is provided for upload; it is not part of the repository.

### Non-goals

- Positioning text on PDFs without form fields.
- Storing the prefilled documents, or using them as the signed document: the signed upload stays the record.
- Online signing; the change `document-signing` builds on these documents.
- Kind-specific mandate wording.

## Capabilities

### New Capabilities
- `agreement-documents`: contract templates per kind, the field-name convention, the prefilled contract and the generated mandate.

### Modified Capabilities
- `organization-agreements`: "Signed document" offers the prefilled contract; agreements record their contact person.
- `sepa-mandates`: "One active mandate per agreement" links the generated mandate instead of a blank form.

## Impact

- `agreements`: `AgreementKind.contract_template`, `Agreement.contact_person`, migration, new `documents.py`, two download views, admin field overview, templates, tests.
- New dependencies `pypdf` (filling form fields) and `reportlab` (rendering the mandate).
- Settings: remove `SEPA_MANDATE_FORM_URL`, add `SEPA_CREDITOR_ADDRESS`; README.
- `document-signing` (open change): its mandate rendering and contract source are now provided here; its proposal gets a note.
