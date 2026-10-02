"""SchemaReader — read-only façade over a LinkML schema via SchemaView.

Provides convenient access to descriptions, annotations, and enum
metadata that downstream generators need.  All ``linkml_runtime``
interaction is encapsulated here; renderers never import it directly.

LinkML SchemaView reference
    https://linkml.io/linkml/developers/schemaview.html
    "The SchemaView class in the linkml-runtime provides a method for
     dynamically introspecting and manipulating schemas."

LinkML enum descriptions (§Basic Enums)
    https://linkml.io/linkml/schemas/enums.html#basic-enums
    "You can also make your enums into a richer controlled vocabulary,
     with definitions built in."  Each ``permissible_value`` may carry
    a ``description`` string.

LinkML annotations (§Adding your own annotations)
    https://linkml.io/linkml/schemas/annotations.html#adding-your-own-annotations
    "The LinkML metamodel has a generic annotations slot that can be
     used to assign arbitrary tags and values to any schema element."
    Used here to read generation-control metadata (e.g. which diagram
    type a class should produce).

LinkML class/slot model (§Classes, §Slots)
    https://linkml.io/linkml/schemas/models.html#classes
    https://linkml.io/linkml/schemas/models.html#slots
    Classes define data templates; slots carry ``description`` and
    ``range`` metadata that this reader surfaces.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from linkml_runtime.utils.schemaview import SchemaView

if TYPE_CHECKING:
    from .mapping import StateDiagramConfig
    from .types import ColumnDef


class SchemaReader:
    """Read-only façade over a LinkML schema.

    Wraps :class:`linkml_runtime.utils.schemaview.SchemaView` to expose
    only the metadata queries that diagram/table generators need.

    Parameters:
        schema_path: Path to a ``.yaml`` LinkML schema file.

    Example::

        reader = SchemaReader("specs/linkml/requirement_process.yaml")
        descs = reader.enum_descriptions("ItemState")
        # {'NEW': 'Initial state when item is created', ...}
    """

    def __init__(self, schema_path: str | Path) -> None:
        self._sv = SchemaView(str(schema_path))

    @property
    def schema_view(self) -> SchemaView:
        """Expose the underlying SchemaView for advanced queries."""
        return self._sv

    # ── Enum helpers ─────────────────────────────────────────────────
    #
    # LinkML enums: https://linkml.io/linkml/schemas/enums.html
    # Each permissible_value has optional: description, meaning,
    # title, annotations.

    def enum_values(self, enum_name: str) -> list[str]:
        """Return ordered list of permissible value names.

        Per LinkML §Basic Enums, the ``permissible_values`` dict
        preserves insertion order.
        """
        enum_def = self._sv.get_enum(enum_name)
        return list(enum_def.permissible_values.keys())

    def enum_descriptions(self, enum_name: str) -> dict[str, str]:
        """Return ``{value_name: description}`` for every value in an enum.

        Reads the ``description`` field from each permissible_value.
        Values without a description map to ``""``.

        LinkML ref: https://linkml.io/linkml/schemas/enums.html#basic-enums
        """
        enum_def = self._sv.get_enum(enum_name)
        return {name: (pv.description or "") for name, pv in enum_def.permissible_values.items()}

    def enum_description(self, enum_name: str) -> str:
        """Return the description of the enum itself."""
        return self._sv.get_enum(enum_name).description or ""

    # ── Class / slot helpers ─────────────────────────────────────────
    #
    # LinkML classes: https://linkml.io/linkml/schemas/models.html#classes
    # LinkML slots:   https://linkml.io/linkml/schemas/models.html#slots
    #
    # Slots defined via ``attributes:`` are class-local (§The
    # Attributes slot).  Both top-level slots and attributes carry
    # ``description`` and ``range``.

    def class_description(self, class_name: str) -> str:
        """Return the description of a class.

        LinkML ref: https://linkml.io/linkml/schemas/models.html#classes
        """
        cls = self._sv.get_class(class_name)
        return (cls.description if cls else "") or ""

    def slot_description(self, class_name: str, slot_name: str) -> str | None:
        """Return a slot's description within a class, or *None*.

        LinkML ref: https://linkml.io/linkml/schemas/models.html#the-attributes-slot
        """
        cls = self._sv.get_class(class_name)
        if cls and slot_name in cls.attributes:
            return cast(str | None, cls.attributes[slot_name].description)
        return None

    def slot_range(self, class_name: str, slot_name: str) -> str | None:
        """Return a slot's range within a class, or *None*.

        The ``range`` constrains what values the slot can take.
        LinkML ref: https://w3id.org/linkml/range
        """
        cls = self._sv.get_class(class_name)
        if cls and slot_name in cls.attributes:
            return cast(str | None, cls.attributes[slot_name].range)
        return None

    # ── Annotation helpers ───────────────────────────────────────────
    #
    # LinkML annotations: https://linkml.io/linkml/schemas/annotations.html
    # Annotations are arbitrary key-value pairs on any schema element.
    # From §Adding your own annotations:
    #   "annotations:
    #      review: A very useful class that is well defined"
    #
    # Used here to read generation-control metadata such as
    #   annotations:
    #     mermaid_diagram: stateDiagram-v2
    #     table_type: state_reference

    def class_annotation(self, class_name: str, key: str) -> str | None:
        """Return a class-level annotation value, or *None*.

        LinkML ref: https://linkml.io/linkml/schemas/annotations.html
        """
        cls = self._sv.get_class(class_name)
        if cls and cls.annotations:
            ann = cls.annotations.get(key)
            return ann.value if ann else None
        return None

    def enum_annotation(self, enum_name: str, key: str) -> str | None:
        """Return an enum-level annotation value, or *None*.

        LinkML ref: https://linkml.io/linkml/schemas/annotations.html
        """
        enum_def = self._sv.get_enum(enum_name)
        if enum_def and enum_def.annotations:
            ann = enum_def.annotations.get(key)
            return ann.value if ann else None
        return None

    def slot_annotation(self, class_name: str, slot_name: str, key: str) -> str | None:
        """Return a slot-level annotation value, or *None*.

        LinkML ref: https://linkml.io/linkml/schemas/annotations.html
        "The LinkML metamodel has a generic annotations slot that can be
         used to assign arbitrary tags and values to any schema element."
        """
        cls = self._sv.get_class(class_name)
        if cls and slot_name in cls.attributes:
            slot_def = cls.attributes[slot_name]
            if slot_def.annotations:
                ann = slot_def.annotations.get(key)
                return ann.value if ann else None
        return None

    # ── Auto-discovery ───────────────────────────────────────────────
    #
    # Scans mermaid_role annotations on a schema to auto-build a
    # StateDiagramConfig.  Eliminates manual slot-name wiring.
    #
    # See linkml_mermaid.vocab for the annotation vocabulary.

    def _find_slots_by_annotation(self, class_name: str, key: str) -> dict[str, str]:
        """Return ``{annotation_value: slot_name}`` for all slots with
        the given annotation key on a class.

        Example: on State class with ``id: annotations: {mermaid_role: state_id}``
        returns ``{"state_id": "id"}``.
        """
        cls = self._sv.get_class(class_name)
        if not cls:
            return {}
        result: dict[str, str] = {}
        for slot_name, slot_def in cls.attributes.items():
            if slot_def.annotations:
                ann = slot_def.annotations.get(key)
                if ann:
                    result[ann.value] = slot_name
        return result

    def discover_state_diagram_config(self, workflow_class: str) -> StateDiagramConfig:
        """Auto-build a :class:`StateDiagramConfig` by scanning annotations.

        Reads ``mermaid_role`` annotations on the workflow class and its
        child classes (state, transition, guard) to discover which slots
        map to which Mermaid concepts.

        The workflow class must have slots annotated with
        ``mermaid_role: states``, ``mermaid_role: transitions``, and
        optionally ``mermaid_role: guard_list``.  The range classes of
        those slots are then scanned for state/transition/guard role
        annotations.

        See ``linkml_mermaid.vocab`` for the full annotation vocabulary.

        Parameters:
            workflow_class: Name of the LinkML class that contains the
                state machine definition (e.g. ``"Workflow"``).

        Returns:
            A fully populated :class:`StateDiagramConfig`.

        Raises:
            ValueError: If required annotations are missing.
        """
        from .mapping import StateDiagramConfig
        from .vocab import (
            MERMAID_ROLE,
            ROLE_ACTOR,
            ROLE_FROM_STATE,
            ROLE_GUARD_ID,
            ROLE_GUARD_LABEL,
            ROLE_GUARD_LIST,
            ROLE_GUARDS,
            ROLE_INITIAL,
            ROLE_LABEL,
            ROLE_STATE_ID,
            ROLE_STATES,
            ROLE_TERMINAL,
            ROLE_TO_STATE,
            ROLE_TRANSITION_LABEL,
            ROLE_TRANSITIONS,
        )

        # 1. Scan workflow container slots to find child class names
        wf_roles = self._find_slots_by_annotation(workflow_class, MERMAID_ROLE)

        states_slot = wf_roles.get(ROLE_STATES)
        transitions_slot = wf_roles.get(ROLE_TRANSITIONS)
        guards_slot = wf_roles.get(ROLE_GUARD_LIST)

        if not states_slot or not transitions_slot:
            raise ValueError(
                f"Workflow class '{workflow_class}' must have slots annotated "
                f"with mermaid_role: {ROLE_STATES} and mermaid_role: {ROLE_TRANSITIONS}"
            )

        state_class = self.slot_range(workflow_class, states_slot)
        transition_class = self.slot_range(workflow_class, transitions_slot)
        guard_class = self.slot_range(workflow_class, guards_slot) if guards_slot else None

        if state_class is None:
            raise ValueError(f"No range found for states slot '{states_slot}' on {workflow_class}")
        if transition_class is None:
            raise ValueError(
                f"No range found for transitions slot '{transitions_slot}' on {workflow_class}"
            )

        # 2. Scan state class slots
        state_roles = self._find_slots_by_annotation(state_class, MERMAID_ROLE)

        state_id_slot = state_roles.get(ROLE_STATE_ID, "id")
        state_label_slot = state_roles.get(ROLE_LABEL, "display_name")
        state_initial_slot = state_roles.get(ROLE_INITIAL, "is_initial")
        state_terminal_slot = state_roles.get(ROLE_TERMINAL, "is_terminal")

        # Derive enum name from the range of the state_id slot
        state_enum_name = self.slot_range(state_class, state_id_slot)

        # 3. Scan transition class slots
        trans_roles = self._find_slots_by_annotation(transition_class, MERMAID_ROLE)

        transition_from_slot = trans_roles.get(ROLE_FROM_STATE, "from_state")
        transition_to_slot = trans_roles.get(ROLE_TO_STATE, "to_state")
        transition_label_slot = trans_roles.get(ROLE_TRANSITION_LABEL, "name")
        transition_actor_slot = trans_roles.get(ROLE_ACTOR)
        transition_guards_slot = trans_roles.get(ROLE_GUARDS)

        # 4. Scan guard class slots (if present)
        guard_id_slot = "id"
        guard_label_slot = "display_name"
        if guard_class:
            guard_roles = self._find_slots_by_annotation(guard_class, MERMAID_ROLE)
            guard_id_slot = guard_roles.get(ROLE_GUARD_ID, "id")
            guard_label_slot = guard_roles.get(ROLE_GUARD_LABEL, "display_name")

        return StateDiagramConfig(
            state_id_slot=state_id_slot,
            state_label_slot=state_label_slot,
            state_initial_slot=state_initial_slot,
            state_terminal_slot=state_terminal_slot,
            state_enum_name=state_enum_name,
            transition_from_slot=transition_from_slot,
            transition_to_slot=transition_to_slot,
            transition_label_slot=transition_label_slot,
            transition_actor_slot=transition_actor_slot,
            transition_guards_slot=transition_guards_slot,
            guard_id_slot=guard_id_slot,
            guard_label_slot=guard_label_slot,
        )

    def discover_table_columns(self, class_name: str) -> list[ColumnDef]:
        """Auto-build a list of :class:`ColumnDef` from ``table_column`` annotations.

        Scans slots on the named class for the ``table_column`` annotation.
        The annotation value format is ``"Header"`` or ``"Header|format"``
        where format is one of: plain, bold, code, italic.

        Columns are returned in slot declaration order.

        Parameters:
            class_name: Name of the LinkML class to scan.

        Returns:
            A list of :class:`ColumnDef` objects.  The ``key`` of each
            column is the slot name.

        Raises:
            ValueError: If the class does not exist, has no
                ``table_column`` annotations, or an annotation names a
                format that is not in the vocabulary.
        """
        from .types import CELL_FORMATS, ColumnDef
        from .vocab import TABLE_COLUMN

        cls = self._sv.get_class(class_name)
        if not cls:
            raise ValueError(f"Class '{class_name}' not found in schema")

        columns: list[ColumnDef] = []
        for slot_name, slot_def in cls.attributes.items():
            if not slot_def.annotations:
                continue
            ann = slot_def.annotations.get(TABLE_COLUMN)
            if not ann:
                continue
            value = ann.value
            if "|" in value:
                header, fmt = value.rsplit("|", 1)
                if fmt not in CELL_FORMATS:
                    raise ValueError(
                        f"Slot '{class_name}.{slot_name}' has "
                        f"{TABLE_COLUMN}: '{value}', but '{fmt}' is not a "
                        f"known format; expected one of {sorted(CELL_FORMATS)}"
                    )
                columns.append(ColumnDef(header=header, key=slot_name, format=fmt))
            else:
                columns.append(ColumnDef(header=value, key=slot_name))

        if not columns:
            raise ValueError(
                f"Class '{class_name}' has no slots with '{TABLE_COLUMN}' annotations"
            )

        return columns
