"""Reference implementations used as oracles by the conformance tests.

The rest of the suite checks that the renderers produce the text we
intend.  That is circular: if our reading of a specification is wrong,
the expected strings are wrong in exactly the same way.  The tests built
on this module close that loop by handing the output to the software the
specification describes — Mermaid itself, and cmark-gfm, the library
GitHub's own Markdown rendering is built on — and asking what it makes
of it.

Both oracles are optional.  When Node, the Mermaid package or
``cmarkgfm`` is unavailable the dependent tests skip rather than fail, so
a contributor can work without the JavaScript toolchain; CI installs
both, so the gate is enforced there.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import subprocess
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MERMAID_ORACLE = REPO_ROOT / "tests" / "oracle" / "mermaid_oracle.mjs"
NODE_MODULES = REPO_ROOT / "node_modules"

# CI sets this so that a missing Node or cmark-gfm fails the build
# instead of quietly skipping the whole conformance suite and still
# reporting green -- the one outcome the conformance job exists to
# prevent.
REQUIRE_ORACLES = os.environ.get("LINKML_MERMAID_REQUIRE_ORACLES") == "1"


def _unavailable(reason: str) -> None:
    """Skip, or fail when the environment demands a working oracle."""
    if REQUIRE_ORACLES:
        pytest.fail(f"{reason} (LINKML_MERMAID_REQUIRE_ORACLES=1)")
    pytest.skip(reason)


# ── Mermaid ──────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _mermaid_unavailable() -> str | None:
    """Return why the Mermaid oracle cannot run, or *None* if it can."""
    if shutil.which("node") is None:
        return "node is not installed"
    if not (NODE_MODULES / "mermaid").is_dir():
        return "mermaid is not installed (run: pnpm install)"
    if not (NODE_MODULES / "jsdom").is_dir():
        return "jsdom is not installed (run: pnpm install)"
    return None


def requires_mermaid() -> None:
    """Skip the calling test unless the real Mermaid parser is available."""
    reason = _mermaid_unavailable()
    if reason:
        _unavailable(f"Mermaid oracle unavailable: {reason}")


@lru_cache(maxsize=1)
def _oracle_process() -> subprocess.Popen[str]:
    """Start the Mermaid oracle once and keep it for the whole session.

    Importing Mermaid costs seconds, which a few hundred parametrised
    cases cannot pay per test, so the process is cached and talked to
    over a line-delimited protocol.
    """
    requires_mermaid()
    proc = subprocess.Popen(
        ["node", str(MERMAID_ORACLE)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        bufsize=1,
    )
    atexit.register(_stop_oracle, proc)
    handshake = proc.stdout.readline() if proc.stdout else ""
    if '"ready"' not in handshake:
        stderr = proc.stderr.read() if proc.stderr else ""
        pytest.fail(f"Mermaid oracle failed to start:\n{stderr[-4000:]}")
    return proc


def _stop_oracle(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        if proc.stdin:
            proc.stdin.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def mermaid_check(
    cases: dict[str, str], *, render: bool = False, timeout: float = 120.0
) -> dict[str, dict[str, Any]]:
    """Run ``{case_id: diagram_text}`` through Mermaid.

    Parameters:
        render: Also draw each diagram and capture the text Mermaid put
            on screen, which is how an escape sequence is proven to
            arrive as the character it encodes.  Rendering is much
            slower than parsing, so it is opt-in.
        timeout: Seconds to wait for the batch.  Some inputs wedge
            Mermaid-under-jsdom during ``render`` and never produce a
            reply — an unbounded read would hang pytest until the CI job
            hit its own limit hours later, so the wait is bounded and a
            timeout is reported as a failure naming the cases.

    Returns:
        ``{case_id: {"ok": bool, "error": str | None,
        "visible_text": str | None}}``.
    """
    proc = _oracle_process()
    payload = [{"id": k, "text": v, "render": render} for k, v in cases.items()]
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()

    # readline() has no timeout, so it runs on a worker thread the main
    # thread can abandon.
    reply: list[str] = []
    reader = threading.Thread(target=lambda: reply.append(proc.stdout.readline()), daemon=True)  # type: ignore[union-attr]
    reader.start()
    reader.join(timeout)

    if reader.is_alive():
        proc.kill()
        _oracle_process.cache_clear()
        pytest.fail(
            f"Mermaid oracle did not answer within {timeout}s for "
            f"{sorted(cases)!r} (render={render}); the process was killed."
        )
    line = reply[0] if reply else ""
    if not line:
        stderr = proc.stderr.read() if proc.stderr else ""
        _oracle_process.cache_clear()
        pytest.fail(f"Mermaid oracle died:\n{stderr[-4000:]}")
    return {
        r["id"]: {"ok": r["ok"], "error": r["error"], "visible_text": r["visibleText"]}
        for r in json.loads(line)
    }


def assert_parses(cases: dict[str, str], *, render: bool = False) -> dict[str, dict[str, Any]]:
    """Assert every diagram in *cases* compiles, reporting all failures."""
    results = mermaid_check(cases, render=render)
    broken = {k: v["error"] for k, v in results.items() if not v["ok"]}
    if broken:
        detail = "\n".join(f"  {k}: {err}\n{cases[k]}" for k, err in broken.items())
        raise AssertionError(f"Mermaid rejected {len(broken)} of {len(cases)} diagrams:\n{detail}")
    return results


# ── GFM ──────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _cmark() -> Any:
    try:
        import cmarkgfm
        from cmarkgfm.cmark import Options
    except ImportError:
        return None
    return (cmarkgfm, Options)


def requires_cmark() -> None:
    """Skip the calling test unless cmark-gfm is available."""
    if _cmark() is None:
        _unavailable("cmark-gfm oracle unavailable: pip install cmarkgfm")


def gfm_to_html(markdown: str) -> str:
    """Render *markdown* exactly as GitHub's own parser would.

    ``CMARK_OPT_UNSAFE`` keeps raw HTML in the output instead of
    replacing it with a comment.  That is deliberate: a test needs to see
    whether a cell value *could* inject markup, and the safe mode would
    hide the very thing being checked.
    """
    requires_cmark()
    cmarkgfm, options = _cmark()
    return str(
        cmarkgfm.github_flavored_markdown_to_html(markdown, options=options.CMARK_OPT_UNSAFE)
    )


_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_INLINE_TAG_RE = re.compile(r"</?(strong|em|code|a)\b[^>]*>")
_BR_RE = re.compile(r"<br\s*/?>")


def table_cells(markdown: str) -> list[str]:
    """Return the raw inner HTML of every cell in the first rendered table."""
    return _CELL_RE.findall(gfm_to_html(markdown))


def cell_text(cell_html: str) -> str:
    """Reduce a rendered cell to the text a reader would see.

    The wrappers a column format is *supposed* to produce are stripped,
    ``<br>`` becomes a newline, and character references are resolved, so
    what remains can be compared against the value that was put in.
    """
    text = _INLINE_TAG_RE.sub("", cell_html)
    text = _BR_RE.sub("\n", text)
    for entity, char in (
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
        ("&amp;", "&"),
    ):
        text = text.replace(entity, char)
    return text


def render_single_row(cells: list[str]) -> str:
    """Wrap pre-rendered cells in the smallest valid GFM §4.10 table.

    A trailing sentinel column is included by the callers so that a cell
    which leaks an unescaped pipe shows up as a changed cell *count*
    rather than merely changed text.
    """
    headers = " | ".join(f"h{i}" for i in range(len(cells)))
    delimiters = " | ".join("---" for _ in cells)
    body = " | ".join(cells)
    return f"| {headers} |\n| {delimiters} |\n| {body} |\n"
