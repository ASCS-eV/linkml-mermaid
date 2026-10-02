"""linkml_mermaid — generic LinkML-to-Mermaid diagram & table package.

Translates LinkML schema metadata and typed instance data into
syntactically valid Mermaid diagrams and GFM markdown tables.

Architecture (layered)
======================

Layer 1 — Pure renderers (no LinkML knowledge)
    :mod:`~linkml_mermaid.state_diagram`
        Renders ``stateDiagram-v2`` from :class:`MermaidState` /
        :class:`MermaidTransition` objects.
        Spec: https://mermaid.js.org/syntax/stateDiagram.html

    :mod:`~linkml_mermaid.flowchart`
        Renders ``flowchart`` from :class:`FlowchartNode` /
        :class:`FlowchartEdge` objects.
        Spec: https://mermaid.js.org/syntax/flowchart.html

    :mod:`~linkml_mermaid.markdown_table`
        Renders GFM §4.10 pipe tables from :class:`ColumnDef` / row dicts.
        Spec: https://github.github.com/gfm/#tables-extension-

Layer 2 — LinkML mapping (config-driven)
    :mod:`~linkml_mermaid.reader`
        Read-only façade over ``linkml_runtime.SchemaView``.
        Spec: https://linkml.io/linkml/developers/schemaview.html

    :mod:`~linkml_mermaid.mapping`
        Config-driven transformation from LinkML instances to
        Layer 1 primitives.  Uses :class:`StateDiagramConfig` to
        declare which slots map to which Mermaid concepts.

Layer 3 — Application
    :mod:`~linkml_mermaid.cli`
        The ``linkml-mermaid`` console script: renders a diagram or a
        table from a schema plus an instance-data document.

    A consuming project can instead load data through generated Pydantic
    models, apply domain-specific overrides (role resolution, template
    injection), and call Layer 2 directly.

Specification references
========================

Mermaid stateDiagram-v2
    https://mermaid.js.org/syntax/stateDiagram.html

Mermaid Flowchart
    https://mermaid.js.org/syntax/flowchart.html

GitHub Flavored Markdown tables (§4.10)
    https://github.github.com/gfm/#tables-extension-

LinkML SchemaView
    https://linkml.io/linkml/developers/schemaview.html

LinkML enumerations
    https://linkml.io/linkml/schemas/enums.html

LinkML annotations
    https://linkml.io/linkml/schemas/annotations.html

LinkML class/slot model
    https://linkml.io/linkml/schemas/models.html
"""

__version__ = "0.1.0"

# ── Public API ───────────────────────────────────────────────────────

from .escaping import (
    code_span_delimiter,
    escape_mermaid_text,
    escape_state_inline,
    escape_state_label,
    escape_subgraph_title,
    escape_table_cell,
    escape_table_code_cell,
)
from .flowchart import FlowchartRenderer
from .mapping import (
    StateDiagramConfig,
    build_state_descriptions,
    build_table_rows,
    identity_mapping,
    map_states,
    map_transitions,
)
from .markdown_table import MarkdownTableRenderer
from .reader import SchemaReader
from .state_diagram import (
    STATE_DIAGRAM_DIRECTIONS,
    StateDiagramRenderer,
    to_state_id,
)
from .types import (
    CELL_FORMATS,
    COLUMN_ALIGNMENTS,
    FLOWCHART_RESERVED_IDS,
    LINK_STYLES,
    NODE_SHAPES,
    NOTE_POSITIONS,
    STATE_RESERVED_IDS,
    ColumnDef,
    FlowchartEdge,
    FlowchartNode,
    FlowchartSubgraph,
    MermaidNote,
    MermaidState,
    MermaidTransition,
    TableDef,
    validate_flowchart_id,
    validate_state_id,
)

__all__ = [
    # Types — stateDiagram
    "MermaidState",
    "MermaidTransition",
    "MermaidNote",
    # Types — flowchart
    "FlowchartNode",
    "FlowchartEdge",
    "FlowchartSubgraph",
    # Types — tables
    "ColumnDef",
    "TableDef",
    # Renderers
    "StateDiagramRenderer",
    "FlowchartRenderer",
    "MarkdownTableRenderer",
    # Reader
    "SchemaReader",
    # Mapping
    "StateDiagramConfig",
    "map_states",
    "map_transitions",
    "build_state_descriptions",
    "build_table_rows",
    "identity_mapping",
    # Vocabularies of permissible values
    "NODE_SHAPES",
    "LINK_STYLES",
    "CELL_FORMATS",
    "COLUMN_ALIGNMENTS",
    "STATE_DIAGRAM_DIRECTIONS",
    "NOTE_POSITIONS",
    "FLOWCHART_RESERVED_IDS",
    "STATE_RESERVED_IDS",
    # Utilities
    "to_state_id",
    "validate_flowchart_id",
    "validate_state_id",
    "escape_mermaid_text",
    "escape_state_label",
    "escape_state_inline",
    "escape_subgraph_title",
    "escape_table_cell",
    "escape_table_code_cell",
    "code_span_delimiter",
]
