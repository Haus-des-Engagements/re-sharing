## Context

Bootstrap is vendored as static files (ADR-0019: no build step, served locally via whitenoise). The current files are 5.3.3: `css/bootstrap/` holds the plain, minified and RTL variants with source maps; `js/vendors/bootstrap/` holds `bootstrap.bundle.js` and `bootstrap.bundle.min.js` with maps. Two templates reference them: `base.html` and the standalone `bookings/list-bookings-webview.html`, and both load the unminified bundle.

## Goals / Non-Goals

**Goals:**
- Serve Bootstrap 5.3.8 CSS and JS bundle, minified.
- Keep the setup build-free and self-hosted.

**Non-Goals:**
- Bootstrap 6 (alpha only) or a migration to SCSS customization.
- Bootstrap Icons (the project uses its own SVG sprite in `icons.html`).
- Any layout or template redesign (that is `mobile-first-dashboard`).

## Decisions

- **Source the files from the npm package `bootstrap@5.3.8`** (`npm pack`, take `dist/css/bootstrap.css|.min.css` + maps and `dist/js/bootstrap.bundle.js|.min.js` + maps). The npm tarball is integrity-checked by the registry; copying from a CDN would not be. Alternative: GitHub release zip — same content, but more manual.
- **Keep the unminified files and source maps next to the minified ones** for debugging; only templates switch to `.min`.
- **Delete the RTL variants** — the app is German/English only and nothing references them.
- **Guard with a template test** asserting the rendered base page references `bootstrap.min.css` and `bootstrap.bundle.min.js`, and a test that the vendored files' version header reads `v5.3.8`, so an accidental downgrade or switch back to the unminified bundle fails CI.

## Risks / Trade-offs

- [Subtle visual regressions in patch releases] → Manual click-through of navbar (collapse on mobile, Management dropdown), modals, crispy forms, planner/crosshair tables, badges; optionally Playwright screenshots before/after.
- [whitenoise manifest caches old hashed names] → None: hashed filenames change with content, `collectstatic` on deploy picks them up.
- [Webview page served to an embedding context] → It only switches to the minified variant of the same file; check it renders once.
