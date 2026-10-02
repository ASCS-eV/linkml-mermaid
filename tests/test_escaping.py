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
    escape_state_inline,
    escape_state_label,
    escape_subgraph_title,
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

    def test_backslash_is_escaped_so_it_stays_visible(self):
        r"""A backslash is itself an escape character in GFM §2.4, so an
        unescaped one would consume the character after it.

        The colon is escaped too: GFM's autolink extension recognises a
        bare ``scheme:`` and would otherwise swallow following text into
        a link.  ``tests/test_gfm_conformance.py`` proves the round trip
        against cmark-gfm.
        """
        assert escape_table_cell(r"C:\path") == "C\\:\\\\path"

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


class TestEscapeStateInline:
    """Positions in stateDiagram-v2 that are introduced by ':'.

    A transition label (§Transitions) and a note body (§Notes) both
    follow a colon and have no quoted alternative, so a colon in the
    text is read as grammar rather than content.  ``::`` is worse than
    ambiguous: it is the class-application operator.

    ``#58;`` is Mermaid's numeric character reference for the colon and
    renders as one; ``tests/test_mermaid_conformance.py`` proves that
    against the real parser and renderer.
    """

    def test_colon_becomes_a_character_reference(self):
        assert escape_state_inline("a:b") == "a#58;b"

    def test_double_colon_is_fully_escaped(self):
        """Leaving either colon would still read as the class operator."""
        assert escape_state_inline("a :: b") == "a #58;#58; b"

    def test_every_colon_is_escaped(self):
        assert escape_state_inline("a:b:c:d") == "a#58;b#58;c#58;d"

    def test_text_without_a_colon_is_unchanged(self):
        assert escape_state_inline("plain label") == "plain label"

    def test_it_also_applies_the_shared_text_escaping(self):
        """The colon rule is additional to, not instead of, the escaping
        every Mermaid text position needs."""
        assert escape_state_inline('say "hi"') == "say #quot;hi#quot;"
        assert escape_state_inline("#1") == "#35;1"

    def test_entities_it_emits_are_not_re_escaped(self):
        """The escaping runs in one pass.

        ``"`` becomes ``#quot;`` — which contains both ``#`` and ``;``,
        the two other characters being escaped.  A multi-pass
        implementation would corrupt it into ``#quot#59;``.
        """
        assert escape_state_inline('"') == "#quot;"
        assert escape_state_label('"') == "#quot;"
        assert escape_state_inline("#") == "#35;"
        assert escape_state_inline('a"b;c#d:e') == "a#quot;b#59;c#35;d#58;e"

    def test_newline_becomes_a_line_break(self):
        assert escape_state_inline("a\nb") == "a<br>b"

    def test_a_state_label_keeps_its_colon(self):
        """Labels have the quoted ``state "..." as id`` form available,
        so they need no colon escaping and must not get it."""
        assert escape_state_label("a:b") == "a:b"
        assert escape_state_inline("a:b") != escape_state_label("a:b")


class TestEscapeSubgraphTitle:
    """§Subgraphs — ``subgraph id["title"]``.

    The flowchart lexer matches the ``direction`` keyword inside the
    quoted title, which no other quoted position does.  ``#100;`` is the
    character reference for ``d`` and renders as one, so the word
    reaches the reader intact while the lexer no longer sees it.
    """

    def test_direction_keyword_is_defused(self):
        assert escape_subgraph_title("direction") == "#100;irection"

    def test_the_keyword_is_defused_anywhere_in_the_title(self):
        assert escape_subgraph_title("set direction LR") == "set #100;irection LR"

    def test_capitalised_direction_is_left_alone(self):
        """Only the lowercase literal is a keyword; rewriting others
        would change text that was never at risk."""
        assert escape_subgraph_title("Direction") == "Direction"

    def test_a_longer_word_containing_direction_is_left_alone(self):
        assert escape_subgraph_title("redirectional") == "redirectional"

    def test_it_also_applies_the_shared_text_escaping(self):
        assert escape_subgraph_title('say "hi"') == escape_mermaid_text('say "hi"')

    def test_an_ordinary_title_is_unchanged(self):
        assert escape_subgraph_title("Processing stage") == "Processing stage"
