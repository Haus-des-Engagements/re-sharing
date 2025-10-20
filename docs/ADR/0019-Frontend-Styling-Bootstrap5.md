# 19. Frontend Styling - Bootstrap 5

Date: 2025-01-20

## Status

Accepted

## Context

The booking platform requires a responsive, accessible, and professional user interface. As a small project with limited frontend development resources, we need a CSS framework that provides:
* Pre-built, responsive components
* Consistent design system
* Good documentation and community support
* Accessibility features out of the box
* Integration with Django forms
* Low learning curve for developers primarily focused on backend

The project uses Django templates for server-side rendering combined with htmx for dynamic interactions (see ADR-0011). The frontend framework needs to complement this architecture rather than require a separate JavaScript build system.

We considered the following options:
1. **Bootstrap 5** - Popular, comprehensive CSS framework
2. **Tailwind CSS** - Utility-first CSS framework
3. **Bulma** - Modern CSS framework based on Flexbox
4. **Custom CSS** - Build our own design system
5. **Material Design** (via Materialize or Material-UI)

Key evaluation criteria:
* Component library completeness (forms, navigation, modals, alerts)
* Django integration quality (especially form rendering)
* File size and performance
* Customization capabilities
* German language support for error messages
* Integration with htmx patterns
* Long-term maintenance and stability

## Decision

We will use **Bootstrap 5** as our primary CSS framework with the following supporting libraries:
* **django-crispy-forms** with **crispy-bootstrap5** for form rendering
* **Alpine.js** (v3.14.3) for lightweight JavaScript interactivity
* **HTMX** (v2.0.1) for dynamic HTML updates (covered in ADR-0011)

Configuration:
* CRISPY_TEMPLATE_PACK = "bootstrap5"
* Bootstrap CSS and JavaScript served from local static files
* Custom CSS additions in `/re_sharing/static/css/` for project-specific styling
* Bootstrap icons for consistent iconography

Integration approach:
* Django templates extend Bootstrap base templates
* Forms rendered via crispy-forms with Bootstrap 5 styling
* htmx attributes integrated into Bootstrap components (modals, alerts, forms)
* Alpine.js used for client-side state management and simple interactions

## Consequences

* The project has a dependency on Bootstrap's design decisions and class naming
* Bootstrap 5 provides a professional, corporate look that may not feel unique
* All developers need to learn Bootstrap's class naming conventions and grid system
* Form rendering is consistent across the application via crispy-forms
* Bootstrap's JavaScript components (modals, dropdowns, tooltips) are available
* The framework is well-documented, reducing onboarding time for new developers
* Bootstrap updates (v5.x → v6.x) will require migration effort
* File size is larger than Tailwind's purged CSS but acceptable for the project scale
* Responsive design is straightforward using Bootstrap's grid and utility classes
* Accessibility features (ARIA attributes, keyboard navigation) are built-in
* Customization via SCSS variables is possible but not currently implemented
* The framework works seamlessly with server-side rendering (no build step required)
* Integration with htmx is smooth - both use HTML-first approaches
* Alpine.js provides reactivity without the complexity of Vue/React
* Templates are slightly more verbose due to Bootstrap's class-heavy approach
* The multi-page application approach (MPA) with htmx fits Bootstrap's component model
* German translations for form validation work through crispy-forms and Django's i18n
* Bootstrap's utilities reduce the need for custom CSS in most cases
* Upgrading Bootstrap requires testing all UI components for breaking changes
* The design is conventional but trusted - users understand Bootstrap interfaces
