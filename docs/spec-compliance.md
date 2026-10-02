# Specification Compliance

"Spec-compliant" is a claim, and a claim needs evidence. The evidence lives in
[`docs/standards/`](https://github.com/ASCS-eV/linkml-mermaid/tree/main/docs/standards)
in the repository:

- **`manifest.json`** pins every specification this package implements against,
  by SHA-256, to the exact bytes that were read when the code was written.
- **`requirements.json`** maps each catalogued clause to the code that
  implements it and the test that proves it — including the clauses that are
  deliberately **not** implemented, each with a reason.
- **`coverage.md`** is generated from those two files. Read it first.

`scripts/check_standards.py` enforces the record in CI. Its `--verify-hashes`
mode re-downloads each specification and compares; Mermaid's syntax
documentation is a living document, so a failure there means a quoted clause
may have changed and the citations need re-reading.

## Specifications

### Mermaid

- **stateDiagram-v2** — <https://mermaid.js.org/syntax/stateDiagram.html>
- **Flowchart** — <https://mermaid.js.org/syntax/flowchart.html>

### GitHub Flavored Markdown

- **§4.10 Tables** — <https://github.github.com/gfm/#tables-extension->
- **§6.3 Code spans** — <https://github.github.com/gfm/#code-spans>
- **§6.4 Emphasis** — <https://github.github.com/gfm/#emphasis-and-strong-emphasis>

### LinkML

- **SchemaView** — <https://linkml.io/linkml/developers/schemaview.html>
- **Annotations** — <https://linkml.io/linkml/schemas/annotations.html>
- **Basic Enums** — <https://linkml.io/linkml/schemas/enums.html#basic-enums>

## Profile

This package emits a **subset** of each grammar, chosen so that a LinkML schema
plus instance data can be rendered without writing Mermaid by hand. It is not an
attempt to cover either language completely.

Not implemented, by decision:

- Composite states, choice, forks and concurrency in state diagrams — the data
  model has no slot that expresses nesting or concurrency. Branching is
  expressed as guarded transitions, which *are* supported.
- `classDef` styling — presentation is left to the caller.
- Multi-line block notes — only the single-line `note right of` form is emitted.
- Annotation-driven flowcharts — `mermaid_diagram` accepts `stateDiagram-v2`
  only.
- Open links without an arrow head (`A --- B`) — every edge this package emits
  is directed.
- Rendering to images — this emits Mermaid text.
- Validation against a real Mermaid parser — output is checked against grammar
  patterns derived from the specifications and against adversarial input, but no
  JavaScript Mermaid parser runs in CI.

## How it is tested

Escaping is tested against a shared corpus of hostile inputs — quotes, hashes,
pipes, backslash runs, newlines, control characters — applied to every label,
cell and title the package emits. `tests/test_spec_regressions.py` holds one
test class per historical defect, each quoting the clause it violated, so a
regression fails the build rather than shipping a broken diagram.

```bash
uv sync --group dev
uv run pytest --cov
uv run python scripts/check_standards.py
```
