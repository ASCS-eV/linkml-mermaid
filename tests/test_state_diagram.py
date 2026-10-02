"""StateDiagramRenderer tests — validating against the Mermaid spec.

Each test asserts what the Mermaid stateDiagram-v2 specification REQUIRES,
not what our implementation happens to produce.  Expected outputs are
hand-written by reading the spec, and structural validators enforce
grammar rules derived from the spec.

Spec: https://mermaid.js.org/syntax/stateDiagram.html
"""

from __future__ import annotations

import re

import pytest

from linkml_mermaid import MermaidNote, MermaidState, MermaidTransition
from linkml_mermaid.state_diagram import StateDiagramRenderer, to_state_id

# ── Spec-derived grammar patterns ───────────────────────────────────
#
# These regexes are derived directly from the Mermaid stateDiagram-v2
# specification, NOT from our implementation.  They define what valid
# Mermaid syntax looks like.

# §States (colon form): "state id followed by a colon and the description"
_STATE_LABEL_RE = re.compile(r"^\s+(\w+) : (.+)$")

# §Transitions: "text arrow, '-->'", optionally "add text to a transition"
_TRANSITION_RE = re.compile(
    r"^\s+(\[?\*?\]?[\w]+|\[\*\]) --> (\[?\*?\]?[\w]+|\[\*\])"
    r"(?: : (.+))?$"
)

# §Start and End: "[*] syntax"
_START_RE = re.compile(r"^\s+\[\*\] --> (\w+)$")
_END_RE = re.compile(r"^\s+(\w+) --> \[\*\]$")

# §Notes: "note right of StateId : text" or "note left of StateId : text"
_NOTE_RE = re.compile(r"^\s+note (right|left) of (\w+) : (.+)$")

# §Direction: "direction TB|LR|BT|RL"
_DIRECTION_RE = re.compile(r"^\s+direction (TB|LR|BT|RL)$")


def _validate_mermaid_grammar(text: str) -> list[str]:
    """Validate every line of a stateDiagram-v2 against the spec grammar.

    Returns a list of error messages (empty = valid).

    Per the spec, valid content lines are:
    - ``stateDiagram-v2``  (declaration)
    - ``direction {TB|LR|BT|RL}``  (§Setting the direction)
    - ``[*] --> StateId``  (§Start and End — start)
    - ``StateId --> [*]``  (§Start and End — end)
    - ``StateId --> StateId``  (§Transitions — unlabeled)
    - ``StateId --> StateId : label``  (§Transitions — labeled)
    - ``StateId : label``  (§States — colon form)
    - ``note {right|left} of StateId : text``  (§Notes)
    - Empty lines (separators)
    """
    errors = []
    lines = text.split("\n")

    if not lines or lines[0] != "stateDiagram-v2":
        errors.append("Line 0: must be 'stateDiagram-v2' (spec: diagram declaration)")

    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "":
            continue
        if _DIRECTION_RE.match(line):
            continue
        if _START_RE.match(line):
            continue
        if _END_RE.match(line):
            continue
        if _TRANSITION_RE.match(line):
            continue
        if _STATE_LABEL_RE.match(line):
            continue
        if _NOTE_RE.match(line):
            continue
        errors.append(f"Line {i}: '{line}' does not match any spec grammar rule")

    return errors


# ── to_state_id tests ────────────────────────────────────────────────
#
# §Spaces in state names: "Spaces can be added to a state by first
# defining the state with an id and then referencing the id later."
#
# Our to_state_id() converts human labels to valid PascalCase identifiers
# so that Mermaid can reference them without spaces.


