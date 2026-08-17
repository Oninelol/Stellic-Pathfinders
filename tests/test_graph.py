"""Tests for app.graph against the extracted default plan and a cyclic fixture.

The default fixture is the unmodified COURSES/TERMS from the mock in
``Compass Planner.html`` (commit 496bf1e), so these tests double as the check that
the Python port agrees with the values the HTML authored.
"""

import copy
import json
from pathlib import Path

import pytest

from app.graph import (
    CatalogError,
    blocked_by,
    conflicts,
    credit_totals,
    direct_unlocks,
    key_course,
    unlocks,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def plan() -> dict:
    return _load("default_plan.json")


@pytest.fixture
def courses(plan) -> list[dict]:
    return plan["courses"]


@pytest.fixture
def terms(plan) -> list[dict]:
    return plan["terms"]


# --------------------------------------------------------------------------- #
# blocked_by
# --------------------------------------------------------------------------- #

def test_blocked_by_cs210_at_term4_blocked_by_math152(courses):
    # Move the real CS 210 to term 4, where MATH 152 (also term 4) is not yet earlier.
    moved = copy.deepcopy(courses)
    for c in moved:
        if c["c"] == "CS 210" and not c.get("ghost"):
            c["t"] = 4
    assert blocked_by(moved, "CS 210") == ["MATH 152"]


def test_blocked_by_cs210_at_term5_not_blocked(courses):
    # Default fixture: real CS 210 sits at term 5, after MATH 152 (t4) and CS 120 (t1).
    assert blocked_by(courses, "CS 210") == []


def test_blocked_by_absent_prereq_is_unsatisfied():
    cs = [
        {"c": "X 1", "n": "x", "cr": 3, "t": 2, "s": "plan", "tier": 0,
         "req": ["GHOSTLY 999"], "anti": []},
    ]
    assert blocked_by(cs, "X 1") == ["GHOSTLY 999"]


def test_blocked_by_unscheduled_never_blocked():
    cs = [
        {"c": "X 1", "n": "x", "cr": 3, "t": -1, "s": "alt", "tier": 0,
         "req": ["Y 1"], "anti": []},
        {"c": "Y 1", "n": "y", "cr": 3, "t": 3, "s": "plan", "tier": 0,
         "req": [], "anti": []},
    ]
    assert blocked_by(cs, "X 1") == []


def test_blocked_by_gen_row_never_blocked(courses):
    assert blocked_by(courses, "ENGL 101") == []


def test_blocked_by_unknown_code_raises(courses):
    with pytest.raises(CatalogError):
        blocked_by(courses, "NOPE 000")


def test_blocked_by_does_not_mutate(courses):
    before = copy.deepcopy(courses)
    blocked_by(courses, "CS 210")
    assert courses == before


# --------------------------------------------------------------------------- #
# unlocks / direct_unlocks
# --------------------------------------------------------------------------- #

def test_direct_unlocks_math152_includes_alt_dependent(courses):
    # Contract: "Includes alt and unscheduled courses — they are real dependents."
    # MATH 265 is an alt row whose req is ['MATH 152'], so it is a direct dependent.
    # The HTML "DO THIS FIRST" panel hardcodes only the four non-alt courses and
    # omits MATH 265 — a curation choice in the HTML, not what the graph computes.
    assert direct_unlocks(courses, "MATH 152") == {
        "CS 210", "MATH 240", "MATH 260", "STAT 250", "MATH 265"
    }


def test_direct_unlocks_is_subset_of_unlocks(courses):
    for code in {c["c"] for c in courses}:
        assert direct_unlocks(courses, code) <= unlocks(courses, code)


def test_unlocks_excludes_self(courses):
    assert "MATH 152" not in unlocks(courses, "MATH 152")


def test_unlocks_math152_transitive_closure(courses):
    got = unlocks(courses, "MATH 152")
    # 5 direct dependents (incl. the alt MATH 265) + 9 reachable behind them = 14.
    assert got == {
        "CS 210", "MATH 240", "MATH 260", "STAT 250", "MATH 265",
        "CS 310", "CS 320", "CS 330", "CS 340", "CS 360",
        "CS 380", "CS 425", "CS 450", "DATA 340",
    }
    assert "MATH 151" not in got  # a prerequisite, not a dependent


def test_unlocks_includes_alt_dependents():
    cs = [
        {"c": "BASE 1", "n": "b", "cr": 3, "t": 0, "s": "done", "tier": 0,
         "req": [], "anti": []},
        {"c": "ALT 9", "n": "a", "cr": 3, "t": -1, "s": "alt", "tier": 1,
         "req": ["BASE 1"], "anti": [], "alt": 1},
    ]
    assert unlocks(cs, "BASE 1") == {"ALT 9"}


def test_unlocks_cyclic_raises_naming_cycle():
    cyclic = _load("cyclic.json")["courses"]
    with pytest.raises(CatalogError) as exc:
        unlocks(cyclic, "AAA 100")
    msg = str(exc.value)
    assert "AAA 100" in msg and "BBB 200" in msg and "CCC 300" in msg


def test_unlocks_does_not_mutate(courses):
    before = copy.deepcopy(courses)
    unlocks(courses, "MATH 152")
    assert courses == before


# --------------------------------------------------------------------------- #
# credit_totals
# --------------------------------------------------------------------------- #

def test_credit_totals_done_is_computed_42_not_authored_41(courses, terms):
    # The data sums to 42 done credits; the HTML authored "41". The function reports
    # the truth from the data and is NOT tuned to the authored value.
    assert credit_totals(courses, terms)["done"] == 42


def test_credit_totals_excludes_ghost(courses, terms):
    # The ghost CS 210 (blocked, t=4, 4 cr) must not appear in per_term or planned.
    totals = credit_totals(courses, terms, total=120)
    # term 4 holds MATH 152(4) + CS 245(3) + WRIT 200(3) + SOC 101(3) + ANTH 210(3) = 16,
    # NOT 20 — the ghost CS 210's 4 credits are excluded.
    assert totals["per_term"][4]["credits"] == 16


def test_credit_totals_total_is_passthrough_not_sum(courses, terms):
    totals = credit_totals(courses, terms, total=120)
    assert totals["total"] == 120
    assert totals["remaining"] == 120 - (
        totals["done"] + totals["current"] + totals["planned"]
    )


def test_credit_totals_per_term_length_matches_terms(courses, terms):
    assert len(credit_totals(courses, terms)["per_term"]) == len(terms)


def test_credit_totals_does_not_mutate(courses, terms):
    before = copy.deepcopy(courses)
    credit_totals(courses, terms, total=120)
    assert courses == before


# --------------------------------------------------------------------------- #
# conflicts
# --------------------------------------------------------------------------- #

def test_conflicts_finds_stat_pair_once(courses):
    got = conflicts(courses)
    assert got == [{"a": "STAT 210", "b": "STAT 250", "one_sided": False}]


def test_conflicts_ignores_unscheduled_anti(courses):
    # MATH 260 anti MATH 265, but MATH 265 is an unscheduled alt (t=-1) -> not a conflict.
    pairs = {(d["a"], d["b"]) for d in conflicts(courses)}
    assert ("MATH 260", "MATH 265") not in pairs
    assert ("CS 360", "DATA 340") not in pairs


def test_conflicts_one_sided_flagged():
    cs = [
        {"c": "P 1", "n": "p", "cr": 3, "t": 0, "s": "plan", "tier": 0,
         "req": [], "anti": ["Q 1"]},
        {"c": "Q 1", "n": "q", "cr": 3, "t": 1, "s": "plan", "tier": 0,
         "req": [], "anti": []},  # does not name P 1 back
    ]
    assert conflicts(cs) == [{"a": "P 1", "b": "Q 1", "one_sided": True}]


def test_conflicts_does_not_mutate(courses):
    before = copy.deepcopy(courses)
    conflicts(courses)
    assert courses == before


# --------------------------------------------------------------------------- #
# key_course
# --------------------------------------------------------------------------- #

def test_key_course_is_math152(courses):
    assert key_course(courses) == "MATH 152"


def test_key_course_none_when_nothing_blocked():
    cs = [
        {"c": "A 1", "n": "a", "cr": 3, "t": 0, "s": "done", "tier": 0,
         "req": [], "anti": []},
        {"c": "B 1", "n": "b", "cr": 3, "t": 1, "s": "current", "tier": 1,
         "req": ["A 1"], "anti": []},
    ]
    assert key_course(cs) is None


def test_key_course_prefers_more_blocked_dependents():
    # T needs nothing; two todo bottlenecks, one with more not-done dependents.
    cs = [
        {"c": "K 1", "n": "k1", "cr": 3, "t": 4, "s": "todo", "tier": 1,
         "req": [], "anti": []},
        {"c": "K 2", "n": "k2", "cr": 3, "t": 4, "s": "todo", "tier": 1,
         "req": [], "anti": []},
        {"c": "D 1", "n": "d1", "cr": 3, "t": 5, "s": "plan", "tier": 2,
         "req": ["K 1"], "anti": []},
        {"c": "D 2", "n": "d2", "cr": 3, "t": 5, "s": "plan", "tier": 2,
         "req": ["K 1"], "anti": []},
        {"c": "D 3", "n": "d3", "cr": 3, "t": 5, "s": "plan", "tier": 2,
         "req": ["K 2"], "anti": []},
    ]
    assert key_course(cs) == "K 1"


def test_key_course_done_dependents_do_not_count():
    # K's only dependent is already done -> K is not a bottleneck -> None.
    cs = [
        {"c": "K 1", "n": "k", "cr": 3, "t": 4, "s": "todo", "tier": 1,
         "req": [], "anti": []},
        {"c": "D 1", "n": "d", "cr": 3, "t": 0, "s": "done", "tier": 2,
         "req": ["K 1"], "anti": []},
    ]
    assert key_course(cs) is None


def test_key_course_does_not_mutate(courses):
    before = copy.deepcopy(courses)
    key_course(courses)
    assert courses == before


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #

def test_malformed_input_raises():
    with pytest.raises(CatalogError):
        blocked_by("not a list", "X")  # type: ignore[arg-type]
    with pytest.raises(CatalogError):
        credit_totals([{"c": "X 1", "t": "nope", "s": "plan"}], [])  # bad 't'
    with pytest.raises(CatalogError):
        conflicts([{"c": "X 1", "t": 0, "s": "plan", "anti": [1, 2]}])  # bad anti
