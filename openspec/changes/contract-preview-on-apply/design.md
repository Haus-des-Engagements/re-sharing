## Context

`apply_view` validates `ApplicationForm` and calls `create_agreement`. `documents.prefilled_contract(agreement, person)` fills the template from an agreement.

## Decisions

- **Same view, second submit button.** The button carries `name="preview"`. `apply_view` validates the form in both cases; with `preview` it returns the PDF instead of creating the agreement. A separate URL would need the same permission checks and form handling twice.
- **Unsaved agreement.** `services.agreement_from_application(organization, kind, form, user)` builds the `Agreement` instance from the cleaned data without saving it; `create_agreement` saves that same instance. The preview and the later download therefore fill identical values. `contract_values` only reads attributes and the kind's fields, so it works on an unsaved instance.
- **No duplicate check for the preview.** Downloading changes nothing; the duplicate check stays on submission.
- **Attachment response.** `_pdf_response` sends the PDF as attachment, so the browser stays on the form and keeps its values.

## Risks / Trade-offs

- An applicant may change the amount after downloading and upload a contract with the old amount. → A hint below the buttons says to download again after changes; managers check the signed contract before approving.
