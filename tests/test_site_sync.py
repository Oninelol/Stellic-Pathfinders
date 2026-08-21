"""The site's iframe copy of the planner must match the built bundle.

site/README.md defines site/planner-app.html as a byte-for-byte copy of the
repo-root bundle, but nothing checked it, and it silently fell nearly two
megabytes behind — the deployed site would have served a stale app. Run
`make site-sync` (scripts/sync_site.py) when this fails.
"""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "Compass Planner.html"
FRAME = ROOT / "site" / "planner-app.html"


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_site_planner_frame_matches_the_bundle():
    assert BUNDLE.exists(), "the built bundle is missing"
    assert FRAME.exists(), "site/planner-app.html is missing"
    assert _digest(FRAME) == _digest(BUNDLE), (
        "site/planner-app.html has drifted from the bundle — run `make site-sync`"
    )
