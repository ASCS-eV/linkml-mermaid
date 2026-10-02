"""Conformance tests that judge our table output with GitHub's own parser.

``tests/test_markdown_table.py`` asserts that the renderer produces
particular strings.  That cannot catch a misreading of the GFM
specification, because the expected strings encode the same reading.
The tests here render the table with cmark-gfm — the library GitHub's
Markdown pipeline is built on — and check the resulting HTML, so the
contract is stated in terms of what a reader actually sees.

The contract under test is that a cell value is **literal text**:
whatever string is passed in comes back out verbatim, and the only
styling applied is the one the column's ``format`` asked for.  That
means no value can introduce emphasis, a link, raw HTML, or an extra
table column.

Skips when ``cmarkgfm`` is not installed; CI installs it.
"""

from __future__ import annotations

import pytest

from linkml_mermaid import ColumnDef, MarkdownTableRenderer
from linkml_mermaid.escaping import escape_table_cell

from .oracles import cell_text, gfm_to_html, render_single_row, requires_cmark, table_cells

# Values built from the inline constructs GFM defines, so that a cell
# which fails to neutralise one of them shows up as markup in the HTML.
HOSTILE_VALUES = [
    "plain text",
    "a | b",
    "**bold**",
    "*emph*",
    "_under_score_",
    "`code`",
    "~~strike~~",
    "[link](http://evil.example)",
    "![img](http://evil.example/x.png)",
    "<b>raw html</b>",
    "<script>alert(1)</script>",
    "<http://example.com>",
    "http://example.com/?a=1&b=2",
    "www.example.com",
    "see www.evil.example for more",
    "WWW.EXAMPLE.COM",
    "ftp://files.example.com",
    "a & b",
    "5 < 6 > 4",
    "C:\\path\\to\\file",
    "back\\slash",
    "100%",
    "a\nb",
    "trailing  ",
    "  leading",
    "",
    "   ",
    "|",
    "||",
    "\\|",
    "a\\|b",
    "#hash",
    "- item",
    "1. item",
    "> quote",
    "x\ty",
    "ends with backslash\\",
    "``double``",
    "a`b",
    "`",
    "```",
    "mixed `a` **b** [c](d)",
]


class TestLiteralCellContract:
    """A cell value must survive GFM rendering unchanged."""

    @pytest.mark.parametrize("value", HOSTILE_VALUES)
    def test_value_round_trips_through_gfm(self, value):
        """What goes into a cell is what the reader sees."""
        requires_cmark()
        # A sentinel column turns a leaked pipe into a changed cell
        # count, which a text comparison alone would miss.
        markdown = render_single_row([escape_table_cell(value), "sentinel"])
        cells = table_cells(markdown)
        assert len(cells) == 4, f"{value!r} changed the column count: {cells}"
        assert (
            cell_text(cells[2]) == value.strip().replace("\t", " ")
            or cell_text(cells[2]) == value.strip()
        )

    @pytest.mark.parametrize("value", HOSTILE_VALUES)
    def test_value_introduces_no_markup(self, value):
        """No value may turn itself into emphasis, a link or raw HTML."""
        requires_cmark()
        markdown = render_single_row([escape_table_cell(value), "sentinel"])
        cell = table_cells(markdown)[2]
        for tag in ("<strong", "<em", "<a ", "<img", "<code", "<del", "<script", "<b>"):
            assert tag not in cell, f"{value!r} produced {tag} in {cell!r}"

    @pytest.mark.parametrize("value", HOSTILE_VALUES)
    def test_value_cannot_escape_its_cell(self, value):
        """A value must not add, remove or reorder columns."""
        requires_cmark()
        markdown = render_single_row(["before", escape_table_cell(value), "after"])
        cells = table_cells(markdown)
        assert len(cells) == 6
        assert cell_text(cells[3]) == "before"
        assert cell_text(cells[5]) == "after"


class TestAutolinkExtension:
    """GFM §6.9 — the extended autolink extension linkifies text that
    contains no active character at all.

    Escaping the inline-construct characters is therefore not enough on
    its own: ``www.example.com`` needs the dot after ``www`` escaped,
    and ``http://...`` is neutralised by the colon escape.
    """

    @pytest.mark.parametrize(
        "value",
        [
            "www.example.com",
            "see www.evil.example for more",
            "(www.example.com)",
            "www.a",
            "WWW.EXAMPLE.COM",
            "http://example.com",
            "https://example.com/path",
            "ftp://files.example.com",
            "a.www.b.com",
        ],
    )
    def test_url_forms_do_not_become_links(self, value):
        requires_cmark()
        cell = table_cells(render_single_row([escape_table_cell(value), "x"]))[2]
        assert "<a " not in cell, f"{value!r} autolinked: {cell!r}"
        assert cell_text(cell) == value

    @pytest.mark.parametrize("value", ["Version 1.2.3", "e.g. a value", "file.txt", "a.b.c"])
    def test_ordinary_dots_are_left_alone(self, value):
        """Only the dot in a ``www.`` token is escaped, so a version
        number does not acquire backslashes in the Markdown source."""
        requires_cmark()
        assert "\\." not in escape_table_cell(value)
        cell = table_cells(render_single_row([escape_table_cell(value), "x"]))[2]
        assert cell_text(cell) == value

    def test_a_bare_email_address_still_autolinks(self):
        """A documented limit, not an oversight.

        cmark-gfm honours neither ``user\\@host`` nor ``user&#64;host``
        as a way to suppress the email autolink, so there is no escape
        to apply.  The test records the behaviour so a future change
        that *does* fix it is noticed rather than silently contradicting
        the documentation.
        """
        requires_cmark()
        cell = table_cells(render_single_row([escape_table_cell("user@example.com"), "x"]))[2]
        assert "<a " in cell
        assert cell_text(cell) == "user@example.com"

    def test_the_www_escape_is_load_bearing(self):
        """Without it the value really does become a link."""
        requires_cmark()
        cell = table_cells(render_single_row(["www.example.com", "x"]))[2]
        assert "<a " in cell, "fixture no longer demonstrates the autolink"


