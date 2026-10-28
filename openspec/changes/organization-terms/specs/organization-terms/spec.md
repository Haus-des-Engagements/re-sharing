## ADDED Requirements

### Requirement: Registration collects one signed document and the registration terms

The organization creation form SHALL require a signed registration document (PDF, private storage) with its signing date, SHALL render one required checkbox naming every active clicked terms document with the registration scope with a link to its current version, and SHALL NOT contain a values approval checkbox. On creation the system SHALL record an acceptance of the current version of each registration document for the organization with the creating user, the signed document included.

#### Scenario: Registration with documents configured

- **WHEN** a user creates an organization with a signed PDF, a signing date and the terms checkbox checked while privacy, platform and internet terms carry the registration scope
- **THEN** the organization stores the document and date
- **AND** an acceptance of the current version of each registration document exists for the organization with that user

#### Scenario: Missing checkbox

- **WHEN** a user submits the creation form without checking the terms checkbox
- **THEN** the form is rejected naming the documents

#### Scenario: No registration documents configured

- **WHEN** no active document has the registration scope
- **THEN** the creation form shows no terms checkbox and the organization can be created with the signed document alone

#### Scenario: Non-PDF registration document

- **WHEN** a user uploads a non-PDF file as registration document
- **THEN** the form is rejected

### Requirement: Terms documents, scopes and versions are configuration

Staff SHALL manage terms documents with scopes (registration, room booking, item lending, any combination or none), an optional location and a signature flag, and versions with label, file or link, publication date, change summary and a re-acceptance flag. The signature flag SHALL be allowed only on registration documents and on at most one active document; versions of such documents SHALL have a file. The current version SHALL be the latest version whose publication date is not in the future. Inactive documents and documents without a current version SHALL never be required.

#### Scenario: Future version not yet current

- **WHEN** a document has version 1 published last year and version 2 published next month
- **THEN** version 1 is the current version

#### Scenario: Inactive document

- **WHEN** a document is marked inactive
- **THEN** no organization is asked to accept it

#### Scenario: Location-specific document

- **WHEN** a house rules document is bound to location A
- **THEN** it is required for room bookings at location A and not at location B

#### Scenario: Second signed document refused

- **WHEN** staff set the signature flag on a second active document
- **THEN** the document is not saved and a validation error is shown

### Requirement: Missing terms are determined per organization and scope

The system SHALL determine, for an organization and a scope, the current versions it must accept: every active clicked document carrying that scope or the registration scope is missing when the organization accepted no version of it, or when a version with the re-acceptance flag was published after the latest version the organization accepted. A version without the flag SHALL NOT make a document missing for organizations that accepted an earlier version. The signed registration document SHALL never be missing.

#### Scenario: Never accepted

- **WHEN** an organization has no acceptance of a room terms document
- **THEN** its current version is missing for the room booking scope

#### Scenario: New version without re-acceptance

- **WHEN** an organization accepted version 1 and version 2 is published without the flag
- **THEN** nothing is missing for that document

#### Scenario: New version with re-acceptance

- **WHEN** an organization accepted version 1 and version 2 is published with the flag
- **THEN** version 2 is missing

#### Scenario: Accepted after re-acceptance

- **WHEN** an organization accepts version 2
- **THEN** nothing is missing for that document

#### Scenario: Changed registration document at a booking gate

- **WHEN** the privacy policy receives a version with the flag and the organization accepted the current room terms
- **THEN** only the privacy policy is missing for the room booking scope

### Requirement: Interstitial at room and item booking previews

Room booking previews SHALL check the room booking scope with the booking's location, and the item booking preview SHALL check the item lending scope. When documents are missing, the system SHALL show an interstitial listing each missing document with its link and a checkbox, SHALL store one acceptance per document on submit with the acting user, and SHALL then return to the preview with the entered booking data intact. When nothing is missing the preview SHALL open directly.

#### Scenario: Booker accepts room terms

- **WHEN** a booker of an organization that never accepted the room terms opens a room booking preview
- **THEN** the interstitial lists the room terms
- **AND** after checking and submitting, acceptances with that user exist and the preview shows the originally entered booking

#### Scenario: Nothing missing

- **WHEN** a booker of an organization that accepted all current room booking documents opens a preview
- **THEN** no interstitial is shown

#### Scenario: Item lending terms

- **WHEN** a user of an organization that never accepted the lending terms opens the item booking preview
- **THEN** the interstitial lists the lending terms and not the room terms

#### Scenario: Unsafe next URL

- **WHEN** the interstitial is called with an external next URL
- **THEN** the system redirects to the organization page after acceptance instead

### Requirement: Announcing a version

Staff SHALL be able to trigger an announcement email for a version to the admins of all confirmed organizations, naming the document, the change summary and whether re-acceptance is required. Publishing a version SHALL NOT send an email by itself.

#### Scenario: Announcement triggered

- **WHEN** staff run the announce action on a version with the re-acceptance flag
- **THEN** every admin of a confirmed organization receives one email naming the document and that re-acceptance is required

#### Scenario: Publication without announcement

- **WHEN** a version is created
- **THEN** no email is sent

### Requirement: Visibility

The organization page SHALL list the organization's acceptances with version, user and time to its confirmed users and to managers. The admin SHALL list acceptances read-only, filterable by organization and document.

#### Scenario: Acceptances on the organization page

- **WHEN** a confirmed user opens the organization page
- **THEN** the accepted documents with version label, user and time are listed

### Requirement: Existing data is kept

The fields holding the former usage agreement SHALL be renamed and keep their files and dates. The values approval boolean SHALL be removed. Existing organizations SHALL NOT receive acceptances by migration and SHALL be asked for the current documents at their next gated action.

#### Scenario: Existing upload preserved

- **WHEN** the migration runs for an organization with a usage agreement dated 2025-09-01
- **THEN** the organization's registration document and date are that file and date

#### Scenario: Existing organization at next booking

- **WHEN** an organization registered before this change opens a room booking preview
- **THEN** the interstitial lists the current room booking and registration documents
