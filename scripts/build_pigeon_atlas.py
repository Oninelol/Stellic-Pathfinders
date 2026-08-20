#!/usr/bin/env python3
"""Pack the pigeon's hand-drawn frames into the sprite atlas the app embeds.

The 121 source WebPs are 840x882 and total ~14.6 MB — inlining them one by one
as data: URLs would add ~19 MB of base64 to a bundle that is otherwise 1.5 MB.
Packing them into a single atlas and downscaling to the size the pigeon is
actually drawn at gets the same 121 frames down to ~1.35 MB (~1.8 MB base64),
which keeps "Compass Planner.html" a single self-contained file.

Usage:
    python3 scripts/build_pigeon_atlas.py path/to/frames [out_dir]

Writes atlas.webp plus atlas.json ({cell, cols, rows, index}); `index` maps a
manifest filename (u001.webp) to its cell number, which is what the frontend
engine turns into a background-position.

Frames are cropped to ONE union bounding box, never per-frame: cropping each
frame to its own content would shift the bird between frames and make the
animation jitter.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image

CELL_WIDTH = 280      # the pigeon renders at 176px in the corner, 186px in the quiz
QUALITY = 75
COLS = 11


def build(src: Path, out: Path) -> None:
    files = sorted(src.glob("*.webp"))
    if not files:
        raise SystemExit(f"no .webp frames in {src}")

    box = None
    for f in files:
        b = Image.open(f).convert("RGBA").getbbox()
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]),
                                     max(box[2], b[2]), max(box[3], b[3]))

    w, h = box[2] - box[0], box[3] - box[1]
    cw, ch = CELL_WIDTH, round(h * CELL_WIDTH / w)
    rows = math.ceil(len(files) / COLS)

    atlas = Image.new("RGBA", (COLS * cw, rows * ch), (0, 0, 0, 0))
    index: dict[str, int] = {}
    for i, f in enumerate(files):
        cell = Image.open(f).convert("RGBA").crop(box).resize((cw, ch), Image.LANCZOS)
        atlas.paste(cell, ((i % COLS) * cw, (i // COLS) * ch))
        index[f.name] = i

    out.mkdir(parents=True, exist_ok=True)
    atlas.save(out / "atlas.webp", "WEBP", quality=QUALITY, method=6)
    (out / "atlas.json").write_text(json.dumps(
        {"cell": [cw, ch], "cols": COLS, "rows": rows, "index": index}), encoding="utf-8")

    size = (out / "atlas.webp").stat().st_size
    print(f"{len(files)} frames -> {atlas.size[0]}x{atlas.size[1]} atlas, "
          f"{size / 1024 / 1024:.2f} MB ({size * 4 / 3 / 1024 / 1024:.2f} MB as base64)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    build(Path(sys.argv[1]), Path(sys.argv[2] if len(sys.argv) > 2 else "build/pigeon"))
