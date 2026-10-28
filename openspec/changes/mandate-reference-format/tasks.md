## 1. Reference

- [x] 1.1 Setting `SEPA_MANDATE_REFERENCE_PREFIX`; generator with running number from the database
- [x] 1.2 `create_mandate` retries on a taken reference

## 2. File names

- [x] 2.1 `SepaMandate.document_filename(on)` and storing signed PDFs under it
- [x] 2.2 Generated mandate and preview download under that name, RFC 6266 encoded

## 3. Tests and docs

- [x] 3.1 Tests: numbering, ignored formats, retry, file names
- [x] 3.2 README settings table
