# Annotation Vocabulary

The `mermaid_role` annotation declares what Mermaid concept a slot represents.
All valid values are defined in `vocab/mermaid_annotations.yaml` and mirrored as
Python constants in `vocab/__init__.py`.

| `mermaid_role` | Where | Mermaid concept |
| --- | --- | --- |
| `state_id` | State class | State identifier (→ PascalCase) |
| `label` | State / Guard class | Display label (`StateId : Label`) |
| `initial` | State class | Start pseudo-state (`[*] --> Id`) |
| `terminal` | State class | End pseudo-state (`Id --> [*]`) |
| `from_state` | Transition class | Source state |
| `to_state` | Transition class | Target state |
| `transition_label` | Transition class | Transition name |
| `actor` | Transition class | Actor label (appended to name) |
| `guards` | Transition class | Guard ID list |
| `guard_id` | Guard class | Guard identifier |
| `guard_label` | Guard class | Guard display name |
| `states` | Workflow container | Slot holding the state list |
| `transitions` | Workflow container | Slot holding the transition list |
| `guard_list` | Workflow container | Slot holding the guard list |

## Class-level annotations

| Annotation key | Where | Purpose |
| --- | --- | --- |
| `mermaid_diagram` | Class | Declares which Mermaid diagram type the class renders as. `stateDiagram-v2` is the only accepted value — flowcharts are built through the Python API, not from annotations. |
| `table_column` | Attribute | Declares that the slot should appear as a column in generated tables. Value format: `"Header"` or `"Header\|format"`, where format is one of `plain`, `bold`, `italic`, `code`. An unrecognised format raises `ValueError` with the schema location, rather than silently falling back. |

## Using the constants

Reference the vocabulary from Python instead of using magic strings:

```python
from linkml_mermaid.vocab import (
    MERMAID_ROLE,
    ROLE_STATE_ID,
    ROLE_FROM_STATE,
    ROLE_TO_STATE,
    VOCAB_SCHEMA_PATH,
)
```

`VOCAB_SCHEMA_PATH` points at the shipped `mermaid_annotations.yaml` so you can
load or validate against the canonical vocabulary schema.

To validate a value rather than name it, use the frozensets:

```python
from linkml_mermaid import (
    ANNOTATION_KEYS,  # {"mermaid_diagram", "mermaid_role", "table_column"}
    MERMAID_DIAGRAM_TYPES,  # {"stateDiagram-v2"}
    MERMAID_ROLES,  # the 14 roles above
)
```

These are generated from the same source as the YAML schema, and
`tests/test_vocab.py` fails the build if the Python mirror and the YAML ever
disagree.
