"""Regression tests for specification-compliance defects.

Every test here reproduces output that a released version of this
package produced incorrectly.  Each one names the construct it protects
and quotes the clause that makes the old output wrong, so a future
change that reintroduces the defect fails with an explanation rather
than a bare assertion error.

The renderer test modules validate well-formed input against grammar
regexes.  That is how these defects survived: no test ever supplied a
quote, a pipe, or a newline.  This module supplies exactly those.
"""

from __future__ import annotations

import pytest

from linkml_mermaid import (
    ColumnDef,
    FlowchartEdge,
    FlowchartNode,
    FlowchartSubgraph,
    MermaidNote,
    MermaidState,
    MermaidTransition,
    StateDiagramConfig,
)
from linkml_mermaid.flowchart import FlowchartRenderer
from linkml_mermaid.mapping import build_table_rows, map_states, map_transitions
from linkml_mermaid.markdown_table import MarkdownTableRenderer
from linkml_mermaid.state_diagram import StateDiagramRenderer, to_state_id

from .test_escaping import HOSTILE_INPUTS


def split_row(line: str) -> list[str]:
    """Split a GFM table row on its *unescaped* pipes.

    Mirrors how a conforming parser segments a row, so the cell count
    reveals whether escaping actually held.
    """
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for ch in line:
        if escaped:
            current.append(ch)
            escaped = False
        elif ch == "\\":
            current.append(ch)
            escaped = True
        elif ch == "|":
            cells.append("".join(current))
            current = []
        else:
            current.append(ch)
    cells.append("".join(current))
    # Leading and trailing pipes produce empty outer segments.
    return cells[1:-1]


# ── S1/S2: GFM §4.10 cell content ────────────────────────────────────


class TestTableCellEscaping:
    """GFM §4.10: 'include a pipe in a cell's content by escaping it'."""

    def test_pipe_in_value_does_not_split_the_row(self):
        """Previously 'a|b' produced an extra cell, shifting every
        subsequent column one position left."""
        cols = [ColumnDef("A", "a"), ColumnDef("B", "b")]
        rows = [{"a": "x|y", "b": "z"}]
        output = MarkdownTableRenderer().render(cols, rows)
        data = output.split("\n")[2]
        assert len(split_row(data)) == 2
        assert split_row(data)[1].strip() == "z"

    def test_pipe_in_header_does_not_split_the_row(self):
        cols = [ColumnDef("A|B", "a"), ColumnDef("C", "c")]
        output = MarkdownTableRenderer().render(cols, [])
        header = output.split("\n")[0]
        assert len(split_row(header)) == 2

    def test_newline_in_value_does_not_terminate_the_table(self):
        """GFM: 'The table is broken at the first empty line, or
        beginning of another block-level structure.'"""
        cols = [ColumnDef("A", "a"), ColumnDef("B", "b")]
        rows = [{"a": "line1\nline2", "b": "z"}, {"a": "p", "b": "q"}]
        output = MarkdownTableRenderer().render(cols, rows)
        # 1 header + 1 delimiter + 2 data rows, and nothing else.
        assert len(output.split("\n")) == 4
        assert "line1<br>line2" in output

    def test_escaping_precedes_formatting(self):
        """The format wrapper's own markers must not be escaped."""
        cols = [ColumnDef("A", "a", format="bold")]
        rows = [{"a": "x|y"}]
        output = MarkdownTableRenderer().render(cols, rows)
        assert r"**x\|y**" in output

    def test_pipe_inside_code_span_is_still_escaped(self):
        """GFM applies the pipe escape 'including inside other inline
        spans'."""
        cols = [ColumnDef("A", "a", format="code")]
        rows = [{"a": "x|y"}]
        output = MarkdownTableRenderer().render(cols, rows)
        assert r"`x\|y`" in output

    @pytest.mark.parametrize("value", HOSTILE_INPUTS)
    def test_hostile_value_preserves_column_count(self, value):
        cols = [ColumnDef("A", "a"), ColumnDef("B", "b"), ColumnDef("C", "c")]
        rows = [{"a": value, "b": value, "c": "tail"}]
        output = MarkdownTableRenderer().render(cols, rows)
        lines = output.split("\n")
        assert len(lines) == 3, "value leaked a line break into the table"
        for line in lines:
            assert len(split_row(line)) == 3


# ── S3: GFM §4.10 delimiter row alignment ────────────────────────────


