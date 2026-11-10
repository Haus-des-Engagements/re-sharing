# 26. HTML emails

Date: 2026-11-10

## Status

Accepted

## Context

All emails were sent as plain text. Managers want basic formatting (bold, italic, lists, links) in the custom emails they send to organizations. The body of such an email is written by a manager in a rich-text editor and contains Django template tags that are filled with data of the receiving organization. Organization names and similar values are entered by users and are therefore untrusted when placed into HTML. Rich-text editors encode characters inside template tags, in particular in link targets, and email clients differ widely in the HTML and CSS they support.

## Decision

We will send custom organization emails as multipart messages with an HTML part and a plain-text part, using the following pipeline:

1. Restore template tags the editor has encoded.
2. Render the body with autoescaping switched on. The subject is plain text and is rendered without escaping.
3. Sanitise the rendered result on the server to the formatting the editor offers, using `nh3`.
4. Wrap the result in a minimal HTML document with inline styles and no branding.
5. Derive the plain-text part from the sanitised HTML, keeping link targets and list markers.

We will reuse the existing rich-text editor and its configuration instead of introducing Markdown.

The emails based on `EmailTemplate` stay plain text for now. The helpers live in `organizations/email_formatting.py`.

## Consequences

- Managers can format custom emails and use template tags inside links.
- Recipients whose client shows plain text still get readable links and lists.
- User-supplied values cannot inject markup, and pasted markup outside the whitelist is removed regardless of what the browser submitted.
- `nh3` is a new dependency.
- Sanitising happens per recipient after rendering, which costs a little time per email but checks exactly what is sent.
- The layout is deliberately plain. A branded layout would need email-specific HTML and is a separate decision.
- If the system emails should become HTML later, they can follow the same pipeline; the helpers would then move to a shared place.
