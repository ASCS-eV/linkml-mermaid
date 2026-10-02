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

## Validation against the real parsers

Output is not merely checked against grammar patterns derived from the
specifications. Two conformance suites hand it to the software those
specifications describe:

- `tests/test_mermaid_conformance.py` runs every rendered diagram
  through the **real Mermaid package** (`mermaid.parse`), and for the
  cases that turn on an escape sequence it also renders the diagram and
  reads the text back out of the SVG — proving, for example, that
  `#58;` reaches the reader as `:` rather than merely parsing.
- `tests/test_gfm_conformance.py` renders every table through
  **cmark-gfm**, the library GitHub's own Markdown pipeline is built on,
  and checks the resulting HTML.

Both run in CI. Each suite ends with a calibration class that feeds the
oracle input which *must* be rejected, so a silently broken oracle fails
the build instead of making every other assertion vacuous.

The suites skip when Node or `cmarkgfm` is absent, so a contributor
without the JavaScript toolchain can still run the rest of the tests.

What this does **not** claim: acceptance by every Mermaid version. The
oracle pins one version (see `package.json`), and Mermaid's grammar has
changed between releases.

## Escaping contract

A table cell holds **literal text**. GFM §4.10 specifies that "inlines
are parsed" inside a cell, so every character that could open an inline
construct is escaped and the caller's value is displayed verbatim —
including backslashes, which §2.4 makes an escape character in their own
right. Styling comes from `ColumnDef.format` alone, which is why that
field exists.

The colon is escaped too. GFM's autolink extension recognises a bare
`scheme:` and would otherwise pull following text into a link, which was
observed to swallow an adjacent escape and leave a stray backslash
visible. The same extension (§6.9) also linkifies a bare `www.` token,
which contains no active character at all, so the dot after `www` is
escaped — every other dot in the value is left alone, so a version
number does not acquire backslashes.

**One known limit.** The extension's bare-email form cannot be
suppressed. Neither `user\@example\.com` nor a character reference
defeats it in cmark-gfm, so a cell whose value looks like an email
address will render as a `mailto:` link. This is the only case where a
cell is not displayed verbatim, and it is a property of the GFM parser
rather than a choice this package makes.

A cell rendered as a code span takes a different path, because §2.4
states that backslash escapes do not work inside one. There the
delimiter grows to outrun the longest backtick run in the value, a space
of padding is added when §6.3's own unpadding rule will remove it again,
and a multi-line value becomes one span per line joined by `<br>`
*between* the spans — a `<br>` placed inside a span would be shown
literally.

§6.3 declines to unpad a span that "does not consist entirely of space
characters", so a whitespace-only value would come back *wider* than it
went in. Such a line emits no span at all instead.

## State diagram text

`stateDiagram-v2` needs more than the shared entity escaping, because
two of its three text positions are not quotable.

`:` introduces the description in both the `id : description` form and
the transition-label form, and `::` is the class-application operator.
A note body is introduced by `:` as well and a colon anywhere in one is
a parse error. Transition labels and note bodies therefore have every
colon replaced by `#58;`.

`;` ends a statement. This is not stated in the Mermaid documentation;
it was found by feeding the real parser a label of `do x; then A --> B`,
which it accepted by silently adding two states and a transition the
caller never asked for. Unlike the colon this applies to the *quoted*
`state "..." as id` form too, so `;` is escaped as `#59;` in every state
text position.

Both escapes are applied in a single pass. The entities this escaping
emits themselves contain `#` and `;` — the two other characters being
escaped — so a second pass would corrupt `#quot;` into `#quot#59;`. A
regression test pins this, because the bug is invisible in a parse-only
check: the corrupted form still parses.

The flowchart grammar quotes all three of its text positions, so none of
this applies there; that was confirmed by rendering, not assumed.
