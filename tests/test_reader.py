"""SchemaReader tests — validating against the LinkML schema spec.

The test fixture schema (test_schema.yaml) IS the specification.
Tests assert that SchemaReader returns EXACTLY what the YAML declares.
If someone changes the schema, the test expectations must change too —
they are NOT derived from the implementation.

Spec references:
  SchemaView:   https://linkml.io/linkml/developers/schemaview.html
  §Basic Enums: https://linkml.io/linkml/schemas/enums.html#basic-enums
  §Annotations: https://linkml.io/linkml/schemas/annotations.html
  §Classes:     https://linkml.io/linkml/schemas/models.html#classes
  §Slots:       https://linkml.io/linkml/schemas/models.html#slots
"""

from __future__ import annotations

import pytest

from linkml_mermaid import SchemaReader


class TestEnumValues:
    """§Basic Enums: 'permissible_values' dict preserves insertion order.

    The test schema defines TrafficLightState with values:
    RED, YELLOW, GREEN (in that order)."""

    def test_values_in_insertion_order(self, reader: SchemaReader):
        """Values must come back in the order declared in the schema."""
        values = reader.enum_values("TrafficLightState")
        assert values == ["RED", "YELLOW", "GREEN"]

    def test_guard_values_in_order(self, reader: SchemaReader):
        values = reader.enum_values("TrafficGuard")
        assert values == ["TIMER_EXPIRED", "SENSOR_TRIGGERED"]


class TestEnumDescriptions:
    """§Basic Enums: 'make your enums into a richer controlled vocabulary,
    with definitions built in.'  Each permissible_value may carry a
    description string.

    These expected values are copied DIRECTLY from test_schema.yaml."""

    def test_all_descriptions_present(self, reader: SchemaReader):
        descs = reader.enum_descriptions("TrafficLightState")
        assert len(descs) == 3
        assert all(v != "" for v in descs.values())

    def test_red_description_exact(self, reader: SchemaReader):
        """Exact text from test_schema.yaml: 'Stop — vehicles must not proceed'"""
        descs = reader.enum_descriptions("TrafficLightState")
        assert descs["RED"] == "Stop — vehicles must not proceed"

    def test_yellow_description_exact(self, reader: SchemaReader):
        descs = reader.enum_descriptions("TrafficLightState")
        assert descs["YELLOW"] == "Caution — prepare to stop or clear intersection"

    def test_green_description_exact(self, reader: SchemaReader):
        descs = reader.enum_descriptions("TrafficLightState")
        assert descs["GREEN"] == "Go — vehicles may proceed"

    def test_guard_descriptions(self, reader: SchemaReader):
        descs = reader.enum_descriptions("TrafficGuard")
        assert descs["TIMER_EXPIRED"] == "Minimum phase duration has elapsed"
        assert descs["SENSOR_TRIGGERED"] == "Vehicle or pedestrian sensor activated"


class TestEnumDescription:
    """The enum-level description (not per-value)."""

    def test_traffic_light_enum_description(self, reader: SchemaReader):
        """test_schema.yaml: 'Traffic light phases'"""
        assert reader.enum_description("TrafficLightState") == "Traffic light phases"

    def test_guard_enum_description(self, reader: SchemaReader):
        assert reader.enum_description("TrafficGuard") == (
            "Guard conditions for traffic light transitions"
        )


class TestClassDescription:
    """§Classes: classes carry a description field.

    test_schema.yaml: TrafficWorkflow.description = 'A traffic light state machine'"""

    def test_workflow_class_description(self, reader: SchemaReader):
        assert reader.class_description("TrafficWorkflow") == "A traffic light state machine"

    def test_state_class_description(self, reader: SchemaReader):
        assert reader.class_description("TrafficState") == "A traffic light state"

    def test_nonexistent_class_returns_empty(self, reader: SchemaReader):
        """Non-existent class should return '', not raise."""
        assert reader.class_description("NonExistentClass") == ""


