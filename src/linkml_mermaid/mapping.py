"""LinkML-to-Mermaid mapping — config-driven transformation layer.

This module bridges the **LinkML domain** (schemas, typed instances,
enum descriptions) and the **pure Mermaid renderers** (state_diagram,
markdown_table).  It reads schema metadata via :class:`SchemaReader` and
transforms typed data objects into renderer-ready primitives
(:class:`MermaidState`, :class:`MermaidTransition`, :class:`ColumnDef`,
row dicts).

Design principle
    The mapping is **configuration-driven**, not hardcoded.  A
    :class:`StateDiagramConfig` tells this module which slots on your
    LinkML classes correspond to Mermaid concepts (state id, label,
    from/to, terminal flag, …).  This makes the package     reusable for
    *any* LinkML schema that models state machines.

Specification references
========================

LinkML SchemaView
    https://linkml.io/linkml/developers/schemaview.html
    Used via :class:`~linkml_mermaid.reader.SchemaReader` to pull
    ``description`` fields from enum permissible_values.

LinkML enum descriptions (§Basic Enums)
    https://linkml.io/linkml/schemas/enums.html#basic-enums
    "You can also make your enums into a richer controlled vocabulary,
     with definitions built in."
    The :func:`build_state_descriptions` function reads these instead
    of requiring hardcoded description dicts.

Mermaid stateDiagram-v2 §States
    https://mermaid.js.org/syntax/stateDiagram.html#states
    Target output format for :func:`map_states`.

Mermaid stateDiagram-v2 §Transitions
    https://mermaid.js.org/syntax/stateDiagram.html#transitions
    Target output format for :func:`map_transitions`.

GFM §4.10 Tables
    https://github.github.com/gfm/#tables-extension-
    Target output format for :func:`build_table_rows`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .reader import SchemaReader
from .state_diagram import to_state_id
from .types import ColumnDef, MermaidState, MermaidTransition

# ── Helpers ──────────────────────────────────────────────────────────


def identity_mapping(columns: list[ColumnDef]) -> dict[str, str]:
    """Build a slot_mapping where each column key maps to itself."""
    return {col.key: col.key for col in columns}


# ── Configuration ────────────────────────────────────────────────────


@dataclass(frozen=True)
class StateDiagramConfig:
    """Declares how LinkML class slots map to Mermaid state diagram concepts.

    Each field names a slot (attribute) on the LinkML class that provides
    the corresponding Mermaid concept.  This is the **only** place where
    domain knowledge about slot names is encoded — the renderers and
    mapping functions are fully generic.

    This config can be built manually or **auto-discovered** from schema
    annotations via :meth:`SchemaReader.discover_state_diagram_config`.
    See ``linkml_mermaid.vocab`` for the annotation vocabulary.

    Attributes:
        state_id_slot: Slot on the State class that holds the enum ID
            (e.g. ``"id"``).  Mapped to ``MermaidState.id`` after
            PascalCase conversion per §Spaces in state names.
        state_label_slot: Slot for the human-readable display name
            (e.g. ``"display_name"``).  Becomes ``MermaidState.label``.
        state_initial_slot: Boolean slot indicating the start state
            (e.g. ``"is_initial"``).  Controls §Start and End ``[*]``
            rendering.  Symmetrical with ``state_terminal_slot``.
        state_terminal_slot: Boolean slot indicating terminal states
            (e.g. ``"is_terminal"``).  Controls §Start and End ``[*]``
            rendering.
        state_enum_name: Name of the LinkML enum whose permissible_value
            descriptions provide state documentation.  Used by
            :func:`build_state_descriptions` to eliminate hardcoded
            description dicts.
        transition_from_slot: Slot for the source state ID.
        transition_to_slot: Slot for the target state ID.
        transition_label_slot: Slot for the transition display name.
        transition_actor_slot: Slot for the default actor label
            (optional — set to *None* if not applicable).
        transition_guards_slot: Slot for guard ID list (optional).
        guard_id_slot: Slot on the Guard class for the guard ID.
        guard_label_slot: Slot for the guard display name.
        guard_separator: String inserted between the transition name and
            each guard label when assembling a transition label.
            Defaults to ``"<br>"``: the Mermaid stateDiagram-v2 grammar
            documents no line-continuation escape for transition labels,
            so a literal ``\\n`` is rendered verbatim rather than as a
            line break.
    """

    state_id_slot: str = "id"
    state_label_slot: str = "display_name"
    state_initial_slot: str = "is_initial"
    state_terminal_slot: str = "is_terminal"
    state_enum_name: str | None = None
    transition_from_slot: str = "from_state"
    transition_to_slot: str = "to_state"
    transition_label_slot: str = "name"
    transition_actor_slot: str | None = "default_actor"
    transition_guards_slot: str | None = "guards"
    guard_id_slot: str = "id"
    guard_label_slot: str = "display_name"
    guard_separator: str = "<br>"


# ── Attribute access helpers ─────────────────────────────────────────
# Support both Pydantic models (attribute access) and plain dicts.


def _get(obj: Any, slot: str) -> Any:
    """Read a slot value from a typed model or a dict."""
    if isinstance(obj, dict):
        return obj.get(slot)
    return getattr(obj, slot, None)


# ── State mapping ────────────────────────────────────────────────────


def _state_mermaid_id(state: Any, config: StateDiagramConfig) -> str:
    """Derive the Mermaid identifier for one LinkML state instance.

    The identifier comes from ``state_id_slot`` — the schema's own
    identity for the state — not from the display label.  Deriving it
    from the label would make two states that merely *display* the same
    text collapse into one node.
    """
    raw_id = _get(state, config.state_id_slot)
    if raw_id is None or str(raw_id) == "":
        raise ValueError(
            f"State instance has no value for id slot "
            f"'{config.state_id_slot}'; cannot derive a Mermaid state id"
        )
    return to_state_id(str(raw_id))


def map_states(
    states: Sequence[Any],
    config: StateDiagramConfig,
) -> list[MermaidState]:
    """Transform LinkML state instances into :class:`MermaidState` objects.

    Per §States, each state gets a PascalCase ``id`` derived from
    ``state_id_slot`` and optionally a human-readable ``label`` from
    ``state_label_slot``.  Per §Start and End, states whose
    ``state_initial_slot`` is truthy get ``is_initial=True``, and states
    whose ``state_terminal_slot`` is truthy get ``is_terminal=True``.

    Raises:
        ValueError: If a state carries no value for ``state_id_slot``.
    """
    result: list[MermaidState] = []
    for s in states:
        label = _get(s, config.state_label_slot) or _get(s, config.state_id_slot)
        result.append(
            MermaidState(
                id=_state_mermaid_id(s, config),
                label=label,
                is_initial=bool(_get(s, config.state_initial_slot)),
                is_terminal=bool(_get(s, config.state_terminal_slot)),
            )
        )
    return result


# ── Transition mapping ───────────────────────────────────────────────


def map_transitions(
    transitions: Sequence[Any],
    states: Sequence[Any],
    guards: Sequence[Any] | None,
    config: StateDiagramConfig,
    actor_resolver: Callable[[Any], str] | None = None,
) -> list[MermaidTransition]:
    """Transform LinkML transitions into :class:`MermaidTransition` objects.

    Per §Transitions, each edge is ``From --> To : label``.  The label
    is assembled from:
    1. Transition name (from ``transition_label_slot``)
    2. Actor label (from ``transition_actor_slot`` or *actor_resolver*)
    3. Guard display names (from ``transition_guards_slot`` → guard lookup)

    Guard labels are joined with ``config.guard_separator`` (``<br>`` by
    default), because the stateDiagram-v2 grammar documents no escape
    that produces a line break inside a transition label.

    Parameters:
        transitions: Sequence of LinkML transition instances.
        states: Sequence of state instances (for ID → Mermaid id lookup).
        guards: Sequence of guard instances (for guard ID → label lookup).
        config: Slot mapping configuration.
        actor_resolver: Optional callable ``(transition) -> str`` that
            overrides the default actor slot, for schemas where the
            responsible actor depends on more than one slot.

    Raises:
        ValueError: If a transition references a state id that is absent
            from *states*.  Emitting a placeholder would produce a
            diagram that renders but is silently wrong.
    """
    # Build lookup: state enum ID → MermaidState.id (PascalCase)
    state_id_map: dict[str, str] = {}
    for s in states:
        state_id_map[str(_get(s, config.state_id_slot))] = _state_mermaid_id(s, config)

    # Build lookup: guard ID → display name
    guard_label_map: dict[str, str] = {}
    if guards:
        for g in guards:
            gid = _get(g, config.guard_id_slot)
            glabel = _get(g, config.guard_label_slot)
            if gid and glabel:
                guard_label_map[gid] = glabel

    def _resolve(raw: Any, slot: str) -> str:
        key = str(raw)
        if key not in state_id_map:
            raise ValueError(
                f"Transition slot '{slot}' references unknown state "
                f"{raw!r}; known states: {sorted(state_id_map)}"
            )
        return state_id_map[key]

    result: list[MermaidTransition] = []
    for t in transitions:
        from_id = _resolve(_get(t, config.transition_from_slot), config.transition_from_slot)
        to_id = _resolve(_get(t, config.transition_to_slot), config.transition_to_slot)

        # Build label: name + actor + guards
        name = _get(t, config.transition_label_slot) or ""

        if actor_resolver:
            actor = actor_resolver(t)
        elif config.transition_actor_slot:
            actor = _get(t, config.transition_actor_slot) or ""
        else:
            actor = ""

        label = f"{name} {actor}".strip() if actor else name

        if config.transition_guards_slot:
            guard_ids = _get(t, config.transition_guards_slot) or []
            guard_labels = [guard_label_map.get(gid, f"{{{gid}}}") for gid in guard_ids]
            if guard_labels:
                sep = config.guard_separator
                label += sep + sep.join(guard_labels)

        result.append(MermaidTransition(from_id, to_id, label or None))

    return result


# ── Description helpers ──────────────────────────────────────────────


def build_state_descriptions(
    reader: SchemaReader,
    enum_name: str,
) -> dict[str, str]:
    """Read state descriptions from the LinkML enum, not from hardcoded dicts.

    Per LinkML §Basic Enums, each permissible_value can carry a
    ``description`` field.  This function reads those descriptions via
    :meth:`SchemaReader.enum_descriptions`, replacing the need for
    hand-maintained ``STATE_DESCRIPTIONS`` dicts.

    Returns:
        ``{enum_value_name: description}`` — e.g.
        ``{'NEW': 'Initial state when item is created', ...}``
    """
    return reader.enum_descriptions(enum_name)


# ── Table row builders ───────────────────────────────────────────────


def build_table_rows(
    items: Sequence[Any],
    column_slots: dict[str, str],
    *,
    lookups: dict[str, dict[str, str]] | None = None,
    actor_resolver: Callable[[Any], str] | None = None,
    actor_key: str | None = None,
    empty_placeholder: str = "\u2014",
) -> list[dict[str, str]]:
    """Build row dicts for a GFM table from typed instances.

    Generic: the caller declares which column keys map to which slots.
    This replaces the need for separate ``build_states_table_rows``,
    ``build_transitions_table_rows``, ``build_guards_table_rows``
    functions.

    Parameters:
        items: Sequence of LinkML instances (Pydantic models or dicts).
        column_slots: ``{column_key: slot_name}`` — maps output dict
            keys to slot names on each item.  Values are read via
            ``_get(item, slot_name)``.
        lookups: Optional ``{column_key: {raw_value: display_value}}``
            for resolving foreign keys (e.g. state ID → display name).
        actor_resolver: Optional callable ``(item) -> str`` for
            resolving a column value dynamically.
        actor_key: Column key that uses actor_resolver.
        empty_placeholder: Text written for a multi-valued slot that is
            present but empty.  Defaults to an em dash (U+2014), the
            typographic convention for "no value"; pass ``""`` to leave
            such cells blank.

    Returns:
        List of row dicts with keys matching ``column_slots`` keys.
    """
    lookups = lookups or {}
    rows: list[dict[str, str]] = []
    for item in items:
        row: dict[str, str] = {}
        for col_key, slot_name in column_slots.items():
            if actor_resolver and col_key == actor_key:
                row[col_key] = actor_resolver(item)
                continue

            raw = _get(item, slot_name)

            if col_key in lookups and raw is not None:
                # Resolve through lookup (e.g. state_id → display_name)
                if isinstance(raw, list):
                    # Multi-valued (e.g. guard IDs → display names)
                    resolved = [lookups[col_key].get(v, v) for v in raw]
                    row[col_key] = (
                        ", ".join(str(r) for r in resolved if r is not None)
                        if resolved
                        else empty_placeholder
                    )
                else:
                    row[col_key] = lookups[col_key].get(str(raw), str(raw))
            elif isinstance(raw, list):
                row[col_key] = ", ".join(str(v) for v in raw) if raw else empty_placeholder
            else:
                row[col_key] = str(raw) if raw is not None else ""

        rows.append(row)
    return rows
