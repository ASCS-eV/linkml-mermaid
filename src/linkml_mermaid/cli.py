"""Command-line interface for linkml-mermaid.

Renders a Mermaid ``stateDiagram-v2`` or a GFM table from a LinkML
schema plus an instance-data file, using the ``mermaid_role`` and
``table_column`` annotations in the schema to decide what to emit.

The generators shipped with LinkML render the *schema* — class
structure, slots, enums.  This command renders the *instances*: the
states and transitions a particular workflow document declares.  That is
the gap it exists to fill.

Usage::

    linkml-mermaid diagram -s schema.yaml -d data.yaml -c Workflow
    linkml-mermaid table   -s schema.yaml -d data.yaml -c State -r states

Specification references
========================

Mermaid stateDiagram-v2
    https://mermaid.js.org/syntax/stateDiagram.html
GFM §4.10 Tables (extension)
    https://github.github.com/gfm/#tables-extension-
LinkML §Annotations
    https://linkml.io/linkml/schemas/annotations.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .mapping import (
    build_table_rows,
    identity_mapping,
    map_states,
    map_transitions,
)
from .markdown_table import MarkdownTableRenderer
from .reader import SchemaReader
from .state_diagram import STATE_DIAGRAM_DIRECTIONS, StateDiagramRenderer
from .types import ColumnDef


class CliError(Exception):
    """A problem with the user's input, reported without a traceback."""


def load_data(path: Path) -> dict[str, Any]:
    """Load an instance-data document.

    The CLI reads plain YAML rather than instantiating generated
    Pydantic classes, so it works against any schema without a code
    generation step.  The mapping layer already accepts dicts.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliError(f"Cannot read data file '{path}': {exc}") from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CliError(f"'{path}' is not valid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise CliError(
            f"'{path}' must contain a YAML mapping at the top level, found {type(data).__name__}"
        )
    return data


def collection(data: dict[str, Any], slot: str | None, what: str) -> list[Any]:
    """Pull a named list out of the loaded data document."""
    if slot is None:
        return []
    value = data.get(slot)
    if value is None:
        raise CliError(
            f"Data file has no '{slot}' key, which the schema declares as "
            f"the {what}; available keys: {sorted(data)}"
        )
    if not isinstance(value, list):
        raise CliError(f"Data key '{slot}' must be a list of {what}")
    return value


def load_schema(path: Path) -> SchemaReader:
    """Open a LinkML schema, converting loader failures into clean errors.

    ``SchemaView`` surfaces a malformed schema as whatever the YAML
    parser or the metamodel loader happened to raise, which would reach
    the terminal as a traceback.  Every such failure is a problem with
    the file the user named, so it is reported as a :class:`CliError`
    that says which file failed and why.
    """
    try:
        return SchemaReader(path)
    except Exception as exc:
        raise CliError(f"Cannot load LinkML schema '{path}': {exc}") from exc


def require_class(reader: SchemaReader, schema: Path, class_name: str) -> None:
    """Fail with a self-explanatory message if *class_name* is absent.

    Looking up a missing class raises deep inside ``linkml_runtime``
    with a message such as "name must be supplied" that names neither
    the schema nor the class, leaving the user nothing to act on.
    """
    try:
        found = reader.schema_view.get_class(class_name) is not None
    except Exception as exc:
        raise CliError(f"Cannot read class '{class_name}' from '{schema}': {exc}") from exc
    if not found:
        try:
            available = sorted(reader.schema_view.all_classes())
        except Exception:
            available = []
        hint = f"; available classes: {available}" if available else ""
        raise CliError(f"Schema '{schema}' has no class named '{class_name}'{hint}")


def render_diagram(args: argparse.Namespace) -> str:
    reader = load_schema(args.schema)
    require_class(reader, args.schema, args.class_name)
    config = reader.discover_state_diagram_config(args.class_name)
    data = load_data(args.data)

    states = collection(data, args.states_key, "state collection")
    transitions = collection(data, args.transitions_key, "transition collection")
    guards = collection(data, args.guards_key, "guard collection") if args.guards_key else []

    renderer = StateDiagramRenderer(direction=args.direction)
    return renderer.render(
        map_states(states, config),
        map_transitions(transitions, states, guards, config),
    )


def render_table(args: argparse.Namespace) -> str:
    reader = load_schema(args.schema)
    require_class(reader, args.schema, args.class_name)
    columns: list[ColumnDef] = reader.discover_table_columns(args.class_name)
    data = load_data(args.data)

    items = collection(data, args.rows_key, "row collection")
    rows = build_table_rows(items, identity_mapping(columns))
    return MarkdownTableRenderer().render(columns, rows)


def write_output(text: str, destination: Path | None) -> None:
    """Write the rendered text to *destination*, or to stdout if *None*.

    Raises:
        CliError: If the destination cannot be created or written.  The
            path came from the user, so a permission or missing-device
            failure is user input rather than a defect.
    """
    if destination is None:
        sys.stdout.write(text + "\n")
        return
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text + "\n", encoding="utf-8")
    except OSError as exc:
        raise CliError(f"Cannot write output to '{destination}': {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="linkml-mermaid",
        description=(
            "Render Mermaid diagrams and GFM tables from LinkML instance "
            "data, driven by annotations in the schema."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "-s",
            "--schema",
            type=Path,
            required=True,
            help="Path to the LinkML schema (YAML).",
        )
        sub.add_argument(
            "-d",
            "--data",
            type=Path,
            required=True,
            help="Path to the instance-data document (YAML).",
        )
        sub.add_argument(
            "-o",
            "--output",
            type=Path,
            default=None,
            help="Write to this file instead of standard output.",
        )

    diagram = subparsers.add_parser(
        "diagram",
        help="Render a Mermaid stateDiagram-v2 from a workflow instance.",
    )
    add_common(diagram)
    diagram.add_argument(
        "-c",
        "--class-name",
        required=True,
        help="LinkML class annotated with the state-machine roles.",
    )
    diagram.add_argument(
        "--states-key",
        default="states",
        help="Key in the data file holding the state list.",
    )
    diagram.add_argument(
        "--transitions-key",
        default="transitions",
        help="Key in the data file holding the transition list.",
    )
    diagram.add_argument(
        "--guards-key",
        default=None,
        help="Key in the data file holding the guard list, if any.",
    )
    diagram.add_argument(
        "--direction",
        default=None,
        choices=sorted(STATE_DIAGRAM_DIRECTIONS),
        help="Diagram layout direction (Mermaid default is TB).",
    )
    diagram.set_defaults(handler=render_diagram)

    table = subparsers.add_parser(
        "table",
        help="Render a GFM table from a list of instances.",
    )
    add_common(table)
    table.add_argument(
        "-c",
        "--class-name",
        required=True,
        help="LinkML class carrying the table_column annotations.",
    )
    table.add_argument(
        "-r",
        "--rows-key",
        required=True,
        help="Key in the data file holding the list of rows.",
    )
    table.set_defaults(handler=render_table)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``linkml-mermaid`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.schema.is_file():
        print(f"error: schema file not found: {args.schema}", file=sys.stderr)
        return 2

    try:
        output = args.handler(args)
        write_output(output, args.output)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
