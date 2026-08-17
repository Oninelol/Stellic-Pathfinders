#!/usr/bin/env python3
"""Build site/planner-new-app.html from the untouched root bundle.

Reads "Compass Planner.html" (never writes it), pulls the app source out of the
<script type="__bundler/template"> line with json.loads, applies the patches
below, re-encodes exactly the way the bundler does (json.dumps ensure_ascii=False
then "</" -> "<\\u002F") and writes the result to site/planner-new-app.html.
Every patch asserts it matched exactly once, so a drift in the upstream source is
a hard failure rather than a silent no-op.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve()
ROOT = Path(r"C:\Users\linfe\Desktop\careerplanner")
BUNDLE = ROOT / "Compass Planner.html"          # read-only
OUT = ROOT / "site" / "planner-new-app.html"     # our copy
MARKER = '<script type="__bundler/template">'

PATCHES = []


def patch_later(old, new, label):
    """Appended after the packing patches so anchors are matched in order."""
    PATCHES.append((old, new, label))


def patch(old, new, label):
    PATCHES.append((old, new, label))


# ------------------------------------------------------- 0. gutter + pill width ---
# The left meta column (year / semester / term / status / credits, plus an issue
# or blocked button when the term has one) was drawn for a 124px gutter and only
# gets META-30 = 94px of it. Widen the gutter and let the pills give the width
# back: the floor drops from 126 to 112 so PW can actually shrink.
# MH0/MHB are the measured heights of that column — 113px, and 145px when it
# carries a button — and they become the block's minimum height below.
patch(
    "const COLS = 5, META = 124, PADR = 16, CG = 18, PH = 66, RG = 14, "
    "PADT = 18, PADB = 18, GAPB = 58;",
    "const COLS = 5, META = 160, PADR = 16, CG = 18, PH = 66, RG = 14, "
    "PADT = 18, PADB = 18, GAPB = 58, MH0 = 113, MHB = 32;",
    "wider meta gutter",
)

patch(
    "const PW = Math.max(126, Math.floor((cw - META - PADR - (COLS - 1) * CG) / COLS));",
    "const PW = Math.max(112, Math.floor((cw - META - PADR - (COLS - 1) * CG) / COLS));",
    "narrower course pills",
)

# ---------------------------------------------------------------- 1. packing ---
# Courses sit in rows inside their block: one row whenever they fit, and when
# they do not, a brick wall. Long rows hold `top`, the rows between them hold one
# fewer, and every row is centred on the same span — so a course on the lower row
# centres over the gap between two courses above it. `rows` still drives coursesH
# and the block height, so a block that now needs one row instead of two gets
# shorter and the stack closes up behind it.
patch(
    "      const rows = Math.max(...tm.courses.map(c => c.row)) + 1;",
    "      const STEP = PW + CG;\n"
    "      const packed = tm.courses.map((c, k) => ({ c, k })).sort((p, q) => "
    "(p.c.row - q.c.row) || (p.c.col - q.c.col) || (p.k - q.k)).map(o => o.c);\n"
    "      const nC = packed.length;\n"
    "      const cap = (r, p) => Math.ceil(r / 2) * p + Math.floor(r / 2) * (p - 1);\n"
    "      let rows = 1, per = Math.min(COLS, nC);\n"
    "      while (cap(rows, per) < nC) {\n"
    "        rows += 1;\n"
    "        per = Math.max(2, Math.min(COLS, Math.ceil((nC + Math.floor(rows / 2)) / rows)));\n"
    "      }\n"
    "      const slots = Array.from({ length: rows }, (_, r) => r % 2 ? per - 1 : per);\n"
    "      const counts = slots.map(() => 0);\n"
    "      for (let left = nC, r = 0; left > 0; r = (r + 1) % rows) {\n"
    "        if (counts[r] < slots[r]) { counts[r] += 1; left -= 1; }\n"
    "      }",
    "brick rows",
)

# Placement follows those row counts. Each row is a run of adjacent cells on the
# one grid step (PW + CG), centred across the block's full column span; the
# one-fewer row therefore lands exactly half a step over, which is the offset.
patch(
    "      tm.courses.forEach(c => { const cy0 = y + PADT + c.row * (PH + RG); "
    "G[c.c] = { x: px(c.col), y: cy0, cx: px(c.col) + PW / 2, cy: cy0 + PH / 2, "
    "r: px(c.col) + PW, b: cy0 + PH, col: c.col, term: i }; });",
    "      const SPAN = COLS * STEP - CG;\n"
    "      const xEven = px(0) + (SPAN - (per * STEP - CG)) / 2;\n"
    "      let ci = 0;\n"
    "      counts.forEach((m, r) => {\n"
    "        const base = xEven + (r % 2 ? STEP / 2 : 0);\n"
    "        const x0 = base + Math.floor((slots[r] - m) / 2) * STEP;\n"
    "        const cy0 = y + PADT + r * (PH + RG);\n"
    "        for (let j = 0; j < m; j++, ci++) {\n"
    "          const c = packed[ci], cx0 = x0 + j * STEP;\n"
    "          G[c.c] = { x: cx0, y: cy0, cx: cx0 + PW / 2, cy: cy0 + PH / 2, "
    "r: cx0 + PW, b: cy0 + PH, col: j, term: i };\n"
    "        }\n"
    "      });",
    "brick placement",
)

# ------------------------------------------------------------ 3. block height ---
# A block is now the taller of what its course rows need and what the meta column
# needs, so a one-row block no longer clips the text on its left. The rows are
# then centred in whatever height the block ends up with, rather than hugging the
# top and leaving the slack at the bottom.
patch(
    "      const coursesH = rows * PH + (rows - 1) * RG;\n"
    "      const h = PADT + coursesH + warnH + PADB;",
    "      const coursesH = rows * PH + (rows - 1) * RG;\n"
    "      const metaH = MH0 + (iss.length || blk.length ? MHB : 0);\n"
    "      const boxH = Math.max(PADT + coursesH + PADB, PADT + metaH + PADB);\n"
    "      const yOff = (boxH - PADT - PADB - coursesH) / 2;\n"
    "      const h = boxH + warnH;",
    "block height fits the meta column",
)

patch(
    "        const cy0 = y + PADT + r * (PH + RG);\n",
    "        const cy0 = y + PADT + yOff + r * (PH + RG);\n",
    "centre the rows in the block",
)

patch(
    "warnTop: PADT + coursesH + 12 });",
    "warnTop: PADT + yOff + coursesH + 12 });",
    "warning panel follows the rows",
)

# ------------------------------------------------------------------ 2. edges ---
# At rest there is no strand, so not one route is built. `.sort` on the empty
# list keeps the rest of the routing code identical.
patch(
    "    const els = [];\n    this.EDGES.map((e, i) => ({ e, i }))",
    "    const strand = sel ? chainSet : null;\n"
    "    const els = [];\n"
    "    (strand ? this.EDGES.map((e, i) => ({ e, i })) : [])",
    "edges gated on selection",
)

# Only routes wholly inside the selected strand exist — the off-strand ones are
# not drawn faintly, they are never created. This is also what holds the error
# routes back: a broken/anti edge appears only once its course is in the strand.
patch(
    "      const on = !chainSet || (chainSet.has(e.f) && chainSet.has(e.t));\n"
    "      const op = chainSet ? (on ? 1 : 0.05) : 0.14;\n"
    "      const w = chainSet && on ? 2.2 : 1.2;",
    "      if (!(strand.has(e.f) && strand.has(e.t))) return;\n"
    "      const op = 1;\n"
    "      const w = 2.2;",
    "strand-only routes",
)

# No routes, no <svg> either, so the board carries no edge layer at rest.
patch(
    "    const bEdges = React.createElement('svg', { width:STACK_W, height:stackH, "
    "viewBox:`0 0 ${STACK_W} ${stackH}`, style:{ position:'absolute', left:0, top:0, "
    "pointerEvents:'none', zIndex: chainSet ? 2 : 1, overflow:'visible' } }, els);",
    "    const bEdges = els.length ? React.createElement('svg', { width:STACK_W, height:stackH, "
    "viewBox:`0 0 ${STACK_W} ${stackH}`, style:{ position:'absolute', left:0, top:0, "
    "pointerEvents:'none', zIndex:2, overflow:'visible' } }, els) : null;",
    "no edge layer at rest",
)


def main():
    lines = BUNDLE.read_text(encoding="utf-8").split("\n")
    idx = next(i for i, l in enumerate(lines) if MARKER in l) + 1
    src = json.loads(lines[idx])
    before = len(src)

    for old, new, label in PATCHES:
        n = src.count(old)
        if n != 1:
            sys.exit(f"FAIL [{label}]: anchor matched {n} times, expected 1")
        src = src.replace(old, new)
        print(f"ok   [{label}]")

    lines[idx] = json.dumps(src, ensure_ascii=False).replace("</", "<\\u002F")
    OUT.write_text("\n".join(lines), encoding="utf-8")

    # round-trip: the file we just wrote must parse back to exactly what we meant
    check = OUT.read_text(encoding="utf-8").split("\n")
    j = next(i for i, l in enumerate(check) if MARKER in l) + 1
    assert json.loads(check[j]) == src, "round-trip mismatch"
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes); template {before} -> {len(src)} chars; round-trip ok")


if __name__ == "__main__":
    main()
