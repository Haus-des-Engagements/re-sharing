"""
Helpers for emails whose body is written in the rich-text editor.

The body arrives as editor HTML containing Django template tags. It is
normalised, rendered, sanitised and finally converted to a plain-text
alternative:

    normalize_template_tags -> Template.render -> sanitize_email_html -> html_to_text
"""

import html
import re
from html.parser import HTMLParser
from urllib.parse import unquote

import nh3

ALLOWED_TAGS = {"p", "br", "strong", "b", "em", "i", "ul", "ol", "li", "a"}
ALLOWED_ATTRIBUTES = {"a": {"href", "target"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}

_HREF_RE = re.compile(r'href="([^"]*)"')
_ENCODED_BRACE_RE = re.compile(r"%7B|%7D", re.IGNORECASE)
_VARIABLE_TAG_RE = re.compile(r"\{\{.*?\}\}", re.DOTALL)
_TEMPLATE_TAG_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def _decode_href(match: re.Match) -> str:
    href = _ENCODED_BRACE_RE.sub(
        lambda brace: unquote(brace.group()),
        match.group(1),
    )
    href = _VARIABLE_TAG_RE.sub(lambda tag: unquote(tag.group()), href)
    return f'href="{href}"'


def normalize_template_tags(body: str) -> str:
    """
    Undo the encoding the editor applies inside template tags.

    The editor percent-encodes spaces (and possibly braces) of tags in link
    targets and entity-encodes characters such as ``"`` and ``>`` in text.
    Only the tags themselves are restored; everything else is left as is.
    """
    body = _HREF_RE.sub(_decode_href, body)
    return _TEMPLATE_TAG_RE.sub(
        lambda tag: html.unescape(tag.group()).replace("\xa0", " "),
        body,
    )


def sanitize_email_html(body: str) -> str:
    """Reduce HTML to the formatting the editor offers."""
    return nh3.clean(
        body,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel=None,
    )


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        # One entry per open list: the last item number for <ol>, None for <ul>
        self._lists: list[int | None] = []
        self._links: list[tuple[str | None, int]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.parts.append("\n")
        elif tag in ("ul", "ol"):
            self._end_line()
            self._lists.append(0 if tag == "ol" else None)
        elif tag == "li":
            self._end_line()
            self.parts.append(self._list_marker())
        elif tag == "a":
            self._links.append((dict(attrs).get("href"), len(self.parts)))

    def handle_endtag(self, tag):
        if tag == "p":
            self.parts.append("\n\n")
        elif tag in ("ul", "ol") and self._lists:
            self._lists.pop()
            self._end_line()
            # A nested list ends inside its parent item, a top-level one ends a block
            if not self._lists:
                self.parts.append("\n")
        elif tag == "li":
            self._end_line()
        elif tag == "a" and self._links:
            href, start = self._links.pop()
            text = "".join(self.parts[start:]).strip()
            if href and href not in (text, f"mailto:{text}"):
                self.parts.append(f" ({href})")

    def handle_data(self, data):
        # Line breaks between block elements are source formatting, not content
        if "\n" in data and not data.strip():
            return
        self.parts.append(data)

    def _end_line(self):
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def _list_marker(self) -> str:
        if not self._lists:
            return "- "
        indent = "  " * (len(self._lists) - 1)
        number = self._lists[-1]
        if number is None:
            return f"{indent}- "
        self._lists[-1] = number + 1
        return f"{indent}{number + 1}. "


def html_to_text(body: str) -> str:
    """
    Convert editor HTML to plain text.

    Paragraphs and line breaks become line breaks, list items keep a marker
    and links are followed by their target in parentheses.
    """
    extractor = _TextExtractor()
    extractor.feed(body)
    extractor.close()
    lines = [line.rstrip() for line in "".join(extractor.parts).splitlines()]
    text = "\n".join(lines)
    return _BLANK_LINES_RE.sub("\n\n", text).strip()
