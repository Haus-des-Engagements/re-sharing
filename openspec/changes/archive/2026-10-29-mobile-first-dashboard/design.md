## Context

`users_bookings_and_permissions.html` renders three sections as tables: organizations (name, status, free bookings), the next 5 upcoming room bookings (date, timespan, resource, title, organization, status, details button) and, for managers, the 5 latest equipment loans (created, items, period, organization, status, details button). The view and `dashboards/services.py` already deliver everything needed; this is a template-only change. Bootstrap 5.3.8 (after `upgrade-bootstrap-5-3-8`) provides cards and list groups; ADR-0019 keeps us on plain Bootstrap utilities without a build step.

## Goals / Non-Goals

**Goals:**
- Readable without horizontal scrolling at 360px width.
- One markup for all screen sizes; same single-column layout on desktop, cards spanning the full container width.
- Large tap targets: a whole row is the link.
- Valid HTML for empty states.

**Non-Goals:**
- Navbar, logo size and other pages (`base.html` stays untouched).
- Changing what data is shown or how many rows (still max 5 bookings / 5 loans).
- Restyling other list pages (`list-bookings` etc.) — the row partial may be reused there later.

## Decisions

- **Cards + `list-group-flush` instead of tables (option A).** Alternatives: separate mobile cards and desktop table (`d-none d-md-*`) — duplicated markup that drifts; CSS-only stacked table with `data-label` — fights Bootstrap's table styles and degrades screen-reader table semantics. With at most 5 rows per section, a table adds no value.
- **Same layout on desktop, full width.** Sections stacked, each card `w-100`. Inside a row, extra width is used by letting the metadata line flow horizontally (`d-flex flex-wrap gap-*`), not by adding columns.
- **Row anatomy** (`a.list-group-item.list-group-item-action`):
  ```
  ┌──────────────────────────────────────────────┐
  │ Do 30.10. · 18:00–20:00          [Confirmed] │  line 1: when + status badge (ms-auto)
  │ Plenum meeting                               │  line 2: title (fw-semibold, text-break)
  │ Großer Saal · Org XY                         │  line 3: small text-body-secondary
  └──────────────────────────────────────────────┘
  ```
  Organization row: name + status badge / group pills / free-bookings lines (`2026: 2 of 5 used`) underneath. Loan row: period + status / items list / organization.
- **Organization groups**: only groups with `show_on_organization_creation=True` are shown — the others are internal tags (e.g. migration or staff markers) that users never chose. Loaded in `get_users_bookings_and_permissions` with `Prefetch("organization__organization_groups", queryset=…filter(show_on_organization_creation=True).order_by("name"), to_attr="selectable_groups")` plus `select_related("organization")`, so the row needs no extra queries. Rendered as neutral pills (`badge rounded-pill`, border, normal weight) so they don't read as status. Alternative considered: a new `show_to_organizations` flag per group — more control, but needs a migration and form changes for no current need.
- **Card header** = `d-flex align-items-center justify-content-between`: `h2.h5.mb-0` title + `btn btn-sm btn-outline-primary` with the plus icon; label text in `span.d-none.d-sm-inline`, plus `aria-label` on the button so it stays accessible when only the icon shows.
- **Footer links** ("Show all bookings", "booking series") go into `card-footer`.
- **Empty state**: `div.list-group-item.text-body-secondary.fst-italic` inside the list group.
- **Date format**: `D d.m.` (Django localises `D`, e.g. "Do 30.10."); time `H:i–H:i`. Year omitted because upcoming bookings are near-term; loans keep `d.m.Y` on the end date as today.
- **Greeting** stays as `h1` ("Hi, Anna!"), breadcrumb removed.
- **Partials**: one include per row type (`dashboards/_organization_row.html`, `_booking_row.html`, `_loan_row.html`) to keep the page template short and allow reuse later. Optional — inline is acceptable if it stays readable.

## Risks / Trade-offs

- [Desktop users lose the table overview] → Max 5 rows per section; full lists remain at "Show all bookings".
- [Nested links: organization free-bookings or other inner links inside a row link] → Rows contain no inner links; the row is the only link.
- [Long titles / organization names] → `text-break` on title lines, badges `flex-shrink-0`.
- [Translation gaps for new strings] → Add German entries to the `.po` file and compile.
- [Tests asserting markup] → Assert content and URLs (`assertContains` on detail URLs, texts), plus absence of `<table` and `breadcrumb`, not exact class strings.

## Open Questions

- None blocking. Visual check via Playwright screenshots at 375px and 1280px during implementation (needs a non-staff test login).
