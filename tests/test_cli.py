"""Tests for the ``linkml-mermaid`` console script.

The CLI is the package's answer to the question the README poses: it
renders *instance data* as a Mermaid state diagram, which none of
LinkML's bundled generators do.  These tests exercise it end to end
against the fixture schema and data, and pin its failure behaviour —
a command-line tool that exits 0 after printing a broken diagram is
worse than one that refuses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from linkml_mermaid import __version__
from linkml_mermaid.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA = FIXTURES / "test_schema.yaml"
DATA = FIXTURES / "test_data.yaml"


def run(capsys, *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# ── diagram subcommand ───────────────────────────────────────────────


class TestDiagramCommand:
    """Renders a Mermaid stateDiagram-v2 from instance data."""

    def test_renders_a_valid_diagram(self, capsys):
        code, out, _ = run(
            capsys,
            "diagram",
            "-s",
            str(SCHEMA),
            "-d",
            str(DATA),
            "-c",
            "TrafficWorkflow",
        )
        assert code == 0
        assert out.splitlines()[0] == "stateDiagram-v2"

    def test_includes_every_state_and_transition(self, capsys):
        _, out, _ = run(
            capsys,
            "diagram",
            "-s",
            str(SCHEMA),
            "-d",
            str(DATA),
            "-c",
            "TrafficWorkflow",
        )
        for state in ("RED", "YELLOW", "GREEN"):
            assert state in out
        assert "RED --> GREEN" in out
        assert "GREEN --> YELLOW" in out
        assert "YELLOW --> RED" in out

    def test_marks_the_initial_state(self, capsys):
        """§Start and End: '[*] --> State'."""
        _, out, _ = run(
            capsys,
            "diagram",
            "-s",
            str(SCHEMA),
            "-d",
            str(DATA),
            "-c",
            "TrafficWorkflow",
        )
        assert "[*] --> RED" in out

    def test_guards_are_rendered_with_a_renderable_separator(self, capsys):
        _, out, _ = run(
            capsys,
            "diagram",
            "-s",
            str(SCHEMA),
            "-d",
            str(DATA),
            "-c",
            "TrafficWorkflow",
            "--guards-key",
            "guards",
        )
        assert "<br>Timer expired" in out
        assert "\\n" not in out

    def test_direction_is_emitted(self, capsys):
        _, out, _ = run(
            capsys,
            "diagram",
            "-s",
            str(SCHEMA),
            "-d",
            str(DATA),
            "-c",
            "TrafficWorkflow",
            "--direction",
            "LR",
        )
        assert "    direction LR" in out

    def test_undocumented_direction_is_refused_by_the_parser(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(
                [
                    "diagram",
                    "-s",
                    str(SCHEMA),
                    "-d",
                    str(DATA),
                    "-c",
                    "TrafficWorkflow",
                    "--direction",
                    "TD",
                ]
            )
        assert exc.value.code == 2

    def test_writes_to_an_output_file(self, capsys, tmp_path):
        target = tmp_path / "nested" / "diagram.mmd"
        code, out, _ = run(
            capsys,
            "diagram",
            "-s",
            str(SCHEMA),
            "-d",
            str(DATA),
            "-c",
            "TrafficWorkflow",
            "-o",
            str(target),
        )
        assert code == 0
        assert out == ""
        assert target.read_text(encoding="utf-8").startswith("stateDiagram-v2")


# ── table subcommand ─────────────────────────────────────────────────


class TestTableCommand:
    """Renders a GFM §4.10 pipe table from a list of instances."""

    def test_renders_a_table(self, capsys):
        code, out, _ = run(
            capsys,
            "table",
            "-s",
            str(SCHEMA),
            "-d",
            str(DATA),
            "-c",
            "TrafficState",
            "-r",
            "states",
        )
        assert code == 0
        lines = out.strip().split("\n")
        assert lines[0].startswith("|")
        assert set(lines[1].replace("|", "").replace(" ", "")) <= {"-", ":"}
        assert len(lines) == 2 + 3  # header + delimiter + three states

    def test_column_headers_come_from_annotations(self, capsys):
        _, out, _ = run(
            capsys,
            "table",
            "-s",
            str(SCHEMA),
            "-d",
            str(DATA),
            "-c",
            "TrafficState",
            "-r",
            "states",
        )
        assert "State" in out.split("\n")[0]
        assert "Color" in out.split("\n")[0]

    def test_declared_format_is_applied(self, capsys):
        """The schema declares ``table_column: "State|bold"``."""
        _, out, _ = run(
            capsys,
            "table",
            "-s",
            str(SCHEMA),
            "-d",
            str(DATA),
            "-c",
            "TrafficState",
            "-r",
            "states",
        )
        assert "**Red**" in out

    def test_transitions_table(self, capsys):
        _, out, _ = run(
            capsys,
            "table",
            "-s",
            str(SCHEMA),
            "-d",
            str(DATA),
            "-c",
            "TrafficTransition",
            "-r",
            "transitions",
        )
        assert "Transition" in out
        assert "Go" in out


# ── failure behaviour ────────────────────────────────────────────────


class TestCliFailures:
    """Bad input must fail loudly with a non-zero exit code."""

    def test_missing_schema_file(self, capsys):
        code, _, err = run(
            capsys,
            "diagram",
            "-s",
            "no-such-schema.yaml",
            "-d",
            str(DATA),
            "-c",
            "TrafficWorkflow",
        )
        assert code == 2
        assert "schema file not found" in err

    def test_missing_data_file(self, capsys):
        code, _, err = run(
            capsys,
            "diagram",
            "-s",
            str(SCHEMA),
            "-d",
            "no-such-data.yaml",
            "-c",
            "TrafficWorkflow",
        )
        assert code == 2
        assert "Cannot read data file" in err

    def test_data_file_is_not_a_mapping(self, capsys, tmp_path):
        bad = tmp_path / "list.yaml"
        bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
        code, _, err = run(
            capsys,
            "diagram",
            "-s",
            str(SCHEMA),
            "-d",
            str(bad),
            "-c",
            "TrafficWorkflow",
        )
        assert code == 2
        assert "mapping at the top level" in err

    def test_data_file_is_not_valid_yaml(self, capsys, tmp_path):
        bad = tmp_path / "broken.yaml"
        bad.write_text("key: [unclosed\n", encoding="utf-8")
        code, _, err = run(
            capsys,
            "diagram",
            "-s",
            str(SCHEMA),
            "-d",
            str(bad),
            "-c",
            "TrafficWorkflow",
        )
        assert code == 2
        assert "not valid YAML" in err

    def test_missing_collection_key(self, capsys, tmp_path):
        bad = tmp_path / "empty.yaml"
        bad.write_text("something_else: []\n", encoding="utf-8")
        code, _, err = run(
            capsys,
            "diagram",
            "-s",
            str(SCHEMA),
            "-d",
            str(bad),
            "-c",
            "TrafficWorkflow",
        )
        assert code == 2
        assert "has no 'states' key" in err

    def test_collection_key_is_not_a_list(self, capsys, tmp_path):
        bad = tmp_path / "scalar.yaml"
        bad.write_text("states: oops\ntransitions: []\n", encoding="utf-8")
        code, _, err = run(
            capsys,
            "diagram",
            "-s",
            str(SCHEMA),
            "-d",
            str(bad),
            "-c",
            "TrafficWorkflow",
        )
        assert code == 2
        assert "must be a list" in err

    def test_transition_to_an_unknown_state_fails(self, capsys, tmp_path):
        """A dangling reference must not render as a plausible diagram."""
        bad = tmp_path / "dangling.yaml"
        bad.write_text(
            "states:\n"
            "  - id: RED\n"
            "    display_name: Red\n"
            "transitions:\n"
            "  - name: Go\n"
            "    from_state: RED\n"
            "    to_state: PURPLE\n",
            encoding="utf-8",
        )
        code, _, err = run(
            capsys,
            "diagram",
            "-s",
            str(SCHEMA),
            "-d",
            str(bad),
            "-c",
            "TrafficWorkflow",
        )
        assert code == 1
        assert "unknown state 'PURPLE'" in err

    def test_unknown_class_fails(self, capsys):
        code, _, err = run(
            capsys,
            "table",
            "-s",
            str(SCHEMA),
            "-d",
            str(DATA),
            "-c",
            "NoSuchClass",
            "-r",
            "states",
        )
        assert code == 1
        assert "not found in schema" in err

    def test_no_subcommand_is_an_error(self):
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 2


# ── metadata ─────────────────────────────────────────────────────────


class TestCliMetadata:
    def test_version_flag_reports_the_package_version(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0
        assert capsys.readouterr().out.strip() == __version__

    def test_entry_point_is_declared(self):
        """The console script must point at this module's main()."""
        import tomllib

        root = Path(__file__).resolve().parents[1]
        with (root / "pyproject.toml").open("rb") as fh:
            pyproject = tomllib.load(fh)
        scripts = pyproject["project"]["scripts"]
        assert scripts["linkml-mermaid"] == "linkml_mermaid.cli:main"
