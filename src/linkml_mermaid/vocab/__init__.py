"""Annotation vocabulary constants.

Provides the ``mermaid_role`` annotation values as Python constants
so that both the auto-discovery code and user code can reference them
without magic strings.

The canonical source of truth is ``vocab/mermaid_annotations.yaml``
(a LinkML schema).  These constants mirror the ``MermaidRole`` enum
defined there.
"""

from __future__ import annotations

from pathlib import Path

# Path to the shipped annotation vocabulary schema
VOCAB_SCHEMA_PATH = Path(__file__).parent / "mermaid_annotations.yaml"

# ── Annotation keys ─────────────────────────────────────────────────
# These are the annotation tag names that linkml_mermaid recognizes.

MERMAID_ROLE = "mermaid_role"
"""Annotation key on LinkML attributes.
Per LinkML §Annotations: annotations are arbitrary key-value pairs."""

MERMAID_DIAGRAM = "mermaid_diagram"
"""Annotation key on LinkML classes.
Declares which Mermaid diagram type the class renders as."""

TABLE_COLUMN = "table_column"
"""Annotation key on LinkML attributes.
Declares that the slot should appear as a column in generated tables.
Value format: ``"Header"`` or ``"Header|format"`` where format is
one of: bold, code, italic."""

# ── MermaidRole values (from MermaidRole enum in vocab schema) ──────

# State class slots
ROLE_STATE_ID = "state_id"
ROLE_LABEL = "label"
ROLE_INITIAL = "initial"
ROLE_TERMINAL = "terminal"

# Transition class slots
ROLE_FROM_STATE = "from_state"
ROLE_TO_STATE = "to_state"
ROLE_TRANSITION_LABEL = "transition_label"
ROLE_ACTOR = "actor"
ROLE_GUARDS = "guards"

# Guard class slots
ROLE_GUARD_ID = "guard_id"
ROLE_GUARD_LABEL = "guard_label"

# Workflow container slots
ROLE_STATES = "states"
ROLE_TRANSITIONS = "transitions"
ROLE_GUARD_LIST = "guard_list"

# ── Machine-checkable mirrors of the vocabulary schema ──────────────
# ``tests/test_vocab.py`` asserts these match the YAML exactly, so the
# two copies cannot drift apart unnoticed.

ANNOTATION_KEYS: frozenset[str] = frozenset({MERMAID_ROLE, MERMAID_DIAGRAM, TABLE_COLUMN})
"""Every annotation tag name this package reads from a schema."""

MERMAID_ROLES: frozenset[str] = frozenset(
    {
        ROLE_STATE_ID,
        ROLE_LABEL,
        ROLE_INITIAL,
        ROLE_TERMINAL,
        ROLE_FROM_STATE,
        ROLE_TO_STATE,
        ROLE_TRANSITION_LABEL,
        ROLE_ACTOR,
        ROLE_GUARDS,
        ROLE_GUARD_ID,
        ROLE_GUARD_LABEL,
        ROLE_STATES,
        ROLE_TRANSITIONS,
        ROLE_GUARD_LIST,
    }
)
"""Every permissible value of the ``mermaid_role`` annotation."""

MERMAID_DIAGRAM_TYPES: frozenset[str] = frozenset({"stateDiagram-v2"})
"""Diagram types that can be configured from annotations alone.

Flowcharts are rendered through the programmatic API and have no
annotation-driven discovery, so no ``flowchart`` value is offered here.
"""
