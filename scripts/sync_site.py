#!/usr/bin/env python3
"""Copy the built bundle into the site's planner frame.

site/planner.html hosts the planner in an iframe, and site/README.md defines
site/planner-app.html as a byte-for-byte copy of the repo-root bundle. Nothing
enforced that, so the copy had drifted a long way behind — still branded
Compass, missing the catalogue and the pigeon frames. tests/test_site_sync.py
now fails when they differ; this is how you fix it.

    python3 scripts/sync_site.py       # or: make site-sync
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "Compass Planner.html"
FRAME = ROOT / "site" / "planner-app.html"


def sync() -> None:
    if not BUNDLE.exists():
        raise SystemExit(f"missing {BUNDLE.name} — run scripts/rebuild.py embed first")
    FRAME.parent.mkdir(parents=True, exist_ok=True)
    before = FRAME.stat().st_size if FRAME.exists() else 0
    shutil.copyfile(BUNDLE, FRAME)
    after = FRAME.stat().st_size
    print(f"site/planner-app.html  {before/1024/1024:.2f} MB -> {after/1024/1024:.2f} MB")


if __name__ == "__main__":
    sync()
