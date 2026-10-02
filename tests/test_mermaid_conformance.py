"""Conformance tests that judge our output with the real Mermaid parser.

Every other test in this suite asserts that a renderer produces a
particular string.  Those tests cannot catch a misreading of the
specification, because the expected string embodies the same
misreading.  The tests here hand the rendered diagram to Mermaid itself
and fail if Mermaid will not compile it — and, where an escape sequence
is involved, if Mermaid does not draw the character the sequence stands
for.

Each class corresponds to a defect found by fuzzing the public API
against Mermaid 11 and checking which outputs it rejected.  The inputs
are kept as the original hostile values so the tests fail again if a
fix is reverted.

Skips when Node or the Mermaid package is absent; CI installs both.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from linkml_mermaid import (
    FlowchartEdge,
    FlowchartNode,
    FlowchartRenderer,
    FlowchartSubgraph,
    MermaidNote,
    MermaidState,
    MermaidTransition,
    StateDiagramRenderer,
)

from .oracles import assert_parses, mermaid_check

# Values chosen to exercise the characters each grammar assigns meaning
# to, plus the ones that previously produced unparseable output.
HOSTILE_LABELS = [
    'say "hi"',
    "100% #sure",
    "a:b",
    "a :: b",
    "state: ready",
    "x --> y",
    "line1\nline2",
    "set direction LR",
    "a|b",
    "[*]",
    "end",
    "<<fork>>",
    "{braces}",
    "-->|label|",
    "a[b]c",
    "note right of X",
    "50:50 split",
    "a\\b",
    "---",
    "%% comment",
    # ";" ends a statement, so these smuggle whole statements into the
    # diagram rather than merely breaking the parse.
    "step 1; step 2",
    "do x; then Zebra --> Walrus",
    "retry; -- see note",
    "a;b",
    ";",
    "x; note right of A : y",
]

# Every keyword in either grammar. Sweeping this corpus -- rather than
# the frozensets themselves -- is what makes the reserved-word tests
# able to fail: a test that iterates FLOWCHART_RESERVED_IDS can never
# discover a word missing from it.
KEYWORD_CORPUS = [
    "graph", "flowchart", "subgraph", "end", "class", "classDef", "style", "linkStyle",
    "click", "href", "call", "callback", "interpolate", "direction", "default",
    "_self", "_blank", "_parent", "_top", "state", "stateDiagram", "note", "as",
    "TB", "TD", "BT", "RL", "LR", "o", "x", "fork", "join", "choice", "if", "else",
    "accTitle", "accDescr", "cssClass", "End", "START",
]  # fmt: skip


class TestNoteText:
    """§Notes — ``note right of {id} : {text}``.

    The note body is introduced by a colon and has no quoted form, so a
    colon inside the text used to end the diagram's parse.
    """

    @pytest.mark.parametrize("text", HOSTILE_LABELS)
    def test_note_text_never_breaks_the_diagram(self, text):
        output = StateDiagramRenderer().render(
            [MermaidState(id="A")],
            [],
            notes=[MermaidNote(state_id="A", text=text)],
        )
        assert_parses({"note": output})

    def test_colon_in_a_note_is_drawn_as_a_colon(self):
        """The escape must be invisible to the reader, not just to the parser."""
        output = StateDiagramRenderer().render(
            [MermaidState(id="A")],
            [],
            notes=[MermaidNote(state_id="A", text="state: ready")],
        )
        result = assert_parses({"note": output}, render=True)["note"]
        assert "state: ready" in result["visible_text"]


class TestTransitionLabels:
    """§Transitions — ``From --> To : label``.

    ``::`` is Mermaid's class-application operator, so a label such as
    ``"a :: b"`` was read as grammar rather than as text.
    """

    @pytest.mark.parametrize("label", HOSTILE_LABELS)
    def test_transition_label_never_breaks_the_diagram(self, label):
        output = StateDiagramRenderer().render(
            [MermaidState(id="A"), MermaidState(id="B")],
            [MermaidTransition("A", "B", label=label)],
        )
        assert_parses({"transition": output})

    def test_double_colon_is_drawn_as_two_colons(self):
        output = StateDiagramRenderer().render(
            [MermaidState(id="A"), MermaidState(id="B")],
            [MermaidTransition("A", "B", label="a :: b")],
        )
        result = assert_parses({"transition": output}, render=True)["transition"]
        assert "a :: b" in result["visible_text"]

    def test_newline_in_a_label_becomes_a_line_break(self):
        """``<br>`` is the documented substitute; prove it is honoured."""
        output = StateDiagramRenderer().render(
            [MermaidState(id="A"), MermaidState(id="B")],
            [MermaidTransition("A", "B", label="first\nsecond")],
        )
        result = assert_parses({"transition": output}, render=True)["transition"]
        assert "first\nsecond" in result["visible_text"]


class TestStateLabels:
    """§States — the colon form and the quoted ``state "..." as id`` form."""

    @pytest.mark.parametrize("label", HOSTILE_LABELS)
    def test_state_label_never_breaks_the_diagram(self, label):
        output = StateDiagramRenderer().render([MermaidState(id="A", label=label)], [])
        assert_parses({"state": output})

    def test_colon_label_is_drawn_with_its_colon(self):
        output = StateDiagramRenderer().render([MermaidState(id="A", label="Phase 1: review")], [])
        result = assert_parses({"state": output}, render=True)["state"]
        assert "Phase 1: review" in result["visible_text"]


class TestSubgraphTitles:
    """§Subgraphs — ``subgraph id["title"]``.

    The flowchart lexer matches the ``direction`` keyword inside the
    quoted title even though the same text is harmless in a node label.
    """

    @pytest.mark.parametrize("title", HOSTILE_LABELS)
    def test_subgraph_title_never_breaks_the_diagram(self, title):
        output = FlowchartRenderer().render(
            [FlowchartNode(id="A", label="Inside")],
            [],
            [FlowchartSubgraph(id="G", title=title, node_ids=["A"])],
        )
        assert_parses({"subgraph": output})

    def test_direction_keyword_is_drawn_as_written(self):
        output = FlowchartRenderer().render(
            [FlowchartNode(id="A", label="Inside")],
            [],
            [FlowchartSubgraph(id="G", title="set direction LR", node_ids=["A"])],
        )
        result = assert_parses({"subgraph": output}, render=True)["subgraph"]
        assert "set direction LR" in result["visible_text"]


class TestFlowchartLabels:
    """§A node with text and §Text on links — both are quoted positions."""

    @pytest.mark.parametrize("label", HOSTILE_LABELS)
    @pytest.mark.parametrize(
        "shape", ["rect", "round", "stadium", "diamond", "hexagon", "subroutine", "circle"]
    )
    def test_node_label_never_breaks_the_diagram(self, label, shape):
        output = FlowchartRenderer().render([FlowchartNode(id="A", label=label, shape=shape)], [])
        assert_parses({"node": output})

    @pytest.mark.parametrize("label", HOSTILE_LABELS)
    @pytest.mark.parametrize("style", ["solid", "dotted", "thick"])
    def test_edge_label_never_breaks_the_diagram(self, label, style):
        output = FlowchartRenderer().render(
            [FlowchartNode(id="A"), FlowchartNode(id="B")],
            [FlowchartEdge("A", "B", label=label, style=style)],
        )
        assert_parses({"edge": output})

    def test_quotes_and_hashes_are_drawn_as_written(self):
        output = FlowchartRenderer().render(
            [FlowchartNode(id="A", label='issue #42 is "open"')], []
        )
        result = assert_parses({"node": output}, render=True)["node"]
        assert 'issue #42 is "open"' in result["visible_text"]

    @pytest.mark.parametrize("label", ["step 1; step 2", "do x; then Zebra --> Walrus"])
    def test_a_semicolon_is_contained_by_the_quoting(self, label):
        """``;`` ends a statement in the flowchart grammar too, but the
        label position is quoted, so no extra escape is needed.  Proven
        rather than assumed, because the state grammar's unquoted
        positions needed one."""
        output = FlowchartRenderer().render([FlowchartNode(id="A", label=label)], [])
        result = assert_parses({"node": output}, render=True)["node"]
        assert result["visible_text"] == label

    @pytest.mark.parametrize("label", ["step 1; step 2", "a; b --> c"])
    def test_a_semicolon_in_an_edge_label_is_contained(self, label):
        output = FlowchartRenderer().render(
            [FlowchartNode(id="A"), FlowchartNode(id="B")],
            [FlowchartEdge("A", "B", label=label)],
        )
        result = assert_parses({"edge": output}, render=True)["edge"]
        assert label in result["visible_text"]

    @pytest.mark.parametrize("title", ["group 1; group 2", "a; b --> c"])
    def test_a_semicolon_in_a_subgraph_title_is_contained(self, title):
        output = FlowchartRenderer().render(
            [FlowchartNode(id="A", label="Inside")],
            [],
            [FlowchartSubgraph(id="G", title=title, node_ids=["A"])],
        )
        result = assert_parses({"subgraph": output}, render=True)["subgraph"]
        assert title in result["visible_text"]


class TestReservedWordCorpus:
    """Every grammar keyword either is rejected or actually works.

    ``TestFlowchartIdValidation`` and ``TestStateIdValidation`` in
    ``tests/test_types_validation.py`` iterate the reserved-word
    frozensets, so they can only confirm that the listed words are
    rejected — they are structurally incapable of noticing a word that
    is missing from the list.  This class sweeps an independent corpus
    through the real parser instead, so an omission fails the build.
    """

    @pytest.mark.parametrize("word", KEYWORD_CORPUS)
    def test_flowchart_keyword_is_rejected_or_renders(self, word):
        try:
            node = FlowchartNode(id=word, label="L")
            bare = FlowchartNode(id=word)
            sub = FlowchartSubgraph(id=word, node_ids=["Z"])
            edge = FlowchartEdge("Start", word)
        except ValueError:
            return  # rejected up front, which is the other valid outcome

        renderer = FlowchartRenderer()
        assert_parses(
            {
                "node": renderer.render([node], []),
                "bare": renderer.render([bare], []),
                "edge": renderer.render([FlowchartNode(id="Start"), node], [edge]),
                "subgraph": renderer.render([FlowchartNode(id="Z")], [], [sub]),
            }
        )

    @pytest.mark.parametrize("word", KEYWORD_CORPUS)
    def test_state_keyword_is_rejected_or_renders(self, word):
        try:
            bare = MermaidState(id=word)
            labelled = MermaidState(id=word, label="L")
            quoted = MermaidState(id=word, label="a: b")
            transition = MermaidTransition("Start", word)
        except ValueError:
            return

        renderer = StateDiagramRenderer()
        assert_parses(
            {
                "bare": renderer.render([bare], []),
                "labelled": renderer.render([labelled], []),
                "quoted": renderer.render([quoted], []),
                "transition": renderer.render([MermaidState(id="Start"), bare], [transition]),
            }
        )


class TestStatementSeparator:
    """``;`` ends a statement, so text after one becomes diagram source.

    This is worse than a parse error: a label of ``"do x; then A --> B"``
    produced a *valid* diagram with two extra states and a transition
    the caller never asked for.
    """

    @pytest.mark.parametrize(
        "text", ["step 1; step 2", "do x; then Zebra --> Walrus", "retry; -- see note", "a;b", ";"]
    )
    def test_semicolon_in_a_state_label_is_contained(self, text):
        """The text stays one label instead of becoming diagram source."""
        output = StateDiagramRenderer().render([MermaidState(id="A", label=text)], [])
        result = assert_parses({"state": output}, render=True)["state"]
        assert text in result["visible_text"]

    @pytest.mark.parametrize(
        "text", ["step 1; step 2", "do x; then Zebra --> Walrus", "retry; -- see note"]
    )
    def test_semicolon_in_a_transition_label_is_contained(self, text):
        output = StateDiagramRenderer().render(
            [MermaidState(id="A"), MermaidState(id="B")],
            [MermaidTransition("A", "B", label=text)],
        )
        result = assert_parses({"transition": output}, render=True)["transition"]
        assert text in result["visible_text"]

    @pytest.mark.parametrize("text", ["n; Zebra --> Walrus", "a; b"])
    def test_semicolon_in_a_note_is_contained(self, text):
        output = StateDiagramRenderer().render(
            [MermaidState(id="A")], [], notes=[MermaidNote(state_id="A", text=text)]
        )
        result = assert_parses({"note": output}, render=True)["note"]
        assert text in result["visible_text"]

    def test_no_extra_states_are_created(self):
        """The injected text must not become nodes of its own.

        With the escape in place the whole phrase is one label, so the
        rendered diagram shows exactly that text and nothing else — the
        ``-->`` inside it is drawn, not obeyed.
        """
        output = StateDiagramRenderer().render(
            [MermaidState(id="A", label="do x; then Zebra --> Walrus")], []
        )
        result = assert_parses({"state": output}, render=True)["state"]
        assert result["visible_text"] == "do x; then Zebra --> Walrus"

    def test_the_semicolon_is_still_drawn(self):
        """Containing it must not cost the reader the character."""
        output = StateDiagramRenderer().render(
            [MermaidState(id="A"), MermaidState(id="B")],
            [MermaidTransition("A", "B", label="step 1; step 2")],
        )
        result = assert_parses({"transition": output}, render=True)["transition"]
        assert "step 1; step 2" in result["visible_text"]

    def test_a_semicolon_label_really_would_have_injected_states(self):
        """Proves the escape is load-bearing."""
        smuggled = "stateDiagram-v2\n    A : do x; then Zebra --> Walrus\n"
        result = mermaid_check({"smuggled": smuggled}, render=True)["smuggled"]
        assert result["ok"] and "Zebra" in result["visible_text"], (
            "fixture no longer demonstrates the injection"
        )


class TestIdentifierInjection:
    """Identifiers are emitted unquoted, so they are validated instead.

    An id is not merely a rendering risk: ``"A --> Evil"`` produced a
    *valid* diagram containing a node and an edge the caller never asked
    for, which no "does it parse" check could ever catch.
    """

    INJECTIONS: ClassVar[list[str]] = [
        "A --> Evil",
        "A\n    Evil[x]",
        "A;Evil",
        "A --- Evil",
        'A["hijacked"]',
        "A -.-> Evil",
        "A end",
        "A|B",
        "A B",
        "",
        "   ",
        "A\tB",
    ]

    # Hyphen runs need their own list: they contain no spaces, so they
    # look like ordinary kebab-case ids, yet "A---B" draws two nodes
    # joined by a link. State ids reject "-" outright, so this applies
    # to flowcharts only.
    LINK_OPERATOR_IDS: ClassVar[list[str]] = [
        "A---B",
        "A----B",
        "A-.-B",
        "A-.-.B",
        "A-->B",
        "A--B",
        "A-.B",
        "A--.",
    ]

    @pytest.mark.parametrize("bad_id", LINK_OPERATOR_IDS)
    def test_hyphen_runs_are_rejected(self, bad_id):
        with pytest.raises(ValueError, match="Invalid flowchart"):
            FlowchartNode(id=bad_id, label="L")

    @pytest.mark.parametrize("bad_id", ["A---B", "A-.-B", "A----B"])
    def test_a_rejected_hyphen_run_really_would_have_injected_a_link(self, bad_id):
        """Without the rule these render as two nodes, not one."""
        smuggled = f'flowchart TD\n    {bad_id}["L"]\n'
        result = mermaid_check({"smuggled": smuggled}, render=True)["smuggled"]
        assert result["ok"] and result["visible_text"] != "L", (
            "fixture no longer demonstrates the injection"
        )

    @pytest.mark.parametrize("bad_id", INJECTIONS)
    def test_flowchart_node_id_is_rejected(self, bad_id):
        with pytest.raises(ValueError, match="Invalid flowchart"):
            FlowchartNode(id=bad_id, label="L")

    @pytest.mark.parametrize("bad_id", INJECTIONS)
    def test_flowchart_edge_endpoints_are_rejected(self, bad_id):
        with pytest.raises(ValueError, match="Invalid flowchart"):
            FlowchartEdge(bad_id, "B")
        with pytest.raises(ValueError, match="Invalid flowchart"):
            FlowchartEdge("A", bad_id)

    @pytest.mark.parametrize("bad_id", INJECTIONS)
    def test_state_id_is_rejected(self, bad_id):
        with pytest.raises(ValueError, match="Invalid state"):
            MermaidState(id=bad_id)

    @pytest.mark.parametrize("bad_id", INJECTIONS)
    def test_subgraph_id_is_rejected(self, bad_id):
        with pytest.raises(ValueError, match="Invalid flowchart"):
            FlowchartSubgraph(id=bad_id)

    def test_a_rejected_id_would_really_have_injected_structure(self):
        """Proves the validation is load-bearing, not cosmetic.

        Hand-building the text the renderer *would* have produced shows
        Mermaid accepting a two-node, one-edge diagram from a request
        for a single node.
        """
        smuggled = 'flowchart TD\n    A --> Evil["L"]\n'
        results = mermaid_check({"smuggled": smuggled})
        assert results["smuggled"]["ok"], "fixture no longer demonstrates the injection"


class TestValidIdentifiersStillWork:
    """The validation must not reject identifiers Mermaid accepts."""

    @pytest.mark.parametrize("good_id", ["A", "Draft", "state_1", "s.2", "X9", "_private", "End"])
    def test_state_ids_are_accepted(self, good_id):
        output = StateDiagramRenderer().render([MermaidState(id=good_id, label="L")], [])
        assert_parses({"state": output})

    @pytest.mark.parametrize(
        "good_id", ["A", "Start", "node_1", "a.b", "kebab-case", "X9", "End", "class1"]
    )
    def test_flowchart_ids_are_accepted(self, good_id):
        output = FlowchartRenderer().render([FlowchartNode(id=good_id, label="L")], [])
        assert_parses({"node": output})


class TestNotePositions:
    """§Notes defines exactly two positions; anything else is a lex error."""

    @pytest.mark.parametrize("position", ["left", "right"])
    def test_documented_positions_parse(self, position):
        output = StateDiagramRenderer().render(
            [MermaidState(id="A")],
            [],
            notes=[MermaidNote(state_id="A", text="hello", position=position)],
        )
        assert_parses({"note": output})

    @pytest.mark.parametrize("position", ["above", "below", "RIGHT", "", "of", "sideways"])
    def test_undocumented_positions_are_rejected(self, position):
        with pytest.raises(ValueError, match="Invalid note position"):
            MermaidNote(state_id="A", text="hello", position=position)


class TestOracleIsCalibrated:
    """An oracle that accepts everything would make every test above vacuous."""

    @pytest.mark.parametrize(
        "broken",
        [
            "flowchart TD\n    A -->\n",
            'flowchart TD\n    A["unclosed\n',
            "stateDiagram-v2\n    A\n    note sideways of A : x\n",
            "stateDiagram-v2\n    A --> B : a :: b\n",
            'flowchart TD\n    subgraph G["set direction LR"]\n        A\n    end\n',
            "not-a-diagram-type\n    A --> B\n",
        ],
    )
    def test_known_bad_diagrams_are_rejected(self, broken):
        results = mermaid_check({"broken": broken})
        assert not results["broken"]["ok"], (
            "the Mermaid oracle accepted input that must not parse; "
            "the conformance tests above would be meaningless"
        )
