# frontend-assets Specification

## Purpose
Which frontend framework assets the application serves: a self-hosted, build-free Bootstrap of a pinned version, loaded minified by all pages.
## Requirements
### Requirement: Self-hosted Bootstrap 5.3.8

The application SHALL serve Bootstrap 5.3.8 CSS and the Bootstrap 5.3.8 JavaScript bundle from its own static files, without a CDN and without a build step.

#### Scenario: Vendored CSS version

- **WHEN** the vendored `css/bootstrap/bootstrap.min.css` is read
- **THEN** its header names Bootstrap v5.3.8

#### Scenario: Vendored JS version

- **WHEN** the vendored `js/vendors/bootstrap/bootstrap.bundle.min.js` is read
- **THEN** its header names Bootstrap v5.3.8

### Requirement: Minified Bootstrap assets in pages

Pages SHALL load the minified Bootstrap stylesheet and the minified Bootstrap JavaScript bundle.

#### Scenario: Page based on the base template

- **WHEN** a user opens any page extending `base.html`
- **THEN** the HTML references `bootstrap.min.css` and `bootstrap.bundle.min.js` and does not reference the unminified `bootstrap.bundle.js`

#### Scenario: Bookings webview

- **WHEN** the standalone bookings webview is opened
- **THEN** the HTML references `bootstrap.min.css` and `bootstrap.bundle.min.js`

