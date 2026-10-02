"""Tests for the identifier and enum validation on the Mermaid types.

Identifiers are the one caller-supplied value the renderers emit
*unquoted*, because both Mermaid grammars require a bare token there.
No amount of escaping helps, so the types reject an identifier the
grammar would not read as a single token.  This matters beyond
tidiness: ``"A --> Evil"`` as a node id produces a perfectly valid
diagram containing an edge and a node the caller never asked for.

The accepted character sets below were derived by feeding every ASCII
character, plus accented and CJK samples, to Mermaid 11 in both leading
and interior positions and recording which ones it would read as part
of an identifier.  ``tests/test_mermaid_conformance.py`` keeps that
derivation honest against the real parser; these tests pin the
resulting rule.
"""

from __future__ import annotations

import pytest

from linkml_mermaid import (
    FLOWCHART_RESERVED_IDS,
    NOTE_POSITIONS,
    STATE_RESERVED_IDS,
    FlowchartEdge,
    FlowchartNode,
    FlowchartSubgraph,
    MermaidNote,
    MermaidState,
    MermaidTransition,
    validate_flowchart_id,
    validate_state_id,
)

# Separators, grammar operators and whitespace: the ways an identifier
# could stop being one token.
STRUCTURAL = [
    "A B",
    "A\tB",
    "A\nB",
    "A\r\nB",
    "A-->B",
    "A --> B",
    "A---B",
    "A;B",
    "A,B",
    "A:B",
    "A|B",
    "A(B)",
    "A[B]",
    "A{B}",
    'A"B"',
    "A'B'",
    "A<B>",
    "A&B",
    "A#B",
    "A%B",
    "A@B",
    "A!B",
    "A?B",
    "A*B",
    "A+B",
    "A=B",
    "A/B",
    "A\\B",
    "A~B",
    "A`B",
    "A^B",
    "A$B",
    "",
    " ",
    "   ",
    "\n",
]


class TestFlowchartIdValidation:
    """Flowchart ids accept ``[A-Za-z0-9_.-]``."""

    @pytest.mark.parametrize(
        "value", ["A", "node1", "a_b", "a.b", "a-b", "_x", "X9", "End", "TB", "LR", "o", "x"]
    )
    def test_valid_ids_are_accepted(self, value):
        assert validate_flowchart_id(value, "node id") == value

    @pytest.mark.parametrize("value", [*STRUCTURAL, "A---B", "A-.-B", "A----B", "A--B"])
    def test_structural_characters_are_rejected(self, value):
        with pytest.raises(ValueError, match="Invalid flowchart"):
            validate_flowchart_id(value, "node id")

    @pytest.mark.parametrize("value", ["A---B", "A-.-B", "A--B", "A-.B", "a--b", "a-.c"])
    def test_link_operators_hidden_in_an_id_are_rejected(self, value):
        """``-`` alone is safe, but ``--`` and ``-.`` begin a link, so an
        id containing either would draw an edge the caller never asked
        for."""
        with pytest.raises(ValueError, match=r"may not contain"):
            validate_flowchart_id(value, "node id")

    @pytest.mark.parametrize("value", ["a-b", "a-b-c", "kebab-case", "a.b-c", "a-b.c", "-a", "a-"])
    def test_single_hyphens_remain_legal(self, value):
        """Kebab-case is a common naming style and must keep working."""
        assert validate_flowchart_id(value, "node id") == value

    @pytest.mark.parametrize("word", sorted(FLOWCHART_RESERVED_IDS))
    def test_reserved_words_are_rejected(self, word):
        with pytest.raises(ValueError, match="reserves this word"):
            validate_flowchart_id(word, "node id")

    def test_rejection_names_the_field(self):
        """The message has to say which value was wrong, or a caller
        with many nodes cannot find it."""
        with pytest.raises(ValueError, match="node id 'A B'"):
            validate_flowchart_id("A B", "node id")

    @pytest.mark.parametrize(
        "word", ["End", "END", "Class", "Graph", "SubGraph", "direction", "state"]
    )
    def test_reserved_matching_is_case_sensitive(self, word):
        """Only the literals Mermaid actually reserves are rejected;
        over-rejecting would turn working ids into errors."""
        assert validate_flowchart_id(word, "node id") == word


