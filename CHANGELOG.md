# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-04-09

First public release.

### Added

- **StateDiagramRenderer** — Mermaid `stateDiagram-v2` output from `MermaidState`/`MermaidTransition` objects

  - Direction support (`TB`, `BT`, `LR`, `RL`)
  - `[*]` pseudo-states for initial/terminal markers
  - Single-line notes on states (`note right of`)
  - Actor and guard labels on transition arrows
  - Spec: https://mermaid.js.org/syntax/stateDiagram.html

- **FlowchartRenderer** — Mermaid `flowchart` output from `FlowchartNode`/`FlowchartEdge` objects

  - 7 node shapes: rect, round, stadium, diamond, hexagon, subroutine, circle
  - 3 edge styles — solid (`-->`), dotted (`-.->`), thick (`==>`)
  - Subgraphs with nested indentation
  - Spec: https://mermaid.js.org/syntax/flowchart.html

- **MarkdownTableRenderer** — GFM §4.10 pipe table output from `ColumnDef` rows

  - Per-column alignment (`left`, `center`, `right`, `default`) emitted in the delimiter row
  - Cell formats: `plain`, `bold`, `italic`, `code`
  - Lookup-based cell enrichment
  - Spec: https://github.github.com/gfm/#tables-extension-

- **SchemaReader** — Read-only façade over `linkml_runtime.SchemaView`

  - Auto-discovery of `mermaid_role` annotations
  - `discover_state_diagram_config()` for zero-config setup
  - `discover_table_columns()` for table generation
  - Spec: https://linkml.io/linkml/schemas/annotations.html

- **Mapping functions** — Config-driven LinkML-to-Mermaid transformation

  - `map_states()`, `map_transitions()` for diagram data
  - `build_table_rows()`, `build_state_descriptions()` for table data
  - Works with dicts, dataclasses and Pydantic objects

- **Annotation vocabulary** — `vocab/mermaid_annotations.yaml`, a LinkML schema defining the
  three annotation keys (`mermaid_diagram`, `mermaid_role`, `table_column`) and the
  14 `mermaid_role` values

- **Command-line interface** — `linkml-mermaid diagram` and `linkml-mermaid table` render a
  schema plus instance data without writing any Python

- **Escaping helpers** — `escape_mermaid_text`, `escape_state_label` and `escape_table_cell`
  are public, so callers composing their own output can reuse the rules the renderers use

- **Standards compliance record** — `docs/standards/` pins every specification by SHA-256 and
  maps each implemented clause to the code and the test that prove it, including the clauses
  deliberately not implemented. `scripts/check_standards.py` enforces this in CI.

### Notes on strictness

Invalid input fails loudly rather than degrading into malformed diagram text. An unknown node
shape, cell format, column alignment or state-diagram direction raises `ValueError`, as does a
transition that references a state which does not exist, a subgraph that lists an undeclared
member, and a state label that contains no identifier characters.

Every label, cell and title passes through the escaping layer, so characters that would
otherwise terminate a Mermaid string or split a GFM table cell — `"`, `#`, `|`, and backslash
runs before a pipe — are encoded rather than emitted raw.
