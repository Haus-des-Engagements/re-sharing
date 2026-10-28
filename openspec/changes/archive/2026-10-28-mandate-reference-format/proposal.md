## Why

The paper mandates collected so far carry references like `HDE-VM-008`: one running number across all mandates. Their scans are filed as `HDE-VM-008_SEPA-Lastschriftmandat_<organization>_<signature date>.pdf`. The generated references (`HDE-000042-1`) and stored file names (`<timestamp>_<uuid>_mandate.pdf`) break both conventions, so old and new mandates would be numbered and filed differently.

## What Changes

- **BREAKING** Mandate references become `<prefix>-<running number>`, the number padded to three digits, continuing after the highest number with that prefix in the database. Old paper mandates entered in the admin with their references therefore set where numbering continues.
- A new setting `SEPA_MANDATE_REFERENCE_PREFIX` (default `<SEPA_MANDATE_PREFIX>-VM`) sets the prefix. `SEPA_MANDATE_PREFIX` stays the prefix of collection references.
- Signed mandate PDFs are stored as `mandates/<reference>_SEPA-Lastschriftmandat_<organization>_<signature date>.pdf`, all in one folder, so downloads carry that name.
- The generated mandate downloads under the same name with the download date.

### Non-goals

- Renaming references or files of existing mandates.
- Reserving the reference shown in a preview: if another mandate is saved in between, saving assigns the next free number.

## Capabilities

### New Capabilities

### Modified Capabilities
- `sepa-mandates`: "Mandate reference is generated" uses the running number; adds "Mandate file names".
