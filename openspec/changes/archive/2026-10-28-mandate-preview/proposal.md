## Why

To get a prefilled mandate, an admin has to save the bank data first and download the document on the next page. The form already has everything the mandate needs, and the reference it will get is known in advance, so the mandate can be downloaded before saving, like the contract on the application page.

## What Changes

- The mandate form offers a second button, "Download prefilled mandate". It validates the bank data like saving does and returns the generated mandate with the reference the mandate will get, without saving anything.
- Invalid input shows the form's errors instead of a document.
- The download keeps the entered values in the form, so the signed mandate can be uploaded before saving.
- The form's introduction describes both ways.

### Non-goals

- Reserving the reference: it is the one saving would assign at the time of the download.

## Capabilities

### New Capabilities

### Modified Capabilities
- `agreement-documents`: adds "Prefilled mandate before saving".
