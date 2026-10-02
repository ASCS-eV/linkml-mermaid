# linkml-mermaid

Render [Mermaid](https://mermaid.js.org/) diagrams and [GFM](https://github.github.com/gfm/)
tables from **LinkML instance data**, driven by annotations in the schema itself.

## Why this exists

LinkML already generates diagrams — seven generators, in fact, including
`gen-erdiagram` and `gen-mermaid-class-diagram`. Every one of them renders the
**schema**: classes, slots, ranges, inheritance. That is the right answer when
the question is "what does my model look like?".

It is the wrong answer when the question is "what does my *data* look like?".

A LinkML schema that models a workflow says *a Transition has a from_state and a
to_state*. Only the instance data says *Draft goes to InReview when a Reviewer
approves it*. A class diagram of that schema shows three boxes — `Workflow`,
`State`, `Transition` — and tells a reader nothing about the workflow. The
diagram people actually want is a state machine, and it can only be drawn from
the instances.

So teams write it by hand. The schema is the source of truth, the diagram in the
README is a copy of it, and the two drift apart on the first change that nobody
remembers to mirror. The usual fix is a one-off script with slot names hardcoded
into f-strings — which works until the schema is renamed, and which has to be
rewritten from scratch for the next project.

This package closes that gap. You annotate the schema once to say which slot
means "source state" and which means "guard", and the diagram is generated from
the data every time it is needed.

### This is a known gap, not an invented one

[`linkml/linkml#915`](https://github.com/linkml/linkml/issues/915) — *"Add dumpers
for mermaid, markdown"*, opened by LinkML's lead maintainer in August 2022 — is
still open.

To be straight about it: that issue asks for instance-data rendering in general.
We have found **no** issue specifically requesting state diagrams, so this package
is not filling a loudly-articulated demand for *that* shape. It is an answer to
the general request, for the case we needed solved.

### Prior art

**[`linkml/linkml-renderer`](https://github.com/linkml/linkml-renderer)** is the
only existing tool that renders LinkML *instance* data to Mermaid, and it deserves
a look before you reach for this one. It walks an object tree and emits Mermaid.
The differences that matter:

| | `linkml-renderer` | `linkml-mermaid` |
| :--- | :--- | :--- |
| Output | `graph TB` flowchart | `stateDiagram-v2` and `flowchart` |
| Configuration | external YAML style file | annotations inside the schema |
| GFM tables | no | yes, with alignment and cell formats |
| Status | "experimental", last release 2024-06 | — |

If you want a generic object graph, use `linkml-renderer`. If you are modelling a
state machine and want it drawn as one — with guards on the arrows and a table of
states beside it — that is what this package does.

LinkML's own `SQLTableGenerator` already reads unprefixed annotations such as
`primary_key`, so the `mermaid_role` convention used here follows established
LinkML practice rather than inventing a new mechanism.

## Install

```bash
pip install linkml-mermaid
```

## Use it from the command line

```bash
linkml-mermaid diagram -s schema.yaml -d data.yaml -c TrafficWorkflow --direction LR
```

```
stateDiagram-v2
    direction LR
    [*] --> RED

    RED : Red
    YELLOW : Yellow
    GREEN : Green
    RED --> GREEN : Go [Timer]<br>Timer expired
    GREEN --> YELLOW : Caution [Timer]
    YELLOW --> RED : Stop [Timer]
```

```bash
linkml-mermaid table -s schema.yaml -d data.yaml -c TrafficState -r states
```

```
| State | Description | Color |
| --- | --- | --- |
| **Red** | RED | #d32f2f |
| **Yellow** | YELLOW | #fbc02d |
| **Green** | GREEN | #388e3c |
```

`-o FILE` writes to a file instead of standard output, which is what you want in
a pre-commit hook or a docs build. Run `linkml-mermaid diagram --help` for the
remaining options.

## Annotate your schema

`mermaid_role` declares what Mermaid concept a slot carries. The reader discovers
the rest.

```yaml
classes:
  Workflow:
    annotations:
      mermaid_diagram: stateDiagram-v2
    attributes:
      states:
        range: State
        multivalued: true
        annotations: { mermaid_role: states }
      transitions:
        range: Transition
        multivalued: true
        annotations: { mermaid_role: transitions }
      guards:
        range: Guard
        multivalued: true
        annotations: { mermaid_role: guard_list }

  State:
    attributes:
      id:
        range: MyStateEnum
        annotations: { mermaid_role: state_id }
      display_name:
        annotations: { mermaid_role: label }
      is_initial:
        range: boolean
        annotations: { mermaid_role: initial }
      is_terminal:
        range: boolean
        annotations: { mermaid_role: terminal }

  Transition:
    attributes:
      name:
        annotations: { mermaid_role: transition_label }
      from_state:
        range: MyStateEnum
        annotations: { mermaid_role: from_state }
      to_state:
        range: MyStateEnum
        annotations: { mermaid_role: to_state }
      actor:
        annotations: { mermaid_role: actor }
      guards:
        range: MyGuardEnum
        multivalued: true
        annotations: { mermaid_role: guards }

  Guard:
    attributes:
      id:
        range: MyGuardEnum
        annotations: { mermaid_role: guard_id }
      display_name:
        annotations: { mermaid_role: guard_label }
```

### Vocabulary

All 14 `mermaid_role` values are defined in [`vocab/mermaid_annotations.yaml`](src/linkml_mermaid/vocab/mermaid_annotations.yaml)
— a real LinkML schema, so the vocabulary is itself machine-readable — and mirrored
as Python frozensets in `linkml_mermaid.vocab`.

| `mermaid_role`     | Where               | Mermaid concept                   |
| ------------------ | ------------------- | --------------------------------- |
| `state_id`         | State class         | State identifier (→ PascalCase)   |
| `label`            | State / Guard class | Display label (`StateId : Label`) |
| `initial`          | State class         | Start pseudo-state (`[*] --> Id`) |
| `terminal`         | State class         | End pseudo-state (`Id --> [*]`)   |
| `from_state`       | Transition class    | Source state                      |
| `to_state`         | Transition class    | Target state                      |
| `transition_label` | Transition class    | Transition name                   |
| `actor`            | Transition class    | Actor label (appended to name)    |
| `guards`           | Transition class    | Guard ID list                     |
| `guard_id`         | Guard class         | Guard identifier                  |
| `guard_label`      | Guard class         | Guard display name                |
| `states`           | Workflow container  | Slot holding the state list       |
| `transitions`      | Workflow container  | Slot holding the transition list  |
| `guard_list`       | Workflow container  | Slot holding the guard list       |

Two further keys exist: `mermaid_diagram` on the container class (only
`stateDiagram-v2` is accepted), and `table_column` on any slot, whose value is
`Header` or `Header|format`.

## Use it from Python

```python
import yaml

from linkml_mermaid import (
    ColumnDef,
    MarkdownTableRenderer,
    SchemaReader,
    StateDiagramRenderer,
    build_state_descriptions,
    build_table_rows,
    map_states,
    map_transitions,
)

reader = SchemaReader("schema.yaml")
config = reader.discover_state_diagram_config("Workflow")

with open("data.yaml") as fh:
    data = yaml.safe_load(fh)

diagram = StateDiagramRenderer(direction="LR").render(
    map_states(data["states"], config),
    map_transitions(data["transitions"], data["states"], data.get("guards", []), config),
)
print(diagram)

rows = build_table_rows(
    data["states"],
    {"state": "display_name", "description": "id"},
    lookups={"description": build_state_descriptions(reader, config.state_enum_name)},
)
print(
    MarkdownTableRenderer().render(
        [
            ColumnDef("State", "state", format="bold"),
            ColumnDef("Description", "description", align="left"),
        ],
        rows,
    )
)
```

Instances may be dicts, dataclasses or Pydantic models — the mapping layer reads
all three.

## Flowcharts, without LinkML

The renderers are a standalone layer with no LinkML dependency. Build the
dataclasses yourself and render them.

```python
from linkml_mermaid import FlowchartEdge, FlowchartNode, FlowchartRenderer, FlowchartSubgraph

nodes = [
    FlowchartNode("A", "Start", shape="stadium"),
    FlowchartNode("B", "Process"),
    FlowchartNode("C", "Decision", shape="diamond"),
    FlowchartNode("D", "End", shape="round"),
]
edges = [
    FlowchartEdge("A", "B"),
    FlowchartEdge("B", "C"),
    FlowchartEdge("C", "D", label="Yes"),
    FlowchartEdge("C", "B", label="No", style="dotted"),
]
subgraphs = [FlowchartSubgraph("main", "Main Flow", ["A", "B", "C", "D"])]

print(FlowchartRenderer(direction="TD").render(nodes, edges, subgraphs))
```

**Shapes:** `rect` `["…"]`, `round` `("…")`, `stadium` `(["…"])`, `diamond` `{"…"}`,
`hexagon` `{{"…"}}`, `subroutine` `[["…"]]`, `circle` `(("…"))`

**Edge styles:** `solid` `-->`, `dotted` `-.->`, `thick` `==>`

## Escaping is not optional

A state called `Needs "sign-off"` or a table cell containing `a | b` will produce
broken output if it is interpolated into a template. Every label, cell and title
this package emits goes through the escaping layer, which encodes `"` as `#quot;`
and `#` as `#35;` for Mermaid (per the flowchart spec's entity-code rule) and
escapes pipes — including backslash runs preceding them — for GFM.

Those helpers are public, so code that composes its own output can reuse them:

```python
from linkml_mermaid import escape_mermaid_text, escape_state_label, escape_table_cell
```

## Architecture

```
Layer 1 — Pure renderers (no LinkML dependency)
  types.py            Frozen dataclasses: MermaidState, MermaidTransition,
                      FlowchartNode, FlowchartEdge, ColumnDef, …
  escaping.py         The escape rules every renderer shares
  state_diagram.py    StateDiagramRenderer → Mermaid stateDiagram-v2
  flowchart.py        FlowchartRenderer → Mermaid flowchart
  markdown_table.py   MarkdownTableRenderer → GFM §4.10 pipe tables

Layer 2 — Config-driven LinkML mapping
  reader.py           SchemaReader (SchemaView façade + annotation discovery)
  mapping.py          map_states, map_transitions, build_table_rows, …

Layer 3 — Command-line interface
  cli.py              linkml-mermaid diagram | table

Shipped vocabulary
  vocab/              mermaid_annotations.yaml and its Python mirror
```

## Standards compliance

Claims about compliance are only worth the evidence behind them, so the evidence
is in the repository. [`docs/standards/`](docs/standards/) pins each
specification by SHA-256, maps every implemented clause to the code and the test
that prove it, and records the clauses that are deliberately **not** implemented.
Start with [`docs/standards/coverage.md`](docs/standards/coverage.md).
`scripts/check_standards.py` enforces the whole record in CI and will fail if an
upstream specification changes under a quoted citation.

- Mermaid stateDiagram-v2 — https://mermaid.js.org/syntax/stateDiagram.html
- Mermaid flowchart — https://mermaid.js.org/syntax/flowchart.html
- GFM §4.10 Tables — https://github.github.com/gfm/#tables-extension-
- LinkML annotations — https://linkml.io/linkml/schemas/annotations.html

### What this package does not do

- **Composite states, choice, fork/join, concurrency.** Branching is expressed as
  guarded transitions. Nesting is not modelled.
- **Styling.** No `classDef` is emitted; append your own to the output.
- **Images.** This emits Mermaid *text*. Rendering it to SVG or PNG is Mermaid's
  job, or [`mermaid-py`](https://pypi.org/project/mermaid-py/)'s.
- **Annotation-driven flowcharts.** `mermaid_diagram` accepts `stateDiagram-v2`
  only; flowcharts are built through the Python API.
- **Open links.** Every edge is directed; `A --- B` is not emitted.
- **Parser-level validation.** Output is tested against grammar patterns derived
  from the specifications and against adversarial input, but no JavaScript Mermaid
  parser runs in CI.

The full list, with reasons, is in
[`docs/standards/README.md`](docs/standards/README.md).

## Development

```bash
uv sync --group dev
uv run ruff check .
uv run mypy --strict src
uv run pytest --cov
uv run python scripts/check_standards.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
