"""Mermaid ``flowchart`` renderer.

Consumes :class:`~linkml_mermaid.types.FlowchartNode`,
:class:`~linkml_mermaid.types.FlowchartEdge`, and optional
:class:`~linkml_mermaid.types.FlowchartSubgraph` objects and produces
a syntactically valid ``flowchart`` code block.

**This renderer is pure** — it knows nothing about LinkML, YAML files,
or any particular domain model.  Mapping from data to these Mermaid
types is handled by domain-specific generators.

Specification references
========================

Mermaid Flowchart — full spec
    https://mermaid.js.org/syntax/flowchart.html

§A node (default)
    https://mermaid.js.org/syntax/flowchart.html#a-node-default
    "The id is what is displayed in the box."
    Bare form: just the id, renders as a rectangle with the id as text.

§A node with text
    https://mermaid.js.org/syntax/flowchart.html#a-node-with-text
    "It is also possible to set text in the box that differs from the
     id. If this is done several times, it is the last text found for
     the node that will be used."
    Shape is determined by bracket syntax:
        id["text"]   — rectangle
        id("text")   — rounded edges
        id(["text"]) — stadium
        id{"text"}   — rhombus / diamond
        id{{"text"}} — hexagon
        id[["text"]] — subroutine
        id(("text")) — circle

§Direction
    https://mermaid.js.org/syntax/flowchart.html#direction
    "This statement declares the direction of the Flowchart."
    Possible values: TB, TD (same as TB), BT, RL, LR.
    Syntax: ``flowchart TD`` (direction is part of the declaration).

§Links between nodes
    https://mermaid.js.org/syntax/flowchart.html#links-between-nodes

§A link with arrow head
    ``A --> B``

§A link with arrow head and text
    ``A -->|"text"| B``  (pipe form)
    ``A -- "text" --> B`` (inline form)
    This renderer uses the pipe form for consistency.

§Dotted link
    ``A -.-> B``

§Dotted link with text
    ``A -.->|"text"| B``

§Thick link
    ``A ==> B``

§Thick link with text
    ``A ==>|"text"| B``

§Subgraphs
    https://mermaid.js.org/syntax/flowchart.html#subgraphs
    "subgraph title\\n    graph definition\\nend"
    With explicit id: ``subgraph id["title"]``

§Special characters that break syntax
    https://mermaid.js.org/syntax/flowchart.html#special-characters-that-break-syntax
    "It is possible to put text within quotes in order to render more
     troublesome characters."
    We always quote node text and edge labels to handle special chars.

§Comments
    https://mermaid.js.org/syntax/flowchart.html#comments
    "Comments need to be on their own line, and must be prefaced with
     %% (double percent signs)."
"""

from __future__ import annotations

from .escaping import escape_mermaid_text
from .types import FlowchartEdge, FlowchartNode, FlowchartSubgraph

# Shape bracket syntax per §A node with text.
# Maps shape name → (open_bracket, close_bracket).
_SHAPE_BRACKETS: dict[str, tuple[str, str]] = {
    "rect": ('["', '"]'),
    "round": ('("', '")'),
    "stadium": ('(["', '"])'),
    "diamond": ('{"', '"}'),
    "hexagon": ('{{"', '"}}'),
    "subroutine": ('[["', '"]]'),
    "circle": ('(("', '"))'),
}

# Edge arrow syntax per §Links between nodes.
# Maps style → (arrow_plain, arrow_with_label_template).
# Label template uses {label} placeholder.
_EDGE_ARROWS: dict[str, tuple[str, str]] = {
    "solid": ("-->", '-->|"{label}"|'),
    "dotted": ("-.->", '-.->|"{label}"|'),
    "thick": ("==>", '==>|"{label}"|'),
}


def _render_node_declaration(node: FlowchartNode) -> str:
    """Render a single node declaration line.

    Per §A node with text, when a label or a non-default shape is set we
    use the bracket form: ``id["label"]``.  Per §A node (default), the
    bare ``id`` is used only when there is nothing else to express —
    emitting it for a shaped node would silently render a rectangle.

    The label is escaped per §Entity codes to escape characters, so a
    quote or ``#`` in the text cannot terminate the quoted string.
    """
    if (node.label is None or node.label == node.id) and node.shape == "rect":
        return node.id

    open_br, close_br = _SHAPE_BRACKETS[node.shape]
    text = escape_mermaid_text(node.label if node.label is not None else node.id)
    return f"{node.id}{open_br}{text}{close_br}"


