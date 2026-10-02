"""Data types for Mermaid diagram and GFM table generation.

These types represent **pure rendering concepts** — they have no knowledge
of LinkML, YAML data files, or any specific domain.  Renderers consume
them and produce syntactically valid output.

Each type maps directly to a construct defined in the relevant specification:

Mermaid stateDiagram-v2 spec
    https://mermaid.js.org/syntax/stateDiagram.html
    Defines: states, transitions, start/end pseudo-states, notes,
    composite states, choice/fork/join pseudo-states, direction
    directive, classDef styling.

GitHub Flavored Markdown (GFM) table extension — §4.10
    https://github.github.com/gfm/#tables-extension-
    Defines: pipe-delimited table syntax, delimiter row (hyphens with
    optional colon alignment), header row, data rows, inline formatting
    within cells.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Identifier validation ────────────────────────────────────────────
#
# Identifiers are interpolated into the diagram source unquoted, because
# that is the only form the grammars accept.  An unvalidated identifier
# is therefore not merely a rendering risk but an injection vector: an
# id of ``"A --> Evil"`` produces a *valid* diagram containing a node and
# an edge the caller never asked for, so the defect cannot be caught by
# checking that the output parses.
#
# The accepted character sets below were established by feeding
# candidate identifiers to the Mermaid parser, one character at a time,
# and keeping only those both grammars accept in both a declaration and
# a reference.  Flowchart ids additionally accept "-"; state ids do not,
# because the state grammar reads it as the start of an arrow.
#
# A single "-" between other characters is safe in a flowchart id, which
# matters because kebab-case is a common naming style.  What is not safe
# is a "-" followed by another "-" or by ".", because those begin the
# link operators "---", "-->", "-.-" and "-.->": an id of "A---B" draws
# two nodes joined by a link rather than one node called "A---B".  The
# lookahead rejects exactly those two sequences, which was confirmed to
# reject every hyphen pattern the parser mishandles and no other.

_FLOWCHART_ID_RE = re.compile(r"\A(?!.*-[-.])[A-Za-z0-9_.-]+\Z")
_STATE_ID_RE = re.compile(r"\A[A-Za-z0-9_.]+\Z")

# Words the respective lexers claim for their own grammar.  Each list was
# derived by sweeping a corpus of every keyword in both grammars through
# the real parser in all four positions the renderers emit — flowcharts:
# node declaration, bare declaration, edge endpoint and subgraph id;
# state diagrams: bare declaration, "id : label", 'state "label" as id'
# and transition endpoint — and keeping the words that broke any of
# them.  Words that merely look reserved (``direction``, ``End``,
# ``TB``, ``LR``, ``o``, ``x``, ``as``) parse cleanly in every position
# and are deliberately accepted: rejecting them would turn working
# caller code into an exception for no reason.
#
# ``stateDiagram-v2`` also breaks, but the hyphen already puts it
# outside the state identifier character set, so it cannot reach here.
FLOWCHART_RESERVED_IDS = frozenset(
    {
        "_blank",
        "_parent",
        "_self",
        "_top",
        "call",
        "class",
        "classDef",
        "click",
        "default",
        "end",
        "flowchart",
        "graph",
        "href",
        "interpolate",
        "linkStyle",
        "style",
        "subgraph",
    }
)
STATE_RESERVED_IDS = frozenset(
    {
        "class",
        "classDef",
        "click",
        "default",
        "href",
        "note",
        "state",
        "stateDiagram",
        "style",
    }
)

# §Start and End — "written with the [*] syntax".  The renderer emits
# these from the is_initial/is_terminal flags, but a caller may also
# name the pseudo-state directly as a transition endpoint.
START_END_PSEUDO_STATE = "[*]"


def validate_flowchart_id(value: str, field_name: str) -> str:
    """Return *value* if it is a usable flowchart identifier.

    Raises:
        ValueError: If *value* is empty, contains a character outside
            ``[A-Za-z0-9_.-]``, or is a word the flowchart lexer
            reserves.  Rejecting is deliberate: Mermaid would otherwise
            accept many of these and silently render a different diagram
            from the one requested.
    """
    if not isinstance(value, str) or not _FLOWCHART_ID_RE.match(value):
        raise ValueError(
            f"Invalid flowchart {field_name} {value!r}: an identifier must be one or more "
            "of the characters A-Z a-z 0-9 _ . - and may not contain '--' or '-.', which "
            "begin a link operator.  "
            "Put spaces and punctuation in the label instead, which is quoted and escaped."
        )
    if value in FLOWCHART_RESERVED_IDS:
        raise ValueError(
            f"Invalid flowchart {field_name} {value!r}: the Mermaid flowchart grammar "
            f"reserves this word; reserved words are {sorted(FLOWCHART_RESERVED_IDS)}"
        )
    return value


def validate_state_id(value: str, field_name: str, *, allow_pseudo_state: bool = False) -> str:
    """Return *value* if it is a usable ``stateDiagram-v2`` identifier.

    Parameters:
        allow_pseudo_state: Permit the literal ``[*]`` defined in
            §Start and End.  Enabled for transition endpoints, where the
            pseudo-state is a legal target, and disabled for state
            declarations, where it is not.

    Raises:
        ValueError: If *value* is empty, contains a character outside
            ``[A-Za-z0-9_.]``, or is a word the state grammar reserves.
    """
    if allow_pseudo_state and value == START_END_PSEUDO_STATE:
        return value
    if not isinstance(value, str) or not _STATE_ID_RE.match(value):
        hint = (
            f" or the pseudo-state '{START_END_PSEUDO_STATE}'"
            if allow_pseudo_state
            else " Use the label for text that needs spaces or punctuation."
        )
        raise ValueError(
            f"Invalid state {field_name} {value!r}: an identifier must be one or more of "
            f"the characters A-Z a-z 0-9 _ .{hint}  "
            "to_state_id() converts a human-readable label into a valid id."
        )
    if value in STATE_RESERVED_IDS:
        raise ValueError(
            f"Invalid state {field_name} {value!r}: the Mermaid stateDiagram-v2 grammar "
            f"reserves this word; reserved words are {sorted(STATE_RESERVED_IDS)}"
        )
    return value


# ── stateDiagram-v2 primitives ───────────────────────────────────────
#
# Spec §States  — https://mermaid.js.org/syntax/stateDiagram.html#states
#   "A state can be declared in multiple ways. The simplest way is to
#    define a state with just an id … Another way is by using the state
#    keyword with a description … Another way to define a state with a
#    description is to define the state id followed by a colon and the
#    description."
#
# Spec §Start and End  — …#start-and-end
#   "There are two special states indicating the start and stop of the
#    diagram. These are written with the [*] syntax and the direction
#    of the transition to it defines it either as a start or a stop
#    state."


@dataclass(frozen=True)
class MermaidState:
    """A state node in a ``stateDiagram-v2``.

    Maps to the Mermaid "States" construct (§States):
    - ``id`` becomes the Mermaid state identifier (must be a valid
      identifier — PascalCase, no spaces).  See also §Spaces in state
      names: "Spaces can be added to a state by first defining the state
      with an id and then referencing the id later."
    - ``label`` becomes the description shown via ``StateId : Label``.
    - ``is_initial`` / ``is_terminal`` map to the ``[*]`` pseudo-state
      transitions defined in §Start and End.

    Attributes:
        id: Valid Mermaid state identifier (PascalCase, no spaces).
        label: Human-readable display label.  If *None* the renderer
            uses *id* as the label.
        description: Optional documentation text (not rendered in the
            diagram but available to downstream consumers like table
            generators).
        is_initial: If ``True`` the renderer emits ``[*] --> {id}``
            per §Start and End.
        is_terminal: If ``True`` the renderer emits ``{id} --> [*]``
            per §Start and End.
    """

    id: str
    label: str | None = None
    description: str | None = None
    is_initial: bool = False
    is_terminal: bool = False

    def __post_init__(self) -> None:
        validate_state_id(self.id, "id")


# Spec §Transitions  — …#transitions
#   "Transitions are path/edges when one state passes into another.
#    This is represented using text arrow, '-->'.  It is possible to add
#    text to a transition to describe what it represents."


@dataclass(frozen=True)
class MermaidTransition:
    """A directed edge in a ``stateDiagram-v2``.

    Maps to the Mermaid "Transitions" construct (§Transitions).
    Rendered as::

        FromState --> ToState : label

    Multi-line labels use ``\\n`` as the line separator per Mermaid's
    inline label formatting.

    Attributes:
        from_state: Source state ID (must match a ``MermaidState.id``).
        to_state: Target state ID.
        label: Transition label text (action, actor, guard, …).
    """

    from_state: str
    to_state: str
    label: str | None = None

    def __post_init__(self) -> None:
        validate_state_id(self.from_state, "from_state", allow_pseudo_state=True)
        validate_state_id(self.to_state, "to_state", allow_pseudo_state=True)


# Spec §Notes  — …#notes
#   "Here you can choose to put the note to the right of or to the
#    left of a node."
#
# Syntax:  note right of StateId : text

# The two positions §Notes defines.  Mermaid has no fallback for any
# other word: it is a lexical error.
NOTE_POSITIONS = frozenset({"left", "right"})


@dataclass(frozen=True)
class MermaidNote:
    """A note attached to a state (§Notes).

    Rendered as::

        note {position} of {state_id} : {text}

    Attributes:
        state_id: The state ID to attach the note to.
        text: Note content.
        position: ``"right"`` (default) or ``"left"`` per §Notes.

    Raises:
        ValueError: If *state_id* is not a valid state identifier, or
            *position* is not one of the two the grammar defines.  Any
            other position is a lexical error in Mermaid rather than a
            cosmetic difference, so it is rejected at construction.
    """

    state_id: str
    text: str
    position: str = "right"

    def __post_init__(self) -> None:
        validate_state_id(self.state_id, "state_id")
        if self.position not in NOTE_POSITIONS:
            raise ValueError(
                f"Invalid note position '{self.position}'; must be one of {sorted(NOTE_POSITIONS)}"
            )


# ── Flowchart primitives ─────────────────────────────────────────────
#
# Mermaid Flowchart spec
#   https://mermaid.js.org/syntax/flowchart.html
#
# §A node (default)
#   "The id is what is displayed in the box."
#   Bare form: just the id.
#
# §A node with text
#   "It is also possible to set text in the box that differs from the
#    id."
#   Bracket forms define the shape:
#     id["text"]   — rectangle (default)
#     id("text")   — rounded edges
#     id(["text"]) — stadium-shaped
#     id{"text"}   — rhombus (decision)
#     id{{"text"}} — hexagon
#     id[["text"]] — subroutine
#     id(("text")) — circle
#     id>"text"]   — asymmetric
#     id[/"text"/] — parallelogram
#     id[\"text"\] — parallelogram alt
#     id[/"text"\] — trapezoid
#     id[\"text"/] — trapezoid alt
#
# §Direction
#   "This statement declares the direction of the Flowchart."
#   Values: TB, TD (top-down), BT, RL, LR.
#
# §Links between nodes
#   https://mermaid.js.org/syntax/flowchart.html#links-between-nodes
#
# §A link with arrow head
#   "A --> B"
#
# §A link with arrow head and text
#   "A -->|text| B" or "A -- text --> B"
#
# §Dotted link
#   "A -.-> B"
#
# §Dotted link with text
#   "A -.->|text| B" or "A -. text .-> B"
#
# §Thick link
#   "A ==> B"
#
# §Thick link with text
#   "A ==>|text| B" or "A == text ==> B"
#
# §Subgraphs
#   https://mermaid.js.org/syntax/flowchart.html#subgraphs
#   "subgraph title\n    graph definition\nend"
#   "You can also set an explicit id for the subgraph."


# Node shape names, one per bracket form documented in §A node with text.
NODE_SHAPES = frozenset({"rect", "round", "stadium", "diamond", "hexagon", "subroutine", "circle"})


@dataclass(frozen=True)
class FlowchartNode:
    """A node in a Mermaid ``flowchart``.

    Maps to the Mermaid "Nodes" constructs:
    - §A node (default): bare ``id`` (no text, shape defaults to rectangle)
    - §A node with text: ``id["text"]`` and other bracket forms per shape

    The ``shape`` attribute selects the bracket form:
    - ``"rect"``      — ``id["text"]``  (rectangle, default)
    - ``"round"``     — ``id("text")``  (rounded edges)
    - ``"stadium"``   — ``id(["text"])`` (stadium-shaped / pill)
    - ``"diamond"``   — ``id{"text"}``  (rhombus / decision)
    - ``"hexagon"``   — ``id{{"text"}}`` (hexagon)
    - ``"subroutine"``— ``id[["text"]]`` (subroutine)
    - ``"circle"``    — ``id(("text"))`` (circle)

    Attributes:
        id: Valid Mermaid node identifier (no spaces, no reserved words).
            Per the spec warning: avoid using ``"end"`` in all lowercase.
        label: Human-readable text displayed inside the node. If *None*,
            the bare ``id`` is used (§A node default).
        shape: Node shape selector (see above). Default ``"rect"``.
    """

    id: str
    label: str | None = None
    shape: str = "rect"

    def __post_init__(self) -> None:
        validate_flowchart_id(self.id, "node id")
        if self.shape not in NODE_SHAPES:
            raise ValueError(
                f"Invalid node shape '{self.shape}'; must be one of {sorted(NODE_SHAPES)}"
            )


# Link style constants — derived from §Links between nodes:
#   Normal: "---" (open), "-->" (arrow)
#   Dotted: "-.-" (open), "-.->" (arrow)  — §Dotted link
#   Thick:  "===" (open), "==>" (arrow)   — §Thick link

LINK_STYLES = frozenset({"solid", "dotted", "thick"})


@dataclass(frozen=True)
class FlowchartEdge:
    """A directed edge (link) in a Mermaid ``flowchart``.

    Maps to the Mermaid "Links between nodes" constructs:
    - §A link with arrow head: ``A --> B``
    - §A link with arrow head and text: ``A -->|"text"| B``
    - §Dotted link: ``A -.-> B``
    - §Dotted link with text: ``A -.->|"text"| B``
    - §Thick link: ``A ==> B``
    - §Thick link with text: ``A ==>|"text"| B``

    Attributes:
        from_node: Source node ID (must match a ``FlowchartNode.id``).
        to_node: Target node ID.
        label: Optional edge label text. Per §Text on links, rendered
            using the pipe syntax: ``-->|"text"|``.
        style: Link style — ``"solid"`` (default ``-->``),
            ``"dotted"`` (``-.->``), or ``"thick"`` (``==>``).
    """

    from_node: str
    to_node: str
    label: str | None = None
    style: str = "solid"

    def __post_init__(self) -> None:
        validate_flowchart_id(self.from_node, "edge from_node")
        validate_flowchart_id(self.to_node, "edge to_node")
        if self.style not in LINK_STYLES:
            raise ValueError(
                f"Invalid edge style '{self.style}'; must be one of {sorted(LINK_STYLES)}"
            )


@dataclass(frozen=True)
class FlowchartSubgraph:
    """A subgraph container in a Mermaid ``flowchart``.

    Maps to §Subgraphs:
    - ``subgraph title`` / ``subgraph id["title"]``
    - Contains node IDs that belong to this subgraph
    - Closed with ``end``

    Attributes:
        id: Subgraph identifier. Per §Subgraphs: "You can also set
            an explicit id for the subgraph."
        title: Display title. If *None*, uses ``id`` as title.
        node_ids: List of node IDs contained in this subgraph.

    Raises:
        ValueError: If *id* or any entry of *node_ids* is not a valid
            flowchart identifier.
    """

    id: str
    title: str | None = None
    node_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        validate_flowchart_id(self.id, "subgraph id")
        for nid in self.node_ids:
            validate_flowchart_id(nid, "subgraph member node id")


# ── Markdown table primitives ────────────────────────────────────────
#
# GFM §4.10 Tables (extension)
#   https://github.github.com/gfm/#tables-extension-
#
#   "A table is an arrangement of data with rows and columns, consisting
#    of a single header row, a delimiter row separating the header from
#    the data, and zero or more data rows."
#
#   "Each row consists of cells containing arbitrary text, in which
#    inlines are parsed, separated by pipes (|). A leading and trailing
#    pipe is also recommended for clarity of reading."
#
#   "The delimiter row consists of cells whose only content are hyphens
#    (-), and optionally, a leading or trailing colon (:), or both, to
#    indicate left, right, or center alignment respectively."
#
# Inline formatting within cells (GFM §6.4):
#   "emphasis and strong emphasis" — ``*text*`` / ``**text**``
#   "code spans" (§6.3) — `` `text` ``


# Inline formatting names (GFM §6.3 code spans, §6.4 emphasis).
CELL_FORMATS = frozenset({"plain", "bold", "code", "italic"})

# Delimiter-row forms per §4.10: "cells whose only content are hyphens (-),
# and optionally, a leading or trailing colon (:), or both, to indicate
# left, right, or center alignment respectively."
COLUMN_ALIGNMENTS: dict[str, str] = {
    "default": "---",
    "left": ":---",
    "center": ":---:",
    "right": "---:",
}


@dataclass(frozen=True)
class ColumnDef:
    """Definition of a single column in a GFM pipe table.

    Attributes:
        header: Column header text (appears in the header row).
        key: Key to look up in each row dict.
        format: Inline formatting wrapper applied to cell values.
            ``"plain"`` — no wrapping.
            ``"bold"`` — ``**value**``  (GFM §6.4 strong emphasis).
            ``"code"`` — `` `value` ``  (GFM §6.3 code spans).
            ``"italic"`` — ``*value*``  (GFM §6.4 emphasis).
        align: Column alignment, encoded in the §4.10 delimiter row.
            ``"default"`` — ``---`` (no colon; renderer default, which
            CommonMark implementations treat as left).
            ``"left"`` — ``:---``.
            ``"center"`` — ``:---:``.
            ``"right"`` — ``---:``.

    Raises:
        ValueError: If *format* or *align* is not a recognised value.
            Unknown values are rejected rather than silently ignored, so
            a typo surfaces at construction instead of producing a table
            that is quietly formatted wrong.
    """

    header: str
    key: str
    format: str = "plain"
    align: str = "default"

    def __post_init__(self) -> None:
        if self.format not in CELL_FORMATS:
            raise ValueError(
                f"Invalid cell format '{self.format}'; must be one of {sorted(CELL_FORMATS)}"
            )
        if self.align not in COLUMN_ALIGNMENTS:
            raise ValueError(
                f"Invalid column alignment '{self.align}'; "
                f"must be one of {sorted(COLUMN_ALIGNMENTS)}"
            )


@dataclass
class TableDef:
    """Complete definition for a GFM pipe table (§4.10).

    Attributes:
        columns: Ordered column definitions (determines header row
            and delimiter row).
        rows: Data rows; each dict's keys must include every
            ``ColumnDef.key``.
    """

    columns: list[ColumnDef]
    rows: list[dict[str, str]] = field(default_factory=list)
