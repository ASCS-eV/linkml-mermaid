"""FlowchartRenderer tests — validating against the Mermaid spec.

Each test asserts what the Mermaid flowchart specification REQUIRES,
not what our implementation happens to produce.  Expected outputs are
hand-written by reading the spec, and structural validators enforce
grammar rules derived from the spec.

Spec: https://mermaid.js.org/syntax/flowchart.html
"""

from __future__ import annotations

import re

import pytest

from linkml_mermaid import FlowchartEdge, FlowchartNode, FlowchartSubgraph
from linkml_mermaid.flowchart import FlowchartRenderer

# ── Spec-derived grammar patterns ───────────────────────────────────
#
# These regexes are derived directly from the Mermaid flowchart
# specification, NOT from our implementation.  They define what valid
# Mermaid syntax looks like.

# §Direction: "flowchart {TB|TD|BT|RL|LR}"
_DECLARATION_RE = re.compile(r"^flowchart (TB|TD|BT|RL|LR)$")

# §A node (default): bare id
_BARE_NODE_RE = re.compile(r"^\s+(\w+)$")

# §A node with text — all bracket forms:
#   id["text"], id("text"), id(["text"]), id{"text"}, id{{"text"}},
#   id[["text"]], id(("text"))
_NODE_WITH_TEXT_RE = re.compile(
    r"^\s+(\w+)"
    r"(?:"
    r'\["[^"]*"\]'  # rect:      ["text"]
    r'|\("?[^"]*"?\)'  # round:     ("text")
    r'|\(\["[^"]*"\]\)'  # stadium:   (["text"])
    r'|\{"[^"]*"\}'  # diamond:   {"text"}
    r'|\{\{"[^"]*"\}\}'  # hexagon:   {{"text"}}
    r'|\[\["[^"]*"\]\]'  # subroutine:[["text"]]
    r'|\(\("?[^"]*"?\)\)'  # circle:    (("text"))
    r")"
    r"$"
)

# §Links between nodes — arrow forms (with optional label):
#   solid:  -->  or -->|"text"|
#   dotted: -.-> or -.->|"text"|
#   thick:  ==>  or ==>|"text"|
_EDGE_RE = re.compile(
    r"^\s+(\w+)\s+"
    r"(?:"
    r'-->(?:\|"[^"]*"\|)?'  # solid
    r'|-\.->(?:\|"[^"]*"\|)?'  # dotted
    r'|==>(?:\|"[^"]*"\|)?'  # thick
    r")"
    r"\s+(\w+)$"
)

# §Subgraphs: "subgraph id["title"]" or "subgraph title"
_SUBGRAPH_OPEN_RE = re.compile(r'^\s+subgraph\s+\w+(?:\["[^"]*"\])?$')
_SUBGRAPH_END_RE = re.compile(r"^\s+end$")

# §Comments: "%% text"
_COMMENT_RE = re.compile(r"^\s*%%.*$")


def _validate_flowchart_grammar(text: str) -> list[str]:
    """Validate every line of a flowchart against the spec grammar.

    Returns a list of error messages (empty = valid).

    Per the spec, valid content lines are:
    - ``flowchart {direction}``  (declaration)
    - ``id``  (§A node default — bare node)
    - ``id["text"]`` etc.  (§A node with text — shaped node)
    - ``A --> B``  (§Links — solid)
    - ``A -->|"text"| B``  (§Links — solid with label)
    - ``A -.-> B``  (§Links — dotted)
    - ``A ==> B``  (§Links — thick)
    - ``subgraph id["title"]``  (§Subgraphs — open)
    - ``end``  (§Subgraphs — close)
    - ``%% comment``  (§Comments)
    - Empty lines (separators)
    """
    errors = []
    lines = text.split("\n")

    if not lines or not _DECLARATION_RE.match(lines[0]):
        errors.append(
            f"Line 0: must be 'flowchart {{direction}}' "
            f"(spec: §Direction, got '{lines[0] if lines else ''}')"
        )

    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "":
            continue
        if _BARE_NODE_RE.match(line):
            continue
        if _NODE_WITH_TEXT_RE.match(line):
            continue
        if _EDGE_RE.match(line):
            continue
        if _SUBGRAPH_OPEN_RE.match(line):
            continue
        if _SUBGRAPH_END_RE.match(line):
            continue
        if _COMMENT_RE.match(line):
            continue
        errors.append(f"Line {i}: '{line}' does not match any spec grammar rule")

    return errors


