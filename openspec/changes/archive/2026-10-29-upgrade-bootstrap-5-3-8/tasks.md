## 1. Tests first (red)

- [x] 1.1 Add a test that reads the vendored `bootstrap.min.css` and `bootstrap.bundle.min.js` and asserts the header contains `v5.3.8` (fails on 5.3.3)
- [x] 1.2 Add a view test: a page extending `base.html` (e.g. home) references `bootstrap.bundle.min.js` and not `bootstrap.bundle.js`
- [x] 1.3 Add the same assertion for the bookings webview page

## 2. Upgrade (green)

- [x] 2.1 `npm pack bootstrap@5.3.8` in the scratchpad, extract, and copy `dist/css/bootstrap.css`, `bootstrap.min.css` (+ maps) into `re_sharing/static/css/bootstrap/`
- [x] 2.2 Copy `dist/js/bootstrap.bundle.js`, `bootstrap.bundle.min.js` (+ maps) into `re_sharing/static/js/vendors/bootstrap/`
- [x] 2.3 Delete the unused `bootstrap.rtl*.css(.map)` files
- [x] 2.4 Switch `base.html` and `bookings/list-bookings-webview.html` to `bootstrap.bundle.min.js`
- [x] 2.5 Update ADR-0019 consequences/config line if it names a version (keep it generic otherwise) — no change needed, ADR only says "Bootstrap 5"

## 3. Verify

- [x] 3.1 Click through navbar collapse (mobile width), Management dropdown, a modal, a crispy form, the planner table and status badges in the dev server — checked logged out: navbar collapse, forms, cards, no JS errors; Management dropdown and modals still to check with a manager login
- [x] 3.2 Run the full test suite and pre-commit, fix all errors
