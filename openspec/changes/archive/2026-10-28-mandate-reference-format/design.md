## Decisions

- **Next number from the database.** The generator reads all references matching `<prefix>-<digits>` exactly, takes the highest number and adds one. References in other formats, such as the earlier `HDE-000042-1`, are ignored. No counter table: mandates are rare, and staff entering old mandates in the admin should move the sequence without extra steps.
- **Concurrent saves.** Two mandates saved at the same moment could get the same number; the unique constraint rejects the second. `create_mandate` retries with a new number a few times inside a savepoint.
- **Readable file name in storage.** Signed PDFs are served from private storage (presigned S3 URLs in production), whose download name is the stored file name. Storing as `mandates/<readable name>.pdf` names downloads correctly without a proxy view and keeps all mandates in one folder. References are unique, so names only repeat when the same mandate is uploaded again with the same signature date; storage then adds a suffix and both files stay.
- **Spaces kept.** Storage replaces spaces with underscores by default. `ReadableNameFileField` stores the name `upload_to` returns as is, after Django's path validation.
- **Longer names.** `signed_document` gets `max_length=255`; the organization part is capped at 80 characters.
- **Organization in file names.** Characters invalid in file names and dots are removed (`Example e.V.` becomes `Example eV`); whitespace is collapsed. Non-ASCII characters stay; the download response encodes the name per RFC 6266.

## Risks / Trade-offs

- A previewed mandate can show a number that another mandate takes before saving. → Rare given how seldom mandates are created; the mandate page shows the assigned reference.
