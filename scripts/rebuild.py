#!/usr/bin/env python3
"""Round-trip the app source out of and back into the bundled HTML.

The bundle keeps the entire app in a <script type="__bundler/template"> block as a
single JSON-escaped string. Editing that string in place corrupts the escaping, so:

    python3 scripts/rebuild.py extract   # bundle -> build/template.html
    python3 scripts/rebuild.py embed     # build/template.html -> bundle

Only the one line holding the template string is rewritten. The manifest block and
every other byte of the file are passed through untouched.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "Compass Planner.html"
TEMPLATE = ROOT / "build" / "template.html"
MARKER = '<script type="__bundler/template">'


def _split():
    """Return (lines, index of the line holding the JSON template string)."""
    lines = BUNDLE.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if MARKER in line:
            # The payload is the next line; it is the whole JSON string literal.
            return lines, i + 1
    raise SystemExit(f"no {MARKER} block found in {BUNDLE}")


def extract():
    lines, idx = _split()
    source = json.loads(lines[idx])
    TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATE.write_text(source, encoding="utf-8")
    print(f"extracted {len(source)} chars -> {TEMPLATE.relative_to(ROOT)}")


def _encode(source):
    """Reproduce the bundler's own escaping, byte for byte.

    Two rules beyond plain json.dumps, both verified to round-trip the shipped file
    with a zero-byte diff:
      * non-ASCII (·, →, …) stays literal, so ensure_ascii=False
      * the slash of every "</" is escaped, so no closing tag inside the payload can
        terminate the enclosing <script> block early
    """
    return json.dumps(source, ensure_ascii=False).replace("</", "<\\u002F")


def embed():
    lines, idx = _split()
    source = TEMPLATE.read_text(encoding="utf-8")
    lines[idx] = _encode(source)
    BUNDLE.write_text("\n".join(lines), encoding="utf-8")
    print(f"embedded {len(source)} chars -> {BUNDLE.name}")


def verify():
    """Re-parse the bundle and confirm the template round-trips to the build file."""
    lines, idx = _split()
    embedded = json.loads(lines[idx])
    onDisk = TEMPLATE.read_text(encoding="utf-8")
    if embedded != onDisk:
        raise SystemExit("MISMATCH: bundle template != build/template.html")
    print(f"ok: bundle template parses and matches build/template.html ({len(embedded)} chars)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "extract":
        extract()
    elif cmd == "embed":
        embed()
    elif cmd == "verify":
        verify()
    else:
        raise SystemExit("usage: rebuild.py extract|embed|verify")
