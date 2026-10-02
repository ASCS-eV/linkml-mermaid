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
    Cell content is *not* plain text by default: "Each row consists of
    cells containing arbitrary text, in which inlines are parsed."

GFM §2.4 Backslash escapes
    https://github.github.com/gfm/#backslash-escapes
    "Any ASCII punctuation character may be backslash-escaped ...
     Backslash escapes do not work in code blocks, code spans, autolinks,
     or raw HTML."
    This is why :func:`escape_table_cell` and
    :func:`escape_table_code_cell` are separate functions: inside a code
    span a backslash is a literal backslash, so the escapes that make
    text literal everywhere else would themselves become visible.

Cell contract
=============

A cell value is treated as **literal text**.  Every character that could
open an inline construct is neutralised, so the text a caller supplies
is the text a GFM renderer displays.  Styling is requested through
:class:`~linkml_mermaid.types.ColumnDef.format`, never by embedding
markup in the value.  This also means a value can never inject raw HTML
into a rendered page.
"""

from __future__ import annotations

import re

# A line break inside a label or cell would terminate the construct.
# Both Mermaid labels and GFM cells accept inline HTML, so <br> is the
# portable in-place substitute.
_LINE_BREAK = "<br>"

_NEWLINES_RE = re.compile(r"\r\n|\r|\n")

# Characters that can open an inline construct in GFM and therefore
# change what a cell displays: code spans (§6.3), emphasis (§6.4), links
# and images (§6.6/§6.7), raw HTML (§6.11), entity references (§6.2),
# strikethrough (§6.5, extension), the table delimiter (§4.10), and the
# scheme separator that triggers the autolink extension (§6.9).  The
# backslash is listed first so its own escape is not re-escaped.
_TABLE_ACTIVE_CHARS = "\\`*_[]<>&~|!:"

_TABLE_ESCAPE_RE = re.compile("([" + re.escape(_TABLE_ACTIVE_CHARS) + "])")

# GFM's extended autolink extension (§6.9) also linkifies a bare "www."
# token, which involves no active character at all.  Escaping the dot
# that follows the "www" defeats it while leaving every other dot in the
# value untouched, so a version number or an abbreviation does not
# acquire backslashes in the Markdown source.  The match is
# case-insensitive even though cmark-gfm only triggers on lowercase, so
# that a stricter implementation cannot reopen the hole.
_WWW_AUTOLINK_RE = re.compile(r"(?i)\bwww\.")

# Runs of backticks, used to pick a code-span delimiter that cannot be
# terminated early by the content (GFM §6.3).
_BACKTICK_RUN_RE = re.compile(r"`+")

# The stateDiagram-v2 grammar uses ":" to separate a state or transition
# from its description, and "::" to apply a class.  Neither position is
# quotable, so the character itself must be escaped.
_COLON_ENTITY = "#58;"

# ";" ends a statement in the stateDiagram-v2 grammar, so text after one
# is read as new diagram source.  Unlike the colon this applies to the
# state description too, which is why it is escaped in every state text
# position rather than only the unquotable ones.  Verified against the
# parser: a label of "do x; then A --> B" silently adds two states and a
# transition the caller never asked for.
_SEMICOLON_ENTITY = "#59;"

# State text is escaped in a single pass.  Doing it as successive
# str.replace calls would corrupt the output, because the entities this
# escaping emits themselves contain "#" and ";": escaping ";" after
# '"' -> "#quot;" would turn it into "#quot#59;".  One regex pass cannot
# re-enter its own replacements.
_STATE_TEXT_MAP = {"#": "#35;", '"': "#quot;", ";": _SEMICOLON_ENTITY}
_STATE_INLINE_MAP = {**_STATE_TEXT_MAP, ":": _COLON_ENTITY}

_STATE_TEXT_RE = re.compile("[" + re.escape("".join(_STATE_TEXT_MAP)) + "]")
_STATE_INLINE_RE = re.compile("[" + re.escape("".join(_STATE_INLINE_MAP)) + "]")

# Mermaid's flowchart lexer recognises "direction" as a keyword even
# inside a quoted subgraph title.  "#100;" is the entity for "d".
_SUBGRAPH_DIRECTION_RE = re.compile(r"\bdirection\b")


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
    """Escape text for a Mermaid ``stateDiagram-v2`` state description.

    State descriptions are unquoted and run to the end of the line, so a
    newline would silently truncate the label and leave a stray line in
    the diagram body.  Quotes are escaped so the text stays safe in the
    ``state "description" as id`` form, which the renderer selects when
    the label contains a colon.

    ``;`` is escaped as ``#59;`` because it ends a statement: a label of
    ``"do x; then A --> B"`` would otherwise add two states and a
    transition to the diagram.  The quoted form does not protect against
    this, so the escape applies to both forms.

    A colon is deliberately *not* escaped here: the renderer switches to
    the quoted form, which the grammar accepts with any number of
    colons.  Positions that have no quoted form use
    :func:`escape_state_inline` instead.

    Example::

        >>> escape_state_label("stop; go")
        'stop#59; go'
    """
    out = _STATE_TEXT_RE.sub(lambda m: _STATE_TEXT_MAP[m.group()], text)
    return _NEWLINES_RE.sub(_LINE_BREAK, out)


def escape_state_inline(text: str) -> str:
    """Escape text for an unquotable ``stateDiagram-v2`` position.

    Transition labels (§Transitions) and note bodies (§Notes) are
    introduced by ``:`` and have no quoted form, so a colon in the text
    is read as grammar.  A single colon in a transition label happens to
    survive, but ``::`` is the class-application operator and a colon
    anywhere in a note body is a parse error, so every colon is escaped
    as the entity ``#58;``.

    Everything :func:`escape_state_label` handles — including the
    statement separator ``;`` — is handled here too, in the same single
    pass.

    Example::

        >>> escape_state_inline("state: ready")
        'state#58; ready'
    """
    out = _STATE_INLINE_RE.sub(lambda m: _STATE_INLINE_MAP[m.group()], text)
    return _NEWLINES_RE.sub(_LINE_BREAK, out)


def escape_subgraph_title(text: str) -> str:
    """Escape text for a Mermaid flowchart subgraph title (§Subgraphs).

    Mermaid's flowchart lexer matches the ``direction`` keyword inside a
    quoted subgraph title, so a title such as ``"set direction LR"``
    fails to parse even though the same text is accepted in a node or
    edge label.  Writing the leading ``d`` as the entity ``#100;``
    prevents the match; the rendered title is unchanged.

    Example::

        >>> escape_subgraph_title("set direction LR")
        'set #100;irection LR'
    """
    return _SUBGRAPH_DIRECTION_RE.sub("#100;irection", escape_mermaid_text(text))


def escape_table_cell(text: str) -> str:
    """Escape text for a GFM §4.10 pipe-table cell, as literal text.

    Cell content is parsed as inline markdown (§4.10: "cells containing
    arbitrary text, in which inlines are parsed"), so backticks,
    asterisks, brackets, raw HTML and entity references in caller data
    would otherwise be interpreted rather than displayed.  Every such
    character is backslash-escaped per §2.4, which renders it literally
    and — because raw HTML is neutralised too — prevents a cell value
    from injecting markup into the rendered page.

    Newlines become ``<br>`` because a cell holds inline content only.

    One gap remains, and it is a property of GFM rather than of this
    function: the extended autolink extension (§6.9) linkifies a bare
    email address, and cmark-gfm honours neither ``user\\@host`` nor
    ``user&#64;host`` as a way to suppress it.  A cell whose value is an
    email address will therefore render as a ``mailto:`` link.  The
    ``www.`` and ``scheme://`` forms *are* suppressed.

    This function must not be used for text that will be placed inside a
    code span; see :func:`escape_table_code_cell`.

    Example::

        >>> escape_table_cell("x|y")
        'x\\\\|y'
        >>> escape_table_cell("<b>hi</b>")
        '\\\\<b\\\\>hi\\\\</b\\\\>'
    """
    out = _TABLE_ESCAPE_RE.sub(r"\\\1", text)
    out = _WWW_AUTOLINK_RE.sub(lambda m: m.group(0)[:-1] + "\\.", out)
    return _NEWLINES_RE.sub(_LINE_BREAK, out)


def escape_table_code_cell(text: str) -> str:
    """Escape text that will be placed inside a GFM §6.3 code span.

    Per §2.4, "backslash escapes do not work in ... code spans", so the
    escaping applied by :func:`escape_table_cell` would leave visible
    backslashes.  Inside a code span only the table extension still
    applies: §4.10 requires a pipe to be escaped "including inside other
    inline spans".

    Newlines are *not* handled here — a code span cannot contain a line
    break, so the caller splits the text and emits one span per line.

    Example::

        >>> escape_table_code_cell("a|b")
        'a\\\\|b'
    """
    return text.replace("|", r"\|")


def code_span_delimiter(text: str) -> str:
    """Return a backtick run that can safely delimit *text* (GFM §6.3).

    "The contents of the code span are the characters between the two
    backtick strings" — so a delimiter must be longer than any backtick
    run inside the content, otherwise the span ends early and the rest
    of the value is rendered as ordinary text.
    """
    runs = [len(m.group(0)) for m in _BACKTICK_RUN_RE.finditer(text)]
    return "`" * ((max(runs) + 1) if runs else 1)
