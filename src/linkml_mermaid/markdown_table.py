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
    "The contents of the code span are the characters between the two
     backtick strings" — so the delimiter length is chosen per value.

GFM §2.4 Backslash escapes
    https://github.github.com/gfm/#backslash-escapes
    "Backslash escapes do not work in code blocks, code spans,
     autolinks, or raw HTML."  The ``"code"`` format therefore uses a
    different escaper from the other three.
"""

from __future__ import annotations

import re

from .escaping import (
    code_span_delimiter,
    escape_table_cell,
    escape_table_code_cell,
)
from .types import COLUMN_ALIGNMENTS, ColumnDef, TableDef

_NEWLINES_RE = re.compile(r"\r\n|\r|\n")

# Format wrappers for the three formats that take escaped inline text.
# "code" is absent: a code span needs a value-dependent delimiter and a
# different escaper, so it is built by _render_code_cell instead.
_INLINE_MARKERS: dict[str, str] = {
    "bold": "**",  # GFM §6.4 — strong emphasis
    "italic": "*",  # GFM §6.4 — emphasis
}


def _render_code_cell(raw: str) -> str:
    """Wrap *raw* in one or more GFM §6.3 code spans.

    Three properties of code spans drive this:

    - The delimiter must be longer than any backtick run in the content,
      or the span ends early (§6.3).
    - A span whose content begins or ends with a space or a backtick
      needs one space of padding.  §6.3 removes a single space from each
      end when the content "both begins and ends with a space character,
      but does not consist entirely of space characters", so the padding
      is given back and the value survives intact.
    - A code span cannot contain a line break, and raw HTML is not
      parsed inside one, so a ``<br>`` placed *within* the span would be
      displayed literally.  Multi-line values are therefore split into
      one span per line, joined by ``<br>`` *between* the spans.

    A line with no non-whitespace content produces no span at all. The
    padding rule above is the one case §6.3 declines to undo, so such a
    line would come back wider than it went in; it has nothing to show
    in a table either way.
    """
    parts: list[str] = []
    for line in _NEWLINES_RE.split(raw):
        if not line.strip():
            parts.append("")
            continue
        content = escape_table_code_cell(line)
        fence = code_span_delimiter(content)
        pad = " " if content[0] in "` " or content[-1] in "` " else ""
        parts.append(f"{fence}{pad}{content}{pad}{fence}")
    return "<br>".join(parts)


def _render_cell(raw: str, fmt: str) -> str:
    """Escape *raw* and apply the inline format *fmt* requested by the column."""
    if raw == "":
        return ""
    if fmt == "code":
        return _render_code_cell(raw)

    escaped = escape_table_cell(raw)
    marker = _INLINE_MARKERS.get(fmt)
    if marker is None:
        return escaped

    # §6.4: a left-flanking delimiter run may not be followed by
    # whitespace, nor a right-flanking run preceded by it, so emphasis
    # around padded text silently renders as literal asterisks.  The
    # padding is dropped, which is invisible in a table: §4.10 specifies
    # that "spaces between pipes and cell content are trimmed" anyway.
    inner = escaped.strip()
    if not inner:
        return escaped
    return f"{marker}{inner}{marker}"


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

        Cell values and header text are treated as **literal text**: a
        cell holds inline content in which "inlines are parsed" (§4.10),
        so every character that could open an inline construct is
        escaped and the caller's text is displayed verbatim.  Styling
        comes from ``ColumnDef.format`` alone.  Newlines become ``<br>``
        because a cell cannot span lines.

        A value that is not a string is converted with :func:`str`, so a
        row carrying an ``int`` or ``None`` renders rather than raising
        deep inside the join.
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
                text = raw if isinstance(raw, str) else ("" if raw is None else str(raw))
                cells.append(_render_cell(text, col.format))
            data_lines.append("| " + " | ".join(cells) + " |")

        return "\n".join([header, separator, *data_lines])

    def render_from_def(self, table_def: TableDef) -> str:
        """Render from a :class:`TableDef` object."""
        return self.render(table_def.columns, table_def.rows)