def _render_edge(edge: FlowchartEdge) -> str:
    """Render a single edge line.

    Per §Links between nodes, the arrow syntax varies by style.
    Per §A link with arrow head and text, labels use pipe form and are
    escaped per §Entity codes to escape characters.
    """
    arrow_plain, arrow_label_tmpl = _EDGE_ARROWS[edge.style]

    arrow = (
        arrow_label_tmpl.replace("{label}", escape_mermaid_text(edge.label))
        if edge.label
        else arrow_plain
    )

    return f"{edge.from_node} {arrow} {edge.to_node}"


class FlowchartRenderer:
    """Render a Mermaid ``flowchart`` from abstract node/edge objects.

    Produces output that conforms to the Mermaid Flowchart spec:
    https://mermaid.js.org/syntax/flowchart.html

    The output does **not** include fenced code block markers
    (````mermaid`` / ``````) — the caller decides how to embed the
    diagram (inline markdown, HTML, etc.).

    Parameters:
        direction: Flowchart layout direction per §Direction.
            ``"TD"`` (top-down, default), ``"TB"`` (same), ``"LR"``
            (left-right), ``"BT"`` (bottom-top), ``"RL"``
            (right-left).

    Example::

        nodes = [
            FlowchartNode(id="A", label="Start"),
            FlowchartNode(id="B", label="End", shape="round"),
        ]
        edges = [FlowchartEdge("A", "B", label="Go")]
        renderer = FlowchartRenderer(direction="TD")
        print(renderer.render(nodes, edges))
    """

    _VALID_DIRECTIONS = frozenset({"TB", "TD", "BT", "RL", "LR"})

    def __init__(self, direction: str = "TD") -> None:
        if direction not in self._VALID_DIRECTIONS:
            raise ValueError(
                f"Invalid direction '{direction}'; must be one of {sorted(self._VALID_DIRECTIONS)}"
            )
        self._direction = direction

    def render(
        self,
        nodes: list[FlowchartNode],
        edges: list[FlowchartEdge],
        subgraphs: list[FlowchartSubgraph] | None = None,
    ) -> str:
        """Produce the complete ``flowchart`` text.

        Output structure:
        1. Declaration with direction: ``flowchart {direction}``
        2. Subgraph blocks (if any), each containing member node
           declarations
        3. Standalone node declarations (nodes not in any subgraph)
        4. Edge declarations

        Per §Direction, the direction is part of the declaration line.

        Raises:
            ValueError: If a subgraph references a node id that is not
                present in *nodes*.  Mermaid would silently auto-create
                an unlabelled node, hiding the typo.
        """
        lines: list[str] = [f"flowchart {self._direction}"]

        # Collect node IDs that belong to subgraphs
        subgraph_node_ids: set[str] = set()
        if subgraphs:
            for sg in subgraphs:
                subgraph_node_ids.update(sg.node_ids)

        # Build a lookup for node objects
        node_map: dict[str, FlowchartNode] = {n.id: n for n in nodes}

        unknown = sorted(subgraph_node_ids - node_map.keys())
        if unknown:
            raise ValueError(f"Subgraph references undeclared node id(s): {unknown}")

        # A node may be listed by more than one subgraph. Mermaid treats a
        # second bracketed declaration as a redefinition, so only the first
        # occurrence carries the label; later ones reference the bare id.
        declared: set[str] = set()

        # §Subgraphs — render subgraph blocks
        if subgraphs:
            for sg in subgraphs:
                sg_title = escape_mermaid_text(sg.title or sg.id)
                lines.append(f'    subgraph {sg.id}["{sg_title}"]')
                for nid in sg.node_ids:
                    if nid in declared:
                        lines.append(f"        {nid}")
                        continue
                    declared.add(nid)
                    decl = _render_node_declaration(node_map[nid])
                    lines.append(f"        {decl}")
                lines.append("    end")

        # Standalone node declarations (not in any subgraph)
        standalone = [n for n in nodes if n.id not in subgraph_node_ids]
        if standalone:
            for node in standalone:
                decl = _render_node_declaration(node)
                lines.append(f"    {decl}")

        # §Links between nodes — edge declarations
        for edge in edges:
            lines.append(f"    {_render_edge(edge)}")

        return "\n".join(lines)
