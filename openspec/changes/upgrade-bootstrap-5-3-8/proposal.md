## Why

The vendored Bootstrap is 5.3.3 (Feb 2024); the latest stable release is 5.3.8 with three patch releases of bug fixes. The upcoming mobile-first dashboard (`mobile-first-dashboard`) builds on Bootstrap's card and list-group components, so the base should be current first. On top of that, every page loads the unminified `bootstrap.bundle.js` instead of the minified file that is already vendored.

## What Changes

- Replace the vendored Bootstrap CSS and JS (5.3.3) with 5.3.8 from the official distribution.
- Load the minified `bootstrap.bundle.min.js` instead of the unminified bundle in `base.html` and `bookings/list-bookings-webview.html`.
- Remove the unused RTL stylesheets (`bootstrap.rtl*.css`) from the vendored files.
- Bootstrap 6 (currently alpha) is explicitly out of scope.

## Capabilities

### New Capabilities
- `frontend-assets`: which Bootstrap version the application serves and that it serves the minified, locally hosted build.

### Modified Capabilities
<!-- none -->

## Impact

- `re_sharing/static/css/bootstrap/`, `re_sharing/static/js/vendors/bootstrap/`
- `re_sharing/templates/base.html`, `re_sharing/templates/bookings/list-bookings-webview.html`
- Every page (shared base template); patch release, no breaking changes expected. Visual check of navbar, dropdowns, modals, forms, planner tables.