class TestToStateId:
    """Per §Spaces in state names, IDs must not contain spaces."""

    def test_single_word(self):
        assert to_state_id("Draft") == "Draft"

    def test_two_words_become_pascal_case(self):
        """'Content Review' → 'ContentReview' — spaces eliminated per spec."""
        assert to_state_id("Content Review") == "ContentReview"

    def test_underscores_split(self):
        """'in_progress' → 'InProgress' — underscores treated as separators."""
        assert to_state_id("in_progress") == "InProgress"

    def test_hyphens_split(self):
        assert to_state_id("in-progress") == "InProgress"

    def test_mixed_separators(self):
        assert to_state_id("my_state-name here") == "MyStateNameHere"

    def test_empty_string(self):
        """An empty id is not valid Mermaid, so refuse rather than emit it."""
        with pytest.raises(ValueError, match="no alphanumeric characters"):
            to_state_id("")

    def test_punctuation_only_rejected(self):
        """A label with nothing alphanumeric cannot yield an identifier."""
        with pytest.raises(ValueError, match="no alphanumeric characters"):
            to_state_id("--- ___ ---")

    def test_already_pascal_case_is_preserved(self):
        """Inner capitals survive: 'DraftState' must not become 'Draftstate'.

        Round-tripping an id through to_state_id() has to be stable,
        otherwise a schema that already uses PascalCase ids silently
        gets different node names than the schema declares.
        """
        assert to_state_id("DraftState") == "DraftState"

    def test_round_trip_is_idempotent(self):
        """to_state_id(to_state_id(x)) == to_state_id(x).

        Ids this function produces are written into diagrams and may be
        fed back in on a later run; an unstable conversion would rename
        nodes between regenerations.
        """
        labels = [
            "Content Review",
            "in_progress",
            "Draft (new)",
            "A1 b2",
            "IN_REVIEW",
            "2nd pass",
            "DRAFT_A",
            "ContentReview",
            "RED",
        ]
        for label in labels:
            once = to_state_id(label)
            assert to_state_id(once) == once, label

    def test_screaming_snake_case_is_title_cased(self):
        """A separated all-caps label is a SCREAMING_SNAKE identifier."""
        assert to_state_id("IN_REVIEW") == "InReview"
        assert to_state_id("DRAFT_A") == "DraftA"

    def test_unseparated_all_caps_is_preserved(self):
        """Without separators there are no word boundaries to infer, and
        rewriting would break idempotency."""
        assert to_state_id("RED") == "RED"

    def test_strips_arbitrary_punctuation(self):
        """The docstring promises non-alphanumerics are stripped, not just
        whitespace/underscore/hyphen."""
        assert to_state_id("Draft (new)") == "DraftNew"
        assert to_state_id("In-Review!") == "InReview"
        assert to_state_id("a.b,c;d") == "ABCD"

    def test_leading_digit_is_prefixed(self):
        """Mermaid identifiers may not start with a digit."""
        assert to_state_id("2nd pass") == "S2ndPass"

    def test_result_has_no_spaces(self):
        """The fundamental spec requirement: no spaces in IDs."""
        result = to_state_id("A long state name with spaces")
        assert " " not in result

    def test_result_is_alphanumeric(self):
        """IDs contain only alphanumeric characters after conversion.

        §Spaces in state names requires a state to be "first defined
        with an id", which must be a bare identifier — so every
        separator and punctuation mark is removed, not merely spaces.
        """
        for label in ["Content Review", "Draft (new)", "In-Approval!", "a.b"]:
            assert re.fullmatch(r"[A-Za-z0-9]+", to_state_id(label))


# ── StateDiagramRenderer spec compliance ─────────────────────────────


class TestStateDiagramDeclaration:
    """Spec: 'The syntax tries to be compliant' — must start with
    stateDiagram-v2."""

    def test_first_line_is_declaration(self):
        r = StateDiagramRenderer()
        output = r.render([], [])
        assert output.split("\n")[0] == "stateDiagram-v2"

    def test_empty_diagram_is_valid_grammar(self):
        """An empty diagram should still be grammatically valid Mermaid."""
        r = StateDiagramRenderer()
        output = r.render([], [])
        errors = _validate_mermaid_grammar(output)
        assert errors == [], f"Grammar errors: {errors}"