class TestColumnAlignment:
    """GFM §4.10: 'optionally, a leading or trailing colon (:), or both,
    to indicate left, right, or center alignment respectively.'
    """

    @pytest.mark.parametrize(
        ("align", "expected"),
        [
            ("default", "---"),
            ("left", ":---"),
            ("center", ":---:"),
            ("right", "---:"),
        ],
    )
    def test_delimiter_encodes_alignment(self, align, expected):
        cols = [ColumnDef("A", "a", align=align)]
        output = MarkdownTableRenderer().render(cols, [])
        assert output.split("\n")[1] == f"| {expected} |"

    def test_default_alignment_is_unchanged(self):
        """Omitting align must keep the historical bare-hyphen output."""
        output = MarkdownTableRenderer().render([ColumnDef("A", "a")], [])
        assert output.split("\n")[1] == "| --- |"

    def test_mixed_alignments_in_one_table(self):
        cols = [
            ColumnDef("A", "a", align="left"),
            ColumnDef("B", "b", align="center"),
            ColumnDef("C", "c", align="right"),
        ]
        output = MarkdownTableRenderer().render(cols, [])
        assert output.split("\n")[1] == "| :--- | :---: | ---: |"

    def test_invalid_alignment_is_rejected(self):
        with pytest.raises(ValueError, match="Invalid column alignment"):
            ColumnDef("A", "a", align="middle")


# ── S4: Mermaid §Entity codes to escape characters ───────────────────


class TestFlowchartLabelEscaping:
    """Mermaid §Entity codes to escape characters."""

    def test_quote_in_node_label_is_escaped(self):
        """Previously emitted A["say "hi""], which does not parse."""
        output = FlowchartRenderer().render([FlowchartNode(id="A", label='say "hi"')], [])
        assert 'A["say #quot;hi#quot;"]' in output
        assert 'say "hi"' not in output

    def test_quote_in_edge_label_is_escaped(self):
        output = FlowchartRenderer().render(
            [FlowchartNode(id="A"), FlowchartNode(id="B")],
            [FlowchartEdge("A", "B", label='say "hi"')],
        )
        assert "say #quot;hi#quot;" in output

    def test_quote_in_subgraph_title_is_escaped(self):
        output = FlowchartRenderer().render(
            [], [], subgraphs=[FlowchartSubgraph(id="sg", title='The "Box"')]
        )
        assert 'subgraph sg["The #quot;Box#quot;"]' in output

    def test_newline_in_label_does_not_split_the_statement(self):
        output = FlowchartRenderer().render([FlowchartNode(id="A", label="one\ntwo")], [])
        assert len(output.split("\n")) == 2
        assert 'A["one<br>two"]' in output

    @pytest.mark.parametrize("value", HOSTILE_INPUTS)
    def test_hostile_label_keeps_one_statement_per_line(self, value):
        output = FlowchartRenderer().render(
            [FlowchartNode(id="A", label=value or "A")],
            [],
        )
        lines = output.split("\n")
        assert len(lines) == 2
        # Every quote in the declaration is a delimiter, so the count is even.
        assert lines[1].count('"') in (0, 2)


# ── S5: node shape validation ────────────────────────────────────────


class TestNodeShapeValidation:
    """§A node with text defines one bracket form per shape."""

    def test_invalid_shape_is_rejected(self):
        """Previously fell back to a rectangle, so a typo silently
        produced the wrong shape — while an invalid edge style raised."""
        with pytest.raises(ValueError, match="Invalid node shape"):
            FlowchartNode(id="A", label="x", shape="trapezoid")

    @pytest.mark.parametrize(
        "shape",
        ["rect", "round", "stadium", "diamond", "hexagon", "subroutine", "circle"],
    )
    def test_documented_shapes_are_accepted(self, shape):
        assert FlowchartNode(id="A", label="x", shape=shape).shape == shape

    def test_shape_validation_matches_edge_style_validation(self):
        """Both reject unknown values; neither degrades silently."""
        with pytest.raises(ValueError):
            FlowchartNode(id="A", shape="nope")
        with pytest.raises(ValueError):
            FlowchartEdge("A", "B", style="nope")

    def test_shape_survives_label_equal_to_id(self):
        """A shaped node must not collapse to the bare §A node form.

        Previously the bare id was emitted whenever label == id, which
        discarded the bracket form that carries the shape — so the node
        rendered as a rectangle.
        """
        output = FlowchartRenderer().render(
            [FlowchartNode(id="Triage", label="Triage", shape="diamond")], []
        )
        assert '    Triage{"Triage"}' in output

    def test_shape_survives_absent_label(self):
        output = FlowchartRenderer().render([FlowchartNode(id="Check", shape="hexagon")], [])
        assert '    Check{{"Check"}}' in output

    def test_plain_rect_node_still_uses_bare_form(self):
        """§A node (default): 'flowchart LR\\n    id' stays unchanged."""
        output = FlowchartRenderer().render([FlowchartNode(id="A")], [])
        assert output.split("\n")[1] == "    A"


