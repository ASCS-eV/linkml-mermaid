"""Markdown table renderer — GFM §4.10 pipe tables.

Produces a standard GitHub-Flavoured Markdown (GFM) pipe table from a
:class:`~linkml_mermaid.types.TableDef` or from explicit columns + rows.

**This renderer is pure** — it knows nothing about LinkML.  Enrichment
with schema descriptions is done by the mapping layer before data
reaches here.

Specification references
========================

GFM §4.10 Tables (extension)
    https://github.github.com/gfm/#tables-extension-
    "A table is an arrangement of data with rows and columns, consisting
     of a single header row, a delimiter row separating the header from
     the data, and zero or more data rows."

    "Each row consists of cells containing arbitrary text, in which
     inlines are parsed, separated by pipes (|). A leading and trailing
     pipe is also recommended for clarity of reading, and if there's
     otherwise parsing ambiguity. Spaces between pipes and cell content
     are trimmed."

    "The delimiter row consists of cells whose only content are hyphens
     (-), and optionally, a leading or trailing colon (:), or both, to
     indicate left, right, or center alignment respectively."

GFM §6.4 Emphasis and strong emphasis
    https://github.github.com/gfm/#emphasis-and-strong-emphasis
    ``**text**`` produces <strong>text</strong>.
    ``*text*`` produces <em>text</em>.
    Used by the ``"bold"`` and ``"italic"`` column format options.

GFM §6.3 Code spans
    https://github.github.com/gfm/#code-spans
    `` `text` `` produces <code>text</code>.
    Used by the ``"code"`` column format option.
"""

from __future__ import annotations

from .escaping import escape_table_cell
from .types import COLUMN_ALIGNMENTS, ColumnDef, TableDef

# Format wrappers for cell values, corresponding to GFM inline syntax.
# See module-level docstring for spec references.
_FORMATTERS: dict[str, str] = {
    "plain": "{}",
    "bold": "**{}**",  # GFM §6.4 — strong emphasis
    "code": "`{}`",  # GFM §6.3 — code spans
    "italic": "*{}*",  # GFM §6.4 — emphasis
}


class MarkdownTableRenderer:
    """Render a GFM §4.10 pipe table.

    Output structure per spec::

        | Header1 | Header2 |   ← header row
        | ---     | ---     |   ← delimiter row (hyphens only = left-align)
        | cell    | cell    |   ← data rows

    Example::

        from linkml_mermaid.types import ColumnDef

        cols = [
            ColumnDef("State", "state", format="bold"),
            ColumnDef("Description", "description"),
        ]
        rows = [
            {"state": "Draft", "description": "Being defined"},
            {"state": "Approved", "description": "Finalized"},
        ]
        renderer = MarkdownTableRenderer()
        print(renderer.render(cols, rows))
    """

    def render(
        self,
        columns: list[ColumnDef],
        rows: list[dict[str, str]],
    ) -> str:
        """Produce a GFM pipe table string.

        Per GFM §4.10: header row, delimiter row, then data rows.
        Each cell is pipe-delimited with leading and trailing pipes.
        The delimiter row encodes each column's alignment.

        Header text and cell values are escaped per §4.10 — a ``|`` in
        the content becomes ``\\|`` so it cannot be mistaken for a cell
        delimiter, and newlines become ``<br>`` because a cell holds
        inline content only.  Escaping happens *before* the inline
        format wrapper is applied, so the wrapper's own ``*`` or
        backtick characters are never touched.
        """
        # Header row  (GFM §4.10: first row is the header)
        header = "| " + " | ".join(escape_table_cell(c.header) for c in columns) + " |"

        # Delimiter row  (GFM §4.10: hyphens, optional colons for alignment)
        separator = "| " + " | ".join(COLUMN_ALIGNMENTS[c.align] for c in columns) + " |"

        # Data rows  (GFM §4.10: subsequent rows after delimiter)
        data_lines: list[str] = []
        for row in rows:
            cells: list[str] = []
            for col in columns:
                raw = row.get(col.key, "")
                fmt = _FORMATTERS[col.format]
                # Only apply formatting to non-empty values
                cells.append(fmt.format(escape_table_cell(raw)) if raw else raw)
            data_lines.append("| " + " | ".join(cells) + " |")

        return "\n".join([header, separator, *data_lines])

    def render_from_def(self, table_def: TableDef) -> str:
        """Render from a :class:`TableDef` object."""
        return self.render(table_def.columns, table_def.rows)
