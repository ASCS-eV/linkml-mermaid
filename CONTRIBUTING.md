# Contributing to linkml-mermaid

Thanks for your interest in improving `linkml-mermaid`. This document explains
how to set up a development environment, run the checks, and cut a release.

## Development setup

The project uses [uv](https://docs.astral.sh/uv/). `uv.lock` is committed, so
everyone and CI resolve the same dependency versions.

```bash
git clone git@github.com:ASCS-eV/linkml-mermaid.git
cd linkml-mermaid

uv sync --group dev
pre-commit install
```

The package uses the **src layout** (`src/linkml_mermaid/`). `uv sync` installs
it in editable mode, so `import linkml_mermaid` resolves to your working tree.

## Running the checks

These are exactly what CI runs:

```bash
uv run ruff check .                                  # lint
uv run ruff format --check .                         # formatting
uv run mypy --strict src                             # static type checking
uv run pytest --cov --cov-fail-under=95              # tests and coverage gate
uv run python scripts/check_standards.py             # standards record
```

`uv run python scripts/check_standards.py --verify-hashes` re-downloads each
pinned specification and compares it against `docs/standards/manifest.json`. It
needs network access, and a failure means an upstream text changed under a
clause this package quotes — re-read the clause, update the quote and the hash
together.

`pre-commit run --all-files` runs the hooks that also run on every commit.

## Coding conventions

- Target Python 3.11+ and keep the public API fully typed; the package ships
  `py.typed` and must stay clean under `mypy --strict`.
- **Cite the specification.** New rendering behaviour needs the clause it
  implements quoted in the docstring, an entry in
  `docs/standards/requirements.json`, and a test named there that proves it.
  Regenerate `docs/standards/coverage.md` with
  `uv run python scripts/check_standards.py --write-coverage`.
- **Fail loudly.** Invalid input raises `ValueError` with a message that says
  what was wrong and what was expected. Do not silently fall back to a default
  that produces malformed diagram text.
- **Never interpolate untrusted text.** Everything that reaches the output goes
  through `escaping.py`. New escaping behaviour belongs there, with a case added
  to `HOSTILE_INPUTS` in `tests/test_escaping.py` — that corpus is reused across
  the suite, so one addition widens coverage everywhere.
- Keep the Layer 1 renderers (`types`, `escaping`, `state_diagram`, `flowchart`,
  `markdown_table`) free of any LinkML dependency.
- If you change what the package claims, change `tests/test_docs.py` too. It
  asserts that the prose and the code agree.

## Releasing

Publishing uses PyPI [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
via OIDC. There is no API token in the repository, and releases cannot be pushed
from a laptop.

1. Update `__version__` in `src/linkml_mermaid/__init__.py` (the single source
   of truth; `pyproject.toml` reads it dynamically) and `version:` in
   `src/linkml_mermaid/vocab/mermaid_annotations.yaml`.
1. Add a dated `## [X.Y.Z]` section to `CHANGELOG.md`, following
   [Keep a Changelog](https://keepachangelog.com/).
1. Merge to `main` and let CI pass.
1. Publish a GitHub Release tagged `vX.Y.Z`.

`.github/workflows/publish.yml` then re-runs the full check suite and refuses to
publish unless the tag, `__version__` and the `CHANGELOG.md` heading all agree.

## Versioning

This project follows [Semantic Versioning](https://semver.org/).
