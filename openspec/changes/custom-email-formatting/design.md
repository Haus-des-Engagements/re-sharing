## Context

`send_custom_organization_email` (`organizations/mails.py`) renders the manager's subject and body as Django templates with `autoescape=False` and sends a plain-text `EmailMessage`. The compose form in `custom_organization_email.html` is hand-written HTML with a `<textarea name="body" required>`. No email in the project is sent as HTML yet.

`django-tinymce` is installed and configured in `TINYMCE_DEFAULT_CONFIG` with a narrow whitelist (`p, br, strong/b, em/i, ul, ol, li, a[href|target]`); it is used for resource descriptions. htmx is loaded in `base.html`.

Organization names are entered by users, so they are untrusted when placed into HTML. The body itself is written by managers, who are trusted but can paste arbitrary markup.

## Goals / Non-Goals

**Goals:**

- Bold, italic, lists and links in custom emails, with a usable plain-text fallback.
- `{{ … }}` works in text and inside link targets.
- Test-send to a freely entered address that keeps the draft on the page.

**Non-Goals:**

- HTML for `EmailTemplate` system emails.
- Branded layout, images, colours, attachments.
- Saving drafts or reusing custom emails.
- A shared HTML email helper for other apps (extract later if system emails follow).

## Decisions

### 1. Reuse TinyMCE through a small Django form

Add `CustomEmailComposeForm` (`subject`, `body` with the `TinyMCE` widget, optional `test_recipient` as `EmailField`) and render `{{ form.media }}` plus the fields in the existing template. The filter fields stay hand-parsed as today.

The widget gets page-specific settings on top of `TINYMCE_DEFAULT_CONFIG`: `convert_urls: False`, `relative_urls: False`, `entity_encoding: "raw"`, so the editor leaves `{{ … }}` in link targets alone.

- Why not Markdown: needs a new concept for managers and a new dependency; TinyMCE is already known from resource descriptions.
- Why a form rather than hand-initialising the editor in JS: `form.media` loads the right assets, and the form validates subject, body and the test address in one place.

### 2. Render once, sanitise the result, derive the text part

```
body (editor HTML with template tags)
  │ normalise template tags (decision 3)
  ▼
Template(body).render(Context(ctx, autoescape=True))
  │
  ▼
nh3.clean(…, whitelist)  ──▶ wrap in organizations/email/custom_email.html ──▶ text/html
  │
  ▼
html_to_text(…)  ──▶ text/plain
```

- Autoescape is on for the body, so an organization named `A & B <x>` cannot break or inject markup. The subject is still rendered with `autoescape=False` because it is plain text.
- Sanitising happens after rendering, per recipient. This sanitises what is actually sent and avoids the sanitiser's URL check rejecting an `href` that still contains `{{ domain }}`.
- Whitelist mirrors the editor: tags `p, br, strong, b, em, i, ul, ol, li, a`; attributes `href`, `target` on `a`; URL schemes `http`, `https`, `mailto`.
- `nh3` over `bleach`: `bleach` is deprecated; `nh3` is small and maintained.
- The message is an `EmailMultiAlternatives` with the text part as body and the HTML part attached as alternative.

### 3. Normalise template tags before rendering

Editors encode characters inside what they consider text or URLs: `"` → `&quot;`, `>` → `&gt;` in text, and possibly `{{ domain }}` → `%7B%7B%20domain%20%7D%7D` in `href`. A small function restores the content of every `{{ … }}` and `{% … %}` (HTML-unescape) and decodes percent-encoded tag delimiters inside `href` values before the template is compiled.

Spike result (TinyMCE 7.8, headless browser): the editor settings from decision 1 are not enough. The link dialog submits `https://{{%20domain%20}}/x` (braces kept, spaces percent-encoded) with and without `convert_urls: False`, and `>` inside a tag in text arrives as `&gt;`. Quotes in text are left alone. The normaliser is therefore required, not just a safety net; it also accepts fully percent-encoded braces so the server does not depend on the editor version. Percent-decoding is limited to `{{ … }}` inside `href` values so ordinary encoded URLs stay intact.

### 4. Plain-text fallback with the standard library

`html_to_text` is an `html.parser.HTMLParser` subclass handling only the whitelisted tags: paragraphs and `<br>` become line breaks, `<li>` becomes `- item` or `1. item`, `<a href="u">t</a>` becomes `t (u)` (just `u` when text and URL are equal). Entities are decoded.

- Why not `strip_tags`: drops link URLs and list markers, which makes the fallback useless for the main use case (links).
- Why not `html2text`: another dependency for about forty lines over a fixed whitelist.

Both helpers live in a new module `re_sharing/organizations/email_formatting.py` so `mails.py` stays about sending.

### 5. Test-send via htmx to a separate endpoint

A second button in the compose form posts the same form with `hx-post` to a new manager-only view `send-custom-organization-email-test`, which returns a small alert fragment into a result container. The page does not reload, so subject, body, filters and selection stay as they are. `tinymce.triggerSave()` runs before the request so the textarea holds the current editor content.

The view validates the form (`test_recipient` required here), re-applies the filters, picks the first selected organization that still matches (preview order) and enqueues the existing task with a new optional argument `recipient_override`. With an override the task:

- sends only to that address,
- adds no BCC,
- prefixes the subject with `[Test] `.

Everything else (context, statistics, rendering) is identical to the real send, which is the point of the test. The address field is prefilled with the manager's own email.

- Why not a redirect like the real send: it would discard the draft, defeating the purpose.
- Why enqueue rather than send inline: one code path, and SMTP errors are handled the same way as for real sends.

### 6. `required` moves out of the textarea

TinyMCE hides the textarea; a hidden `required` field blocks submission without a visible message. The widget is rendered without `required`, `validateAndConfirm()` calls `tinymce.triggerSave()` and checks for an empty body, and the server keeps rejecting an empty body (also when it is only empty markup such as `<p></p>`).

## Risks / Trade-offs

- [Email clients render HTML inconsistently] → only basic inline tags and a wrapper with inline styles (font, max width); no CSS classes, tables or images.
- [Tasks enqueued before deployment carry plain-text bodies and would lose their line breaks] → the email queue is short-lived; deploy when no custom emails are pending.
- [Managers paste rich content from other tools] → the editor strips it to the whitelist, and the server sanitises again.
- [Test email uses one organization's data] → the result fragment names the organization the test was rendered for.
- [Template syntax errors in the body surface only in the worker] → unchanged from today; the test-send makes them visible before the real send.
- [First HTML email in the project] → record the approach (render, sanitise, derive text) in a short ADR so system emails can follow the same path later.
