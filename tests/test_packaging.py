"""Tests for what actually gets published.

The audit that preceded this release found confidential material inside
a test file that the sdist was shipping. The file has been rewritten,
but rewriting one file does not stop the next one. These tests assert
the shape of the distribution itself: an allowlist, verified by
building, so a new development file cannot reach PyPI by accident.

Building is slow, so the artefacts are built once per session.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Build the real sdist and wheel into a scratch directory."""
    out = tmp_path_factory.mktemp("dist")
    result = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(out), str(REPO_ROOT)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"cannot build distributions here: {result.stderr[-500:]}")
    sdist = next(out.glob("*.tar.gz"), None)
    wheel = next(out.glob("*.whl"), None)
    if sdist is None or wheel is None:
        pytest.skip("build produced no artefacts")
    return {"sdist": sdist, "wheel": wheel}


@pytest.fixture(scope="session")
def sdist_names(built: dict[str, Path]) -> list[str]:
    with tarfile.open(built["sdist"]) as tar:
        # Strip the "linkml_mermaid-0.1.0/" prefix.
        return [n.partition("/")[2] for n in tar.getnames() if "/" in n]


@pytest.fixture(scope="session")
def wheel_names(built: dict[str, Path]) -> list[str]:
    with zipfile.ZipFile(built["wheel"]) as zf:
        return zf.namelist()


class TestNothingPrivateIsPublished:
    """The release blocker that started this: development files, and the
    material inside them, must not reach PyPI."""

    @pytest.mark.parametrize(
        "forbidden",
        ["tests/", "scripts/", ".github/", "docs/.vitepress/", "uv.lock"],
    )
    def test_sdist_excludes_development_files(self, sdist_names: list[str], forbidden: str):
        offenders = [n for n in sdist_names if n.startswith(forbidden)]
        assert not offenders, f"sdist ships {forbidden}: {offenders}"

    def test_sdist_is_an_allowlist_not_a_denylist(self):
        """`include` enumerates what ships. A denylist would let the next
        new directory through silently."""
        text = PYPROJECT.read_text(encoding="utf-8")
        section = text.split("[tool.hatch.build.targets.sdist]")[1]
        assert "include = [" in section
        assert "exclude" not in section.split("[", 2)[0]

    def test_wheel_contains_only_the_package(self, wheel_names: list[str]):
        for name in wheel_names:
            assert name.startswith(("linkml_mermaid/", "linkml_mermaid-")), (
                f"wheel ships unexpected path {name}"
            )

    def test_every_host_referenced_in_the_sdist_is_a_public_one(self, built: dict[str, Path]):
        """A belt-and-braces scan of the shipped bytes, not just the
        file names.

        This is an allowlist of hosts rather than a denylist of private
        ones: a denylist would have to name the very infrastructure it
        is protecting, and would miss the next host nobody thought of.
        """
        allowed = {
            "github.com",
            "raw.githubusercontent.com",
            "github.github.com",
            "ascs-ev.github.io",
            "mermaid.js.org",
            "linkml.io",
            "pypi.org",
            "docs.pypi.org",
            "opensource.org",
            "semver.org",
            "keepachangelog.com",
            "spdx.org",
            "docs.astral.sh",
            "peps.python.org",
            "creativecommons.org",
            "www.apache.org",
            "json-schema.org",
            "w3id.org",
            "example.org",
            "example.com",
        }
        host_re = re.compile(r"https?://([A-Za-z0-9.-]+)")
        email_re = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")

        offenders: dict[str, set[str]] = {}
        with tarfile.open(built["sdist"]) as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                handle = tar.extractfile(member)
                assert handle is not None
                body = handle.read().decode("utf-8", errors="replace")
                hosts = set(host_re.findall(body)) | set(email_re.findall(body))
                unknown = {h.lower() for h in hosts} - allowed
                if unknown:
                    offenders[member.name] = unknown

        assert not offenders, (
            f"the sdist references hosts that are not on the public allowlist: {offenders}"
        )