class TestStateDiagramDirection:
    """§Setting the direction: 'use the direction statement to set the
    direction which the diagram will render.'  Values: TB, LR, BT, RL."""

    @pytest.mark.parametrize("direction", ["TB", "LR", "BT", "RL"])
    def test_direction_emitted(self, direction):
        r = StateDiagramRenderer(direction=direction)
        output = r.render([], [])
        assert f"    direction {direction}" in output

    def test_no_direction_by_default(self):
        r = StateDiagramRenderer()
        output = r.render([], [])
        assert "direction" not in output

    def test_direction_line_grammar(self):
        """Direction line must match spec grammar exactly."""
        r = StateDiagramRenderer(direction="LR")
        output = r.render([], [])
        errors = _validate_mermaid_grammar(output)
        assert errors == []


class TestStateDiagramStates:
    """§States: 'define the state id followed by a colon and the description'
    — the colon form (form 3).

    Per spec, form 3 is: ``s1 : This is a state``
    We emit this ONLY when label differs from id (no redundant labels)."""

    def test_label_emitted_when_different_from_id(self):
        """Spec example: s1 : This is a state"""
        states = [MermaidState(id="Draft", label="Draft Phase")]
        r = StateDiagramRenderer()
        output = r.render(states, [])
        assert "    Draft : Draft Phase" in output

    def test_label_not_emitted_when_equal_to_id(self):
        """No redundancy: if label == id, don't emit a label line."""
        states = [MermaidState(id="Draft", label="Draft")]
        r = StateDiagramRenderer()
        output = r.render(states, [])
        # Should NOT contain a colon label line
        assert "Draft : Draft" not in output

    def test_label_not_emitted_when_none(self):
        states = [MermaidState(id="Draft")]
        r = StateDiagramRenderer()
        output = r.render(states, [])
        assert "Draft :" not in output

    def test_colon_form_grammar(self):
        """Label line must match the spec colon-form grammar."""
        states = [MermaidState(id="ContentReview", label="Content Review")]
        r = StateDiagramRenderer()
        output = r.render(states, [])
        for line in output.split("\n"):
            if ":" in line and "stateDiagram" not in line:
                assert _STATE_LABEL_RE.match(line), f"Bad label line: {line}"


class TestStateDiagramStartEnd:
    """§Start and End: 'written with the [*] syntax and the direction of
    the transition to it defines it either as a start or a stop state.'

    - Start: [*] --> StateId
    - Stop:  StateId --> [*]"""

    def test_initial_state_start_transition(self):
        """Spec: [*] --> StateId for start states."""
        states = [MermaidState(id="Red", is_initial=True)]
        r = StateDiagramRenderer()
        output = r.render(states, [])
        assert "    [*] --> Red" in output

    def test_terminal_state_end_transition(self):
        """Spec: StateId --> [*] for stop states."""
        states = [MermaidState(id="Done", is_terminal=True)]
        r = StateDiagramRenderer()
        output = r.render(states, [])
        assert "    Done --> [*]" in output

    def test_both_initial_and_terminal(self):
        """A trivial single-state machine: both start and stop."""
        states = [MermaidState(id="Only", is_initial=True, is_terminal=True)]
        r = StateDiagramRenderer()
        output = r.render(states, [])
        assert "    [*] --> Only" in output
        assert "    Only --> [*]" in output

    def test_no_initial_state(self):
        """No [*] --> if no state is initial."""
        states = [MermaidState(id="Middle")]
        r = StateDiagramRenderer()
        output = r.render(states, [])
        assert "[*] -->" not in output

    def test_no_terminal_state(self):
        """No --> [*] if no state is terminal."""
        states = [MermaidState(id="Middle")]
        r = StateDiagramRenderer()
        output = r.render(states, [])
        assert "--> [*]" not in output

    def test_multiple_initial_states(self):
        """Both should get [*] --> transitions."""
        states = [
            MermaidState(id="A", is_initial=True),
            MermaidState(id="B", is_initial=True),
        ]
        r = StateDiagramRenderer()
        output = r.render(states, [])
        assert output.count("[*] -->") == 2


