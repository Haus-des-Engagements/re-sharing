## 1. Setup and editor spike

- [x] 1.1 Add `nh3` to the dependencies in `pyproject.toml` and update the lock file.
- [x] 1.2 Spike in the browser (no production code): initialise TinyMCE on the body textarea with `convert_urls: False`, `relative_urls: False`, `entity_encoding: "raw"`, insert a link to `https://{{ domain }}/x` and a `{{ total_amount|floatformat:"2" }}` in text, and note the exact HTML the editor submits. Use the observed strings as test inputs in group 2.

## 2. Formatting helpers (red/green)

- [x] 2.1 Create `re_sharing/organizations/tests/test_email_formatting.py` with failing tests for `normalize_template_tags`: entity-encoded quotes and `&gt;` inside `{{ }}` / `{% %}` are restored, percent-encoded `{{ }}` inside `href` is decoded, text outside tags is untouched.
- [x] 2.2 Add failing tests for `sanitize_email_html`: whitelisted tags pass, `script`, event-handler attributes and `javascript:` targets are removed, `http`/`https`/`mailto` targets are kept.
- [x] 2.3 Add failing tests for `html_to_text`: paragraphs and `<br>` become line breaks, `ul` items get `- `, `ol` items get their number, links become `text (url)` or the bare URL when identical, entities are decoded.
- [x] 2.4 Implement the three functions in `re_sharing/organizations/email_formatting.py` (`nh3` for sanitising, `html.parser.HTMLParser` for the text conversion). Run tests (green).

## 3. Email task: multipart and recipient override (red/green)

- [x] 3.1 In `re_sharing/organizations/tests/test_mails.py`, add failing tests: the message has an HTML alternative and a plain-text body; an organization name with `&` and `<` is escaped in the HTML part and unescaped in the text part and subject; template tags in an `href` are resolved in both parts; submitted `script` markup is absent from the HTML part.
- [x] 3.2 Add failing tests for `recipient_override`: the message goes only to the override, has no BCC, the subject starts with `[Test] `, and the content matches the organization's regular rendering.
- [x] 3.3 Add the wrapper template `re_sharing/templates/organizations/email/custom_email.html` (minimal document, inline font and max-width, no branding).
- [x] 3.4 Implement in `send_custom_organization_email`: normalise tags, render the body with `autoescape=True`, sanitise, wrap, derive the text part, send as `EmailMultiAlternatives`; add the optional `recipient_override` argument. Update the docstring. Adjust existing custom-email tests that assert on `body`. Run tests (green).

## 4. Compose form and real send (red/green)

- [x] 4.1 Add failing tests in `re_sharing/organizations/tests/test_forms.py` (or the existing forms test module) for `CustomEmailComposeForm`: subject and body required, a body of only empty markup is invalid, `test_recipient` optional but validated as an email address.
- [x] 4.2 Implement `CustomEmailComposeForm` in `re_sharing/organizations/forms.py` with the `TinyMCE` widget and the page-specific editor settings from the design. Run tests (green).
- [x] 4.3 In `test_views.py`, add failing tests: the GET page context contains the compose form with the manager's email as initial `test_recipient` and the response includes the editor assets; the send view rejects an empty-markup body; a filled `test_recipient` does not change the real send.
- [x] 4.4 Wire the form into `custom_organization_email_view` and `send_custom_organization_email_view`. Run tests (green).

## 5. Test-send endpoint (red/green)

- [x] 5.1 Add failing view tests for `send-custom-organization-email-test`: non-manager rejected; valid request enqueues exactly one task with `recipient_override` and the first selected matching organization; invalid address, missing address, no selected organization and invalid filters enqueue nothing and return an error fragment; the success fragment names the address and the organization.
- [x] 5.2 Implement the view and URL in `re_sharing/organizations/views.py` / `urls.py`, returning a small alert fragment (`organizations/partials/custom_email_test_result.html`). Share the filter parsing and organization lookup with the real send view. Run tests (green).

## 6. Template

- [x] 6.1 In `custom_organization_email.html`, render `{{ form.media }}`, the subject field and the editor-backed body field; remove `required` from the textarea; make `validateAndConfirm()` call `tinymce.triggerSave()` and reject an empty body.
- [x] 6.2 Add the test-send controls: recipient input, button with `hx-post` to the test endpoint, result container, and a `tinymce.triggerSave()` before the htmx request.
- [x] 6.3 Update the template-tag help: add `domain` and the note that tags work inside link targets. Add a view test asserting `domain` is listed.
- [ ] 6.4 Manual check in the browser: compose with bold, a list and a link to `https://{{ domain }}/…`, test-send to an own address, confirm the draft stays, and check HTML and plain-text parts in the received mail.

## 7. Documentation and verification

- [x] 7.1 Add a short ADR in `docs/ADR/` on HTML emails: render with autoescape, sanitise the rendered output, derive the plain-text part; scope limited to custom emails for now.
- [x] 7.2 Run the full suite with coverage (`export DJANGO_READ_DOT_ENV_FILE=true && python -m pytest --cov=re_sharing`) and confirm coverage stays above 95% for the touched modules.
- [x] 7.3 Run `pre-commit run --all-files` and fix any ruff, django-upgrade or djlint findings.
