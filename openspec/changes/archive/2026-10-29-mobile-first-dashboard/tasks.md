## 1. Prerequisite

- [x] 1.1 Confirm `upgrade-bootstrap-5-3-8` is implemented (Bootstrap 5.3.8 served)

## 2. Tests first (red)

- [x] 2.1 Test: dashboard response contains no `<table` and no `breadcrumb`
- [x] 2.2 Test: section order — "My organizations" appears before "My upcoming bookings" in the response; equipment loans section only for managers and after bookings
- [x] 2.3 Test: organization row links to the organization detail URL and shows the status; free-bookings lines still render (existing tests stay green)
- [x] 2.4 Test: booking row links to the booking detail URL and shows short date (`D d.m.`), time span, title, resource, organization and status; no "Details" button text
- [x] 2.5 Test: manager sees loan row linking to the booking group detail URL with items, period, organization, status (items via `BookingGroup.get_items_summary`, e.g. "2 Beamer")
- [x] 2.6 Test: empty states "No upcoming bookings" and "No organizations yet. Go and add yours!" render inside the list group (valid HTML, not in a table)
- [x] 2.7 Test: create links (organization, booking, item booking) present with `aria-label`; footer links to bookings list and booking series list

## 3. Template rewrite (green)

- [x] 3.1 Remove the breadcrumb; keep the greeting `h1`
- [x] 3.2 Build the organizations card: header with title + create button (icon-only below `sm`, `aria-label`), flush list group with row-links, empty state row
- [x] 3.3 Build the upcoming bookings card with the row anatomy from design.md and a card footer with the two list links
- [x] 3.4 Build the equipment loans card (managers only)
- [x] 3.5 Extract row partials (`_organization_row.html`, `_booking_row.html`, `_loan_row.html`) if it keeps the page readable
- [x] 3.6 Add minimal CSS to `project.css` only if utilities are not enough (e.g. badge `flex-shrink-0`) — not needed

## 4. Translations

- [x] 4.1 Run `makemessages` for German, translate new/changed strings, `compilemessages` — all strings already translated, no new msgids

## 5. Verify

- [x] 5.1 Playwright screenshots of the dashboard at 375px and 1280px (regular user and manager); no horizontal scroll at 360px — rendered with test data (no dev DB login), checked 360/375/1280px: no horizontal scroll
- [x] 5.2 Run the full test suite and pre-commit, fix all errors — 1294 passed; the one loan test that failed had been edited mid-run, green on re-run

## 6. Organization groups on organization rows

- [x] 6.1 Test (service): booking permissions come with `organization.selectable_groups` holding only groups with `show_on_organization_creation=True`, sorted by name, in a constant number of queries
- [x] 6.2 Test (view): organization row shows selectable group names and not internal ones
- [x] 6.3 Prefetch selectable groups in `get_users_bookings_and_permissions` (select_related organization + Prefetch with to_attr)
- [x] 6.4 Render the groups as neutral pills in `_organization_row.html`
- [x] 6.5 Re-run screenshots at 375/1280, the dashboard tests and pre-commit