class TestFullTableRoundTrip:
    """The same contract, through the public renderer rather than the
    escaping helper alone."""

    @pytest.mark.parametrize("value", HOSTILE_VALUES)
    def test_rendered_table_preserves_the_value(self, value):
        requires_cmark()
        columns = [ColumnDef("Value", "v"), ColumnDef("Sentinel", "s")]
        markdown = MarkdownTableRenderer().render(columns, [{"v": value, "s": "sentinel"}])
        cells = table_cells(markdown)
        assert len(cells) == 4
        assert cell_text(cells[3]) == "sentinel"

    def test_a_hostile_value_cannot_forge_a_row(self):
        requires_cmark()
        columns = [ColumnDef("Value", "v"), ColumnDef("Sentinel", "s")]
        markdown = MarkdownTableRenderer().render(
            columns, [{"v": "x |\n| forged | row |\n| a", "s": "sentinel"}]
        )
        html = gfm_to_html(markdown)
        assert "forged" in html, "fixture no longer contains the payload"
        assert html.count("<tr>") == 2, "the payload created extra rows"


class TestCodeSpanDelimiters:
    """GFM §6.3 — a code span is delimited by a backtick string, and the
    content may not contain a run of the same length."""

    @pytest.mark.parametrize(
        "value",
        ["a", "`", "``", "```", "a`b", "`leading", "trailing`", "`both`", "a | b", "``x``"],
    )
    def test_code_cell_renders_as_one_code_span(self, value):
        requires_cmark()
        columns = [ColumnDef("V", "v", format="code"), ColumnDef("S", "s")]
        markdown = MarkdownTableRenderer().render(columns, [{"v": value, "s": "sentinel"}])
        cells = table_cells(markdown)
        assert len(cells) == 4, f"{value!r} changed the column count: {cells}"
        cell = cells[2]
        assert cell.count("<code>") == 1, f"{value!r} did not make exactly one span: {cell!r}"
        assert cell_text(cell) == value.strip()
        assert cell_text(cells[3]) == "sentinel"

    @pytest.mark.parametrize("value", ["", " ", "   ", "\t", "\n"])
    def test_a_blank_code_value_renders_as_an_empty_cell(self, value):
        """A span of only spaces is the one case §6.3 will not unpad, and
        it has nothing to show, so no span is emitted."""
        requires_cmark()
        columns = [ColumnDef("V", "v", format="code"), ColumnDef("S", "s")]
        markdown = MarkdownTableRenderer().render(columns, [{"v": value, "s": "sentinel"}])
        cells = table_cells(markdown)
        assert len(cells) == 4
        assert cell_text(cells[2]).strip() == ""
        assert cell_text(cells[3]) == "sentinel"

    def test_a_pipe_inside_a_code_span_still_needs_escaping(self):
        """GFM §4.10 requires ``\\|`` even inside other inline spans."""
        requires_cmark()
        columns = [ColumnDef("V", "v", format="code"), ColumnDef("S", "s")]
        markdown = MarkdownTableRenderer().render(columns, [{"v": "a | b", "s": "sentinel"}])
        cells = table_cells(markdown)
        assert len(cells) == 4
        assert cell_text(cells[2]) == "a | b"

    def test_multi_line_code_becomes_separate_spans(self):
        """``<br>`` inside a code span would render literally, so each
        line gets its own span."""
        requires_cmark()
        columns = [ColumnDef("V", "v", format="code")]
        markdown = MarkdownTableRenderer().render(columns, [{"v": "line1\nline2"}])
        cell = table_cells(markdown)[1]
        assert cell.count("<code>") == 2
        assert "<br" in cell
        assert "&lt;br" not in cell

    @pytest.mark.parametrize(
        "value",
        [
            "  x  ",
            " lead and trail ",
            "   three   ",
            " `tick` ",
            "  def f():  ",
        ],
    )
    def test_surrounding_spaces_survive_the_unpadding_rule(self, value):
        """GFM §6.3 strips one space from each end of a span that *both*
        begins and ends with a space.  Without compensating padding the
        value would come back a character shorter at each end."""
        requires_cmark()
        columns = [ColumnDef("V", "v", format="code")]
        markdown = MarkdownTableRenderer().render(columns, [{"v": value}])
        assert cell_text(table_cells(markdown)[1]) == value

    @pytest.mark.parametrize("value", ["a\n  b \nc", "if x:\n    return 1\n", " a \n b "])
    def test_indentation_survives_in_multi_line_code(self, value):
        """Each line is its own span, so each line needs the padding rule
        applied independently."""
        requires_cmark()
        columns = [ColumnDef("V", "v", format="code")]
        markdown = MarkdownTableRenderer().render(columns, [{"v": value}])
        assert cell_text(table_cells(markdown)[1]) == value

    def test_indentation_inside_a_code_value_survives(self):
        """§6.3 strips only one space from each end, so the padding
        added for a space-flanked line is given back."""
        requires_cmark()
        columns = [ColumnDef("V", "v", format="code")]
        markdown = MarkdownTableRenderer().render(columns, [{"v": "def f():\n    return 1"}])
        cell = table_cells(markdown)[1]
        assert cell.count("<code>") == 2
        assert cell_text(cell) == "def f():\n    return 1"

    def test_a_backtick_run_cannot_close_the_span_early(self):
        """The fence must outgrow the longest run inside the value."""
        requires_cmark()
        columns = [ColumnDef("V", "v", format="code"), ColumnDef("S", "s")]
        for value in ("a`b``c```d", "`" * 7, "x```````y"):
            markdown = MarkdownTableRenderer().render(columns, [{"v": value, "s": "sentinel"}])
            cells = table_cells(markdown)
            assert len(cells) == 4, f"{value!r} changed the column count"
            assert cells[2].count("<code>") == 1, f"{value!r} broke out of its span"
            assert cell_text(cells[2]) == value.strip()