class TestEverythingNeededIsPublished:
    """An allowlist that is too tight is its own bug."""

    @pytest.mark.parametrize(
        "required",
        [
            "README.md",
            "CHANGELOG.md",
            "LICENSE",
            "pyproject.toml",
            "src/linkml_mermaid/__init__.py",
            "src/linkml_mermaid/py.typed",
            "src/linkml_mermaid/vocab/mermaid_annotations.yaml",
            "docs/standards/coverage.md",
            "docs/standards/manifest.json",
            "docs/standards/requirements.json",
        ],
    )
    def test_sdist_includes(self, sdist_names: list[str], required: str):
        assert required in sdist_names

    def test_wheel_ships_the_typing_marker(self, wheel_names: list[str]):
        """Without py.typed, every annotation in the package is invisible
        to a consumer's type checker."""
        assert "linkml_mermaid/py.typed" in wheel_names

    def test_wheel_ships_the_vocabulary_schema(self, wheel_names: list[str]):
        """VOCAB_SCHEMA_PATH points at this file at runtime; a wheel
        without it raises FileNotFoundError on a working install."""
        assert "linkml_mermaid/vocab/mermaid_annotations.yaml" in wheel_names

    def test_wheel_declares_the_console_script(self, built: dict[str, Path]):
        with zipfile.ZipFile(built["wheel"]) as zf:
            name = next(n for n in zf.namelist() if n.endswith("entry_points.txt"))
            entry_points = zf.read(name).decode("utf-8")
        assert "[console_scripts]" in entry_points
        assert "linkml-mermaid = linkml_mermaid.cli:main" in entry_points

    def test_wheel_ships_the_licence(self, wheel_names: list[str]):
        assert any(n.endswith("licenses/LICENSE") for n in wheel_names)


class TestPublishedMetadata:
    """What PyPI will show, and what pip will enforce."""

    @pytest.fixture(scope="class")
    @staticmethod
    def metadata(built: dict[str, Path]) -> str:
        with zipfile.ZipFile(built["wheel"]) as zf:
            name = next(n for n in zf.namelist() if n.endswith("METADATA"))
            return zf.read(name).decode("utf-8")

    def test_version_matches_the_package(self, metadata: str):
        from linkml_mermaid import __version__

        assert f"Version: {__version__}" in metadata

    def test_description_is_the_readme(self, metadata: str):
        assert "Description-Content-Type: text/markdown" in metadata
        assert "Why this exists" in metadata

    def test_project_urls_point_at_the_publishing_organisation(self, metadata: str):
        urls = re.findall(r"^Project-URL: .*$", metadata, re.MULTILINE)
        assert urls, "no Project-URL metadata"
        for url in urls:
            assert "ASCS-eV/linkml-mermaid" in url, f"unexpected URL: {url}"

    def test_licence_is_declared_with_an_spdx_expression(self, metadata: str):
        """PEP 639: a classifier alone is deprecated."""
        assert "License-Expression: MIT" in metadata
        assert "License :: OSI Approved" not in metadata

    def test_requires_python_is_declared(self, metadata: str):
        assert "Requires-Python: >=3.11" in metadata

    def test_runtime_dependencies_are_declared(self, metadata: str):
        requires = re.findall(r"^Requires-Dist: (\S+)", metadata, re.MULTILINE)
        names = {re.split(r"[<>=!~\[;]", r)[0].strip().lower() for r in requires}
        assert "linkml-runtime" in names
        assert "pyyaml" in names, "the CLI imports yaml at runtime"

    def test_runtime_dependencies_have_lower_bounds(self, metadata: str):
        """An unpinned floor lets pip resolve to a version too old to
        contain the API this package calls."""
        for requirement in re.findall(r"^Requires-Dist: (.+)$", metadata, re.MULTILINE):
            assert ">=" in requirement, f"{requirement} declares no minimum version"

    def test_development_tools_are_not_runtime_dependencies(self, metadata: str):
        requires = re.findall(r"^Requires-Dist: (\S+)", metadata, re.MULTILINE)
        names = {re.split(r"[<>=!~\[;]", r)[0].strip().lower() for r in requires}
        for tool in ("pytest", "ruff", "mypy", "build", "twine"):
            assert tool not in names, f"{tool} must not be a runtime dependency"
