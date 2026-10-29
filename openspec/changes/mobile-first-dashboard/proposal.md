## Why

The user dashboard (`/dashboard/`) is built from wide tables (up to 7 columns) inside `table-responsive`. On a phone the status and the details link sit off-screen behind horizontal scrolling, the "create" buttons wrap inside the headings, and empty-state texts are emitted as invalid HTML inside `<tbody>` and float above the tables. Many users check their next booking on the go, so the dashboard should be designed for small screens first.

## What Changes

- Rebuild the dashboard template mobile-first: every section (organizations, upcoming bookings, equipment loans for managers) becomes a full-width Bootstrap card with a flush list group; the **same single-column layout** is used on phones and desktops.
- Section order stays: organizations, upcoming bookings, equipment loans.
- Each organization, booking and loan is one tappable row linking to its detail page; the separate "Details" buttons are removed.
- Create actions ("New Organization", "New Booking Request", "Borrow Equipment") move into the card headers; on narrow screens they shrink to an icon with an accessible label.
- Empty states are rendered as rows inside their card (fixes the invalid `<em>` in `<tbody>`).
- Booking dates use a short format (weekday abbreviation + day.month.) instead of the full weekday and year.
- The single-item breadcrumb on the dashboard is removed.
- Depends on `upgrade-bootstrap-5-3-8` being done first.

## Capabilities

### New Capabilities
- `user-dashboard`: layout and content of the logged-in user's dashboard — sections, their order, what each row shows and links to, create actions, empty states, small-screen behaviour.

### Modified Capabilities
<!-- none: the free-bookings display requirement in organization-free-bookings stays valid (each organization still has its own row) -->

## Impact

- `re_sharing/templates/dashboards/users_bookings_and_permissions.html` (rewrite), possibly small partials under `templates/dashboards/`
- `re_sharing/dashboards/tests/test_views.py` (new content assertions)
- Maybe a few lines in `re_sharing/static/css/project.css`
- No changes to views, services, URLs or models; new/changed UI strings need German translations
