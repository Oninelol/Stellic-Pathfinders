#!/usr/bin/env python3
"""Produce the static site Cloudflare serves, in ``dist/``.

Two things have to happen that a plain file copy would not do:

* The bundle is named "Compass Planner.html" — a space in a URL path is a poor
  front door, so it is written out as ``index.html``.
* Served from Cloudflare, the page is NOT on the same origin as the API, so its
  same-origin default (``location.origin + /api``) would point at Cloudflare,
  where no API exists. The API's base URL is injected as ``window.COMPASS_API_BASE``,
  which the app already prefers over its default.

    python3 scripts/build_static.py                     # uses API_BASE_URL from env
    API_BASE_URL=https://example.vercel.app/api python3 scripts/build_static.py

Leaving API_BASE_URL unset is allowed and leaves the page on its own default —
useful only if you later serve the API from this same origin.
"""

from __future__ import annotations

import html
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "Compass Planner.html"
OUT = ROOT / "dist"


def build(api_base: str) -> Path:
    if not BUNDLE.exists():
        raise SystemExit(f"missing {BUNDLE.name} — run scripts/rebuild.py embed first")

    page = BUNDLE.read_text(encoding="utf-8")

    if api_base:
        # Set before any app code runs. json-ish quoting via html.escape keeps a
        # stray quote in the URL from breaking out of the script tag.
        safe = html.escape(api_base.rstrip("/"), quote=True)
        inject = f'<script>window.COMPASS_API_BASE = "{safe}";</script>'
        marker = "<head>"
        if marker not in page:
            raise SystemExit("could not find <head> to inject the API base into")
        page = page.replace(marker, marker + "\n" + inject, 1)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT / "index.html").write_text(page, encoding="utf-8")
    # Any unknown path serves the app rather than a bare Cloudflare 404.
    (OUT / "404.html").write_text(page, encoding="utf-8")

    size = (OUT / "index.html").stat().st_size
    print(f"dist/index.html  {size / 1024 / 1024:.2f} MB"
          f"  api_base={api_base or '(same origin)'}")
    return OUT


if __name__ == "__main__":
    build(os.environ.get("API_BASE_URL", "").strip())
    sys.exit(0)
