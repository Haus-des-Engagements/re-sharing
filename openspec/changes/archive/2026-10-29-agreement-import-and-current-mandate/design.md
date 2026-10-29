## Decisions

- **Mandate at use, not at creation.** `collections_for_run` selects notified collections whose agreement has an active mandate (a subquery, as only one mandate per agreement is not revoked) and `build_collection_run` writes that mandate to each collection before building the XML. `notify_due_collections` sets it as well, so the pre-notification names the mandate that will be used. Submitted collections are not touched, so a later revocation leaves them as they were.
- **Attention list** uses the same subquery: notified collections whose agreement has no active mandate.
- **django-import-export**, already used in other admins. `AgreementResource` with `ImportExportMixin`, `SepaMandateResource` with `ImportMixin` only. `clean_model_instances` runs `full_clean`, so IBAN checksum, unique reference and the one-open-mandate and one-open-agreement constraints are reported per row in the preview.
- **Identifiers.** Organizations by id (the organization admin already exports them), kinds by slug, agreements by id. Names are not unique.
- **Translation context.** `pgettext_lazy("agreements", "Agreement")` in the agreements models and the collections template; the organizations app keeps the plain msgid.