class TestStateDiagramTransitions:
    """§Transitions: 'text arrow, "-->"' and 'possible to add text to a
    transition to describe what it represents.'

    Labeled:   A --> B : label
    Unlabeled: A --> B"""

    def test_labeled_transition(self):
        """Spec: FromState --> ToState : label"""
        t = [MermaidTransition("Red", "Green", label="Go")]
        r = StateDiagramRenderer()
        output = r.render([], t)
        assert "    Red --> Green : Go" in output

    def test_unlabeled_transition(self):
        """Spec: FromState --> ToState (no colon, no label)"""
        t = [MermaidTransition("Red", "Green")]
        r = StateDiagramRenderer()
        output = r.render([], t)
        assert "    Red --> Green" in output
        # Must NOT have a dangling colon
        assert "    Red --> Green :" not in output

    def test_self_loop(self):
        """A --> A is valid per spec (transition to self)."""
        t = [MermaidTransition("Draft", "Draft", label="Revise")]
        r = StateDiagramRenderer()
        output = r.render([], t)
        assert "    Draft --> Draft : Revise" in output

    def test_multiple_transitions_same_pair(self):
        """Two transitions between the same states, different labels."""
        t = [
            MermaidTransition("A", "B", label="Path 1"),
            MermaidTransition("A", "B", label="Path 2"),
        ]
        r = StateDiagramRenderer()
        output = r.render([], t)
        assert "    A --> B : Path 1" in output
        assert "    A --> B : Path 2" in output

    def test_transition_grammar(self):
        """Every transition line must match the spec grammar."""
        transitions = [
            MermaidTransition("Red", "Green", label="Go [Timer]"),
            MermaidTransition("Green", "Yellow"),
        ]
        r = StateDiagramRenderer()
        output = r.render([], transitions)
        errors = _validate_mermaid_grammar(output)
        assert errors == [], f"Grammar errors: {errors}"


class TestStateDiagramNotes:
    """§Notes: 'note right of StateId : text' or 'note left of'."""

    def test_right_note(self):
        """Spec: note right of StateId : text"""
        notes = [MermaidNote(state_id="Red", text="Important", position="right")]
        r = StateDiagramRenderer()
        output = r.render([], [], notes=notes)
        assert "    note right of Red : Important" in output

    def test_left_note(self):
        notes = [MermaidNote(state_id="Green", text="Safe to go", position="left")]
        r = StateDiagramRenderer()
        output = r.render([], [], notes=notes)
        assert "    note left of Green : Safe to go" in output

    def test_no_notes_by_default(self):
        r = StateDiagramRenderer()
        output = r.render([], [])
        assert "note" not in output

    def test_note_grammar(self):
        notes = [MermaidNote(state_id="A", text="Test note")]
        r = StateDiagramRenderer()
        output = r.render([], [], notes=notes)
        errors = _validate_mermaid_grammar(output)
        assert errors == [], f"Grammar errors: {errors}"


