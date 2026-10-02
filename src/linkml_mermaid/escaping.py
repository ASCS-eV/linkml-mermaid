"""Text escaping for Mermaid and GFM output.

Renderers interpolate caller-supplied text into grammars that assign
meaning to specific characters.  Without escaping, an ordinary label
containing a quote or a pipe silently produces output that no longer
parses as the construct it was meant to be.  These helpers translate
such characters into the escape mechanism each specification defines.

Specification references
========================

Mermaid §Entity codes to escape characters
    https://mermaid.js.org/syntax/flowchart.html#entity-codes-to-escape-characters
    "It is possible to escape characters using the syntax exemplified
     here:  ``A["A double quote:#quot;"] --> B["A dec char:#9829;"]``.
     Numbers given are base 10, so ``#`` can be encoded as ``#35;``."

Mermaid §Special characters that break syntax
    https://mermaid.js.org/syntax/flowchart.html#special-characters-that-break-syntax
    "It is possible to put text within quotes in order to render more
     troublesome characters."

GFM §4.10 Tables (extension)
    https://github.github.com/gfm/#tables-extension-
    "The pipes that delimit cells ... include a pipe in a cell's content
     by escaping it, including inside other inline spans."
    Cells hold inline content only, so a cell cannot contain a newline:
    "The table is broken at the first empty line, or beginning of
     another block-level structure."
"""

from __future__ import annotations

import re

# A line break inside a label or cell would terminate the construct.
# Both Mermaid labels and GFM cells accept inline HTML, so <br> is the
# portable in-place substitute.
_LINE_BREAK = "<br>"

_NEWLINES_RE = re.compile(r"\r\n|\r|\n")

# Runs of backslashes immediately preceding a pipe.  GFM consumes a
# backslash before ASCII punctuation, so an existing backslash run must
# be doubled before the pipe's own escape is added — otherwise the
# caller's literal backslash would swallow it.
_BACKSLASH_RUN_BEFORE_PIPE_RE = re.compile(r"(\\*)\|")


def escape_mermaid_text(text: str) -> str:
    """Escape text for interpolation into a quoted Mermaid label.

    Applies the entity escapes defined in §Entity codes to escape
    characters.  ``#`` is escaped first because it introduces an entity:
    escaping it afterwards would corrupt the entities this function
    itself emits.

    Used for flowchart node labels, edge labels and subgraph titles —
    every position where the renderer emits ``"..."``.

    Example::

        >>> escape_mermaid_text('say "hi"')
        'say #quot;hi#quot;'
    """
    out = text.replace("#", "#35;")
    out = out.replace('"', "#quot;")
    return _NEWLINES_RE.sub(_LINE_BREAK, out)


def escape_state_label(text: str) -> str:
    """Escape text for a Mermaid ``stateDiagram-v2`` label.

    State descriptions are unquoted and run to the end of the line, so a
    newline would silently truncate the label and leave a stray line in
    the diagram body.  Quotes are escaped so the text stays safe in the
    ``state "description" as id`` form, which the renderer selects when
    the label contains a colon.
    """
    out = text.replace("#", "#35;")
    out = out.replace('"', "#quot;")
    return _NEWLINES_RE.sub(_LINE_BREAK, out)


def escape_table_cell(text: str) -> str:
    """Escape text for a GFM §4.10 pipe-table cell.

    Escapes ``|`` as ``\\|`` per the table extension, and replaces
    newlines with ``<br>`` because a cell holds inline content only.

    Example::

        >>> escape_table_cell("x|y")
        'x\\\\|y'
    """
    out = _BACKSLASH_RUN_BEFORE_PIPE_RE.sub(lambda m: "\\" * (2 * len(m.group(1))) + r"\|", text)
    return _NEWLINES_RE.sub(_LINE_BREAK, out)