# ── FlowchartNode type tests ────────────────────────────────────────


class TestFlowchartNodeType:
    """FlowchartNode dataclass invariants."""

    def test_default_shape_is_rect(self):
        """Per §A node with text, rectangle is the default shape."""
        node = FlowchartNode(id="A")
        assert node.shape == "rect"

    def test_label_defaults_to_none(self):
        """When label is None, bare id is used per §A node (default)."""
        node = FlowchartNode(id="A")
        assert node.label is None

    def test_frozen_dataclass(self):
        """Nodes should be immutable."""
        node = FlowchartNode(id="A")
        with pytest.raises(AttributeError):
            node.id = "B"  # type: ignore[misc]


# ── FlowchartEdge type tests ────────────────────────────────────────


class TestFlowchartEdgeType:
    """FlowchartEdge dataclass invariants."""

    def test_default_style_is_solid(self):
        """Per §A link with arrow head, solid arrow '-->' is default."""
        edge = FlowchartEdge(from_node="A", to_node="B")
        assert edge.style == "solid"

    def test_invalid_style_raises(self):
        """Only solid/dotted/thick are valid per spec."""
        with pytest.raises(ValueError, match="Invalid edge style"):
            FlowchartEdge(from_node="A", to_node="B", style="wavy")

    @pytest.mark.parametrize("style", ["solid", "dotted", "thick"])
    def test_valid_styles_accepted(self, style):
        edge = FlowchartEdge(from_node="A", to_node="B", style=style)
        assert edge.style == style


# ── FlowchartRenderer — Declaration ─────────────────────────────────


class TestFlowchartDeclaration:
    """§Direction: 'This statement declares the direction of the
    Flowchart.'  Syntax: ``flowchart {TB|TD|BT|RL|LR}``."""

    def test_default_direction_td(self):
        """Default direction is TD (top-down) per §Direction."""
        r = FlowchartRenderer()
        output = r.render([], [])
        assert output.split("\n")[0] == "flowchart TD"

    @pytest.mark.parametrize("direction", ["TB", "TD", "BT", "RL", "LR"])
    def test_all_valid_directions(self, direction):
        """§Direction: 'Possible FlowChart orientations are: TB, TD, BT, RL, LR'"""
        r = FlowchartRenderer(direction=direction)
        output = r.render([], [])
        assert output.split("\n")[0] == f"flowchart {direction}"

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError, match="Invalid direction"):
            FlowchartRenderer(direction="XX")

    def test_empty_diagram_is_valid_grammar(self):
        """An empty flowchart should still be grammatically valid."""
        r = FlowchartRenderer()
        output = r.render([], [])
        errors = _validate_flowchart_grammar(output)
        assert errors == [], f"Grammar errors: {errors}"


# ── FlowchartRenderer — Nodes ───────────────────────────────────────


