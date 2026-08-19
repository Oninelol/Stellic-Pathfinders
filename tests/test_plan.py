"""Tests for app.plan — the edit model must reproduce the JS ``get COURSES()``.

The fixture ``tests/fixtures/edit_plan.json`` carries a base plan, an edit set (a
move, a no-op move, a ghost move, an add and a remove), and ``expected`` — the output
of the actual frontend ``get COURSES()`` captured via node. So this pins the Python
port against the JS rather than against a re-derivation of it.
"""

import copy
import json
from pathlib import Path

from app import plan

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture() -> dict:
    return json.loads((FIXTURES / "edit_plan.json").read_text())


def _key(rows):
    """Order-independent comparison key: sort rows by (code, ghost, term)."""
    return sorted(
        (json.dumps(r, sort_keys=True) for r in rows)
    )


# --------------------------------------------------------------------------- #
# row_id
# --------------------------------------------------------------------------- #

def test_row_id_plain_and_ghost():
    assert plan.row_id({"c": "CS 210"}) == "CS 210"
    assert plan.row_id({"c": "CS 210", "ghost": 1}) == "CS 210#g"


# --------------------------------------------------------------------------- #
# apply_edits matches the JS get COURSES()  (acceptance 7)
# --------------------------------------------------------------------------- #

def test_apply_edits_matches_js_fixture():
    fx = _fixture()
    got = plan.apply_edits(fx["base"], fx["edits"])
    assert _key(got) == _key(fx["expected"])


def test_apply_edits_no_edits_returns_copy():
    fx = _fixture()
    got = plan.apply_edits(fx["base"], {})
    assert _key(got) == _key(fx["base"])
    # fresh objects, not the same list/dicts
    assert got is not fx["base"]
    assert all(a is not b for a, b in zip(got, fx["base"]))


def test_apply_edits_does_not_mutate_arguments():
    fx = _fixture()
    base_before = copy.deepcopy(fx["base"])
    edits_before = copy.deepcopy(fx["edits"])
    plan.apply_edits(fx["base"], fx["edits"])
    assert fx["base"] == base_before
    assert fx["edits"] == edits_before


def test_move_recomputes_status():
    base = [{"c": "X 1", "n": "x", "cr": 4, "t": 3, "s": "current",
             "tier": 1, "req": [], "anti": []}]
    terms_current = 3  # base row at t3 is 'current', so cur=3
    # move to a later term -> plan
    out = plan.apply_edits(base, {"moved": {"X 1": 5}})
    assert len(out) == 1 and out[0]["t"] == 5 and out[0]["s"] == "plan"
    # move to an earlier term -> done
    out = plan.apply_edits(base, {"moved": {"X 1": 1}})
    assert out[0]["s"] == "done"
    del terms_current


def test_no_op_move_is_not_a_move():
    base = [{"c": "K 9", "t": 4, "s": "todo", "key": 1, "cr": 3}]
    out = plan.apply_edits(base, {"moved": {"K 9": 4}})
    # unchanged term: the row is kept as-is, status not recomputed away from 'todo'
    assert out[0]["s"] == "todo" and out[0]["t"] == 4


def test_remove_drops_row():
    base = [{"c": "A 1", "t": 0, "s": "done", "cr": 3},
            {"c": "B 2", "t": 1, "s": "done", "cr": 3}]
    out = plan.apply_edits(base, {"removed": ["A 1"]})
    assert [r["c"] for r in out] == ["B 2"]


def test_ghost_move_stays_blocked_and_uses_g_suffix():
    base = [{"c": "G 3", "t": 4, "s": "blocked", "ghost": 1, "cr": 3},
            {"c": "G 3", "t": 5, "s": "plan", "tier": 2, "cr": 3, "req": [], "anti": []}]
    # the ghost is addressed by its "#g" id; the real twin is untouched
    out = plan.apply_edits(base, {"moved": {"G 3#g": 2}})
    ghost = [r for r in out if r.get("ghost")][0]
    real = [r for r in out if not r.get("ghost")][0]
    assert ghost["t"] == 2 and ghost["s"] == "blocked"
    assert real["t"] == 5 and real["s"] == "plan"


def test_added_row_is_appended_verbatim():
    base = [{"c": "A 1", "t": 0, "s": "done", "cr": 3}]
    added = {"c": "NEW 1", "t": 4, "s": "plan", "cr": 3}
    out = plan.apply_edits(base, {"added": [added]})
    assert out[-1]["c"] == "NEW 1" and out[-1]["s"] == "plan"
    assert out[-1] is not added  # a copy, not the same object


# --------------------------------------------------------------------------- #
# apply_edits over a real loaded catalog stays graph-evaluable
# --------------------------------------------------------------------------- #

def test_apply_edits_on_real_catalog_runs_through_graph():
    from app import catalog, graph
    catalog.load_all.cache_clear()
    cat = catalog.get("nyu-cs")
    base = cat.graph_courses()
    # move the real Basic Algorithms one term later
    edited = plan.apply_edits(base, {"moved": {"CSCI-UA 310": 6}})
    assert len(edited) == len(base)
    moved = [r for r in edited if r["c"] == "CSCI-UA 310" and not r.get("ghost")][0]
    assert moved["t"] == 6
    # the edited plan is still a valid graph input
    graph.key_course(edited)
    graph.credit_totals(edited, list(cat.terms), cat.program.total_units)
