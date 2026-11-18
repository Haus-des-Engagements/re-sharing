## Why

The manager's agreement list does not show whether an agreement has a SEPA mandate. To find agreements that still lack one, for example after an import or a revocation, a manager has to open each agreement.

## What Changes

- The manager's agreement list gets a column with the reference of the agreement's open mandate, the one that is not revoked, linked to the mandate. A mandate whose signed document is missing is marked as awaiting it. Agreements without an open mandate show a dash.
- The list gets a third filter: with or without an open mandate. It combines with the status and kind filters.
- Out of scope: a separate filter for mandates awaiting the signed document.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `organization-agreements`: the manager list shows the open mandate's reference and is filterable by it.

## Impact

- `re_sharing/agreements/selectors.py`: `manager_agreements` takes a `mandate` filter and prefetches the mandates.
- `re_sharing/agreements/views.py`, `re_sharing/templates/agreements/manager_list_agreements.html`: filter and column.
- Manager guide and German translation.