class TestFlowchartNodes:
    """§A node (default) and §A node with text."""

    def test_bare_node_when_no_label(self):
        """§A node (default): 'The id is what is displayed in the box.'"""
        nodes = [FlowchartNode(id="Start")]
        r = FlowchartRenderer()
        output = r.render(nodes, [])
        assert "    Start" in output

    def test_bare_node_when_label_equals_id(self):
        """No bracket form needed when label matches id."""
        nodes = [FlowchartNode(id="Start", label="Start")]
        r = FlowchartRenderer()
        output = r.render(nodes, [])
        assert "    Start" in output
        assert '["' not in output

    def test_rect_node_with_text(self):
        """§A node with text: id[\"text\"] for rectangle."""
        nodes = [FlowchartNode(id="A", label="Hello World")]
        r = FlowchartRenderer()
        output = r.render(nodes, [])
        assert '    A["Hello World"]' in output

    def test_round_node(self):
        """§A node with round edges: id(\"text\")"""
        nodes = [FlowchartNode(id="B", label="Rounded", shape="round")]
        r = FlowchartRenderer()
        output = r.render(nodes, [])
        assert '    B("Rounded")' in output

    def test_stadium_node(self):
        """§A stadium-shaped node: id([\"text\"])"""
        nodes = [FlowchartNode(id="C", label="Stadium", shape="stadium")]
        r = FlowchartRenderer()
        output = r.render(nodes, [])
        assert '    C(["Stadium"])' in output

    def test_diamond_node(self):
        """§A node (rhombus): id{\"text\"}"""
        nodes = [FlowchartNode(id="D", label="Decision?", shape="diamond")]
        r = FlowchartRenderer()
        output = r.render(nodes, [])
        assert '    D{"Decision?"}' in output

    def test_hexagon_node(self):
        """§A hexagon node: id{{\"text\"}}"""
        nodes = [FlowchartNode(id="E", label="Hex", shape="hexagon")]
        r = FlowchartRenderer()
        output = r.render(nodes, [])
        assert '    E{{"Hex"}}' in output

    def test_subroutine_node(self):
        """§A node in a subroutine shape: id[[\"text\"]]"""
        nodes = [FlowchartNode(id="F", label="Sub", shape="subroutine")]
        r = FlowchartRenderer()
        output = r.render(nodes, [])
        assert '    F[["Sub"]]' in output

    def test_circle_node(self):
        """§A node in the form of a circle: id((\"text\"))"""
        nodes = [FlowchartNode(id="G", label="Round", shape="circle")]
        r = FlowchartRenderer()
        output = r.render(nodes, [])
        assert '    G(("Round"))' in output

    def test_multiple_nodes(self):
        """Multiple nodes are listed in order."""
        nodes = [
            FlowchartNode(id="A", label="First"),
            FlowchartNode(id="B", label="Second"),
        ]
        r = FlowchartRenderer()
        output = r.render(nodes, [])
        lines = output.split("\n")
        a_idx = next(i for i, l in enumerate(lines) if "First" in l)
        b_idx = next(i for i, l in enumerate(lines) if "Second" in l)
        assert a_idx < b_idx


# ── FlowchartRenderer — Edges ───────────────────────────────────────