class TestSlotHelpers:
    """§Slots: slots carry description and range metadata."""

    def test_slot_description(self, reader: SchemaReader):
        """test_schema.yaml: TrafficState.display_name.description =
        'Human-readable name shown in diagrams'"""
        desc = reader.slot_description("TrafficState", "display_name")
        assert desc == "Human-readable name shown in diagrams"

    def test_slot_range_boolean(self, reader: SchemaReader):
        """test_schema.yaml: TrafficState.is_terminal.range = boolean"""
        assert reader.slot_range("TrafficState", "is_terminal") == "boolean"

    def test_slot_range_enum(self, reader: SchemaReader):
        """test_schema.yaml: TrafficState.id.range = TrafficLightState"""
        assert reader.slot_range("TrafficState", "id") == "TrafficLightState"

    def test_nonexistent_slot_description(self, reader: SchemaReader):
        assert reader.slot_description("TrafficState", "nonexistent") is None

    def test_nonexistent_slot_range(self, reader: SchemaReader):
        assert reader.slot_range("TrafficState", "nonexistent") is None


class TestAnnotationHelpers:
    """§Annotations: 'arbitrary key-value pairs on any schema element.'

    test_schema.yaml: TrafficWorkflow.annotations.mermaid_diagram = 'stateDiagram-v2'"""

    def test_class_annotation_exists(self, reader: SchemaReader):
        assert reader.class_annotation("TrafficWorkflow", "mermaid_diagram") == "stateDiagram-v2"

    def test_class_annotation_nonexistent_key(self, reader: SchemaReader):
        assert reader.class_annotation("TrafficWorkflow", "nonexistent") is None

    def test_class_annotation_nonexistent_class(self, reader: SchemaReader):
        assert reader.class_annotation("FakeClass", "mermaid_diagram") is None

    def test_enum_annotation_nonexistent(self, reader: SchemaReader):
        """Enums in test schema have no annotations."""
        assert reader.enum_annotation("TrafficLightState", "any_key") is None


class TestSchemaViewExposed:
    """The underlying SchemaView should be accessible for advanced queries."""

    def test_schema_view_not_none(self, reader: SchemaReader):
        assert reader.schema_view is not None

    def test_can_get_all_classes(self, reader: SchemaReader):
        """SchemaView should expose all classes from the test schema."""
        class_names = list(reader.schema_view.all_classes().keys())
        assert "TrafficWorkflow" in class_names
        assert "TrafficState" in class_names
        assert "TrafficTransition" in class_names


class TestSlotAnnotation:
    """slot_annotation() reads annotations from individual attributes."""

    def test_state_id_has_mermaid_role(self, reader: SchemaReader):
        """test_schema.yaml: TrafficState.id has mermaid_role: state_id"""
        assert reader.slot_annotation("TrafficState", "id", "mermaid_role") == "state_id"

    def test_display_name_has_label_role(self, reader: SchemaReader):
        assert reader.slot_annotation("TrafficState", "display_name", "mermaid_role") == "label"

    def test_unannotated_slot_returns_none(self, reader: SchemaReader):
        """color has no mermaid_role annotation."""
        assert reader.slot_annotation("TrafficState", "color", "mermaid_role") is None

    def test_nonexistent_slot_returns_none(self, reader: SchemaReader):
        assert reader.slot_annotation("TrafficState", "fake_slot", "mermaid_role") is None


