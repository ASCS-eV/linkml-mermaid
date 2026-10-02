"""MarkdownTableRenderer tests — validating against GFM §4.10.

Each test asserts what the GFM specification REQUIRES for pipe tables,
not what our implementation happens to produce.  Structural validators
enforce invariants derived directly from the spec.

Spec: https://github.github.com/gfm/#tables-extension-
Inline formatting:
  §6.3 Code spans: https://github.github.com/gfm/#code-spans
  §6.4 Emphasis:   https://github.github.com/gfm/#emphasis-and-strong-emphasis
"""

from __future__ import annotations

import re

import pytest

from linkml_mermaid import ColumnDef, TableDef
from linkml_mermaid.markdown_table import MarkdownTableRenderer

# ── Spec-derived structural validators ───────────────────────────────
#
# These validators enforce the structural rules from GFM §4.10,
# independent of our implementation.


def _validate_gfm_table(text: str) -> list[str]:
    """Validate a GFM pipe table against §4.10 structural rules.

    Returns a list of error messages (empty = valid).

    Rules checked:
    1. At least 2 rows (header + delimiter)
    2. Every row starts with '|' and ends with '|'
    3. Row 1 (delimiter) cells match :?-+:? (hyphens, optional colons)
    4. Header row cell count == delimiter row cell count
    5. All data rows have same cell count as header
    """
    errors = []
    lines = text.strip().split("\n")

    if len(lines) < 2:
        errors.append("Table must have at least 2 rows (header + delimiter)")
        return errors

    # Rule: every row uses pipe delimiters
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            errors.append(f"Row {i}: must start with '|' (§4.10: leading pipe)")
        if not line.endswith("|"):
            errors.append(f"Row {i}: must end with '|' (§4.10: trailing pipe)")

    def _cell_count(line: str) -> int:
        """Count cells by splitting on | and ignoring outer empties."""
        parts = line.split("|")
        # Leading and trailing | produce empty strings at edges
        return len(parts) - 2  # subtract the two outer empties

    # Rule: delimiter row cells must be hyphens (with optional colons)
    # §4.10: "cells whose only content are hyphens (-), and optionally,
    # a leading or trailing colon (:), or both"
    delimiter_cells = lines[1].split("|")[1:-1]
    for j, cell in enumerate(delimiter_cells):
        cell = cell.strip()
        if not re.match(r"^:?-+:?$", cell):
            errors.append(
                f"Delimiter cell {j}: '{cell}' does not match "
                "§4.10 pattern ':?-+:?' (hyphens with optional colons)"
            )

    # Rule: "header row must match the delimiter row in the number of cells"
    header_count = _cell_count(lines[0])
    delim_count = _cell_count(lines[1])
    if header_count != delim_count:
        errors.append(
            f"Header has {header_count} cells but delimiter has "
            f"{delim_count} — §4.10 requires match"
        )

    # Rule: data rows should have consistent cell count
    for i, line in enumerate(lines[2:], start=2):
        data_count = _cell_count(line)
        if data_count != header_count:
            errors.append(f"Data row {i} has {data_count} cells but header has {header_count}")

    return errors


# ── Table structure tests (§4.10) ────────────────────────────────────


class TestTableStructure:
    """GFM §4.10: 'consisting of a single header row, a delimiter row
    separating the header from the data, and zero or more data rows.'"""

    def test_basic_two_column_table(self):
        """Hand-written expected output from spec reading.

        Per §4.10:
        | Header1 | Header2 |
        | --- | --- |
        | cell1 | cell2 |
        """
        cols = [ColumnDef("Name", "name"), ColumnDef("Value", "value")]
        rows = [{"name": "Red", "value": "Stop"}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)

        expected = "\n".join(
            [
                "| Name | Value |",
                "| --- | --- |",
                "| Red | Stop |",
            ]
        )
        assert output == expected

    def test_structural_validity(self):
        """Every rendered table must pass GFM structural validation."""
        cols = [ColumnDef("A", "a"), ColumnDef("B", "b"), ColumnDef("C", "c")]
        rows = [
            {"a": "1", "b": "2", "c": "3"},
            {"a": "4", "b": "5", "c": "6"},
        ]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)
        errors = _validate_gfm_table(output)
        assert errors == [], f"GFM errors: {errors}"

    def test_zero_data_rows_valid(self):
        """§4.10: 'zero or more data rows' — header + delimiter alone is valid.

        Spec example: '| abc | def |\\n| --- | --- |' produces a valid
        table with <thead> but no <tbody>."""
        cols = [ColumnDef("abc", "a"), ColumnDef("def", "b")]
        r = MarkdownTableRenderer()
        output = r.render(cols, [])

        expected = "\n".join(
            [
                "| abc | def |",
                "| --- | --- |",
            ]
        )
        assert output == expected
        errors = _validate_gfm_table(output)
        assert errors == []

    def test_single_column(self):
        """Minimal table: one column."""
        cols = [ColumnDef("Only", "x")]
        rows = [{"x": "val"}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)
        errors = _validate_gfm_table(output)
        assert errors == []

    def test_cell_count_consistency(self):
        """§4.10: header row must match delimiter in cell count.
        All data rows should also match."""
        cols = [ColumnDef("A", "a"), ColumnDef("B", "b")]
        rows = [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)

        lines = output.split("\n")
        counts = [line.count("|") for line in lines]
        # All rows should have the same pipe count
        assert len(set(counts)) == 1

    def test_delimiter_uses_hyphens_only(self):
        """§4.10: delimiter cells are hyphens only (left-aligned = no colons)."""
        cols = [ColumnDef("H1", "a"), ColumnDef("H2", "b")]
        r = MarkdownTableRenderer()
        output = r.render(cols, [])

        delimiter_line = output.split("\n")[1]
        cells = delimiter_line.split("|")[1:-1]
        for cell in cells:
            assert cell.strip() == "---", f"Delimiter cell should be '---', got '{cell.strip()}'"


