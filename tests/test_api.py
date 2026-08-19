"""Tests for the Phase 1 read-only API.

Everything runs through FastAPI's TestClient (no network, no server process). The
catalog is the real nine seeds; the API is asserted to stay program-agnostic — same
shape for all nine, no program-specific keys.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import catalog, graph
from app.main import app

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
import curricula  # noqa: E402

NINE = sorted(curricula.PROGRAMS)
client = TestClient(app)


# --------------------------------------------------------------------------- #
# healthz + schools
# --------------------------------------------------------------------------- #

def test_healthz_reports_nine_programs():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["programs"] == 9
    assert body["courses"] > 0


def test_schools_returns_all_nine_in_one_call():
    r = client.get("/schools")
    assert r.status_code == 200
    body = r.json()
    assert [s["school"] for s in body] == ["CMU", "NYU"]
    ids = {p["id"] for s in body for p in s["programs"]}
    assert ids == set(NINE)


# --------------------------------------------------------------------------- #
# coursemap — complete, self-contained, program-agnostic
# --------------------------------------------------------------------------- #

_TOP_KEYS = {
    "program_id", "school", "program_name", "unit_label", "unit_abbr",
    "total_units", "tiers", "terms", "groups", "requirements",
    "needs_requirements", "meta", "nodes", "edges",
}
_META_KEYS = {
    "done_cr", "in_prog_cr", "pct", "behind_cr", "grad_term", "class_year",
    "key_code", "key_name", "headline", "blurb", "snapshot",
}
_NODE_KEYS = {
    "code", "title", "units", "term", "status", "tier", "group", "offering",
    "offering_source", "requirement_ids", "needs_review", "review_note",
    "ghost", "alt", "key",
}


@pytest.mark.parametrize("pid", NINE)
def test_coursemap_complete(pid):
    cm = client.get(f"/programs/{pid}/coursemap").json()
    assert set(cm) == _TOP_KEYS
    assert set(cm["meta"]) == _META_KEYS
    assert cm["tiers"] and len(cm["tiers"]) == 5
    assert cm["terms"] and cm["nodes"] and cm["edges"]
    for n in cm["nodes"]:
        assert set(n) == _NODE_KEYS


def test_shape_identical_across_all_nine():
    maps = {pid: client.get(f"/programs/{pid}/coursemap").json() for pid in NINE}
    # top-level, meta, node and edge key sets are identical for every program
    assert len({frozenset(m) for m in maps.values()}) == 1
    assert len({frozenset(m["meta"]) for m in maps.values()}) == 1
    node_keysets = {frozenset(n) for m in maps.values() for n in m["nodes"]}
    assert len(node_keysets) == 1
    edge_keysets = {frozenset(e) for m in maps.values() for e in m["edges"]}
    assert edge_keysets == {frozenset({"from", "to", "kind"})}


def test_nyu_credits_cmu_units():
    for pid in NINE:
        cm = client.get(f"/programs/{pid}/coursemap").json()
        expect = "credits" if pid.startswith("nyu") else "units"
        assert cm["unit_label"] == expect, f"{pid} unit_label"


def test_edges_kinds_and_endpoints_are_nodes():
    for pid in NINE:
        cm = client.get(f"/programs/{pid}/coursemap").json()
        codes = {n["code"] for n in cm["nodes"]}
        for e in cm["edges"]:
            assert e["kind"] in ("prereq", "anti")
            assert e["from"] in codes and e["to"] in codes


def test_offerings_flagged_derived():
    cm = client.get("/programs/nyu-cs/coursemap").json()
    assert all(n["offering_source"] == "derived" for n in cm["nodes"])


def test_requirements_only_for_cs_programs():
    for pid in NINE:
        cm = client.get(f"/programs/{pid}/coursemap").json()
        if pid in ("nyu-cs", "cmu-cs"):
            assert cm["requirements"] and cm["needs_requirements"] is False
        else:
            assert cm["requirements"] == [] and cm["needs_requirements"] is True


# --------------------------------------------------------------------------- #
# detail matches the graph functions, per program
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("pid", NINE)
def test_detail_matches_graph(pid):
    cat = catalog.get(pid)
    rows = cat.graph_courses()
    # spot-check a course that actually has prerequisites
    code = next(c.code for c in cat.courses.values() if c.req)
    d = client.get(f"/programs/{pid}/courses/{code}").json()
    assert d["blocked_by"] == graph.blocked_by(rows, code)
    assert d["direct_unlocks"] == sorted(graph.direct_unlocks(rows, code))
    assert d["unlocks"] == sorted(graph.unlocks(rows, code))


def test_detail_blocked_case_nyu_cs():
    # CSCI-UA 310 (real, t5) is not blocked in the published plan.
    d = client.get("/programs/nyu-cs/courses/CSCI-UA 310").json()
    assert d["blocked_by"] == []
    assert "MATH-UA 120" in d["req"]


# --------------------------------------------------------------------------- #
# 404s with useful messages
# --------------------------------------------------------------------------- #

def test_unknown_program_404_lists_known():
    r = client.get("/programs/nope/coursemap")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert "nope" in detail["error"]
    assert set(detail["known_programs"]) == set(NINE)


def test_unknown_course_404_names_program():
    r = client.get("/programs/nyu-cs/courses/ZZZ 999")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert "ZZZ 999" in detail["error"] and "nyu-cs" in detail["error"]
    assert "CSCI-UA 102" in detail["known_courses"]


def test_unknown_course_detail_endpoint_also_404():
    assert client.get("/programs/does-not-exist/courses/CS 1").status_code == 404