# ── Subgraph membership integrity ────────────────────────────────────


class TestSubgraphIntegrity:
    """§Subgraphs: 'subgraph title\\n graph definition\\nend'."""

    def test_undeclared_member_is_rejected(self):
        """Previously dropped silently, so the node vanished from the
        subgraph with no diagnostic."""
        with pytest.raises(ValueError, match="undeclared node id"):
            FlowchartRenderer().render(
                [FlowchartNode(id="A")],
                [],
                subgraphs=[FlowchartSubgraph(id="sg", node_ids=["A", "GHOST"])],
            )

    def test_node_in_two_subgraphs_is_declared_once(self):
        """A second bracketed declaration is a redefinition in Mermaid."""
        output = FlowchartRenderer().render(
            [FlowchartNode(id="A", label="Shared")],
            [],
            subgraphs=[
                FlowchartSubgraph(id="sg1", node_ids=["A"]),
                FlowchartSubgraph(id="sg2", node_ids=["A"]),
            ],
        )
        assert output.count('A["Shared"]') == 1
        # It still appears inside the second subgraph, as a bare reference.
        sg2_block = output.split("subgraph sg2")[1]
        assert "\n        A\n" in sg2_block


# ── S7: stateDiagram direction ───────────────────────────────────────


class TestStateDiagramDirectionValidation:
    """§Setting the direction of the diagram documents TB, BT, RL, LR."""

    @pytest.mark.parametrize("direction", ["TB", "BT", "RL", "LR"])
    def test_documented_directions_accepted(self, direction):
        output = StateDiagramRenderer(direction=direction).render([], [])
        assert f"    direction {direction}" in output

    def test_none_omits_the_directive(self):
        assert "direction" not in StateDiagramRenderer().render([], [])

    def test_undocumented_direction_is_rejected(self):
        """Previously any string was emitted verbatim, producing a
        diagram that failed to parse at render time instead of at the
        call site."""
        with pytest.raises(ValueError, match="Invalid direction"):
            StateDiagramRenderer(direction="sideways")

    def test_flowchart_only_direction_is_rejected(self):
        """'TD' is documented for flowcharts, not for stateDiagram-v2."""
        with pytest.raises(ValueError, match="Invalid direction"):
            StateDiagramRenderer(direction="TD")


# ── S8: stateDiagram label escaping ──────────────────────────────────


class TestStateLabelEscaping:
    """§States colon form runs to the end of the line."""

    def test_newline_in_state_label_does_not_add_a_statement(self):
        output = StateDiagramRenderer().render([MermaidState(id="A", label="one\ntwo")], [])
        assert "    A : one<br>two" in output
        assert "two" not in output.replace("one<br>two", "")

    def test_colon_in_label_switches_to_quoted_form(self):
        """§Spaces in state names documents 'state "description" as id',
        which is unambiguous when the text itself contains a colon."""
        output = StateDiagramRenderer().render([MermaidState(id="A", label="Phase 1: review")], [])
        assert '    state "Phase 1: review" as A' in output
        assert "    A : Phase 1: review" not in output

    def test_quote_in_label_is_escaped(self):
        output = StateDiagramRenderer().render(
            [MermaidState(id="A", label='a "quoted": label')], []
        )
        assert '    state "a #quot;quoted#quot;: label" as A' in output

    def test_newline_in_transition_label_does_not_add_a_statement(self):
        output = StateDiagramRenderer().render(
            [MermaidState(id="A"), MermaidState(id="B")],
            [MermaidTransition("A", "B", label="go\nnow")],
        )
        assert "    A --> B : go<br>now" in output

    def test_newline_in_note_does_not_add_a_statement(self):
        output = StateDiagramRenderer().render(
            [MermaidState(id="A")],
            [],
            notes=[MermaidNote(state_id="A", text="first\nsecond")],
        )
        assert "    note right of A : first<br>second" in output

    @pytest.mark.parametrize("value", HOSTILE_INPUTS)
    def test_hostile_label_keeps_statement_count(self, value):
        baseline = StateDiagramRenderer().render([MermaidState(id="A")], [])
        output = StateDiagramRenderer().render([MermaidState(id="A", label=value)], [])
        extra = len(output.split("\n")) - len(baseline.split("\n"))
        assert extra <= 1, "label leaked a line break into the diagram"


# ── S9 / map_states: mapping-layer correctness ───────────────────────