class TestFlowchartEdges:
    """§Links between nodes — arrow types and labels."""

    def test_solid_arrow_no_label(self):
        """§A link with arrow head: 'A --> B'"""
        edges = [FlowchartEdge("A", "B")]
        r = FlowchartRenderer()
        output = r.render([], edges)
        assert "    A --> B" in output

    def test_solid_arrow_with_label(self):
        """§A link with arrow head and text: 'A -->|\"text\"| B'"""
        edges = [FlowchartEdge("A", "B", label="Go")]
        r = FlowchartRenderer()
        output = r.render([], edges)
        assert '    A -->|"Go"| B' in output

    def test_dotted_arrow_no_label(self):
        """§Dotted link: 'A -.-> B'"""
        edges = [FlowchartEdge("A", "B", style="dotted")]
        r = FlowchartRenderer()
        output = r.render([], edges)
        assert "    A -.-> B" in output

    def test_dotted_arrow_with_label(self):
        """§Dotted link with text: 'A -.->|\"text\"| B'"""
        edges = [FlowchartEdge("A", "B", label="Maybe", style="dotted")]
        r = FlowchartRenderer()
        output = r.render([], edges)
        assert '    A -.->|"Maybe"| B' in output

    def test_thick_arrow_no_label(self):
        """§Thick link: 'A ==> B'"""
        edges = [FlowchartEdge("A", "B", style="thick")]
        r = FlowchartRenderer()
        output = r.render([], edges)
        assert "    A ==> B" in output

    def test_thick_arrow_with_label(self):
        """§Thick link with text: 'A ==>|\"text\"| B'"""
        edges = [FlowchartEdge("A", "B", label="Important", style="thick")]
        r = FlowchartRenderer()
        output = r.render([], edges)
        assert '    A ==>|"Important"| B' in output

    def test_self_loop(self):
        """A --> A is valid per spec (edge to self)."""
        edges = [FlowchartEdge("A", "A", label="Retry")]
        r = FlowchartRenderer()
        output = r.render([], edges)
        assert '    A -->|"Retry"| A' in output

    def test_multiple_edges_between_same_nodes(self):
        """Two edges between same nodes, different labels."""
        edges = [
            FlowchartEdge("A", "B", label="Path 1"),
            FlowchartEdge("A", "B", label="Path 2"),
        ]
        r = FlowchartRenderer()
        output = r.render([], edges)
        assert '-->|"Path 1"|' in output
        assert '-->|"Path 2"|' in output

    def test_edge_grammar(self):
        """Every edge line must match the spec grammar."""
        edges = [
            FlowchartEdge("A", "B", label="Go"),
            FlowchartEdge("B", "C", style="dotted"),
            FlowchartEdge("C", "D", label="Done", style="thick"),
        ]
        r = FlowchartRenderer()
        output = r.render([], edges)
        errors = _validate_flowchart_grammar(output)
        assert errors == [], f"Grammar errors: {errors}"


# ── FlowchartRenderer — Subgraphs ───────────────────────────────────


class TestFlowchartSubgraphs:
    """§Subgraphs: 'subgraph title\\n    graph definition\\nend'"""

    def test_subgraph_with_title(self):
        """§Subgraphs: explicit id + title form."""
        nodes = [
            FlowchartNode(id="A", label="Node A"),
            FlowchartNode(id="B", label="Node B"),
        ]
        subgraphs = [
            FlowchartSubgraph(id="sg1", title="My Group", node_ids=["A", "B"]),
        ]
        r = FlowchartRenderer()
        output = r.render(nodes, [], subgraphs=subgraphs)
        assert '    subgraph sg1["My Group"]' in output
        assert "    end" in output

    def test_subgraph_contains_member_nodes(self):
        """Nodes in a subgraph are rendered inside the subgraph block."""
        nodes = [FlowchartNode(id="A", label="Inside")]
        subgraphs = [FlowchartSubgraph(id="sg1", title="Box", node_ids=["A"])]
        r = FlowchartRenderer()
        output = r.render(nodes, [], subgraphs=subgraphs)
        lines = output.split("\n")
        sg_start = next(i for i, l in enumerate(lines) if "subgraph" in l)
        sg_end = next(i for i, l in enumerate(lines) if l.strip() == "end")
        a_line = next(i for i, l in enumerate(lines) if "Inside" in l)
        assert sg_start < a_line < sg_end

    def test_standalone_nodes_outside_subgraph(self):
        """Nodes not in any subgraph are rendered as standalone."""
        nodes = [
            FlowchartNode(id="A", label="In Group"),
            FlowchartNode(id="B", label="Standalone"),
        ]
        subgraphs = [FlowchartSubgraph(id="sg1", title="Box", node_ids=["A"])]
        r = FlowchartRenderer()
        output = r.render(nodes, [], subgraphs=subgraphs)
        # B should be outside the subgraph block
        lines = output.split("\n")
        sg_end = next(i for i, l in enumerate(lines) if l.strip() == "end")
        b_line = next(i for i, l in enumerate(lines) if "Standalone" in l)
        assert b_line > sg_end

    def test_subgraph_title_defaults_to_id(self):
        """When title is None, id is used as the display title."""
        subgraphs = [FlowchartSubgraph(id="mygroup", node_ids=[])]
        r = FlowchartRenderer()
        output = r.render([], [], subgraphs=subgraphs)
        assert '    subgraph mygroup["mygroup"]' in output

    def test_edges_across_subgraphs(self):
        """§Subgraphs: 'it is also possible to set edges to and from subgraphs'"""
        nodes = [
            FlowchartNode(id="A", label="In SG1"),
            FlowchartNode(id="B", label="In SG2"),
        ]
        subgraphs = [
            FlowchartSubgraph(id="sg1", title="Group 1", node_ids=["A"]),
            FlowchartSubgraph(id="sg2", title="Group 2", node_ids=["B"]),
        ]
        edges = [FlowchartEdge("A", "B", label="Cross")]
        r = FlowchartRenderer()
        output = r.render(nodes, edges, subgraphs=subgraphs)
        assert '-->|"Cross"|' in output


