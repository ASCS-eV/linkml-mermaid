"""Tests that stop the documentation from making false claims.

Documentation drifts silently: a count in prose stays at 15 long after
the enum drops to 14, and nothing fails. These tests tie the prose to
the code, so a statement that stops being true stops the build.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from linkml_mermaid.types import (
    CELL_FORMATS,
    COLUMN_ALIGNMENTS,
    LINK_STYLES,
    NODE_SHAPES,
)
from linkml_mermaid.vocab import (
    ANNOTATION_KEYS,
    MERMAID_DIAGRAM_TYPES,
    MERMAID_ROLES,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
DOCS = REPO_ROOT / "docs"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestFactualClaims:
    """Every number and name the prose states must match the code."""

    @pytest.mark.parametrize("path", [README, DOCS / "annotations.md"])
    def test_every_role_is_documented(self, path: Path):
        text = read(path)
        for role in MERMAID_ROLES:
            assert f"`{role}`" in text, f"{path.name} does not document '{role}'"

    @pytest.mark.parametrize("path", [README, DOCS / "annotations.md"])
    def test_no_undocumented_role_is_invented(self, path: Path):
        """A table row naming a role that no longer exists is worse than
        a missing row: it sends the reader to write a schema that fails."""
        text = read(path)
        for match in re.finditer(r"mermaid_role: ([a-z_]+)", text):
            assert match.group(1) in MERMAID_ROLES, (
                f"{path.name} uses unknown mermaid_role '{match.group(1)}'"
            )

    @pytest.mark.parametrize("path", [README, CHANGELOG])
    def test_role_count_is_correct(self, path: Path):
        """The original CHANGELOG claimed 15 roles when there were 14."""
        text = read(path)
        counts = re.findall(r"(\d+)\s+`?mermaid_role`?\s+values", text)
        assert counts, f"{path.name} no longer states a role count"
        for count in counts:
            assert int(count) == len(MERMAID_ROLES)

    def test_changelog_does_not_claim_unimplemented_formats(self):
        """'Bold, code, and emoji formatting' was claimed; no emoji
        formatter has ever existed."""
        text = read(CHANGELOG).lower()
        assert "emoji" not in text, "CHANGELOG claims an emoji cell format"
        for fmt in CELL_FORMATS:
            assert f"`{fmt}`" in read(CHANGELOG)

    def test_documented_shapes_match_the_code(self):
        text = read(README)
        for shape in NODE_SHAPES:
            assert f"`{shape}`" in text, f"README does not document shape '{shape}'"

    @pytest.mark.parametrize("path", [README, CHANGELOG, DOCS / "flowchart.md"])
    def test_documented_edge_styles_match_the_code(self, path: Path):
        text = read(path)
        for style in LINK_STYLES:
            assert f"`{style}`" in text or f"{style} (" in text, (
                f"{path.name} does not document edge style '{style}'"
            )

    def test_no_arrowless_link_feature_is_advertised(self):
        """Open links (---, -.-, ===) are a real Mermaid feature that
        this package does not emit. Claiming it would send a reader
        looking for a parameter that does not exist."""
        import inspect

        from linkml_mermaid import FlowchartEdge

        assert "arrow" not in inspect.signature(FlowchartEdge).parameters
        for path in [README, CHANGELOG, DOCS / "flowchart.md"]:
            assert "arrow=False" not in read(path), (
                f"{path.name} advertises an arrow parameter that does not exist"
            )

    def test_documented_alignments_match_the_code(self):
        text = read(CHANGELOG)
        for align in COLUMN_ALIGNMENTS:
            assert f"`{align}`" in text

    def test_annotation_keys_are_documented(self):
        text = read(DOCS / "annotations.md")
        for key in ANNOTATION_KEYS:
            assert f"`{key}`" in text

    def test_only_supported_diagram_types_are_advertised(self):
        text = read(README)
        assert frozenset({"stateDiagram-v2"}) == MERMAID_DIAGRAM_TYPES
        assert "`mermaid_diagram` accepts `stateDiagram-v2`" in text


class TestVersionConsistency:
    """The release workflow refuses to publish unless these agree."""

    def test_changelog_documents_the_current_version(self):
        from linkml_mermaid import __version__

        assert f"## [{__version__}]" in read(CHANGELOG)

    def test_version_matches_the_vocabulary_schema(self):
        from linkml_mermaid import __version__

        vocab = read(REPO_ROOT / "src" / "linkml_mermaid" / "vocab" / "mermaid_annotations.yaml")
        assert f"version: {__version__}" in vocab


class TestHonestPositioning:
    """The audit required that prior art be cited rather than ignored,
    and that limits be stated rather than implied."""

    @pytest.mark.parametrize("path", [README, DOCS / "index.md"])
    def test_prior_art_is_cited(self, path: Path):
        text = read(path)
        assert "linkml-renderer" in text, (
            f"{path.name} must cite linkml/linkml-renderer, the only other "
            "tool that renders LinkML instance data to Mermaid"
        )
        assert "linkml/linkml/issues/915" in text

    def test_readme_states_what_is_not_done(self):
        text = read(README)
        assert "What this package does not do" in text
        for limit in ("Composite states", "classDef", "Parser-level validation"):
            assert limit in text

    def test_readme_links_the_standards_record(self):
        text = read(README)
        assert "docs/standards/coverage.md" in text
        assert "docs/standards/README.md" in text


class TestDocsSiteMirrors:
    """Hand-copied content drifts. The changelog page must include the
    root file rather than duplicate it."""

    def test_changelog_page_includes_rather_than_copies(self):
        text = read(DOCS / "changelog.md")
        assert "<!--@include: ../CHANGELOG.md-->" in text
        assert "## [" not in text, "docs/changelog.md duplicates the changelog"

    def test_no_page_advertises_the_removed_dev_extra(self):
        """The dev dependencies moved to a PEP 735 group; `pip install
        -e '.[dev]'` no longer works and must not be documented."""
        for path in [README, *DOCS.glob("*.md"), REPO_ROOT / "CONTRIBUTING.md"]:
            assert ".[dev]" not in read(path), f"{path.name} documents a dead extra"
