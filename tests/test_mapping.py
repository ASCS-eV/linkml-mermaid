"""Mapping function tests — validating the contract between layers.

These tests verify that the mapping layer correctly translates LinkML-style
data into Mermaid/GFM primitives.  The CONTRACT is:
- map_states() produces MermaidState objects whose fields match the spec
- map_transitions() produces MermaidTransition objects with correctly
  assembled labels (name + actor + guards per §Transitions)
- build_table_rows() produces row dicts ready for GFM rendering
- build_state_descriptions() reads from the schema, not from hardcoded data

Tests use BOTH dict inputs and object inputs to verify polymorphism.

Spec references:
  §States:      https://mermaid.js.org/syntax/stateDiagram.html#states
  §Transitions: https://mermaid.js.org/syntax/stateDiagram.html#transitions
  §Start/End:   https://mermaid.js.org/syntax/stateDiagram.html#start-and-end
  §Spaces:      https://mermaid.js.org/syntax/stateDiagram.html#spaces-in-state-names
  GFM §4.10:    https://github.github.com/gfm/#tables-extension-
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from linkml_mermaid import (
    SchemaReader,
    StateDiagramConfig,
    build_state_descriptions,
    build_table_rows,
    map_states,
    map_transitions,
)

# ── Helper: object-style data (simulates Pydantic models) ───────────


@dataclass
class FakeState:
    id: str
    display_name: str
    is_initial: bool = False
    is_terminal: bool = False
    color: str = ""


@dataclass
class FakeTransition:
    name: str
    from_state: str
    to_state: str
    default_actor: str = ""
    guards: list[str] | None = None


@dataclass
class FakeGuard:
    id: str
    display_name: str
    description: str = ""


# ── map_states tests ─────────────────────────────────────────────────


class TestMapStatesWithDicts:
    """Contract: map_states(dicts, config) → MermaidState objects.

    Per §States and §Spaces in state names:
    - id = PascalCase of display_name
    - label = display_name
    - is_initial = True if raw id in config.initial_state_ids
    - is_terminal = True if terminal slot is truthy
    """

    def test_basic_mapping(self, sample_states, traffic_config):
        result = map_states(sample_states, traffic_config)
        assert len(result) == 3
        # The Mermaid id comes from the id slot, not the display label
        assert result[0].id == "RED"
        assert result[0].label == "Red"

    def test_id_derives_from_id_slot_not_label(self, traffic_config):
        """Two states sharing a display label must stay distinct nodes.

        Deriving the Mermaid id from display_name would collapse both
        into one node and silently drop a state from the diagram.
        """
        states = [
            {"id": "DRAFT_A", "display_name": "Draft", "is_initial": False, "is_terminal": False},
            {"id": "DRAFT_B", "display_name": "Draft", "is_initial": False, "is_terminal": False},
        ]
        result = map_states(states, traffic_config)
        assert [s.id for s in result] == ["DraftA", "DraftB"]
        assert len({s.id for s in result}) == 2

    def test_missing_id_slot_raises(self, traffic_config):
        """A state with no id has no usable Mermaid identifier."""
        states = [{"id": None, "display_name": "Nameless"}]
        with pytest.raises(ValueError, match="id slot"):
            map_states(states, traffic_config)

    def test_initial_state_flag(self, sample_states, traffic_config):
        """RED has is_initial=True in data → is_initial=True in output."""
        result = map_states(sample_states, traffic_config)
        assert result[0].is_initial is True  # RED (is_initial=True)
        assert result[1].is_initial is False  # YELLOW
        assert result[2].is_initial is False  # GREEN

    def test_terminal_state_flag(self, traffic_config):
        """is_terminal=True states get is_terminal=True in output."""
        states = [{"id": "DONE", "display_name": "Done", "is_initial": False, "is_terminal": True}]
        result = map_states(states, traffic_config)
        assert result[0].is_terminal is True

    def test_label_fallback_to_id(self, traffic_config):
        """When display_name is None, label falls back to raw id."""
        states = [
            {"id": "ORPHAN", "display_name": None, "is_initial": False, "is_terminal": False}
        ]
        result = map_states(states, traffic_config)
        assert result[0].label == "ORPHAN"

    def test_empty_states(self, traffic_config):
        assert map_states([], traffic_config) == []


class TestMapStatesWithObjects:
    """Same contract but with object-style access (getattr)."""

    def test_basic_mapping(self, traffic_config):
        states = [
            FakeState(id="RED", display_name="Red", is_initial=True, is_terminal=False),
            FakeState(id="GREEN", display_name="Green", is_initial=False, is_terminal=False),
        ]
        result = map_states(states, traffic_config)
        assert result[0].id == "RED"
        assert result[0].label == "Red"
        assert result[0].is_initial is True  # RED has is_initial=True
        assert result[1].is_initial is False

    def test_terminal_flag_from_object(self, traffic_config):
        states = [FakeState(id="END", display_name="End", is_terminal=True)]
        result = map_states(states, traffic_config)
        assert result[0].is_terminal is True


# ── map_transitions tests ────────────────────────────────────────────


class TestMapTransitionsWithDicts:
    """Contract: map_transitions produces MermaidTransition with:
    - from_state / to_state = PascalCase of the state's id slot
    - label = 'name actor<br>guard1<br>guard2' per §Transitions"""

    def test_basic_transition(
        self, sample_states, sample_transitions, sample_guards, traffic_config
    ):
        result = map_transitions(sample_transitions, sample_states, sample_guards, traffic_config)
        assert len(result) == 3
        # First transition: RED→GREEN with guard
        assert result[0].from_state == "RED"
        assert result[0].to_state == "GREEN"

    def test_label_includes_name_and_actor(
        self, sample_states, sample_transitions, sample_guards, traffic_config
    ):
        """Label should be 'name actor' when actor is present."""
        result = map_transitions(sample_transitions, sample_states, sample_guards, traffic_config)
        # "Go [Timer]" — name + actor
        assert "Go [Timer]" in result[0].label

    def test_guard_appended_to_label(
        self, sample_states, sample_transitions, sample_guards, traffic_config
    ):
        """Guards are separated by <br>, which Mermaid actually renders.

        stateDiagram-v2 documents no backslash-n escape, so a literal
        "\\n" would appear verbatim in the rendered label.
        """
        result = map_transitions(sample_transitions, sample_states, sample_guards, traffic_config)
        # First transition has TIMER_EXPIRED guard → "{Timer expired}"
        assert "<br>{Timer expired}" in result[0].label
        assert "\\n" not in result[0].label

    def test_guard_separator_is_configurable(
        self, sample_states, sample_transitions, sample_guards
    ):
        """Callers targeting a renderer with other conventions can override."""
        config = StateDiagramConfig(guard_separator=" / ")
        result = map_transitions(sample_transitions, sample_states, sample_guards, config)
        assert " / {Timer expired}" in result[0].label

    def test_transition_without_guards(
        self, sample_states, sample_transitions, sample_guards, traffic_config
    ):
        """Transition with empty guards list → no separator in label."""
        result = map_transitions(sample_transitions, sample_states, sample_guards, traffic_config)
        # Third transition (Stop) has no guards
        assert "<br>" not in result[2].label

    def test_unknown_from_state_raises(self, traffic_config):
        """An unresolvable state must fail loudly.

        The previous '?' placeholder is not a valid Mermaid identifier,
        so it produced a diagram that silently misrepresented the data.
        """
        states = [{"id": "A", "display_name": "Alpha", "is_initial": False, "is_terminal": False}]
        transitions = [
            {
                "name": "Go",
                "from_state": "UNKNOWN",
                "to_state": "A",
                "default_actor": "",
                "guards": [],
            }
        ]
        with pytest.raises(ValueError, match="unknown state 'UNKNOWN'"):
            map_transitions(transitions, states, [], traffic_config)

    def test_unknown_to_state_raises(self, traffic_config):
        states = [{"id": "A", "display_name": "Alpha", "is_initial": False, "is_terminal": False}]
        transitions = [
            {
                "name": "Go",
                "from_state": "A",
                "to_state": "NOPE",
                "default_actor": "",
                "guards": [],
            }
        ]
        with pytest.raises(ValueError, match="unknown state 'NOPE'"):
            map_transitions(transitions, states, [], traffic_config)

    def test_unknown_guard_shows_raw_id(self, traffic_config):
        """If guard ID not in guard list → '{RAW_ID}' in label."""
        states = [
            {"id": "A", "display_name": "A", "is_initial": False, "is_terminal": False},
            {"id": "B", "display_name": "B", "is_initial": False, "is_terminal": False},
        ]
        transitions = [
            {
                "name": "Go",
                "from_state": "A",
                "to_state": "B",
                "default_actor": "",
                "guards": ["MYSTERY"],
            }
        ]
        result = map_transitions(transitions, states, [], traffic_config)
        assert "{MYSTERY}" in result[0].label

    def test_self_loop(self, traffic_config):
        """Self-transition: from_state == to_state."""
        states = [
            {"id": "DRAFT", "display_name": "Draft", "is_initial": False, "is_terminal": False}
        ]
        transitions = [
            {
                "name": "Revise",
                "from_state": "DRAFT",
                "to_state": "DRAFT",
                "default_actor": "[Author]",
                "guards": [],
            }
        ]
        result = map_transitions(transitions, states, [], traffic_config)
        assert result[0].from_state == "DRAFT"
        assert result[0].to_state == "DRAFT"
        assert "Revise [Author]" in result[0].label

    def test_empty_transitions(self, sample_states, traffic_config):
        assert map_transitions([], sample_states, [], traffic_config) == []

    def test_no_actor_slot(self, sample_states, sample_transitions, sample_guards):
        """When transition_actor_slot=None, no actor in label."""
        config = StateDiagramConfig(
            transition_actor_slot=None,
        )
        result = map_transitions(sample_transitions, sample_states, sample_guards, config)
        # Label should be name only (no actor)
        assert result[1].label == "Caution"

    def test_actor_resolver_overrides_slot(
        self, sample_states, sample_transitions, sample_guards, traffic_config
    ):
        """actor_resolver takes precedence over the default_actor slot."""
        resolver = lambda t: "[Override]"
        result = map_transitions(
            sample_transitions,
            sample_states,
            sample_guards,
            traffic_config,
            actor_resolver=resolver,
        )
        assert "[Override]" in result[0].label
        assert "[Timer]" not in result[0].label


class TestMapTransitionsWithObjects:
    """Same contract but with object-style access (Pydantic-like)."""

    def test_basic_object_transition(self, traffic_config):
        states = [
            FakeState(id="RED", display_name="Red"),
            FakeState(id="GREEN", display_name="Green"),
        ]
        transitions = [
            FakeTransition(
                name="Go", from_state="RED", to_state="GREEN", default_actor="[Timer]", guards=[]
            ),
        ]
        result = map_transitions(transitions, states, [], traffic_config)
        assert result[0].from_state == "RED"
        assert result[0].to_state == "GREEN"
        assert "Go [Timer]" in result[0].label

    def test_object_with_guards(self, traffic_config):
        states = [
            FakeState(id="A", display_name="Alpha"),
            FakeState(id="B", display_name="Beta"),
        ]
        guards = [FakeGuard(id="G1", display_name="{Check}")]
        transitions = [
            FakeTransition(
                name="Move", from_state="A", to_state="B", default_actor="", guards=["G1"]
            ),
        ]
        result = map_transitions(transitions, states, guards, traffic_config)
        assert "<br>{Check}" in result[0].label


# ── build_state_descriptions tests ───────────────────────────────────


class TestBuildStateDescriptions:
    """Contract: returns enum descriptions from the SCHEMA, not hardcoded.

    Per LinkML §Basic Enums, each permissible_value has a description.
    build_state_descriptions reads these via SchemaReader."""

    def test_returns_all_values(self, reader: SchemaReader):
        descs = build_state_descriptions(reader, "TrafficLightState")
        assert set(descs.keys()) == {"RED", "YELLOW", "GREEN"}

    def test_descriptions_match_schema(self, reader: SchemaReader):
        """Values MUST match what's declared in test_schema.yaml."""
        descs = build_state_descriptions(reader, "TrafficLightState")
        assert descs["RED"] == "Stop — vehicles must not proceed"
        assert descs["GREEN"] == "Go — vehicles may proceed"


