## 1. Setup

- [x] 1.1 Add `pypdf` and `reportlab` as dependencies
- [x] 1.2 Add `SEPA_CREDITOR_ADDRESS`, remove `SEPA_MANDATE_FORM_URL` from settings, views, templates, tests and README

## 2. Model

- [x] 2.1 Add `AgreementKind.contract_template` (private storage, PDF validator) and `Agreement.contact_person`; migration
- [x] 2.2 `create_agreement` records the applicant as contact person, with a test

## 3. Documents (red, then green)

- [x] 3.1 Test fixture: a small fillable PDF built in the tests with known field names
- [x] 3.2 Tests and implementation of `template_field_names`, `contract_values(agreement, person)` and `prefilled_contract(agreement, person)`: values per field name, German formatting, detail fields, contact person and fallback, unknown fields untouched, fields stay editable
- [x] 3.3 Tests and implementation of `render_mandate(mandate)`: contains reference, creditor identifier and address, account holder, IBAN, BIC and kind

## 4. Admin, views and pages

- [x] 4.1 Kind admin: read-only overview of template fields, filled or empty; test
- [x] 4.2 Views and routes for the contract and mandate downloads with permission, status and template checks, attachment and no-store headers; tests
- [x] 4.3 Agreement page links the prefilled contract; mandate page links the generated mandate; application success message and page text point to the download

## 5. Wrap-up

- [x] 5.1 Note in the `document-signing` proposal that mandate rendering and the prefilled contract come from this change
- [x] 5.2 German translations, compile messages, README (field-name convention, settings, rollout)
- [x] 5.3 Full test suite and pre-commit