class TestEmphasisFlanking:
    """GFM §6.2 — a left-flanking delimiter run may not be followed by
    whitespace, so a padded value would render its asterisks literally."""

    @pytest.mark.parametrize("value", ["  padded  ", "bold", " x", "y ", "a b", "*star*"])
    def test_bold_format_produces_real_emphasis(self, value):
        requires_cmark()
        columns = [ColumnDef("V", "v", format="bold")]
        markdown = MarkdownTableRenderer().render(columns, [{"v": value}])
        cell = table_cells(markdown)[1]
        assert "<strong>" in cell, f"{value!r} did not render as bold: {cell!r}"
        assert cell_text(cell) == value.strip()

    @pytest.mark.parametrize("value", ["  padded  ", "italic", " x", "y ", "a_b"])
    def test_italic_format_produces_real_emphasis(self, value):
        requires_cmark()
        columns = [ColumnDef("V", "v", format="italic")]
        markdown = MarkdownTableRenderer().render(columns, [{"v": value}])
        cell = table_cells(markdown)[1]
        assert "<em>" in cell, f"{value!r} did not render as italic: {cell!r}"
        assert cell_text(cell) == value.strip()

    def test_empty_value_is_not_wrapped(self):
        """``****`` is not emphasis; an empty cell must stay empty."""
        requires_cmark()
        columns = [ColumnDef("V", "v", format="bold")]
        markdown = MarkdownTableRenderer().render(columns, [{"v": ""}])
        cell = table_cells(markdown)[1]
        assert "*" not in cell
        assert cell_text(cell) == ""


class TestAlignment:
    """GFM §4.10 — the delimiter row's colons set column alignment."""

    @pytest.mark.parametrize(
        ("align", "expected"),
        [("left", "left"), ("center", "center"), ("right", "right")],
    )
    def test_alignment_reaches_the_html(self, align, expected):
        requires_cmark()
        columns = [ColumnDef("V", "v", align=align)]
        html = gfm_to_html(MarkdownTableRenderer().render(columns, [{"v": "x"}]))
        assert f'align="{expected}"' in html


class TestOracleIsCalibrated:
    """If the oracle reported no markup for anything, every test above
    would pass vacuously."""

    def test_unescaped_markup_really_is_detected(self):
        requires_cmark()
        cells = table_cells(render_single_row(["**bold**", "x"]))
        assert "<strong>" in cells[2]

    def test_an_unescaped_pipe_really_does_split_a_cell(self):
        """GFM truncates a row to the header's column count, so a leaked
        pipe shows up as displaced content rather than an extra cell."""
        requires_cmark()
        cells = table_cells(render_single_row(["a | b", "x"]))
        assert cell_text(cells[2]) != "a | b", "an unescaped pipe must split the cell"
        assert cell_text(cells[3]) != "x", "the sentinel column must be displaced"

    def test_an_unescaped_autolink_really_is_detected(self):
        requires_cmark()
        cells = table_cells(render_single_row(["<http://example.com>", "x"]))
        assert "<a " in cells[2]