# ── FlowchartRenderer — Content Indentation ─────────────────────────


class TestFlowchartIndentation:
    """Convention: content lines are indented 4 spaces (like stateDiagram)."""

    def test_node_lines_are_indented(self):
        nodes = [FlowchartNode(id="A", label="Test")]
        r = FlowchartRenderer()
        output = r.render(nodes, [])
        for line in output.split("\n"):
            if line.strip() and not line.startswith("flowchart"):
                assert line.startswith("    "), f"Not indented: '{line}'"

    def test_edge_lines_are_indented(self):
        edges = [FlowchartEdge("A", "B")]
        r = FlowchartRenderer()
        output = r.render([], edges)
        for line in output.split("\n"):
            if line.strip() and not line.startswith("flowchart"):
                assert line.startswith("    "), f"Not indented: '{line}'"

    def test_subgraph_member_nodes_double_indented(self):
        """Nodes inside subgraphs get 8-space indent (4 for subgraph + 4)."""
        nodes = [FlowchartNode(id="A", label="Inside")]
        subgraphs = [FlowchartSubgraph(id="sg", title="Box", node_ids=["A"])]
        r = FlowchartRenderer()
        output = r.render(nodes, [], subgraphs=subgraphs)
        for line in output.split("\n"):
            if "Inside" in line:
                assert line.startswith("        "), f"Not double-indented: '{line}'"


# ── Full Diagram Grammar Compliance ─────────────────────────────────


