# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-10-02

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

- **Escaping helpers** — `escape_mermaid_text`, `escape_state_label`, `escape_state_inline`,
  `escape_subgraph_title`, `escape_table_cell`, `escape_table_code_cell` and
  `code_span_delimiter` are public, so callers composing their own output can reuse the rules
  the renderers use

- **Identifier validation** — `validate_flowchart_id` and `validate_state_id` reject an
  identifier either Mermaid grammar would not read as a single token. Every type that carries
  an id (`MermaidState`, `MermaidTransition`, `MermaidNote`, `FlowchartNode`, `FlowchartEdge`,
  `FlowchartSubgraph`) checks its own on construction

- **Standards compliance record** — `docs/standards/` pins every specification by SHA-256 and
  maps each implemented clause to the code and the test that prove it, including the clauses
  deliberately not implemented. `scripts/check_standards.py` enforces this in CI.

- **Conformance tests against the real parsers** — rendered diagrams are handed to the actual
  Mermaid package and rendered tables to cmark-gfm, the library behind GitHub's own Markdown.
  Both run in CI, and each suite includes a calibration class that fails if the oracle stops
  rejecting input it must reject.

### Notes on strictness

Invalid input fails loudly rather than degrading into malformed diagram text. An unknown node
shape, cell format, column alignment or state-diagram direction raises `ValueError`, as does a
transition that references a state which does not exist, a subgraph that lists an undeclared
member, and a state label that contains no identifier characters.

Identifiers are the one caller-supplied value emitted unquoted, because that is the only form
the grammars accept, so they are validated instead of escaped. Flowchart ids accept
`[A-Za-z0-9_.-]` and state ids `[A-Za-z0-9_.]`; a flowchart id may not contain `--` or `-.`,
which begin a link operator. This is not cosmetic: an id of `A --> Evil` or `A---B` produced a
*valid* diagram containing a node and an edge the caller never asked for, a defect no
"does it parse" check could catch. Put text that needs spaces or punctuation in the label,
which is quoted and escaped; `to_state_id()` converts a label into a usable id.

A table cell holds **literal text**. GFM §4.10 specifies that inlines are parsed inside a cell,
so every character that could open an inline construct is escaped and the value is displayed
verbatim. Styling comes from `ColumnDef.format` alone. Cells rendered as code spans take a
separate path, because GFM §2.4 states that backslash escapes do not work inside one.

Every label, cell and title passes through the escaping layer, so characters that would
otherwise terminate a Mermaid string, split a GFM table cell, or change the meaning of either —
`"`, `#`, `:`, `;`, `|`, backslashes, a bare `www.` token and the `direction` keyword in a
subgraph title — are encoded rather than emitted raw.

The `;` escape is specific to `stateDiagram-v2`, where `;` ends a statement. That is not in the
Mermaid documentation; it was found by handing the real parser a state label of
`do x; then A --> B`, which it accepted by silently adding two states and a transition. Unlike
the colon it applies to the quoted `state "..." as id` form as well. The flowchart grammar
quotes its label positions and needs no equivalent escape, which was confirmed by rendering.

One known limit is documented rather than worked around: GFM's autolink extension linkifies a
bare email address in a table cell, and no escaping suppresses it. Every other value is
displayed verbatim.
