# Standards

This directory is the package's compliance record. It exists because
"spec-compliant" is a claim, and a claim needs evidence.

## What is here

| File | Purpose |
| :--- | :--- |
| [`manifest.json`](manifest.json) | Every specification this package implements against, pinned by SHA-256 to the exact bytes that were read when the code was written. |
| [`requirements.json`](requirements.json) | Every catalogued clause, mapped to the code that implements it and the test that proves it — including the clauses deliberately **not** implemented. |
| [`coverage.md`](coverage.md) | Generated from the two files above. Read this first. |

`scripts/check_standards.py` enforces all of it in CI:

```bash
python scripts/check_standards.py                  # structure + coverage.md freshness
python scripts/check_standards.py --verify-hashes  # re-download and compare (network)
python scripts/check_standards.py --write-coverage # regenerate coverage.md
```

The hash check is the part that matters. Mermaid's syntax documentation
is a living document: if a clause quoted in a docstring changes, the
check fails and the quote gets re-read rather than silently rotting.

## Why the specification texts are not vendored

`manifest.json` records a URL, a retrieval timestamp and a SHA-256 for
each specification, but no byte-exact copy is committed. The GitHub
Flavored Markdown spec is CC-BY-SA-4.0; vendoring it into an MIT-licensed
distribution would mix licences in the sdist for no practical gain. The
hash gives the same guarantee — anyone can re-download and verify that
the text being cited is the text that was read.

## Profile: what this package claims

This package emits a **subset** of each grammar. The subset is chosen so
that a LinkML schema plus instance data can be rendered without the
caller writing Mermaid by hand; it is not an attempt to cover either
language completely.

**Mermaid `flowchart`** — nodes (all seven documented shapes), the three
link styles with and without arrow heads, edge labels, direction, and
subgraphs. Entity escaping is applied to every label.

**Mermaid `stateDiagram-v2`** — states, state descriptions, transitions
with labels, start/end pseudo-states, direction, and single-line notes.

**GFM §4.10 tables** — header row, delimiter row with per-column
alignment, data rows, pipe escaping, and the inline formats used for
cell values (plain, bold, italic, code).

## What this package does not claim

These are documented decisions, not oversights. Each appears in
`requirements.json` with `"implemented": false` and a reason:

- **Composite states**, **choice**, **forks** (fork/join) and
  **concurrency** in state diagrams. The data model has no slot to
  express nesting or concurrency, so there is nothing to render; a
  LinkML schema expresses branching as guarded transitions, which *are*
  supported.
- **Styling with `classDef`** in state diagrams. Presentation is left to
  the caller, who can append style statements to the rendered output.
- **Multi-line block notes** (`note right of X ... end note`). Only the
  single-line form is emitted; a newline in note text becomes `<br>`.
- **Open links** without an arrow head (`A --- B`, `A -.- B`, `A === B`)
  in flowcharts. Every edge this package emits is directed, so an
  undirected link would misrepresent the data.
- **Annotation-driven flowcharts.** `mermaid_diagram` accepts only
  `stateDiagram-v2`. Flowcharts are rendered through the programmatic
  `FlowchartRenderer` API.
- **Rendering diagrams to images.** This package emits Mermaid text.
  Turning that into SVG or PNG is the job of Mermaid itself, or of a
  wrapper such as `mermaid-py`.
- **Validating the emitted text against a real Mermaid parser.** The
  tests assert against grammar patterns derived from the specification
  and against adversarial input, but no JavaScript Mermaid parser runs
  in CI. Output is checked for conformance to the documented grammar,
  not for acceptance by a specific Mermaid version.

## Known limits of the escaping

`escape_table_cell` doubles backslash runs that immediately precede a
pipe, which is what GFM requires to keep a cell from splitting. It does
not escape backslashes elsewhere, because a cell rendered as a code span
is literal and doubling them there would be visible in the output. The
practical consequence: a value ending in a backslash immediately before
a cell boundary is passed through unchanged.
