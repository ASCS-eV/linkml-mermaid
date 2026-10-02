"""Verify the standards manifest and requirements map.

Run with no arguments to check; run with ``--write-coverage`` to
regenerate ``docs/standards/coverage.md``.

Three things are checked:

1. Every requirement names a standard that the manifest pins.
2. Every implemented requirement names code and at least one test, and
   the named test files exist.
3. Every pinned standard still hashes to the bytes recorded when the
   implementation was written (``--verify-hashes``, network required).

The third check is what makes the quoted clauses in the source
trustworthy: if a living specification changes under us, CI says so
rather than leaving the docstrings quietly wrong.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

STANDARDS_DIR = Path(__file__).resolve().parents[1] / "docs" / "standards"
REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = STANDARDS_DIR / "manifest.json"
REQUIREMENTS = STANDARDS_DIR / "requirements.json"
COVERAGE = STANDARDS_DIR / "coverage.md"


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def check_code_target(rid: str, target: str | None) -> list[str]:
    """A citation that points at a renamed symbol is worse than none.

    ``target`` is ``path/to/module.py`` or ``path/to/module.py::symbol``.
    """
    if not target:
        return []
    path, _, symbol = target.partition("::")
    source_file = REPO_ROOT / path
    if not source_file.is_file():
        return [f"{rid}: code file '{path}' does not exist"]
    if symbol:
        source = source_file.read_text(encoding="utf-8")
        # Targets may be dotted (``Class.method``); the final segment is
        # what the file actually defines.
        leaf = symbol.rsplit(".", 1)[-1]
        patterns = (
            f"def {leaf}(",
            f"class {leaf}",
            f"{leaf} =",
            f"{leaf}:",
        )
        if not any(p in source for p in patterns):
            return [f"{rid}: '{path}' defines no '{symbol}'"]
    return []


def check_test_target(rid: str, target: str) -> list[str]:
    """Verify the named test still exists under that name."""
    path, _, node = target.partition("::")
    test_file = REPO_ROOT / path
    if not test_file.is_file():
        return [f"{rid}: test file '{path}' does not exist"]
    if node:
        source = test_file.read_text(encoding="utf-8")
        name = node.split("::")[0]
        if f"class {name}" not in source and f"def {name}(" not in source:
            return [f"{rid}: '{path}' defines no '{name}'"]
    return []


def check_structure(manifest: dict, requirements: dict) -> list[str]:
    errors: list[str] = []
    known = {s["id"] for s in manifest["standards"]}
    anchors = {s["id"]: set(s.get("anchors", {})) for s in manifest["standards"]}

    seen: set[str] = set()
    for req in requirements["requirements"]:
        rid = req["id"]
        if rid in seen:
            errors.append(f"{rid}: duplicate requirement id")
        seen.add(rid)

        std = req["standard"]
        if std not in known:
            errors.append(f"{rid}: unknown standard '{std}'")
            continue

        anchor = req.get("anchor")
        if anchor and anchor not in anchors[std]:
            errors.append(f"{rid}: anchor '{anchor}' is not pinned for '{std}'")

        if req["implemented"]:
            if not req.get("code"):
                errors.append(f"{rid}: implemented but names no code")
            errors += check_code_target(rid, req.get("code"))
            for test in req.get("tests") or []:
                errors += check_test_target(rid, test)
            if not req.get("tests"):
                errors.append(f"{rid}: implemented but names no test")
        elif not req.get("reason"):
            errors.append(f"{rid}: not implemented but gives no reason")

    return errors


def check_hashes(manifest: dict) -> list[str]:
    errors: list[str] = []
    for std in manifest["standards"]:
        expected = std.get("sha256")
        if not expected:
            continue
        try:
            with urllib.request.urlopen(std["source_url"], timeout=60) as resp:
                body = resp.read()
        except OSError as exc:
            errors.append(f"{std['id']}: cannot fetch {std['source_url']}: {exc}")
            continue
        actual = hashlib.sha256(body).hexdigest()
        if actual != expected:
            errors.append(
                f"{std['id']}: specification text has changed since "
                f"{std['retrieved_at']}\n"
                f"    pinned: {expected}\n"
                f"    actual: {actual}\n"
                f"    Re-read the clauses quoted in the source, update the "
                f"implementation if needed, then re-pin the hash."
            )
            continue
        errors += check_anchors(std, body)
    return errors


def check_anchors(std: dict, body: bytes) -> list[str]:
    """Every pinned anchor must be a real heading in the source text.

    The anchors become links in ``coverage.md``; an invented one sends a
    reader to the top of a page and quietly undermines the citation.
    Only markdown sources can be checked this way.
    """
    if not std["source_url"].endswith(".md"):
        return []
    text = body.decode("utf-8", errors="replace")
    real = {
        re.sub(r"\s+", "-", re.sub(r"[^a-z0-9\s-]", "", m.group(1).lower()).strip())
        for m in re.finditer(r"^#{1,6}\s+(.+?)\s*$", text, re.MULTILINE)
    }
    return [
        f"{std['id']}: anchor '{anchor}' is not a heading in {std['source_url']}"
        for anchor in std.get("anchors", {})
        if anchor not in real
    ]


def _cell(text: str) -> str:
    """Escape one table cell.

    The requirement prose quotes specification syntax verbatim, so it is
    full of characters that are themselves markup. Three layers have to be
    satisfied at once:

    * GFM tables end a cell at an unescaped ``|``.
    * Markdown would read ``*text*`` as emphasis and swallow the asterisks
      the clause is actually about.
    * VitePress compiles the rendered HTML as a Vue template, where ``<<fork>>``
      parses as an unclosed ``<fork>`` element and ``{{}}`` as an interpolation.

    ``<`` and ``{`` are written as numeric character references, which Markdown
    renders back to the literal character without Vue ever seeing a tag or a
    moustache. Everything else is backslash-escaped, which both GFM and
    VitePress honour.
    """
    for literal, escaped in (
        ("|", r"\|"),
        ("*", r"\*"),
        ("_", r"\_"),
        ("<", "&#60;"),
        (">", "&#62;"),
        ("{", "&#123;"),
        ("}", "&#125;"),
    ):
        text = text.replace(literal, escaped)
    return text


def render_coverage(manifest: dict, requirements: dict) -> str:
    titles = {s["id"]: s["title"] for s in manifest["standards"]}
    authority = {s["id"]: s["authority"] for s in manifest["standards"]}
    anchors = {s["id"]: s.get("anchors", {}) for s in manifest["standards"]}

    lines = [
        "# Standards coverage",
        "",
        "<!-- Generated by scripts/check_standards.py; do not edit by hand. -->",
        "",
        "This table is the package's honest account of what it implements.",
        "Rows marked *not implemented* are constructs the specifications",
        "define that this package deliberately does not emit — they are",
        "listed so the omission is a documented decision rather than a",
        "silent gap.",
        "",
        "Each clause links to the section of the specification that defines",
        "it. The hash recorded below is of the exact text that was read.",
        "",
    ]

    for std in manifest["standards"]:
        sid = std["id"]
        rows = [r for r in requirements["requirements"] if r["standard"] == sid]
        if not rows:
            continue
        lines += [
            f"## {titles[sid]}",
            "",
            f"- Authority: <{authority[sid]}>",
            f"- Edition pinned: {std['edition']}",
            f"- Retrieved: {std['retrieved_at']}",
            f"- Licence: {std['license']}",
            f"- SHA-256: `{std['sha256']}`"
            if std.get("sha256")
            else f"- SHA-256: not pinned — {std.get('note', '')}",
            "",
            "| Clause | Requirement | Status | Implementation |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for req in rows:
            status = "implemented" if req["implemented"] else "**not** implemented"
            detail = req.get("code") or req.get("reason", "")
            clause = _cell(req["clause"])
            fragment = anchors[sid].get(req.get("anchor", ""))
            if fragment:
                clause = f"[{clause}]({authority[sid]}{fragment})"
            text = _cell(req["requirement"])
            detail = _cell(detail)
            lines.append(f"| {clause} | {text} | {status} | {detail} |")
        lines.append("")

    implemented = sum(1 for r in requirements["requirements"] if r["implemented"])
    total = len(requirements["requirements"])
    lines += [
        "## Summary",
        "",
        f"{implemented} of {total} catalogued clauses are implemented; "
        f"{total - implemented} are documented non-claims.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-coverage", action="store_true")
    parser.add_argument(
        "--verify-hashes",
        action="store_true",
        help="Re-download each pinned specification and compare hashes.",
    )
    args = parser.parse_args(argv)

    manifest = load(MANIFEST)
    requirements = load(REQUIREMENTS)

    errors = check_structure(manifest, requirements)
    if args.verify_hashes:
        errors += check_hashes(manifest)

    coverage = render_coverage(manifest, requirements)
    if args.write_coverage:
        COVERAGE.write_text(coverage + "\n", encoding="utf-8")
        print(f"wrote {COVERAGE}")
    elif COVERAGE.is_file():
        current = COVERAGE.read_text(encoding="utf-8")
        if current != coverage + "\n":
            errors.append(
                "docs/standards/coverage.md is out of date; "
                "run: python scripts/check_standards.py --write-coverage"
            )

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