# ── Inline formatting tests (§6.3, §6.4) ────────────────────────────


class TestTableFormatting:
    """GFM §6.4: '**text** produces <strong>text</strong>'
    GFM §6.3: '`text` produces <code>text</code>'"""

    def test_bold_format(self):
        """§6.4: **value** for strong emphasis."""
        cols = [ColumnDef("State", "s", format="bold")]
        rows = [{"s": "Draft"}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)
        assert "| **Draft** |" in output

    def test_code_format(self):
        """§6.3: `value` for code spans."""
        cols = [ColumnDef("ID", "id", format="code")]
        rows = [{"id": "NEW"}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)
        assert "| `NEW` |" in output

    def test_italic_format(self):
        """§6.4: *value* for emphasis."""
        cols = [ColumnDef("Note", "n", format="italic")]
        rows = [{"n": "important"}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)
        assert "| *important* |" in output

    def test_plain_format_no_wrapping(self):
        """Plain format: raw value, no wrapper."""
        cols = [ColumnDef("X", "x", format="plain")]
        rows = [{"x": "hello"}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)
        assert "| hello |" in output

    def test_empty_cell_not_bold_wrapped(self):
        """Empty values must NOT produce '****' — that would render as
        visible GFM strong emphasis markers, not an empty cell."""
        cols = [ColumnDef("S", "s", format="bold")]
        rows = [{"s": ""}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)
        assert "****" not in output

    def test_empty_cell_not_code_wrapped(self):
        """Empty values must NOT produce '``'."""
        cols = [ColumnDef("S", "s", format="code")]
        rows = [{"s": ""}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)
        assert "``" not in output

    def test_empty_cell_not_italic_wrapped(self):
        """Empty values must NOT produce '**' (single asterisk pairs)."""
        cols = [ColumnDef("S", "s", format="italic")]
        rows = [{"s": ""}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)
        # Should have an empty cell, not *-wrapped
        data_line = output.split("\n")[2]
        cells = data_line.split("|")[1:-1]
        assert cells[0].strip() == ""

    def test_unknown_format_is_rejected(self):
        """An unknown format must fail at construction, not render wrong.

        Silently falling back to plain text meant a typo in a format
        name produced an unformatted table with no indication of why.
        """
        with pytest.raises(ValueError, match="Invalid cell format"):
            ColumnDef("X", "x", format="strikethrough")


# ── Edge cases ───────────────────────────────────────────────────────


class TestTableEdgeCases:
    """Edge cases that the spec defines or leaves as implementation choice."""

    def test_missing_key_produces_empty_cell(self):
        """Row dict missing a column key → empty cell.

        Per §4.10: 'If there are a number of cells fewer than the number
        of cells in the header row, empty cells are inserted.'"""
        cols = [ColumnDef("A", "a"), ColumnDef("B", "b")]
        rows = [{"a": "present"}]  # missing "b"
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)
        # The table should still be structurally valid
        errors = _validate_gfm_table(output)
        assert errors == []
        # The missing cell should be empty
        data_line = output.split("\n")[2]
        cells = [c.strip() for c in data_line.split("|")[1:-1]]
        assert cells[1] == ""

    def test_render_from_def_convenience(self):
        """TableDef convenience method produces same result as render()."""
        cols = [ColumnDef("H", "h")]
        rows = [{"h": "val"}]
        r = MarkdownTableRenderer()
        direct = r.render(cols, rows)
        from_def = r.render_from_def(TableDef(columns=cols, rows=rows))
        assert direct == from_def

    def test_many_columns(self):
        """Stress: 10 columns should still produce valid GFM."""
        cols = [ColumnDef(f"H{i}", f"k{i}") for i in range(10)]
        rows = [{f"k{i}": f"v{i}" for i in range(10)}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)
        errors = _validate_gfm_table(output)
        assert errors == [], f"GFM errors: {errors}"

    def test_many_rows(self):
        """Stress: 100 rows should still produce valid GFM."""
        cols = [ColumnDef("Idx", "i")]
        rows = [{"i": str(n)} for n in range(100)]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)
        errors = _validate_gfm_table(output)
        assert errors == []
        assert len(output.split("\n")) == 102  # 1 header + 1 delim + 100 data


class TestTableHandWrittenOutput:
    """Hand-written expected tables based on reading GFM §4.10 examples.

    The spec shows this exact pattern:
        | foo | bar |
        | --- | --- |
        | baz | bim |
    """

    def test_spec_example_foo_bar(self):
        """Directly from GFM §4.10 Example 198."""
        cols = [ColumnDef("foo", "f"), ColumnDef("bar", "b")]
        rows = [{"f": "baz", "b": "bim"}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)

        expected = "\n".join(
            [
                "| foo | bar |",
                "| --- | --- |",
                "| baz | bim |",
            ]
        )
        assert output == expected

    def test_mixed_formatting(self):
        """Bold + code + plain columns — hand-written expected output."""
        cols = [
            ColumnDef("State", "state", format="bold"),
            ColumnDef("ID", "id", format="code"),
            ColumnDef("Description", "desc"),
        ]
        rows = [{"state": "Draft", "id": "DRAFT", "desc": "Being defined"}]
        r = MarkdownTableRenderer()
        output = r.render(cols, rows)

        expected = "\n".join(
            [
                "| State | ID | Description |",
                "| --- | --- | --- |",
                "| **Draft** | `DRAFT` | Being defined |",
            ]
        )
        assert output == expected
