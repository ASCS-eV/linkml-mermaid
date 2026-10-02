# Contributing

The canonical guide lives in
[`CONTRIBUTING.md`](https://github.com/ASCS-eV/linkml-mermaid/blob/main/CONTRIBUTING.md);
this page summarises it.

## Development setup

The project uses [uv](https://docs.astral.sh/uv/), and `uv.lock` is committed so
that everyone and CI resolve identical versions.

```bash
git clone git@github.com:ASCS-eV/linkml-mermaid.git
cd linkml-mermaid

uv sync --group dev
pre-commit install
```

## Running the checks

These are exactly what CI runs:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src
uv run pytest --cov --cov-fail-under=95
uv run python scripts/check_standards.py
```

Add `--verify-hashes` to the last one to re-download each pinned specification
and confirm the quoted clauses have not changed upstream.

## Coding conventions

- Target Python 3.11+ and keep the public API fully typed; the package ships
  `py.typed` and must stay clean under `mypy --strict`.
- **Cite the specification.** New rendering behaviour needs the clause quoted in
  the docstring, an entry in `docs/standards/requirements.json`, and a named
  test that proves it.
- **Fail loudly.** Invalid input raises `ValueError` rather than degrading into
  malformed diagram text.
- **Never interpolate untrusted text** — everything reaching the output goes
  through `escaping.py`, and new cases belong in the shared `HOSTILE_INPUTS`
  corpus.
- Keep the Layer 1 renderers free of any LinkML dependency.

## Releasing

Publishing uses PyPI Trusted Publishing via OIDC; there is no API token in the
repository.

1. Update `__version__` in `src/linkml_mermaid/__init__.py` and `version:` in
   the vocabulary schema.
1. Add a dated section to [`CHANGELOG.md`](/changelog).
1. Merge to `main` and let CI pass.
1. Publish a GitHub Release tagged `vX.Y.Z`. The publish workflow refuses to
   proceed unless the tag, `__version__` and the changelog heading agree.

## Documentation

This site is built with [VitePress](https://vitepress.dev/):

```bash
pnpm install
pnpm docs:dev        # local preview at http://localhost:5173
pnpm docs:build      # production build into docs/.vitepress/dist
```
