"""Phase 3 — stateless evaluation."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import catalog, plan
from app.main import app

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
import curricula  # noqa: E402

NINE = sorted(curricula.PROGRAMS)
client = TestClient(app)


def ev(pid, edits=None):
    return client.post(f"/programs/{pid}/evaluate", json={"edits": edits or {}})


@pytest.mark.parametrize("pid", NINE)
def test_empty_edits_reproduce_seed_derivation(pid):
    """Acceptance: empty edits reproduce each seed's derived META, all nine."""
    cat = catalog.get(pid)
    d = ev(pid).json()
    seed_groups = [(g["name"], g["done"], g["in_progress"], g["total"]) for g in cat.groups]
    got_groups = [(g["name"], g["done"], g["in_progress"], g["total"]) for g in d["groups"]]
    assert got_groups == seed_groups
    cm = client.get(f"/programs/{pid}/coursemap").json()
    assert d["totals"]["done"] == cm["meta"]["done_cr"]
    assert d["totals"]["current"] == cm["meta"]["in_prog_cr"]
    assert d["key_course"] == cm["meta"]["key_code"]


# Two programs ship a same-term prerequisite in the PUBLISHED curriculum — a real
# authoring defect in scripts/curricula.py that /evaluate correctly detects. These
# are recorded here rather than papered over; the computed "blocked" is right and
# the authored course placement is what is wrong. Fixing the tuples (moving the
# dependent course one term later) is a data change, tracked in PROGRESS.md.
KNOWN_SAME_TERM_DEFECTS = {
    "nyu-me": [("ME-UY 2223", "ME-UY 2213")],    # Dynamics vs Statics, both term 4
    "nyu-enve": [("CE-UY 2253", "CE-UY 2213")],  # Hydrology vs Fluid Mechanics, both term 4
}


@pytest.mark.parametrize("pid", NINE)
def test_published_plan_blocked_matches_known_defects(pid):
    got = {(b["code"], m) for b in ev(pid).json()["blocked"] for m in b["missing"]}
    assert got == set(KNOWN_SAME_TERM_DEFECTS.get(pid, []))


def test_seven_programs_are_clean():
    clean = [p for p in NINE if p not in KNOWN_SAME_TERM_DEFECTS]
    assert len(clean) == 7
    for pid in clean:
        assert ev(pid).json()["blocked"] == []


def test_move_before_prereq_blocks_then_clears():
    # Move Data Structures to the last term: everything downstream is blocked.
    d = ev("nyu-cs", {"moved": {"CSCI-UA 102": 7}}).json()
    blocked = {b["code"] for b in d["blocked"]}
    assert "CSCI-UA 201" in blocked and "CSCI-UA 310" in blocked
    assert all(b["missing"] == ["CSCI-UA 102"] for b in d["blocked"])
    # Moving it back clears them.
    assert ev("nyu-cs", {"moved": {"CSCI-UA 102": 2}}).json()["blocked"] == []


def test_unknown_code_reported_not_rejected():
    """A transfer credit deserves an answer, not a 422."""
    r = ev("nyu-cs", {"added": [{"c": "XFER 101", "n": "Transfer", "cr": 3,
                                 "t": 5, "s": "plan", "g": "free"}]})
    assert r.status_code == 200
    assert r.json()["unknown_codes"] == ["XFER 101"]


def test_out_of_range_term_422_names_range():
    r = ev("nyu-cs", {"moved": {"CSCI-UA 102": 99}})
    assert r.status_code == 422
    assert "0..7" in r.json()["detail"]["error"]


def test_status_derived_not_taken_from_seed():
    """A moved course reflects its new term, not the status baked into the seed."""
    d = ev("nyu-cs", {"moved": {"CSCI-UA 2": 7}}).json()
    # CSCI-UA 2 is 'done' at t0 in the seed; at t7 it must count as planned.
    assert d["totals"]["done"] < client.get(
        "/programs/nyu-cs/coursemap").json()["meta"]["done_cr"]


def test_conflicts_surface_for_scheduled_anti_pair():
    # 21-127 and its alt 15-151 are anti-requisites; schedule the alt to collide.
    d = ev("cmu-cs", {"moved": {"15-151": 4}}).json()
    pairs = {(c["a"], c["b"]) for c in d["conflicts"]}
    assert ("15-151", "21-127") in pairs


def test_evaluate_is_stateless_repeatable():
    a = ev("nyu-cs", {"moved": {"CSCI-UA 102": 6}}).json()
    b = ev("nyu-cs", {"moved": {"CSCI-UA 102": 6}}).json()
    assert a == b
    assert ev("nyu-cs").json()["blocked"] == []   # no residue from the edited call


def test_client_and_server_agree_on_apply_edits():
    """The endpoint applies edits with the same pure function the client mirrors."""
    cat = catalog.get("nyu-cs")
    edits = {"moved": {"CSCI-UA 102": 6}, "added": [], "removed": []}
    rows = plan.apply_edits(cat.graph_courses(), edits)
    moved = [r for r in rows if r["c"] == "CSCI-UA 102" and not r.get("ghost")][0]
    assert moved["t"] == 6