class TestStateIdValidation:
    """State ids accept ``[A-Za-z0-9_.]`` — notably *not* ``-``, which
    the state grammar reads as the start of an arrow."""

    @pytest.mark.parametrize(
        "value", ["A", "state1", "a_b", "a.b", "_x", "X9", "End", "direction"]
    )
    def test_valid_ids_are_accepted(self, value):
        assert validate_state_id(value, "id") == value

    @pytest.mark.parametrize("value", STRUCTURAL)
    def test_structural_characters_are_rejected(self, value):
        with pytest.raises(ValueError, match="Invalid state"):
            validate_state_id(value, "id")

    def test_hyphen_is_rejected_even_though_flowcharts_allow_it(self):
        """The two grammars genuinely differ here."""
        assert validate_flowchart_id("a-b", "node id") == "a-b"
        with pytest.raises(ValueError, match="Invalid state"):
            validate_state_id("a-b", "id")

    @pytest.mark.parametrize("word", sorted(STATE_RESERVED_IDS))
    def test_reserved_words_are_rejected(self, word):
        with pytest.raises(ValueError, match="reserves this word"):
            validate_state_id(word, "id")

    def test_pseudo_state_is_opt_in(self):
        """``[*]`` is legal as a transition endpoint and nowhere else,
        so the caller has to ask for it."""
        assert validate_state_id("[*]", "id", allow_pseudo_state=True) == "[*]"
        with pytest.raises(ValueError, match="Invalid state"):
            validate_state_id("[*]", "id")


class TestStateValidation:
    @pytest.mark.parametrize("bad", ["A B", "A-->B", "", "A-b"])
    def test_state_id_is_validated_on_construction(self, bad):
        with pytest.raises(ValueError, match="Invalid state"):
            MermaidState(id=bad)

    def test_a_label_is_not_an_identifier_and_stays_free(self):
        """Labels are quoted or escaped, so they carry no restriction."""
        state = MermaidState(id="A", label="any --> text: here | ok")
        assert state.label == "any --> text: here | ok"


class TestTransitionValidation:
    @pytest.mark.parametrize("bad", ["A B", "A-->B", ""])
    def test_endpoints_are_validated(self, bad):
        with pytest.raises(ValueError, match="Invalid state"):
            MermaidTransition(bad, "B")
        with pytest.raises(ValueError, match="Invalid state"):
            MermaidTransition("A", bad)

    def test_start_end_pseudo_state_is_allowed_as_an_endpoint(self):
        """§Start and End defines ``[*]``; it is grammar, not an id."""
        assert MermaidTransition("[*]", "A").from_state == "[*]"
        assert MermaidTransition("A", "[*]").to_state == "[*]"

    def test_start_end_pseudo_state_is_not_a_state_declaration(self):
        """``[*]`` names no state, so it cannot be declared as one."""
        with pytest.raises(ValueError, match="Invalid state"):
            MermaidState(id="[*]")


class TestNoteValidation:
    @pytest.mark.parametrize("bad", ["A B", "A-->B", ""])
    def test_state_id_is_validated(self, bad):
        with pytest.raises(ValueError, match="Invalid state"):
            MermaidNote(state_id=bad, text="hello")

    @pytest.mark.parametrize("position", sorted(NOTE_POSITIONS))
    def test_documented_positions_are_accepted(self, position):
        assert MermaidNote(state_id="A", text="x", position=position).position == position

    @pytest.mark.parametrize("position", ["above", "below", "Right", "RIGHT", "", "of"])
    def test_undocumented_positions_are_rejected(self, position):
        """§Notes defines exactly two; anything else is a lex error, so
        failing here beats emitting an unparseable diagram."""
        with pytest.raises(ValueError, match="Invalid note position"):
            MermaidNote(state_id="A", text="x", position=position)


class TestFlowchartNodeValidation:
    @pytest.mark.parametrize("bad", ["A B", "A-->B", "", "A;B"])
    def test_node_id_is_validated(self, bad):
        with pytest.raises(ValueError, match="Invalid flowchart"):
            FlowchartNode(id=bad)

    def test_hyphenated_ids_are_allowed(self):
        assert FlowchartNode(id="kebab-case").id == "kebab-case"


class TestFlowchartEdgeValidation:
    @pytest.mark.parametrize("bad", ["A B", "A-->B", ""])
    def test_endpoints_are_validated(self, bad):
        with pytest.raises(ValueError, match="Invalid flowchart"):
            FlowchartEdge(bad, "B")
        with pytest.raises(ValueError, match="Invalid flowchart"):
            FlowchartEdge("A", bad)


class TestFlowchartSubgraphValidation:
    @pytest.mark.parametrize("bad", ["A B", "A-->B", ""])
    def test_subgraph_id_is_validated(self, bad):
        with pytest.raises(ValueError, match="Invalid flowchart"):
            FlowchartSubgraph(id=bad)

    @pytest.mark.parametrize("bad", ["A B", "A-->B", ""])
    def test_every_member_id_is_validated(self, bad):
        """A subgraph lists its members as bare ids, so each one is as
        dangerous as the subgraph's own id."""
        with pytest.raises(ValueError, match="Invalid flowchart"):
            FlowchartSubgraph(id="G", node_ids=["A", bad, "B"])

    def test_a_valid_member_list_is_accepted(self):
        assert FlowchartSubgraph(id="G", node_ids=["A", "B"]).node_ids == ["A", "B"]