# ── build_table_rows tests ───────────────────────────────────────────


class TestBuildTableRowsWithDicts:
    """Contract: builds row dicts for GFM table rendering.

    column_slots maps output keys to slot names.
    lookups resolve foreign keys.
    Lists are comma-joined; empty lists → em dash."""

    def test_basic_dict_mapping(self):
        items = [{"name": "Go", "from_state": "RED"}]
        column_slots = {"label": "name", "source": "from_state"}
        rows = build_table_rows(items, column_slots)
        assert rows == [{"label": "Go", "source": "RED"}]

    def test_lookup_resolution(self):
        """Foreign key resolved through lookups dict."""
        items = [{"from_state": "RED"}]
        column_slots = {"source": "from_state"}
        lookups = {"source": {"RED": "Red Light"}}
        rows = build_table_rows(items, column_slots, lookups=lookups)
        assert rows[0]["source"] == "Red Light"

    def test_list_values_comma_joined(self):
        """Multi-valued slot → comma-separated string."""
        items = [{"tags": ["a", "b", "c"]}]
        column_slots = {"tags": "tags"}
        rows = build_table_rows(items, column_slots)
        assert rows[0]["tags"] == "a, b, c"

    def test_empty_list_em_dash(self):
        """Empty list → '—' (em dash) per our convention."""
        items = [{"tags": []}]
        column_slots = {"tags": "tags"}
        rows = build_table_rows(items, column_slots)
        assert rows[0]["tags"] == "\u2014"

    def test_none_value_empty_string(self):
        """None → empty string (renders as empty cell in GFM)."""
        items = [{"notes": None}]
        column_slots = {"notes": "notes"}
        rows = build_table_rows(items, column_slots)
        assert rows[0]["notes"] == ""

    def test_missing_slot_empty_string(self):
        """Missing key in dict → empty string."""
        items = [{"a": "1"}]
        column_slots = {"b": "b"}
        rows = build_table_rows(items, column_slots)
        assert rows[0]["b"] == ""

    def test_actor_resolver(self):
        """actor_resolver overrides the value for actor_key."""
        items = [{"name": "Go", "actor": "default"}]
        column_slots = {"label": "name", "actor": "actor"}
        resolver = lambda item: "[Resolved]"
        rows = build_table_rows(
            items,
            column_slots,
            actor_resolver=resolver,
            actor_key="actor",
        )
        assert rows[0]["actor"] == "[Resolved]"
        assert rows[0]["label"] == "Go"  # other columns unaffected

    def test_list_with_lookup(self):
        """Multi-valued foreign key → comma-joined resolved values."""
        items = [{"guard_ids": ["G1", "G2"]}]
        column_slots = {"guards": "guard_ids"}
        lookups = {"guards": {"G1": "Guard One", "G2": "Guard Two"}}
        rows = build_table_rows(items, column_slots, lookups=lookups)
        assert rows[0]["guards"] == "Guard One, Guard Two"

    def test_empty_items(self):
        """No items → no rows."""
        assert build_table_rows([], {"a": "a"}) == []


