"""Unit tests for the escaping helpers.

Each test cites the specification clause that makes the escape
necessary.  These are the lowest-level guarantees the renderers rely
on, so they are tested directly rather than only through rendered
output.
"""

from __future__ import annotations

import pytest

from linkml_mermaid.escaping import (
    escape_mermaid_text,
    escape_state_label,
    escape_table_cell,
)

# Inputs that previously produced structurally broken output.  Reused
# across renderer tests so every output path sees the same hostile set.
HOSTILE_INPUTS = [
    'say "hi"',
    'a "quoted" phrase with | pipe',
    "line1\nline2",
    "line1\r\nline2",
    "line1\rline2",
    "pipe|separated",
    "escaped\\|pipe",
    "double\\\\|pipe",
    "hash # symbol",
    "entity-looking #quot; text",
    "colon: in the middle",
    "brackets [x] and {y} and (z)",
    "arrow --> like",
    "semi;colon",
    "trailing backslash\\",
    "unicode — em dash",
    "",
]


class TestEscapeMermaidText:
    """§Entity codes to escape characters:
    'A["A double quote:#quot;"] --> B["A dec char:#9829;"]'
    """

    def test_double_quote_becomes_entity(self):
        assert escape_mermaid_text('say "hi"') == "say #quot;hi#quot;"

    def test_hash_becomes_entity(self):
        """'Numbers given are base 10, so # can be encoded as #35;'"""
        assert escape_mermaid_text("C# code") == "C#35; code"

    def test_hash_escaped_before_quote(self):
        """A literal '#quot;' in the input must not survive as an entity.

        If '#' were escaped after '"', the escape this function emits
        would be indistinguishable from caller-supplied text.
        """
        assert escape_mermaid_text("#quot;") == "#35;quot;"

    def test_newline_becomes_br(self):
        assert escape_mermaid_text("a\nb") == "a<br>b"

    def test_crlf_becomes_single_br(self):
        assert escape_mermaid_text("a\r\nb") == "a<br>b"

    def test_lone_cr_becomes_br(self):
        assert escape_mermaid_text("a\rb") == "a<br>b"

    def test_plain_text_unchanged(self):
        assert escape_mermaid_text("Content Review") == "Content Review"

    @pytest.mark.parametrize("text", HOSTILE_INPUTS)
    def test_output_never_contains_raw_quote(self, text):
        """The renderer wraps this output in quotes, so a surviving raw
        quote would terminate the label early."""
        assert '"' not in escape_mermaid_text(text)

    @pytest.mark.parametrize("text", HOSTILE_INPUTS)
    def test_output_is_single_line(self, text):
        assert "\n" not in escape_mermaid_text(text)
        assert "\r" not in escape_mermaid_text(text)

    @pytest.mark.parametrize("text", HOSTILE_INPUTS)
    def test_idempotent_on_safe_text(self, text):
        """Escaping is stable once applied to already-safe characters."""
        once = escape_mermaid_text(text)
        assert "\n" not in escape_mermaid_text(once)


class TestEscapeStateLabel:
    """stateDiagram-v2 descriptions are unquoted and run to end of line."""

    @pytest.mark.parametrize("text", HOSTILE_INPUTS)
    def test_output_is_single_line(self, text):
        assert "\n" not in escape_state_label(text)
        assert "\r" not in escape_state_label(text)

    @pytest.mark.parametrize("text", HOSTILE_INPUTS)
    def test_output_never_contains_raw_quote(self, text):
        assert '"' not in escape_state_label(text)

    def test_newline_becomes_br(self):
        assert escape_state_label("a\nb") == "a<br>b"


class TestEscapeTableCell:
    """GFM §4.10: 'include a pipe in a cell's content by escaping it'."""

    def test_pipe_is_escaped(self):
        assert escape_table_cell("a|b") == r"a\|b"

    def test_newline_becomes_br(self):
        """Cells hold inline content only; a newline would end the table."""
        assert escape_table_cell("a\nb") == "a<br>b"

    def test_backslash_before_pipe_is_doubled(self):
        r"""Input 'a\|b' must render as a literal backslash then a pipe.

        Escaping only the pipe would yield 'a\\|b', where GFM consumes
        the pair as one literal backslash and treats the pipe as a cell
        delimiter — splitting the row.
        """
        assert escape_table_cell(r"a\|b") == r"a\\\|b"

    def test_backslash_run_before_pipe_is_doubled(self):
        assert escape_table_cell("a\\\\|b") == "a\\\\\\\\\\|b"

    def test_backslash_not_before_pipe_is_untouched(self):
        r"""A backslash elsewhere is left alone so code-span cells keep
        their literal content."""
        assert escape_table_cell(r"C:\path") == r"C:\path"

    def test_plain_text_unchanged(self):
        assert escape_table_cell("Content Review") == "Content Review"

    @pytest.mark.parametrize("text", HOSTILE_INPUTS)
    def test_no_unescaped_pipe_survives(self, text):
        """The defining property: every pipe in the output is preceded by
        an odd-length run of backslashes, i.e. is escaped."""
        out = escape_table_cell(text)
        for i, ch in enumerate(out):
            if ch != "|":
                continue
            backslashes = 0
            j = i - 1
            while j >= 0 and out[j] == "\\":
                backslashes += 1
                j -= 1
            assert backslashes % 2 == 1, f"unescaped pipe at {i} in {out!r}"

    @pytest.mark.parametrize("text", HOSTILE_INPUTS)
    def test_output_is_single_line(self, text):
        assert "\n" not in escape_table_cell(text)
        assert "\r" not in escape_table_cell(text)
