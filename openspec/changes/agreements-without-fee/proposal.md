## Why

Some agreements carry no fee, for example a membership free of charge. They could not be entered: the agreement refused every amount that was not above zero, in the admin and in the spreadsheet import, whatever the kind's minimum amount, and an empty amount failed as a missing value. The manager forms asked for at least one cent as well.

## What Changes

- An agreement's amount may be zero. Only negative amounts are refused.
- The spreadsheet import, the admin and the manager forms for creating and editing accept zero, whatever the kind's minimum amount, which does not bind staff and managers anyway. The import treats an empty amount as zero.
- Applicants still enter an amount above zero and at least the kind's minimum.
- An agreement with amount zero is never collected: no regular fee collections and no prorated first period at approval.
- Out of scope: approving an agreement without a fee still requires a signed SEPA mandate.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `organization-agreements`: the amount may be zero for staff, the import and managers; applicants need an amount above zero.
- `agreement-collections`: agreements with amount zero get no fee collections.

## Impact

- `re_sharing/agreements/models.py`: `Agreement.clean` refuses only negative amounts.
- `re_sharing/agreements/resources.py`: the import's amount defaults to zero.
- `re_sharing/agreements/forms.py`: manager forms accept zero; the applicant rule moves into `clean_amount`.
- `re_sharing/agreements/services_collections.py`: `create_due_collections` and `create_first_period_collection` skip agreements without an amount.
- Manager guide: the import table names the option.