class TestBuildTableRowsWithObjects:
    """Same contract but with object-style access."""

    def test_basic_object_mapping(self):
        items = [FakeState(id="RED", display_name="Red")]
        column_slots = {"state": "id", "name": "display_name"}
        rows = build_table_rows(items, column_slots)
        assert rows[0]["state"] == "RED"
        assert rows[0]["name"] == "Red"

    def test_object_with_lookup(self):
        items = [FakeTransition(name="Go", from_state="RED", to_state="GREEN")]
        column_slots = {"source": "from_state"}
        lookups = {"source": {"RED": "Red Light"}}
        rows = build_table_rows(items, column_slots, lookups=lookups)
        assert rows[0]["source"] == "Red Light"

    def test_object_with_list_guards(self):
        items = [FakeTransition(name="Go", from_state="A", to_state="B", guards=["G1", "G2"])]
        column_slots = {"guards": "guards"}
        rows = build_table_rows(items, column_slots)
        assert rows[0]["guards"] == "G1, G2"

    def test_object_none_guards(self):
        """guards=None → empty string."""
        items = [FakeTransition(name="Go", from_state="A", to_state="B", guards=None)]
        column_slots = {"guards": "guards"}
        rows = build_table_rows(items, column_slots)
        assert rows[0]["guards"] == ""
