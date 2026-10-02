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

from dataclasses import dataclass, field

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


# Spec §Notes  — …#notes
#   "Here you can choose to put the note to the right of or to the
#    left of a node."
#
# Syntax:  note right of StateId : text


@dataclass(frozen=True)
class MermaidNote:
    """A note attached to a state (§Notes).

    Rendered as::

        note {position} of {state_id} : {text}

    Attributes:
        state_id: The state ID to attach the note to.
        text: Note content.
        position: ``"right"`` (default) or ``"left"`` per §Notes.
    """

    state_id: str
    text: str
    position: str = "right"


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
    """

    id: str
    title: str | None = None
    node_ids: list[str] = field(default_factory=list)


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
