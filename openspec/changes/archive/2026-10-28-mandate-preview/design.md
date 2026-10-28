## Decisions

- **Same view, second submit button** named `preview`, as on the application page. "Save mandate" stays first so Enter saves.
- **Unsaved mandate.** `services.mandate_from_form(agreement, form)` builds the `SepaMandate` with `generate_mandate_reference(agreement)`; `create_mandate` saves that instance. The reference counts the agreement's mandates, and only one non-revoked mandate may exist, so the preview shows the reference saving will assign.
- **Same checks as saving.** `create_mandate`'s permission and status checks move to a helper used by both paths, so a closed agreement offers no preview either.