class TestMappingCorrectness:
    """The mapping layer must not invent identifiers or placeholders."""

    def test_state_id_comes_from_the_id_slot(self):
        """StateDiagramConfig.state_id_slot documents that it is 'Mapped
        to MermaidState.id after PascalCase conversion'."""
        config = StateDiagramConfig()
        states = [{"id": "IN_REVIEW", "display_name": "In review"}]
        assert map_states(states, config)[0].id == "InReview"

    def test_distinct_states_with_one_label_stay_distinct(self):
        config = StateDiagramConfig()
        states = [
            {"id": "A_DRAFT", "display_name": "Draft"},
            {"id": "B_DRAFT", "display_name": "Draft"},
        ]
        ids = [s.id for s in map_states(states, config)]
        assert len(set(ids)) == 2

    def test_transition_ids_agree_with_state_ids(self):
        """A diagram whose edges name states that were never declared
        renders as disconnected nodes."""
        config = StateDiagramConfig()
        states = [
            {"id": "A_DRAFT", "display_name": "Draft"},
            {"id": "B_DRAFT", "display_name": "Draft"},
        ]
        transitions = [
            {
                "name": "Move",
                "from_state": "A_DRAFT",
                "to_state": "B_DRAFT",
                "default_actor": "",
                "guards": [],
            }
        ]
        declared = {s.id for s in map_states(states, config)}
        edges = map_transitions(transitions, states, [], config)
        assert {edges[0].from_state, edges[0].to_state} <= declared

    def test_guard_separator_is_renderable(self):
        """stateDiagram-v2 documents no backslash escape, so a literal
        '\\n' appeared verbatim in the rendered label."""
        config = StateDiagramConfig()
        states = [{"id": "A"}, {"id": "B"}]
        transitions = [
            {
                "name": "Go",
                "from_state": "A",
                "to_state": "B",
                "default_actor": "",
                "guards": ["G1", "G2"],
            }
        ]
        guards = [
            {"id": "G1", "display_name": "first"},
            {"id": "G2", "display_name": "second"},
        ]
        label = map_transitions(transitions, states, guards, config)[0].label
        assert label == "Go<br>first<br>second"
        assert "\\n" not in label

    def test_empty_placeholder_default_is_em_dash(self):
        rows = build_table_rows([{"g": []}], {"g": "g"})
        assert rows[0]["g"] == "\u2014"

    def test_empty_placeholder_is_configurable(self):
        rows = build_table_rows([{"g": []}], {"g": "g"}, empty_placeholder="")
        assert rows[0]["g"] == ""


# ── Cross-layer: end-to-end hostile input ────────────────────────────


class TestEndToEndHostileInput:
    """Hostile text must survive the full mapping→render pipeline."""

    @pytest.mark.parametrize("value", HOSTILE_INPUTS)
    def test_state_diagram_pipeline(self, value):
        config = StateDiagramConfig()
        states = [{"id": "A", "display_name": value}, {"id": "B", "display_name": "B"}]
        transitions = [
            {"name": value, "from_state": "A", "to_state": "B", "default_actor": "", "guards": []}
        ]
        output = StateDiagramRenderer().render(
            map_states(states, config),
            map_transitions(transitions, states, [], config),
        )
        for line in output.split("\n"):
            assert "\r" not in line
        assert output.splitlines()[0] == "stateDiagram-v2"

    @pytest.mark.parametrize("value", HOSTILE_INPUTS)
    def test_table_pipeline(self, value):
        rows = build_table_rows([{"a": value, "b": "tail"}], {"a": "a", "b": "b"})
        cols = [ColumnDef("A", "a"), ColumnDef("B", "b")]
        output = MarkdownTableRenderer().render(cols, rows)
        assert len(output.split("\n")) == 3
        for line in output.split("\n"):
            assert len(split_row(line)) == 2


# ── to_state_id stability ────────────────────────────────────────────


class TestStateIdStability:
    """to_state_id must be total, stable and injective enough to use as
    a node identifier."""

    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("Draft", "Draft"),
            ("Content Review", "ContentReview"),
            ("in_progress", "InProgress"),
            ("in-progress", "InProgress"),
            ("DraftState", "DraftState"),
            ("Draft (new)", "DraftNew"),
            ("In-Review!", "InReview"),
            ("2nd pass", "S2ndPass"),
            ("  padded  ", "Padded"),
        ],
    )
    def test_known_conversions(self, label, expected):
        assert to_state_id(label) == expected

    @pytest.mark.parametrize("value", HOSTILE_INPUTS)
    def test_output_is_a_valid_identifier_or_raises(self, value):
        try:
            result = to_state_id(value)
        except ValueError:
            return
        assert result
        assert result.isalnum()
        assert not result[0].isdigit()
