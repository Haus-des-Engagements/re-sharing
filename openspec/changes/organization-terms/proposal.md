## Why

Eleven published documents govern what organizations may do, from values and privacy policy to room terms, lending terms and house rules per location. Registration asks for a values checkbox and a signed room usage agreement; nothing records which version an organization accepted or asks for re-acceptance after a change. A member who signed a membership contract signs the room agreement again. The signature at registration is a deliberate barrier; everything after it should be a click.

## What Changes

- Registration collects one signed document: the values sheet with the organization's name and address, uploaded as PDF with signing date, in the two renamed fields that held the room usage agreement. Checkboxes for privacy acknowledgement, platform terms and internet terms are recorded as acceptances. The `values_approval` checkbox leaves; the signature is the approval. Manager confirmation is unchanged.
- Terms documents, versions and acceptances become data in the `agreements` app. A document has one or more scopes: registration, room booking, item lending, or an agreement kind; optionally a location. A version has a label, file or link, publication date, change summary and a re-acceptance flag.
- An acceptance records organization, version, user and time.
- Room and item booking previews and agreement applications show an interstitial with the missing documents and store the acceptance before continuing. The room terms carry the room booking scope and every agreement kind, so a member who accepted them while applying is not asked again at the first booking.
- A document can be restricted to acceptance by organization admins; a booker is then told whom to ask.
- A version with the re-acceptance flag makes the interstitial reappear at the next relevant action; without the flag nothing changes. An admin action announces a version by email.
- Managers see on the organization list which organizations lack a current acceptance; the admin shows acceptances per organization.
- Existing organizations keep their uploaded room usage agreement as registration document and accept the current room terms at their next booking. No data migration beyond the rename.

### Non-goals

- Signatures on terms. The one signature is at registration; acceptance elsewhere is a click.
- A new values sheet or a digital signature. The current values document is signed as is; the upload is the place a digital signature can replace later.
- Re-signing by existing organizations.
- Blocking already confirmed bookings when terms change.
- Editing document content in re-sharing.

## Capabilities

### New Capabilities
- `organization-terms`: terms documents with versions and scopes, acceptance records, the missing-terms selector, the registration document and checkboxes, interstitial gating at booking and application, re-acceptance on new versions, manager visibility.

### Modified Capabilities

None. Registration requirements in `organization-lifecycle` are unchanged; the form's fields are an implementation detail.

## Impact

- `agreements`: three new models, selector, services, admin, interstitial view and template.
- `organizations`: creation form and template, field rename and removal of `values_approval`, organization page, manager list column.
- `bookings`: both preview views and the item booking preview call the gate; one shared partial.
- If shipped before `organization-agreements`, it creates the app skeleton; the kind scope is wired once kinds exist.
