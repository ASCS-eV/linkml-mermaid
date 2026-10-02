# Getting Started

## Installation

```bash
pip install linkml-mermaid
```

For a local checkout with the test and build tooling:

```bash
uv sync --group dev
```

## 1. Try it from the command line

If your schema is already annotated (see step 2), nothing needs writing in
Python:

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

Add `-o FILE` to write to a file — what you want from a pre-commit hook or a
docs build. `--help` lists the rest.

## 2. Annotate your schema

Add `mermaid_role` annotations to your LinkML class attributes:

```yaml
classes:
  Workflow:
    annotations:
      mermaid_diagram: stateDiagram-v2
    attributes:
      states:
        range: State
        multivalued: true
        annotations:
          mermaid_role: states
      transitions:
        range: Transition
        multivalued: true
        annotations:
          mermaid_role: transitions
      guards:
        range: Guard
        multivalued: true
        annotations:
          mermaid_role: guard_list

  State:
    attributes:
      id:
        range: MyStateEnum
        annotations:
          mermaid_role: state_id
      display_name:
        annotations:
          mermaid_role: label
      is_initial:
        range: boolean
        annotations:
          mermaid_role: initial
      is_terminal:
        range: boolean
        annotations:
          mermaid_role: terminal

  Transition:
    attributes:
      name:
        annotations:
          mermaid_role: transition_label
      from_state:
        range: MyStateEnum
        annotations:
          mermaid_role: from_state
      to_state:
        range: MyStateEnum
        annotations:
          mermaid_role: to_state
      actor:
        annotations:
          mermaid_role: actor
      guards:
        range: MyGuardEnum
        multivalued: true
        annotations:
          mermaid_role: guards

  Guard:
    attributes:
      id:
        range: MyGuardEnum
        annotations:
          mermaid_role: guard_id
      display_name:
        annotations:
          mermaid_role: guard_label
```

See the **[Annotation Vocabulary](/annotations)** for every valid `mermaid_role` value.

## 3. Auto-discover and render from Python

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

# Load schema — discover config from annotations (zero manual wiring)
reader = SchemaReader("path/to/your_schema.yaml")
config = reader.discover_state_diagram_config("Workflow")

# Load your data (dicts, dataclasses and Pydantic models all work)
with open("path/to/data.yaml") as fh:
    data = yaml.safe_load(fh)

# Render Mermaid state diagram
diagram = StateDiagramRenderer(direction="LR").render(
    map_states(data["states"], config),
    map_transitions(data["transitions"], data["states"], data.get("guards", []), config),
)
print(diagram)

# Render GFM table
rows = build_table_rows(
    data["states"],
    {"state": "display_name", "description": "id", "color": "color"},
    lookups={"description": build_state_descriptions(reader, config.state_enum_name)},
)
table = MarkdownTableRenderer().render(
    [
        ColumnDef("State", "state", format="bold"),
        ColumnDef("Description", "description", align="left"),
    ],
    rows,
)
print(table)
```

That's it — the config is derived entirely from your schema annotations.

## A note on invalid input

This package fails loudly rather than emitting a broken diagram. An unknown node
shape, cell format, column alignment or direction raises `ValueError`, as does a
transition that points at a state which does not exist. Labels containing
quotes, hashes or pipes are escaped, not passed through.

## Next steps

- **[Architecture](/architecture)** — the layered design
- **[Flowchart Renderer](/flowchart)** — pure diagram rendering with no LinkML needed
- **[Specification Compliance](/spec-compliance)** — what is claimed, what is not, and the evidence