class TestFullFlowchartGrammarCompliance:
    """End-to-end grammar validation: build realistic diagrams and check
    every line against the spec grammar."""

    def test_simple_linear_flow(self):
        """A --> B --> C linear flow."""
        nodes = [
            FlowchartNode(id="A", label="Start"),
            FlowchartNode(id="B", label="Process"),
            FlowchartNode(id="C", label="End"),
        ]
        edges = [
            FlowchartEdge("A", "B", label="Step 1"),
            FlowchartEdge("B", "C", label="Step 2"),
        ]
        r = FlowchartRenderer()
        output = r.render(nodes, edges)
        errors = _validate_flowchart_grammar(output)
        assert errors == [], "Grammar errors:\n" + "\n".join(errors)

    def test_mixed_edge_styles(self):
        """All three edge styles in one diagram."""
        edges = [
            FlowchartEdge("A", "B", label="Solid", style="solid"),
            FlowchartEdge("B", "C", label="Dotted", style="dotted"),
            FlowchartEdge("C", "D", label="Thick", style="thick"),
        ]
        r = FlowchartRenderer()
        output = r.render([], edges)
        errors = _validate_flowchart_grammar(output)
        assert errors == [], "Grammar errors:\n" + "\n".join(errors)

    def test_diagram_with_subgraphs(self):
        """Subgraph blocks are valid grammar."""
        nodes = [
            FlowchartNode(id="A", label="Node A"),
            FlowchartNode(id="B", label="Node B"),
            FlowchartNode(id="C", label="Node C"),
        ]
        subgraphs = [
            FlowchartSubgraph(id="sg1", title="Group", node_ids=["A", "B"]),
        ]
        edges = [FlowchartEdge("A", "C")]
        r = FlowchartRenderer()
        output = r.render(nodes, edges, subgraphs=subgraphs)
        errors = _validate_flowchart_grammar(output)
        assert errors == [], "Grammar errors:\n" + "\n".join(errors)

    def test_expected_output_hand_written(self):
        """Hand-written expected output based on spec reading.

        This is the KEY test: we write what the spec says the output
        SHOULD be, and assert the implementation matches.
        """
        nodes = [
            FlowchartNode(id="A", label="Start"),
            FlowchartNode(id="B", label="End", shape="round"),
        ]
        edges = [FlowchartEdge("A", "B", label="Go")]

        r = FlowchartRenderer(direction="LR")
        output = r.render(nodes, edges)

        # Per spec:
        # - Line 0: flowchart LR  (§Direction)
        # - A["Start"]  (§A node with text — rect)
        # - B("End")    (§A node with text — round)
        # - A -->|"Go"| B  (§A link with arrow head and text)
        expected = "\n".join(
            [
                "flowchart LR",
                '    A["Start"]',
                '    B("End")',
                '    A -->|"Go"| B',
            ]
        )
        assert output == expected

    def test_expected_output_with_subgraph(self):
        """Hand-written expected output with a subgraph."""
        nodes = [
            FlowchartNode(id="X", label="Entry"),
            FlowchartNode(id="Y", label="Inside"),
            FlowchartNode(id="Z", label="Exit"),
        ]
        subgraphs = [
            FlowchartSubgraph(id="box", title="The Box", node_ids=["Y"]),
        ]
        edges = [
            FlowchartEdge("X", "Y"),
            FlowchartEdge("Y", "Z"),
        ]

        r = FlowchartRenderer(direction="TD")
        output = r.render(nodes, edges, subgraphs=subgraphs)

        expected = "\n".join(
            [
                "flowchart TD",
                '    subgraph box["The Box"]',
                '        Y["Inside"]',
                "    end",
                '    X["Entry"]',
                '    Z["Exit"]',
                "    X --> Y",
                "    Y --> Z",
            ]
        )
        assert output == expected

    def test_branching_pipeline_use_case(self):
        """Realistic test: a document review pipeline that branches and
        rejoins, exercising labelled and unlabelled edges together."""
        nodes = [
            FlowchartNode(id="Intake", label="Intake<br>(single entry point)"),
            FlowchartNode(id="Triage", label="Triage", shape="diamond"),
            FlowchartNode(id="FastTrack", label="Fast track"),
            FlowchartNode(id="FullReview", label="Full review"),
            FlowchartNode(id="Approval", label="Approval"),
            FlowchartNode(id="Published", label="Published", shape="stadium"),
        ]
        edges = [
            FlowchartEdge("Intake", "Triage", label="editor screens"),
            FlowchartEdge("Triage", "FastTrack", label="minor change"),
            FlowchartEdge("Triage", "FullReview", label="major change"),
            FlowchartEdge("FastTrack", "Approval"),
            FlowchartEdge("FullReview", "Approval"),
            FlowchartEdge("Approval", "Published"),
        ]
        r = FlowchartRenderer(direction="TD")
        output = r.render(nodes, edges)
        errors = _validate_flowchart_grammar(output)
        assert errors == [], "Grammar errors:\n" + "\n".join(errors)

        # Verify key structural elements
        assert "Intake" in output
        assert 'Triage{"Triage"}' in output
        assert 'Published(["Published"])' in output
        assert '-->|"editor screens"|' in output
        assert '-->|"minor change"|' in output
