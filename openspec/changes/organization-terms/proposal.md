## Why

Eleven published documents govern what organizations may do, from values and privacy policy to room terms, lending terms and house rules per location. Registration asks for a values checkbox and a signed room usage agreement; nothing records which version an organization accepted or asks for re-acceptance after a change. The signature at registration is a deliberate barrier; everything after it should be a click.

## What Changes

- Registration collects one signed document: the values sheet with the organization's name and address, uploaded as PDF with signing date, in the two renamed fields that held the room usage agreement. One checkbox accepts the other registration documents (privacy acknowledgement, platform terms, internet terms) and is recorded as one acceptance per document. The `values_approval` checkbox leaves; the signature is the approval. Manager confirmation is unchanged.
- Terms documents, versions and acceptances become data in a new `terms` app. A document has scopes: registration, room booking, item lending; optionally a location; and a flag whether it is signed instead of clicked. A version has a label, file or link, publication date, change summary and a re-acceptance flag.
- An acceptance records organization, version, user and time.
- Room and item booking previews show an interstitial with the missing documents and store the acceptance before continuing. Registration documents are checked at every gate, so a changed privacy policy with the re-acceptance flag reappears at the next booking.
- A version with the re-acceptance flag makes the interstitial reappear at the next relevant action; without the flag nothing changes. An admin action announces a version by email.
- The admin shows acceptances per organization; the organization page lists them.
- Existing organizations keep their uploaded room usage agreement as registration document and accept the current room terms at their next booking. No data migration beyond the rename.

### Non-goals

- Signatures on terms. The one signature is at registration; acceptance elsewhere is a click. Signing the registration document online instead of uploading it is the subject of `document-signing`, which uses the signed registration document's current version as its source.
- Re-signing by existing organizations.
- Blocking already confirmed bookings when terms change.
- Editing document content in re-sharing.
- Terms tied to agreement kinds. Contracts are signed when applying (`organization-agreements`, `document-signing`); room and lending terms are accepted at the first booking, which is one click.

## Capabilities

### New Capabilities
- `organization-terms`: terms documents with versions and scopes, acceptance records, the missing-terms selector, the registration document and checkbox, interstitial gating at booking, re-acceptance on new versions, visibility.

### Modified Capabilities

None. Registration requirements in `organization-lifecycle` are unchanged; the form's fields are an implementation detail.

## Impact

- New app `terms`: three models, selector, services, admin, interstitial view and template.
- `organizations`: creation form and template, field rename and removal of `values_approval`, organization page.
- `bookings`: both preview views and the item booking preview call the gate; one shared partial.
- Independent of `organization-agreements`. `document-signing` builds on the renamed fields and the signed registration document.
