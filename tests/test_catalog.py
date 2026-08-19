"""Tests for app.catalog and scripts/validate_catalog.

Loading is exercised against the real seed files; each hard-error and warning
check is exercised against a small synthetic seed written to a temp file, so a
failure points at exactly one rule.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from app import catalog, graph

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import curricula  # noqa: E402  (the single source of the nine tuple tables)
import emit_frontend  # noqa: E402
import emit_seeds  # noqa: E402

# import scripts/validate_catalog.py by path (it is a script, not a package module)
_spec = importlib.util.spec_from_file_location(
    "validate_catalog", ROOT / "scripts" / "validate_catalog.py"
)
validate_catalog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_catalog)

# The nine program ids are the frontend keys (identity mapping).
NINE = set(curricula.PROGRAMS)


# --------------------------------------------------------------------------- #
# a minimal, valid synthetic seed to mutate per error test
# --------------------------------------------------------------------------- #

def _seed() -> dict:
    return {
        "school": "TESTU",
        "program": {
            "id": "test-prog", "name": "Test Program", "degree": "BS",
            "catalog_year": "2026", "unit_label": "units", "unit_abbr": "u",
            "total_units": 40,
        },
        "terms": [
            {"index": 0, "key": "F24", "label": "Fall 2024"},
            {"index": 1, "key": "S25", "label": "Spring 2025"},
            {"index": 2, "key": "F25", "label": "Fall 2025"},
        ],
        "requirements": [
            {"id": "core", "name": "Core", "min_courses": 2,
             "match": {"explicit": ["AA 100", "AA 200"]}},
        ],
        "courses": [
            {"c": "AA 100", "n": "Intro", "cr": 10, "t": 0, "s": "done",
             "tier": 0, "req": [], "anti": [], "g": "major",
             "offering": "Fall · Spring", "needs_review": False, "review_note": None},
            {"c": "AA 200", "n": "Second", "cr": 10, "t": 1, "s": "current",
             "tier": 1, "req": ["AA 100"], "anti": [], "g": "major",
             "offering": "Fall · Spring", "needs_review": False, "review_note": None},
        ],
    }


def _write(tmp_path: Path, seed: dict) -> Path:
    p = tmp_path / "seed.json"
    p.write_text(json.dumps(seed))
    return p


def _validate(tmp_path: Path, seed: dict) -> validate_catalog.Report:
    return validate_catalog.validate(catalog.load_file(_write(tmp_path, seed)))


# --------------------------------------------------------------------------- #
# loading API  (acceptance 3, 4, 5)
# --------------------------------------------------------------------------- #

def test_load_all_returns_nine_catalogs():
    catalog.load_all.cache_clear()
    cats = catalog.load_all()
    assert set(cats) == NINE
    assert len(cats) == 9


def test_every_frontend_key_maps_to_exactly_one_seed():
    # Acceptance 5: the seed program ids ARE the frontend keys (identity mapping).
    catalog.load_all.cache_clear()
    cats = catalog.load_all()
    for key in curricula.PROGRAMS:
        seed = ROOT / "data" / f"{key}.json"
        assert seed.exists(), f"no seed file for frontend key {key!r}"
        assert key in cats
        assert cats[key].program.id == key


def test_load_all_is_memoised():
    catalog.load_all.cache_clear()
    assert catalog.load_all() is catalog.load_all()


def test_nyu_credits_cmu_units():
    assert catalog.get("nyu-cs").program.unit_label == "credits"
    assert catalog.get("cmu-cs").program.unit_label == "units"


def test_key_course_runs_on_all_nine():
    # Acceptance 4: graph.key_course runs on every loaded catalog without raising.
    catalog.load_all.cache_clear()
    for cat in catalog.load_all().values():
        graph.key_course(cat.graph_courses())


def test_get_unknown_raises():
    with pytest.raises(catalog.CatalogError):
        catalog.get("does-not-exist")


def test_schools_nested_single_call():
    sc = catalog.schools()
    assert [s["school"] for s in sc] == ["CMU", "NYU"]
    for entry in sc:
        assert entry["programs"] and all("id" in p for p in entry["programs"])
    # every loaded program is represented exactly once
    nested = {p["id"] for s in sc for p in s["programs"]}
    assert nested == set(catalog.load_all())


def test_courses_are_code_keyed_and_ghost_separated():
    cat = catalog.get("nyu-cs")
    assert isinstance(cat.courses, dict)
    assert "CSCI-UA 102" in cat.courses
    assert isinstance(cat.courses["CSCI-UA 102"], catalog.Course)
    assert cat.courses["CSCI-UA 102"].group == "major"  # the g field survives load
    # the ghost CSCI-UA 310 lives on .ghosts, and its real twin is in .courses
    assert any(g.code == "CSCI-UA 310" for g in cat.ghosts)
    assert "CSCI-UA 310" in cat.courses


def test_graph_runs_against_loaded_catalog_unchanged():
    # Acceptance 5: the Stage-1 functions consume Catalog.graph_courses() directly.
    for pid, expected_key in [("nyu-cs", "MATH-UA 120"), ("cmu-cs", "15-251")]:
        cat = catalog.get(pid)
        rows = cat.graph_courses()
        assert graph.key_course(rows) == expected_key
        totals = graph.credit_totals(rows, list(cat.terms), cat.program.total_units)
        assert totals["done"] == cat.program.total_units - totals["remaining"] - \
            totals["current"] - totals["planned"]


# --------------------------------------------------------------------------- #
# the real seed files are clean (no hard errors) — all nine
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("pid", sorted(curricula.PROGRAMS))
def test_real_seed_has_no_hard_errors(pid):
    rep = validate_catalog.validate(catalog.get(pid))
    assert rep.errors == [], f"{pid} unexpectedly has hard errors: {rep.errors}"


# --------------------------------------------------------------------------- #
# emitter agreement + determinism  (acceptance 1, 6)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("key", sorted(curricula.PROGRAMS))
def test_seed_groups_match_frontend_reqs(key):
    """Acceptance 6: the seed's derived group counts equal what the frontend REQS
    emitter produces from the same tuples. Catches drift between the two emitters."""
    P = curricula.PROGRAMS[key]
    seed_groups = json.loads((ROOT / "data" / f"{key}.json").read_text())["groups"]
    # rebuild the frontend REQS the way emit_frontend does
    front = curricula.derive_groups(P)
    assert [(g["name"], g["done"], g["in_progress"], g["total"]) for g in seed_groups] == \
           [(g["name"], g["done"], g["in_progress"], g["total"]) for g in front]
    # and the loaded catalog exposes the same groups
    assert len(catalog.get(key).groups) == len(front)


def test_emitters_are_deterministic():
    """Acceptance 1: regenerating from the tuples twice is byte-stable."""
    assert emit_frontend.render() == emit_frontend.render()
    for key, P in curricula.PROGRAMS.items():
        a = json.dumps(emit_seeds.seed_payload(key, P), sort_keys=True)
        b = json.dumps(emit_seeds.seed_payload(key, P), sort_keys=True)
        assert a == b, f"{key} seed payload not deterministic"


def test_seven_engineering_programs_have_no_matchers():
    # The 2 CS programs carry real matchers; the 7 engineering programs must not
    # invent any, and must flag needs_requirements instead.
    for pid, cat in catalog.load_all().items():
        if pid in ("nyu-cs", "cmu-cs"):
            assert cat.requirements and not cat.program.needs_requirements
        else:
            assert cat.requirements == () and cat.program.needs_requirements


# --------------------------------------------------------------------------- #
# hard-error checks — one synthetic breakage each
# --------------------------------------------------------------------------- #

def test_dangling_req(tmp_path):
    seed = _seed()
    seed["courses"][1]["req"] = ["AA 100", "ZZ 999"]
    rep = _validate(tmp_path, seed)
    assert any("ZZ 999" in e for e in rep.errors)


def test_cycle_is_named(tmp_path):
    seed = _seed()
    # AA 100 -> AA 200 -> AA 100
    seed["courses"][0]["req"] = ["AA 200"]
    rep = _validate(tmp_path, seed)
    assert rep.errors
    assert any("AA 100" in e and "AA 200" in e for e in rep.errors)


def test_one_sided_anti(tmp_path):
    seed = _seed()
    seed["courses"][0]["anti"] = ["AA 200"]  # AA 200 does not name AA 100 back
    rep = _validate(tmp_path, seed)
    assert any("one side only" in e for e in rep.errors)


def test_requirement_names_missing_course(tmp_path):
    seed = _seed()
    seed["requirements"][0]["match"]["explicit"] = ["AA 100", "AA 999"]
    rep = _validate(tmp_path, seed)
    assert any("AA 999" in e and "core" in e for e in rep.errors)


def test_duplicate_code(tmp_path):
    seed = _seed()
    seed["courses"].append(dict(seed["courses"][0]))  # AA 100 twice
    rep = _validate(tmp_path, seed)
    assert any("duplicate" in e and "AA 100" in e for e in rep.errors)


def test_term_out_of_range(tmp_path):
    seed = _seed()
    seed["courses"][1]["t"] = 9  # only 3 terms
    rep = _validate(tmp_path, seed)
    assert any("term index 9" in e for e in rep.errors)


def test_ghost_without_real(tmp_path):
    seed = _seed()
    seed["courses"].append({
        "c": "GG 300", "n": "Ghosty", "cr": 10, "t": 2, "s": "blocked",
        "g": "major", "ghost": 1, "note": "deferred", "offering": "UNKNOWN",
        "needs_review": False, "review_note": None,
    })
    rep = _validate(tmp_path, seed)
    assert any("ghost" in e and "GG 300" in e for e in rep.errors)


def test_unscheduled_term_minus_one_is_allowed(tmp_path):
    seed = _seed()
    seed["courses"].append({
        "c": "AA 900", "n": "Alt", "cr": 10, "t": -1, "s": "alt", "alt": 1,
        "g": "math", "tier": 1, "req": [], "anti": [], "offering": "UNKNOWN",
        "needs_review": False, "review_note": None,
    })
    rep = _validate(tmp_path, seed)
    assert not any("term index" in e for e in rep.errors)


# --------------------------------------------------------------------------- #
# warnings do not become errors
# --------------------------------------------------------------------------- #

def test_warnings_counted_not_fatal(tmp_path):
    seed = _seed()
    seed["courses"][0]["needs_review"] = True
    seed["courses"][0]["review_note"] = "inferred"
    seed["courses"][1]["offering"] = "UNKNOWN"
    # AA 200 is covered by the requirement; add an uncovered course
    seed["courses"].append({
        "c": "BB 100", "n": "Loose", "cr": 10, "t": 2, "s": "plan", "tier": 0,
        "req": [], "anti": [], "g": "free", "offering": "Fall",
        "needs_review": False, "review_note": None,
    })
    rep = _validate(tmp_path, seed)
    assert rep.errors == []
    assert any("needs_review: AA 100" in w for w in rep.warnings)
    assert any("offering UNKNOWN: AA 200" in w for w in rep.warnings)
    assert any("reachable from no requirement: BB 100" in w for w in rep.warnings)