class TestDiscoverStateDiagramConfig:
    """Auto-discovery: scan mermaid_role annotations to build config.

    The test schema has annotations on all relevant slots.  The
    discovered config must match the hand-written traffic_config
    fixture exactly — this validates that auto-discovery produces
    the same result as manual wiring."""

    def test_discovers_state_slots(self, reader: SchemaReader):
        config = reader.discover_state_diagram_config("TrafficWorkflow")
        assert config.state_id_slot == "id"
        assert config.state_label_slot == "display_name"
        assert config.state_initial_slot == "is_initial"
        assert config.state_terminal_slot == "is_terminal"

    def test_discovers_state_enum_name(self, reader: SchemaReader):
        """Enum name derived from range of the state_id slot."""
        config = reader.discover_state_diagram_config("TrafficWorkflow")
        assert config.state_enum_name == "TrafficLightState"

    def test_discovers_transition_slots(self, reader: SchemaReader):
        config = reader.discover_state_diagram_config("TrafficWorkflow")
        assert config.transition_from_slot == "from_state"
        assert config.transition_to_slot == "to_state"
        assert config.transition_label_slot == "name"
        assert config.transition_actor_slot == "default_actor"
        assert config.transition_guards_slot == "guards"

    def test_discovers_guard_slots(self, reader: SchemaReader):
        config = reader.discover_state_diagram_config("TrafficWorkflow")
        assert config.guard_id_slot == "id"
        assert config.guard_label_slot == "display_name"

    def test_matches_hand_written_config(self, reader: SchemaReader, traffic_config):
        """The discovered config must equal the manually written one."""
        discovered = reader.discover_state_diagram_config("TrafficWorkflow")
        assert discovered == traffic_config

    def test_raises_on_missing_annotations(self, reader: SchemaReader):
        """A class without mermaid_role annotations should raise ValueError."""
        # TrafficState has state-level annotations but is NOT a workflow container
        with pytest.raises(ValueError, match="must have slots annotated"):
            reader.discover_state_diagram_config("TrafficState")


class TestDiscoverTableColumns:
    """Auto-discovery: scan table_column annotations to build ColumnDefs.

    The test schema has table_column annotations on TrafficState,
    TrafficTransition, and TrafficGuardDef slots.  The discovered
    columns must match the annotation values exactly.

    GFM §4.10: https://github.github.com/gfm/#tables-extension-
    """

    def test_state_columns(self, reader: SchemaReader):
        """State columns: State(bold), Description, Color."""
        cols = reader.discover_table_columns("TrafficState")
        assert len(cols) == 3
        assert cols[0].header == "State"
        assert cols[0].key == "display_name"
        assert cols[0].format == "bold"
        assert cols[1].header == "Description"
        assert cols[1].key == "id"
        assert cols[1].format is None or cols[1].format == "plain"
        assert cols[2].header == "Color"
        assert cols[2].key == "color"

    def test_transition_columns(self, reader: SchemaReader):
        """Transition columns: Transition, From, To, Actor, Guard / Condition."""
        cols = reader.discover_table_columns("TrafficTransition")
        assert len(cols) == 5
        headers = [c.header for c in cols]
        assert headers == ["Transition", "From", "To", "Actor", "Guard / Condition"]
        keys = [c.key for c in cols]
        assert keys == ["name", "from_state", "to_state", "default_actor", "guards"]

    def test_guard_columns(self, reader: SchemaReader):
        """Guard columns: Guard(code), Description."""
        cols = reader.discover_table_columns("TrafficGuardDef")
        assert len(cols) == 2
        assert cols[0].header == "Guard"
        assert cols[0].key == "display_name"
        assert cols[0].format == "code"
        assert cols[1].header == "Description"
        assert cols[1].key == "description"

    def test_column_order_follows_declaration(self, reader: SchemaReader):
        """Columns appear in slot declaration order (YAML ordering)."""
        cols = reader.discover_table_columns("TrafficState")
        keys = [c.key for c in cols]
        # display_name declared before id before color in test_schema.yaml
        assert keys == ["display_name", "id", "color"]

    def test_raises_on_missing_class(self, reader: SchemaReader):
        with pytest.raises(ValueError, match="not found"):
            reader.discover_table_columns("NonExistent")

    def test_raises_on_no_annotations(self, reader: SchemaReader):
        """TrafficWorkflow has mermaid_role but no table_column annotations."""
        with pytest.raises(ValueError, match="no slots with"):
            reader.discover_table_columns("TrafficWorkflow")
