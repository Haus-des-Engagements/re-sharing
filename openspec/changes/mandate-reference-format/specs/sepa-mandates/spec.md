## MODIFIED Requirements

### Requirement: Mandate reference is generated

The system SHALL generate the mandate reference from a configured prefix and a running number across all mandates, padded to three digits, continuing after the highest number of the references in the database that consist of the prefix, a hyphen and digits. The reference SHALL be unique. References entered through the admin for existing paper mandates SHALL be accepted when unique, and the generator SHALL never produce a reference that already exists.

#### Scenario: Numbering continues after existing mandates

- **WHEN** mandates `HDE-VM-007` and `HDE-VM-008` exist and a new mandate is created with prefix `HDE-VM`
- **THEN** its reference is `HDE-VM-009`

#### Scenario: First mandate reference

- **WHEN** no reference with prefix `HDE-VM` exists and a mandate is created
- **THEN** its reference is `HDE-VM-001`

#### Scenario: Other formats ignored

- **WHEN** only the reference `HDE-000042-1` exists and a mandate is created with prefix `HDE-VM`
- **THEN** its reference is `HDE-VM-001`

#### Scenario: Duplicate reference entered in the admin

- **WHEN** staff enter a reference that already exists on another mandate
- **THEN** the form is rejected

## ADDED Requirements

### Requirement: Mandate file names

Signed mandate PDFs SHALL be stored and downloaded under the name `<reference>_SEPA-Lastschriftmandat_<organization>_<signature date as YYYY-MM-DD>.pdf`, and the generated mandate SHALL download under the same name with the download date. The organization's name SHALL appear without dots and without characters invalid in file names.

#### Scenario: Signed mandate uploaded

- **WHEN** the signed PDF of mandate `HDE-VM-008` of `Example e.V.` signed on 2024-04-15 is uploaded
- **THEN** it is stored as `HDE-VM-008_SEPA-Lastschriftmandat_Example eV_2024-04-15.pdf`

#### Scenario: Generated mandate downloaded

- **WHEN** an admin downloads the generated mandate `HDE-VM-009` on 2026-10-28
- **THEN** the file is named `HDE-VM-009_SEPA-Lastschriftmandat_<organization>_2026-10-28.pdf`
