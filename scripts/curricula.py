#!/usr/bin/env python3
"""The single source of course data: nine programs as compact tuple tables.

Each program is written as a compact course table; META credit totals, the
requirement buckets and every course status are DERIVED from that table, so the
numbers can never drift from the courses.

Course tuple: (code, title, credits, term, group, tier, prereqs, antis, flag)
  term   0-7 index into TERMS, or -1 for an unscheduled alternative
  group  'major' | 'math' | 'sci' | 'huss' | 'free'  -> drives requirement buckets
  tier   0-4 column on the dependency graph, or None for a breadth row (gen:1)
  flag   None | 'key' (the bottleneck) | 'ghost' (deferred placeholder) | 'alt'

Status is derived from the term via graph.status_for: 0-2 done, 3 current, 4+ plan;
'key' becomes todo and 'ghost' becomes blocked.

This file is DATA + shared derivation only. As of Phase 2 there is ONE emitter:

    scripts/emit_seeds.py   tuples -> data/<program-id>.json (one per program)

The frontend no longer inlines a SCHOOLS block — it fetches the seeds through the
API and adapts them client-side. (emit_frontend.py is retired.) A course edit
happens in exactly one place (the tuple tables below); the seeds regenerate from it.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import graph  # noqa: E402  (scripts may import app.graph; graph imports no app)

# ---------------------------------------------------------------- term tables
CMU_TERMS = [
    ('F24', 'Fall 2024', 'FIRST YEAR', 'done'), ('S25', 'Spring 2025', 'FIRST YEAR', 'done'),
    ('F25', 'Fall 2025', 'SOPHOMORE', 'done'), ('S26', 'Spring 2026', 'IN PROGRESS', 'current'),
    ('F26', 'Fall 2026', 'JUNIOR · DRAFT', 'plan'), ('S27', 'Spring 2027', 'JUNIOR · DRAFT', 'plan'),
    ('F27', 'Fall 2027', 'SENIOR · DRAFT', 'plan'), ('S28', 'Spring 2028', 'SENIOR · DRAFT', 'plan'),
]

GROUP_LABEL = {
    'major': 'Major sequence', 'math': 'Mathematics', 'sci': 'Science',
    'huss': 'Humanities & social sciences', 'free': 'Free electives',
}

# ============================================================ PROGRAM TABLES
PROGRAMS = {}

PROGRAMS['cmu-cs'] = dict(
    school='CMU', program='CS BS · SCS', tab='Computer Science',
    unit='units', abbr='u', total=360, grad='Spring 2028', year='SOPHOMORE',
    terms=CMU_TERMS, tiers=['IMPERATIVE START', 'CORE SEQUENCE', 'SYSTEMS & MATRICES',
                            'THEORY & ALGORITHMS', 'ADVANCED ELECTIVES'],
    key='15-251', keyname='Great Ideas in Theoretical Computer Science',
    headline="Register for 15-251 — Algorithm Design and Complexity Theory are both waiting on it.",
    blurb="Great Ideas is the gate into the theory sequence. Until it clears, 15-451 will not register, and the complexity elective stacked behind it has nowhere to go.",
    requirements=[
        {'id': 'cs-core', 'name': 'Computer science core', 'min_courses': 5,
         'match': {'explicit': ['15-122', '15-150', '15-210', '15-213', '15-251']}},
        {'id': 'cs-electives', 'name': 'CS electives', 'min_courses': 4,
         'match': {'any_of': ['15-451', '15-410', '15-411', '15-455', '15-462', '10-315']}},
        {'id': 'math-core', 'name': 'Mathematics', 'min_courses': 4,
         'match': {'explicit': ['21-120', '21-122', '21-127', '21-241']}},
        {'id': 'probability', 'name': 'Probability', 'min_courses': 1,
         'match': {'any_of': ['15-259', '36-218']}},
        {'id': 'science', 'name': 'Science & engineering', 'min_courses': 2,
         'match': {'any_of': ['33-121', '09-105']}},
        {'id': 'humanities', 'name': 'Humanities & arts', 'min_courses': 3,
         'match': {'any_of': ['76-101', '76-270', '79-104', '73-102']}},
    ],
    courses=[
        ('15-112', 'Fundamentals of Programming and CS', 12, 0, 'major', 0, [], [], None),
        ('21-120', 'Differential and Integral Calculus', 10, 0, 'math', 0, [], [], None),
        ('76-101', 'Interpretation and Argument', 9, 0, 'huss', None, [], [], None),
        ('99-101', 'Computing @ Carnegie Mellon', 3, 0, 'free', None, [], [], None),
        ('15-122', 'Principles of Imperative Computation', 12, 1, 'major', 1, ['15-112'], [], None),
        ('21-122', 'Integration and Approximation', 10, 1, 'math', 1, ['21-120'], [], None),
        ('15-128', 'Freshman Immigration Course', 3, 1, 'major', None, [], [], None),
        ('79-104', 'Global Histories', 9, 1, 'huss', None, [], [], None),
        ('15-150', 'Principles of Functional Programming', 12, 2, 'major', 2, ['15-122'], [], None),
        ('21-127', 'Concepts of Mathematics', 12, 2, 'math', 1, [], ['15-151'], None),
        ('33-121', 'Physics I for Science Students', 12, 2, 'sci', None, [], [], None),
        ('15-213', 'Introduction to Computer Systems', 12, 3, 'major', 2, ['15-122'], [], None),
        ('15-210', 'Parallel and Sequential Data Structures and Algorithms', 12, 3, 'major', 3, ['15-150', '15-122'], [], None),
        ('76-270', 'Writing for the Professions', 9, 3, 'huss', None, ['76-101'], [], None),
        ('15-251', 'Great Ideas in Theoretical Computer Science', 12, 4, 'major', 3, ['15-122', '21-127'], [], 'key'),
        ('21-241', 'Matrices and Linear Transformations', 11, 4, 'math', 2, ['21-122'], [], None),
        ('09-105', 'Introduction to Modern Chemistry I', 10, 4, 'sci', None, [], [], None),
        ('15-451', 'Algorithm Design and Analysis', 12, 4, 'major', None, [], [], 'ghost'),
        ('15-451', 'Algorithm Design and Analysis', 12, 5, 'major', 4, ['15-210', '15-251'], [], None),
        ('15-259', 'Probability and Computing', 12, 5, 'math', 3, ['21-127'], ['36-218'], None),
        ('73-102', 'Principles of Microeconomics', 9, 5, 'huss', None, [], [], None),
        ('15-410', 'Operating System Design and Implementation', 15, 6, 'major', 4, ['15-213', '15-210'], [], None),
        ('10-315', 'Introduction to Machine Learning (SCS majors)', 12, 6, 'major', 4, ['21-241', '15-259'], [], None),
        ('76-271', 'Minor Elective', 9, 6, 'huss', None, [], [], None),
        ('15-411', 'Compiler Design', 15, 7, 'major', 4, ['15-213', '15-210'], [], None),
        ('15-455', 'Undergraduate Complexity Theory', 12, 7, 'major', 4, ['15-251'], [], None),
        ('15-462', 'Computer Graphics', 12, 7, 'major', 4, ['15-213'], [], None),
        ('15-151', 'Mathematical Foundations for Computer Science', 12, -1, 'math', 1, [], ['21-127'], 'alt'),
        ('36-218', 'Probability Theory for Computer Scientists', 9, -1, 'math', 3, ['21-122'], ['15-259'], 'alt'),
    ])

# ------------------------------------------------------ CMU Mechanical (BS)
PROGRAMS['cmu-me'] = dict(
    school='CMU', program='MECHANICAL ENG BS · CIT', tab='Mechanical Engineering',
    unit='units', abbr='u', total=380, grad='Spring 2028', year='SOPHOMORE',
    terms=CMU_TERMS, tiers=['FIRST YEAR', 'MATH & PHYSICS', 'ENGINEERING SCIENCE',
                            'MECHANICS & THERMAL', 'DESIGN & CAPSTONE'],
    key='24-261', keyname='Mechanics I: 2D Design',
    headline="Register for 24-261 — Mechanics II and Mechanical Design are both waiting on it.",
    blurb="Mechanics I is the gate into the design sequence. Until it clears, 24-262 will not register, and the mechanical design capstone behind it slides a year.",
    courses=[
        ('21-120', 'Differential and Integral Calculus', 10, 0, 'math', 0, [], [], None),
        ('33-141', 'Physics I for Engineering Students', 12, 0, 'sci', 0, [], [], None),
        ('76-101', 'Interpretation and Argument', 9, 0, 'huss', None, [], [], None),
        ('99-101', 'Computing @ Carnegie Mellon', 3, 0, 'free', None, [], [], None),
        ('21-122', 'Integration and Approximation', 10, 1, 'math', 1, ['21-120'], [], None),
        ('24-101', 'Fundamentals of Mechanical Engineering', 12, 1, 'major', 1, ['21-120'], [], None),
        ('09-105', 'Introduction to Modern Chemistry I', 10, 1, 'sci', 1, [], [], None),
        ('15-110', 'Principles of Computing', 10, 1, 'major', 1, [], [], None),
        ('21-259', 'Calculus in Three Dimensions', 10, 2, 'math', 2, ['21-122'], [], None),
        ('33-142', 'Physics II for Engineering Students', 12, 2, 'sci', 2, ['33-141'], [], None),
        ('24-221', 'Thermodynamics', 10, 2, 'major', 2, ['24-101', '21-122'], [], None),
        ('79-104', 'Global Histories', 9, 2, 'huss', None, [], [], None),
        ('21-260', 'Differential Equations', 10, 3, 'math', 2, ['21-122'], [], None),
        ('24-231', 'Fluid Mechanics', 10, 3, 'major', 3, ['24-101', '21-259'], [], None),
        ('24-251', 'Electronics for Sensing and Actuation', 3, 3, 'major', 2, ['24-101'], [], None),
        ('76-270', 'Writing for the Professions', 9, 3, 'huss', None, ['76-101'], [], None),
        ('24-261', 'Mechanics I: 2D Design', 10, 4, 'major', 2, ['24-101', '21-122'], [], 'key'),
        ('24-351', 'Dynamics', 10, 4, 'major', 3, ['24-101', '21-260'], [], None),
        ('24-311', 'Numerical Methods', 12, 4, 'major', 3, ['21-260', '15-110'], [], None),
        ('24-262', 'Mechanics II: 3D Design', 10, 4, 'major', None, [], [], 'ghost'),
        ('24-262', 'Mechanics II: 3D Design', 10, 5, 'major', 3, ['24-261'], [], None),
        ('24-322', 'Heat Transfer', 10, 5, 'major', 3, ['24-231', '24-221'], [], None),
        ('24-352', 'Dynamic Systems and Controls', 12, 5, 'major', 4, ['24-351', '21-260'], [], None),
        ('24-321', 'Thermal-Fluids Experimentation', 12, 6, 'major', 4, ['24-231', '24-221'], [], None),
        ('24-370', 'Mechanical Design: Methods and Applications', 12, 6, 'major', 4, ['24-262'], [], None),
        ('73-102', 'Principles of Microeconomics', 9, 6, 'huss', None, [], [], None),
        ('24-441', 'Product Design', 12, 7, 'major', 4, ['24-370'], ['24-671'], None),
        ('24-402', 'Mechanical Engineering Elective', 9, 7, 'major', 4, ['24-262'], [], None),
        ('76-272', 'Free Elective', 9, 7, 'free', None, [], [], None),
        ('24-671', 'Electromechanical Systems Design', 12, -1, 'major', 4, ['24-370'], ['24-441'], 'alt'),
    ])


# ------------------------------------------------------- CMU Civil Engineering
# Source: CMU Civil & Environmental Engineering, "Civil Engineering B.S. Course
# Sequence" (cee.engineering.cmu.edu). Course numbers, titles and unit counts are
# transcribed from that published sequence; term placement is the sequence's own.
# Prerequisites are NOT published there — the ones below are inferred from
# sequence order and carried as needs_review (see REVIEW_NOTES).
PROGRAMS['cmu-ce'] = dict(
    school='CMU', program='CIVIL ENG BS · CIT', tab='Civil Engineering',
    unit='units', abbr='u', total=384, grad='Spring 2028', year='SOPHOMORE',
    terms=CMU_TERMS, tiers=['FIRST YEAR', 'MECHANICS & MATH', 'SYSTEMS & COMPUTING',
                            'ENVIRONMENT & FLUIDS', 'DESIGN & MANAGEMENT'],
    key='12-355', keyname='Fluid Mechanics',
    headline="Register for 12-355 — the Fluid Mechanics Lab cannot run before it.",
    blurb="Fluid Mechanics gates its own lab. The draft has the lab in the same term, which will not register; the lab has to move a term later.",
    courses=[
        ('12-100', 'Exploring CEE: Infrastructure and Environment in a Changing World', 12, 0, 'major', 0, [], [], None),
        ('21-120', 'Differential and Integral Calculus', 10, 0, 'math', 0, [], [], None),
        ('33-141', 'Physics I for Engineering Students', 12, 0, 'sci', 0, [], [], None),
        ('99-101', 'Core@CMU', 3, 0, 'free', None, [], [], None),
        ('21-122', 'Integration and Approximation', 10, 1, 'math', 1, ['21-120'], [], None),
        ('33-142', 'Physics II for Engineering and Physics Students', 12, 1, 'sci', 1, ['33-141'], [], None),
        ('09-101', 'Introduction to Experimental Chemistry', 3, 1, 'sci', 1, [], [], None),
        ('12-200', 'CEE Challenges: Design in a Changing World', 9, 2, 'major', 1, ['12-100'], [], None),
        ('12-212', 'Statics', 9, 2, 'major', 1, ['21-120', '33-141'], [], 'key'),
        ('12-233', 'CEE Infrastructure Systems in Action', 2, 2, 'major', 1, [], [], None),
        ('21-259', 'Calculus in Three Dimensions', 9, 2, 'math', 2, ['21-122'], ['21-254'], None),
        ('15-110', 'Principles of Computing', 10, 2, 'major', 1, [], [], None),
        ('12-231', 'Solid Mechanics', 9, 3, 'major', 2, ['12-212'], [], None),
        ('12-234', 'Sensing and Data Acquisition for Engineering Systems', 4, 3, 'major', 2, ['12-233'], [], None),
        ('12-271', 'Computation and Data Science for Civil & Environmental Engineering', 9, 3, 'major', 2, ['15-110'], [], None),
        ('21-260', 'Differential Equations', 9, 3, 'math', 2, ['21-122'], [], None),
        ('09-105', 'Introduction to Modern Chemistry I', 9, 3, 'sci', 2, ['09-101'], [], None),
        ('12-301', 'CEE Projects: Integrating the Built, Natural and Information Environments', 9, 4, 'major', 3, ['12-200'], [], None),
        ('12-351', 'Environmental Engineering', 9, 4, 'major', 3, ['09-105'], [], None),
        ('12-355', 'Fluid Mechanics', 9, 4, 'major', 3, ['12-212', '21-260'], [], 'key'),
        # seeded student's mis-sequencing: the lab drafted alongside its own
        # prerequisite. The published sequence puts both in Junior Fall.
        ('12-356', 'Fluid Mechanics Lab', 2, 4, 'major', None, [], [], 'ghost'),
        ('12-356', 'Fluid Mechanics Lab', 2, 5, 'major', 3, ['12-355'], [], None),
        ('36-220', 'Engineering Statistics and Quality Control', 9, 4, 'math', 3, ['21-122'], [], None),
        ('12-335', 'Soil Mechanics', 9, 5, 'major', 3, ['12-231'], [], None),
        ('27-357', 'Introduction to Materials Selection', 6, 5, 'sci', 3, [], [], None),
        ('12-371', 'Advanced Computing and Problem Solving in Civil and Environmental Engineering', 9, 5, 'major', 3, ['12-271'], [], None),
        ('12-333', 'Experimental & Sensing Systems Design and Computation for Infrastructure Systems', 4, 5, 'major', 3, ['12-234'], [], None),
        ('12-401', 'CEE Design: Imagine, Build, Test', 12, 6, 'major', 4, ['12-301', '12-335'], [], None),
        ('12-411', 'Project Management for Engineering and Construction', 9, 6, 'major', 4, ['12-301'], [], None),
        ('GEN-1', 'General Education Course', 9, 1, 'huss', None, [], [], None),
        ('GEN-2', 'General Education Course', 9, 5, 'huss', None, [], [], None),
        ('ELEC-1', 'Civil Engineering Elective', 9, 6, 'free', None, [], [], None),
        ('ELEC-2', 'Civil Engineering Elective', 9, 7, 'free', None, [], [], None),
    ])

# ---------------------------------------------------- CMU Chemical Engineering
# Source: CMU Chemical Engineering, "Curriculum" — sequence for the graduating
# class of 2028 and beyond (cheme.engineering.cmu.edu). Numbers, titles and units
# are transcribed from that page; its per-semester unit totals sum to 391, which
# is the published minimum for the degree. Prerequisites are inferred from
# sequence order, as above.
PROGRAMS['cmu-cheme'] = dict(
    school='CMU', program='CHEMICAL ENG BS · CIT', tab='Chemical Engineering',
    unit='units', abbr='u', total=391, grad='Spring 2028', year='SOPHOMORE',
    terms=CMU_TERMS, tiers=['FIRST YEAR', 'CHEMISTRY & MATH', 'TRANSPORT & THERMO',
                            'REACTION & SEPARATION', 'DESIGN & CONTROL'],
    key='06-323', keyname='Heat and Mass Transfer',
    headline="Register for 06-323 — Unit Operations and everything after it wait on this one.",
    blurb="Heat and Mass Transfer is the gate into the separations sequence. Until it clears, Unit Operations will not register, and process design behind it slides a year.",
    courses=[
        ('21-120', 'Differential and Integral Calculus', 10, 0, 'math', 0, [], [], None),
        ('99-101', 'Core@CMU', 3, 0, 'free', None, [], [], None),
        ('06-100', 'Introduction to Chemical Engineering', 12, 0, 'major', 0, [], [], None),
        ('09-105', 'Introduction to Modern Chemistry I', 10, 0, 'sci', 0, [], [], None),
        ('21-122', 'Integration and Approximation', 10, 1, 'math', 1, ['21-120'], [], None),
        ('33-141', 'Physics I for Engineering Students', 12, 1, 'sci', 1, ['21-120'], [], None),
        ('21-254', 'Linear Algebra and Vector Calculus for Engineers', 11, 2, 'math', 2, ['21-122'], [], None),
        ('06-223', 'Chemical Engineering Thermodynamics', 12, 2, 'major', 1, ['06-100', '21-122'], [], 'key'),
        ('06-222', 'Sophomore Chemical Engineering Seminar', 1, 2, 'major', 1, ['06-100'], [], None),
        ('09-106', 'Modern Chemistry II', 10, 2, 'sci', 2, ['09-105'], [], None),
        ('06-261', 'Fluid Mechanics', 9, 3, 'major', 2, ['06-100', '21-122'], [], None),
        ('06-262', 'Mathematical Methods of Chemical Engineering', 12, 3, 'major', 2, ['21-254'], [], None),
        ('09-221', 'Laboratory I: Introduction to Chemical Analysis', 12, 3, 'sci', 2, ['09-106'], [], None),
        ('06-322', 'Junior Chemical Engineering Seminar', 2, 4, 'major', 3, ['06-222'], [], None),
        ('06-323', 'Heat and Mass Transfer', 9, 4, 'major', 3, ['06-223', '06-261'], [], 'key'),
        # seeded student's mis-sequencing, not the published sequence, which
        # places Unit Operations in Third Year Spring.
        ('06-361', 'Unit Operations of Chemical Engineering', 9, 4, 'major', None, [], [], 'ghost'),
        ('06-324', 'Computational Optimization and Machine Learning for Chemical Engineering', 12, 4, 'major', 3, ['06-262'], [], None),
        ('09-217', 'Organic Chemistry I', 9, 4, 'sci', 3, ['09-106'], ['09-219'], None),
        ('06-310', 'Molecular Foundations of Chemical Engineering', 9, 4, 'major', 3, ['09-106'], [], None),
        ('06-361', 'Unit Operations of Chemical Engineering', 9, 5, 'major', 3, ['06-323'], [], None),
        ('06-363', 'Transport Process Laboratory', 9, 5, 'major', 3, ['06-323'], [], None),
        ('06-364', 'Chemical Reaction Engineering', 9, 5, 'major', 3, ['06-223', '06-310'], [], None),
        ('06-421', 'Chemical Process Systems Design', 12, 6, 'major', 4, ['06-361', '06-364'], [], None),
        ('06-423', 'Unit Operations Laboratory', 9, 6, 'major', 4, ['06-363'], [], None),
        ('06-463', 'Chemical Product Design', 9, 7, 'major', 4, ['06-421'], [], None),
        ('06-464', 'Chemical Engineering Process Control', 9, 7, 'major', 4, ['06-421'], [], None),
        ('09-219', 'Modern Organic Chemistry', 10, -1, 'sci', 3, ['09-106'], ['09-217'], 'alt'),
        ('76-101', 'Interpretation and Argument', 9, 0, 'huss', None, [], [], None),
        ('GEN-1', 'General Education Course', 9, 1, 'huss', None, [], [], None),
        ('GEN-2', 'General Education Course', 9, 5, 'huss', None, [], [], None),
        ('ELEC-1', 'Unrestricted Elective', 9, 6, 'free', None, [], [], None),
        ('ELEC-2', 'Unrestricted Elective', 9, 7, 'free', None, [], [], None),
    ])

# --------------------------------------------------------------------------- #
# Inferred-prerequisite notes (sidecar so the tuple tables stay 9-wide).
# These are prerequisites collapsed from CMU's published OR-lists or inferred from
# sample-sequence order; the seeds carry them as needs_review + review_note.
# --------------------------------------------------------------------------- #
REVIEW_NOTES = {
    # Civil and Chemical publish a sample sequence with numbers, titles and units,
    # but no prerequisite lists — these are read off the sequence order and must
    # be confirmed against the department's own prerequisite tables.
    'cmu-ce': {
        '12-231': 'Prerequisite inferred from the published sequence order, not a stated prerequisite.',
        '12-355': 'Prerequisite inferred from the published sequence order, not a stated prerequisite.',
        '12-335': 'Prerequisite inferred from the published sequence order, not a stated prerequisite.',
        '12-401': 'Prerequisite inferred from the published sequence order, not a stated prerequisite.',
    },
    'cmu-cheme': {
        '06-323': 'Prerequisite inferred from the published sequence order, not a stated prerequisite.',
        '06-364': 'Prerequisite inferred from the published sequence order, not a stated prerequisite.',
        '06-421': 'Prerequisite inferred from the published sequence order, not a stated prerequisite.',
    },
    'cmu-cs': {
        '10-315': 'Prerequisites inferred from sample-sequence order; program page printed none.',
        '15-259': "Prereq collapsed from CMU's OR-list (21-127 / 15-251 / 21-128 / 15-151) to the "
                  "sample-sequence course; grades dropped.",
    },
}

PROGRAM_ORDER = list(PROGRAMS)

# Tuple index names, so the shared helpers read clearly.
CODE, TITLE, CR, TERM, GROUP, TIER, REQ, ANTI, FLAG = range(9)


# --------------------------------------------------------------------------- #
# shared derivation — used by BOTH emitters so they cannot disagree
# --------------------------------------------------------------------------- #

def repo_root() -> Path:
    """Repo root, derived like rebuild.py — never an absolute machine path."""
    return ROOT


def level_of(code: str) -> int:
    """Course level from the trailing number — mirrors the JS ``levelOf``."""
    m = re.search(r'(\d{3,4})\s*$', code)
    if not m:
        return 100
    n = int(m.group(1))
    if n >= 1000:
        return (n // 1000) * 100
    return (n // 100) * 100 or 100


def offering_of(code: str, tier) -> str:
    """Fabricated offered-terms string — an exact mirror of the JS ``offeringOf`` hash.

    This is DERIVED data, not catalog data; the seed marks it ``offering_source:
    "derived"`` so a planner never mistakes it for a real registrar offering.
    """
    lvl = level_of(code)
    h = 5
    for ch in code:
        h = (h * 33 + ord(ch)) & 0xFFFFFFFF
    if lvl <= 100 or tier == 0:
        return 'Summer · Fall · Spring'
    if lvl >= 400 or tier == 4:
        return 'Fall' if (h % 2) else 'Spring'
    if h % 4 == 0:
        return 'Fall' if ((h >> 1) % 2) else 'Spring'
    return 'Fall · Spring'


def _terms_st(P) -> list[dict]:
    return [{'st': tm[3]} for tm in P['terms']]


def status_of(P, t, flag) -> str:
    """The single status rule, delegated to ``graph.status_for`` (the canonical copy)."""
    return graph.status_for(_terms_st(P), t, {'ghost': flag == 'ghost', 'key': flag == 'key'})


GROUPS_ORDER = ['major', 'math', 'sci', 'huss', 'free']


def derive_groups(P) -> list[dict]:
    """The requirement group buckets, counted off the tuple table.

    Reproduces the frontend's ``REQS`` exactly. Both emitters format from this one
    function, so the JS ``REQS`` and the seed ``groups`` cannot drift apart. These are
    *display groupings by ``g``*, NOT degree rules — see ``requirements`` for those.
    """
    cs = P['courses']
    out = []
    for g in GROUPS_ORDER:
        rows = [c for c in cs if c[GROUP] == g and c[FLAG] not in ('ghost', 'alt')]
        if not rows:
            continue
        d = sum(1 for c in rows if status_of(P, c[TERM], c[FLAG]) == 'done')
        p = sum(1 for c in rows if status_of(P, c[TERM], c[FLAG]) == 'current')
        missing = [c[CODE] for c in rows if status_of(P, c[TERM], c[FLAG]) in ('todo', 'plan')][:5]
        out.append({'group': g, 'name': GROUP_LABEL[g], 'done': d, 'in_progress': p,
                    'total': len(rows), 'count': f'{d} of {len(rows)} courses', 'missing': missing})
    return out


def derived_totals(P) -> dict:
    """The META credit numbers the frontend shows, derived from the table."""
    cs = P['courses']
    done = sum(c[CR] for c in cs if status_of(P, c[TERM], c[FLAG]) == 'done')
    prog = sum(c[CR] for c in cs if status_of(P, c[TERM], c[FLAG]) == 'current')
    key_cr = next((c[CR] for c in cs if c[FLAG] == 'key'), 0)
    ghost_cr = next((c[CR] for c in cs if c[FLAG] == 'ghost'), 0)
    return {'doneCr': done, 'inProgCr': prog, 'totalCr': P['total'],
            'behindCr': key_cr + ghost_cr, 'pct': round(done / P['total'] * 100)}


def snapshot_of(P) -> str:
    """The snapshot sentence, derived — references the bottleneck (keyname)."""
    tot = derived_totals(P)
    return (f"{tot['doneCr']} of {P['total']} {P['unit']} are in the bank with "
            f"{tot['inProgCr']} more in progress. The gap isn't effort, it's sequencing: "
            f"{P['keyname']} never made it onto a schedule, and the courses above it are still waiting.")
