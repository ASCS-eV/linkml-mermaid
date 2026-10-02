"""Parity tests between the Python constants and the vocabulary schema.

``vocab/__init__.py`` declares the YAML schema to be "the canonical
source of truth", but nothing enforced that claim: the two copies were
free to drift, and they had.  These tests make the claim checkable.

Specification reference
-----------------------
LinkML §Annotations
    https://linkml.io/linkml/schemas/annotations.html
    Annotations are arbitrary key-value pairs, so the vocabulary is a
    convention this package defines rather than a metamodel construct —
    which is exactly why it has to be pinned down somewhere single.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import yaml

import linkml_mermaid
from linkml_mermaid import vocab

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def vocab_schema() -> dict:
    with vocab.VOCAB_SCHEMA_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def permissible(schema: dict, enum_name: str) -> set[str]:
    return set(schema["enums"][enum_name]["permissible_values"])


class TestVocabParity:
    """The Python constants must mirror the YAML enums exactly."""

    def test_schema_file_is_shipped(self):
        assert vocab.VOCAB_SCHEMA_PATH.is_file()

    def test_mermaid_roles_match(self, vocab_schema):
        assert permissible(vocab_schema, "MermaidRole") == vocab.MERMAID_ROLES

    def test_annotation_keys_match(self, vocab_schema):
        """``table_column`` existed only in Python before this test."""
        assert permissible(vocab_schema, "AnnotationKey") == vocab.ANNOTATION_KEYS

    def test_diagram_types_match(self, vocab_schema):
        assert permissible(vocab_schema, "MermaidDiagramType") == vocab.MERMAID_DIAGRAM_TYPES

    def test_every_role_constant_is_in_the_set(self):
        """A new ROLE_* constant must be added to MERMAID_ROLES too."""
        declared = {
            value
            for name, value in vars(vocab).items()
            if name.startswith("ROLE_") and isinstance(value, str)
        }
        assert declared == vocab.MERMAID_ROLES

    def test_every_permissible_value_has_a_description(self, vocab_schema):
        """LinkML §Basic Enums: enums should be a documented controlled
        vocabulary, not bare tokens."""
        for enum_name in ("MermaidRole", "MermaidDiagramType", "AnnotationKey"):
            values = vocab_schema["enums"][enum_name]["permissible_values"]
            for value_name, body in values.items():
                assert body and body.get("description"), (
                    f"{enum_name}.{value_name} has no description"
                )


class TestVocabVersionConsistency:
    """The vocabulary ships inside the package, so it versions with it."""

    def test_schema_version_matches_package_version(self, vocab_schema):
        assert str(vocab_schema["version"]) == linkml_mermaid.__version__

    def test_package_version_matches_pyproject(self):
        """The version is declared once, in ``__init__.py``.

        Hatchling reads it from there, so this test pins the wiring
        rather than a duplicated literal.
        """
        with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
            pyproject = tomllib.load(fh)
        assert "version" in pyproject["project"]["dynamic"]
        assert pyproject["tool"]["hatch"]["version"]["path"] == "src/linkml_mermaid/__init__.py"


class TestVocabNamespace:
    """The schema id must resolve to a namespace the project controls."""

    def test_id_is_under_the_publishing_organisation(self, vocab_schema):
        assert vocab_schema["id"].startswith("https://ascs-ev.github.io/linkml-mermaid")

    def test_default_prefix_expands_to_the_schema_namespace(self, vocab_schema):
        default_prefix = vocab_schema["default_prefix"]
        expansion = vocab_schema["prefixes"][default_prefix]
        assert expansion.rstrip("/") == vocab_schema["id"].rstrip("/")


class TestVocabIsUsedByDiscovery:
    """The constants must be the ones the reader actually looks for."""

    def test_reader_uses_the_annotation_key_constants(self):
        from linkml_mermaid import reader

        source = Path(reader.__file__).read_text(encoding="utf-8")
        for key in vocab.ANNOTATION_KEYS:
            assert key in source, f"{key} is declared but never read"
