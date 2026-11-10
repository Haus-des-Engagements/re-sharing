from re_sharing.organizations.email_formatting import html_to_text
from re_sharing.organizations.email_formatting import normalize_template_tags
from re_sharing.organizations.email_formatting import sanitize_email_html


class TestNormalizeTemplateTags:
    def test_restores_spaces_the_editor_encoded_in_link_targets(self):
        # What the editor's link dialog submits for "https://{{ domain }}/x"
        body = '<a href="https://{{%20domain%20}}/x/{{%20organization.slug%20}}/">L</a>'

        assert normalize_template_tags(body) == (
            '<a href="https://{{ domain }}/x/{{ organization.slug }}/">L</a>'
        )

    def test_decodes_percent_encoded_braces_in_link_targets(self):
        body = '<a href="https://%7B%7B%20domain%20%7D%7D/x">Link</a>'

        assert (
            normalize_template_tags(body) == '<a href="https://{{ domain }}/x">Link</a>'
        )

    def test_decodes_lowercase_percent_encoded_braces(self):
        body = '<a href="https://%7b%7bdomain%7d%7d/x">Link</a>'

        assert (
            normalize_template_tags(body) == '<a href="https://{{domain}}/x">Link</a>'
        )

    def test_keeps_percent_encoding_outside_tags_in_link_targets(self):
        body = '<a href="https://example.org/a%20b?q={{%20domain%20}}">L</a>'

        assert normalize_template_tags(body) == (
            '<a href="https://example.org/a%20b?q={{ domain }}">L</a>'
        )

    def test_restores_entity_encoded_quotes_in_variable_tags(self):
        body = "<p>{{ total_amount|floatformat:&quot;2&quot; }}</p>"

        assert normalize_template_tags(body) == (
            '<p>{{ total_amount|floatformat:"2" }}</p>'
        )

    def test_restores_entity_encoded_operators_in_block_tags(self):
        body = "<p>{% if number_of_bookings &gt; 3 %}many{% endif %}</p>"

        assert normalize_template_tags(body) == (
            "<p>{% if number_of_bookings > 3 %}many{% endif %}</p>"
        )

    def test_replaces_non_breaking_spaces_inside_tags(self):
        body = "<p>{{&nbsp;organization.name&nbsp;}}</p>"

        assert normalize_template_tags(body) == "<p>{{ organization.name }}</p>"

    def test_leaves_text_outside_tags_untouched(self):
        body = "<p>A &amp; B &lt;x&gt; 100%20</p>"

        assert normalize_template_tags(body) == body


class TestSanitizeEmailHtml:
    def test_keeps_whitelisted_formatting(self):
        body = (
            "<p>Hi <strong>a</strong> <b>b</b> <em>c</em> <i>d</i><br></p>"
            "<ul><li>one</li></ul><ol><li>two</li></ol>"
        )

        assert sanitize_email_html(body) == body

    def test_removes_script_with_its_content(self):
        cleaned = sanitize_email_html("<script>alert(1)</script><p>Hi</p>")

        assert cleaned == "<p>Hi</p>"

    def test_removes_event_handler_attributes(self):
        assert sanitize_email_html('<p onclick="x()">Hi</p>') == "<p>Hi</p>"

    def test_removes_tags_outside_the_whitelist_but_keeps_their_text(self):
        cleaned = sanitize_email_html('<h1>Title</h1><img src="x.png"><p>Hi</p>')

        assert cleaned == "Title<p>Hi</p>"

    def test_removes_javascript_link_targets(self):
        cleaned = sanitize_email_html('<a href="javascript:alert(1)">x</a>')

        assert "javascript" not in cleaned
        assert "x" in cleaned

    def test_keeps_http_https_and_mailto_link_targets(self):
        for url in (
            "http://example.org/a",
            "https://example.org/a",
            "mailto:someone@example.org",
        ):
            assert f'href="{url}"' in sanitize_email_html(f'<a href="{url}">x</a>')

    def test_keeps_link_target_attribute(self):
        cleaned = sanitize_email_html(
            '<a href="https://example.org" target="_blank" style="color:red">x</a>'
        )

        assert 'target="_blank"' in cleaned
        assert "style" not in cleaned


class TestHtmlToText:
    def test_plain_text_passes_through(self):
        assert html_to_text("Hello all") == "Hello all"

    def test_paragraphs_are_separated_by_a_blank_line(self):
        assert html_to_text("<p>one</p>\n<p>two</p>") == "one\n\ntwo"

    def test_line_break_becomes_newline(self):
        assert html_to_text("<p>one<br>two</p>") == "one\ntwo"

    def test_inline_formatting_is_dropped(self):
        assert html_to_text("<p>Hello <strong>all</strong> <em>of</em> you</p>") == (
            "Hello all of you"
        )

    def test_bulleted_list_items_get_a_dash(self):
        text = html_to_text("<p>List:</p>\n<ul>\n<li>one</li>\n<li>two</li>\n</ul>")

        assert text == "List:\n\n- one\n- two"

    def test_numbered_list_items_get_their_number(self):
        assert html_to_text("<ol><li>one</li><li>two</li></ol>") == "1. one\n2. two"

    def test_nested_list_is_indented(self):
        text = html_to_text("<ul><li>one<ul><li>inner</li></ul></li><li>two</li></ul>")

        assert text == "- one\n  - inner\n- two"

    def test_list_item_without_list_gets_a_dash(self):
        assert html_to_text("<li>one</li><li>two</li>") == "- one\n- two"

    def test_link_is_followed_by_its_url(self):
        text = html_to_text('<p>See <a href="https://example.org/x">our page</a>.</p>')

        assert text == "See our page (https://example.org/x)."

    def test_link_with_identical_text_shows_url_once(self):
        text = html_to_text('<a href="https://example.org/x">https://example.org/x</a>')

        assert text == "https://example.org/x"

    def test_mailto_link_with_address_as_text_shows_address_once(self):
        text = html_to_text('<a href="mailto:a@example.org">a@example.org</a>')

        assert text == "a@example.org"

    def test_link_without_target_keeps_its_text(self):
        assert html_to_text("<a>text</a>") == "text"

    def test_entities_are_decoded(self):
        assert html_to_text("<p>A &amp; B &lt;Team&gt;</p>") == "A & B <Team>"

    def test_empty_markup_yields_empty_text(self):
        assert html_to_text("<p></p>") == ""
        assert html_to_text("<p>&nbsp;</p>\n<p><br></p>") == ""
