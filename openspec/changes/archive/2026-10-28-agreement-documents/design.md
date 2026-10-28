## Context

Kinds link their contract through the intro text; the mandate page links `SEPA_MANDATE_FORM_URL`. The current membership form is a two-page PDF without form fields: page 1 the application, page 2 a SEPA mandate with the creditor's wording. The stakeholder decided: build a fillable PDF of page 1 with a single amount field, and generate the mandate as a standard document.

The open change `document-signing` planned to render the mandate from data and to take the contract from a terms document. Both remain possible on top of this change.

## Goals / Non-Goals

**Goals:** applicants never retype data re-sharing has; a mandate printed by hand carries its reference and bank data; staff replace a template by uploading a new PDF.

**Non-Goals:** see the proposal.

## Decisions

### D1: Fill AcroForm fields by name

`AgreementKind.contract_template` (PDF, private storage, PDF validator). `agreements/documents.py` fills it with `pypdf`, keeping fields editable so the signer can correct a typo before printing, and sets `NeedAppearances` so viewers render the values. Field names are the contract: `organization_name`, `organization_address` (street, zip and city in one line), `organization_phone`, `organization_email`, `organization_website`, `represented_by_person` (checkbox, ticked), `representative_name`, `representative_function`, `representative_email`, `amount`, `start_date`, `end_date`, `deposit_amount`, `kind_name`, and `detail_<key>` for application fields. Amounts and dates are formatted in German (`80,00`, `01.03.2027`).

Alternative: placing text at coordinates configured per kind. Rejected by the stakeholder in favour of a fillable PDF; it needs no layout configuration and survives a new form version as long as the field names stay.

### D2: Admin overview of template fields

The kind admin shows a read-only list of the template's field names, each marked as filled or left empty, so a misspelt field is visible right after upload.

### D3: Contact person

`Agreement.contact_person` (User, nullable, `SET_NULL`) is set to the applicant in `create_agreement`. The prefilled contract takes the representative's name and email from it, and the function from `contact_person_function`. Without a contact person (manager-created agreements) the downloading organization admin is used; a manager downloading such an agreement gets these fields empty.

### D4: Generated mandate

`render_mandate(mandate)` draws one A4 page with `reportlab`: title "SEPA-Lastschriftmandat", creditor name, `SEPA_CREDITOR_ADDRESS`, creditor identifier, mandate reference, "wiederkehrende Zahlungen", the standard authorization and refund notice for core direct debits, the agreement kind, then debtor organization, address, account holder, bank, IBAN (grouped by four), BIC, and lines for place, date and signature. Built-in Helvetica, so no font files are needed on the server. German only, like the contract.

### D5: Downloads

`GET /agreements/<uuid>/contract.pdf` for those who may administer the agreement, only while it is submitted or active and the kind has a template (404 otherwise). `GET /agreements/mandates/<uuid>/mandate.pdf` for those who may administer the mandate's agreement, not for revoked mandates. Both are rendered per request with `Content-Disposition: attachment` and `Cache-Control: no-store`; nothing is stored.

## Risks / Trade-offs

- [Viewers that ignore `NeedAppearances`] → `pypdf` also writes appearance streams for text fields; checked with poppler and a browser viewer.
- [Template replaced with other field names] → The admin overview shows unfilled fields immediately.
- [Generated mandate wording] → Standard text for core direct debits; the legal check listed in `document-signing` covers it before rollout.

## Migration Plan

1. Deploy, set `SEPA_CREDITOR_ADDRESS`, drop `SEPA_MANDATE_FORM_URL`.
2. Upload the fillable membership form as the membership kind's contract template and check the field overview.
3. Rollback: the setting is unused afterwards; the new columns are nullable.

## Open Questions

None.
