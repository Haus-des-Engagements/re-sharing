## Why

Custom emails to organizations are composed in a plain textarea and sent as plain text, so managers cannot emphasise text, structure content with lists or hide long URLs behind link text. There is also no way to check how an email looks before it goes out to many organizations.

## What Changes

- The body field on the custom email page becomes a rich-text editor with the formatting already used for resource descriptions: bold, italic, bulleted and numbered lists, links.
- Custom emails are sent as multipart messages: an HTML part in a minimal, unbranded wrapper and a plain-text fallback derived from it that keeps link URLs and list markers.
- Template tags (`{{ … }}`) keep working in running text and additionally work inside link targets (e.g. `https://{{ domain }}/…`).
- Values inserted into the HTML part are HTML-escaped, and the rendered body is reduced server-side to the allowed formatting.
- New test-send: the manager enters a recipient address and receives the email exactly as one of the selected organizations would, without anything being sent to organizations. The composed draft stays on the page.
- The page help additionally lists `domain` as a template tag.
- Out of scope: the `EmailTemplate`-based system emails (booking confirmations etc.) stay plain text; no branded layout (logo, header, footer).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `organization-custom-email`: adds requirements for body formatting, multipart sending, escaping and sanitising, template tags in links, and test-send; the template-tag help requirement gains `domain`.

## Impact

- `re_sharing/organizations/mails.py`: `send_custom_organization_email` builds a multipart message and accepts an optional recipient override.
- `re_sharing/organizations/views.py`, `urls.py`, `forms.py`: compose form with the editor widget, new manager-only test-send endpoint.
- `re_sharing/templates/organizations/custom_organization_email.html`: editor, test-send controls, client-side validation; new HTML email wrapper template.
- New dependency: `nh3` (HTML sanitiser). `django-tinymce` is already installed.
- Existing tests in `organizations/tests/test_mails.py` and `test_views.py` need adjusting to the multipart message.
- No model or migration changes.
