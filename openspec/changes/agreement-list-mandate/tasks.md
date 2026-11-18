## 1. Mandate column and filter (red, then green)

- [x] 1.1 Add tests: the list shows the open mandate's reference with a link, marks a mandate without signed document and leaves out a revoked one; the filter narrows to agreements with and without an open mandate, combines with the status filter and ignores unknown values; the mandates are read in one query
- [x] 1.2 Implement the `mandate` filter and the prefetch in `manager_agreements`, the view context and the column and filter in the template
- [x] 1.3 Describe the column and filter in the manager guide; add the German translation
- [x] 1.4 Run the agreement tests and pre-commit on the changed files