class TestStateDiagramOrdering:
    """Conventional ordering — not spec-mandated but important for
    readability and deterministic output:
    1. Declaration  2. Direction  3. Start transitions
    4. Labels  5. Transitions  6. End transitions  7. Notes"""

    def test_full_diagram_ordering(self):
        states = [
            MermaidState(id="Red", label="Red Light", is_initial=True),
            MermaidState(id="Green", label="Green Light", is_terminal=True),
        ]
        transitions = [MermaidTransition("Red", "Green", label="Go")]
        notes = [MermaidNote(state_id="Red", text="Wait here")]
        r = StateDiagramRenderer(direction="LR")
        output = r.render(states, transitions, notes=notes)
        lines = output.split("\n")

        # Find positions of each section
        decl_idx = next(i for i, l in enumerate(lines) if "stateDiagram-v2" in l)
        dir_idx = next(i for i, l in enumerate(lines) if "direction" in l)
        start_idx = next(i for i, l in enumerate(lines) if "[*] -->" in l)
        label_idx = next(i for i, l in enumerate(lines) if "Red : Red Light" in l)
        trans_idx = next(i for i, l in enumerate(lines) if "Red --> Green" in l)
        end_idx = next(i for i, l in enumerate(lines) if "--> [*]" in l)
        note_idx = next(i for i, l in enumerate(lines) if "note" in l)

        assert decl_idx < dir_idx < start_idx < label_idx < trans_idx < end_idx < note_idx

    def test_content_lines_are_indented(self):
        """Convention: all content lines are indented (4 spaces)."""
        states = [MermaidState(id="A", is_initial=True)]
        r = StateDiagramRenderer()
        output = r.render(states, [])
        for line in output.split("\n"):
            if line.strip() and line != "stateDiagram-v2":
                assert line.startswith("    "), f"Not indented: '{line}'"


class TestFullDiagramGrammarCompliance:
    """End-to-end grammar validation: build a realistic diagram and check
    every single line against the spec grammar."""

    def test_traffic_light_diagram(self):
        """A complete traffic-light state machine."""
        states = [
            MermaidState(id="Red", label="Red Light", is_initial=True),
            MermaidState(id="Yellow", label="Yellow Light"),
            MermaidState(id="Green", label="Green Light"),
        ]
        transitions = [
            MermaidTransition("Red", "Green", label="Go"),
            MermaidTransition("Green", "Yellow", label="Caution"),
            MermaidTransition("Yellow", "Red", label="Stop"),
        ]
        notes = [MermaidNote(state_id="Red", text="Wait for green")]
        r = StateDiagramRenderer(direction="LR")
        output = r.render(states, transitions, notes=notes)
        errors = _validate_mermaid_grammar(output)
        assert errors == [], "Grammar errors:\n" + "\n".join(errors)

    def test_expected_output_hand_written(self):
        """Hand-written expected output based on spec reading.

        This is the KEY test: we write what the spec says the output
        SHOULD be, and assert the implementation matches.  If someone
        changes the implementation, this test breaks unless the change
        still conforms to the spec.
        """
        states = [
            MermaidState(id="Open", label="Open", is_initial=True),
            MermaidState(id="Closed", label="Closed", is_terminal=True),
        ]
        transitions = [MermaidTransition("Open", "Closed", label="Close")]

        r = StateDiagramRenderer()
        output = r.render(states, transitions)

        # Per spec:
        # - Line 0: stateDiagram-v2
        # - [*] --> Open  (§Start and End — Open is initial)
        # - No label line (label == id for both states)
        # - Open --> Closed : Close  (§Transitions — labeled)
        # - Closed --> [*]  (§Start and End — Closed is terminal)
        expected = "\n".join(
            [
                "stateDiagram-v2",
                "    [*] --> Open",
                "",
                "    Open --> Closed : Close",
                "",
                "    Closed --> [*]",
            ]
        )
        assert output == expected

    def test_expected_output_with_labels(self):
        """When label ≠ id, the colon form MUST appear per §States."""
        states = [
            MermaidState(id="ContentReview", label="Content Review", is_initial=True),
        ]
        r = StateDiagramRenderer()
        output = r.render(states, [])

        # Per spec: declaration, start transition, blank, label, then
        # the terminal section (empty since no terminals — just the blank)
        expected = "\n".join(
            [
                "stateDiagram-v2",
                "    [*] --> ContentReview",
                "",
                "    ContentReview : Content Review",
                "",
            ]
        )
        assert output == expected
