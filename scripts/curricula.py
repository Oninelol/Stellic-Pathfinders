#!/usr/bin/env python3
"""Author the SCHOOLS dataset and splice it into build/template.html.

Each program is written as a compact course table; META credit totals, the
requirement buckets and every course status are DERIVED from that table, so the
numbers on screen cannot drift from the courses on the board.

Course tuple: (code, title, credits, term, group, tier, prereqs, antis, flag)
  term   0-7 index into TERMS, or -1 for an unscheduled alternative
  group  'major' | 'math' | 'sci' | 'huss' | 'free'  -> drives requirement buckets
  tier   0-4 column on the dependency graph, or None for a breadth row (gen:1)
  flag   None | 'key' (the bottleneck) | 'ghost' (deferred placeholder) | 'alt'

Status is derived from the term: 0-2 done, 3 current, 4+ plan; 'key' becomes
todo and 'ghost' becomes blocked.

This file is now DATA + shared derivation only. Two thin formatters consume it:

    scripts/emit_frontend.py   tuples -> SCHOOLS block -> build/template.html
    scripts/emit_seeds.py      tuples -> data/<program-id>.json (one per program)

A course edit therefore happens in exactly one place (the tuple tables below) and
both targets regenerate from it. Status, the requirement group buckets, and the
derived offerings all live here so the two emitters cannot disagree.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import graph  # noqa: E402  (scripts may import app.graph; graph imports no app)

# ---------------------------------------------------------------- term tables
NYU_TERMS = [
    ('F24', 'Fall 2024', 'FRESHMAN', 'done'), ('S25', 'Spring 2025', 'FRESHMAN', 'done'),
    ('F25', 'Fall 2025', 'SOPHOMORE', 'done'), ('S26', 'Spring 2026', 'IN PROGRESS', 'current'),
    ('F26', 'Fall 2026', 'JUNIOR · DRAFT', 'plan'), ('S27', 'Spring 2027', 'JUNIOR · DRAFT', 'plan'),
    ('F27', 'Fall 2027', 'SENIOR · DRAFT', 'plan'), ('S28', 'Spring 2028', 'SENIOR · DRAFT', 'plan'),
]
CMU_TERMS = [(k, l, ('FIRST YEAR' if t in ('FRESHMAN',) else t), s) for k, l, t, s in NYU_TERMS]

GROUP_LABEL = {
    'major': 'Major sequence', 'math': 'Mathematics', 'sci': 'Science',
    'huss': 'Humanities & social sciences', 'free': 'Free electives',
}

# Shared NYU Tandon first-year spine (identical across the engineering majors).
def tandon_core(prog_intro):
    """(code,title,cr) rows every Tandon engineering major shares, plus its intro course."""
    return [
        ('MA-UY 1024', 'Calculus I for Engineers', 4, 0, 'math', 0, [], [], None),
        ('EG-UY 1004', 'Introduction to Engineering and Design', 4, 0, 'major', 0, [], [], None),
        ('EXPOS-UA 1', 'Writing as Inquiry', 4, 0, 'huss', None, [], [], None),
        ('MA-UY 1124', 'Calculus II for Engineers', 4, 1, 'math', 1, ['MA-UY 1024'], [], None),
        ('PH-UY 1013', 'Mechanics', 3, 1, 'sci', 1, ['MA-UY 1024'], [], None),
        ('EXPOS-UA 22', 'Advanced Writing for Engineers', 4, 1, 'huss', None, ['EXPOS-UA 1'], [], None),
        prog_intro,
    ]

# ============================================================ PROGRAM TABLES
PROGRAMS = {}

# ---------------------------------------------------------------- NYU CS (BA)
PROGRAMS['nyu-cs'] = dict(
    school='NYU', program='CS BA · COURANT', tab='Computer Science',
    unit='credits', abbr='cr', total=128, grad='Spring 2028', year='SOPHOMORE',
    terms=NYU_TERMS, tiers=['PREREQUISITE', 'INTRO SEQUENCE', 'DATA STRUCTURES & MATH',
                            'SYSTEMS & ALGORITHMS', '400-LEVEL ELECTIVES'],
    key='MATH-UA 120', keyname='Discrete Mathematics',
    headline="Register for MATH-UA 120 — Basic Algorithms and Theory of Computation are both waiting on it.",
    blurb="Discrete Mathematics is the one prerequisite of Basic Algorithms you never scheduled. Until it clears, CSCI-UA 310 will not register, and the 400-level electives stacked behind it all slide a year.",
    requirements=[
        {'id': 'cs-required', 'name': 'Required computer science', 'min_courses': 6,
         'match': {'explicit': ['CSCI-UA 2', 'CSCI-UA 101', 'CSCI-UA 102', 'CSCI-UA 201', 'CSCI-UA 202', 'CSCI-UA 310']}},
        {'id': 'math-required', 'name': 'Required mathematics', 'min_courses': 2,
         'match': {'explicit': ['MATH-UA 120', 'MATH-UA 121']}},
        {'id': 'cs-electives', 'name': '400-level CS electives', 'min_courses': 5,
         'match': {'any_of': ['CSCI-UA 453', 'CSCI-UA 479', 'CSCI-UA 473', 'CSCI-UA 467', 'CSCI-UA 421', 'CSCI-UA 480']}},
        {'id': 'college-core', 'name': 'College Core Curriculum', 'min_courses': 6,
         'match': {'any_of': ['EXPOS-UA 1', 'FYSEM-UA 1', 'CORE-UA 401', 'CORE-UA 550', 'CORE-UA 710', 'CORE-UA 201', 'CORE-UA 301', 'CORE-UA 610']}},
        {'id': 'language', 'name': 'Foreign language', 'min_courses': 4,
         'match': {'any_of': ['FREN-UA 1', 'FREN-UA 2', 'FREN-UA 11']}},
    ],
    courses=[
        ('CSCI-UA 2', 'Intro to Computer Programming', 4, 0, 'major', 0, [], [], None),
        ('MATH-UA 121', 'Calculus I', 4, 0, 'math', 0, [], ['MATH-UA 131'], None),
        ('EXPOS-UA 1', 'Writing as Inquiry', 4, 0, 'huss', None, [], [], None),
        ('FYSEM-UA 1', 'First-Year Seminar', 4, 0, 'huss', None, [], [], None),
        ('CSCI-UA 101', 'Intro to Computer Science', 4, 1, 'major', 1, ['CSCI-UA 2'], [], None),
        ('CORE-UA 401', 'Texts and Ideas', 4, 1, 'huss', None, [], [], None),
        ('CORE-UA 550', 'Cultures and Contexts', 4, 1, 'huss', None, [], [], None),
        ('FREN-UA 1', 'Elementary French I', 4, 1, 'huss', None, [], [], None),
        ('CSCI-UA 102', 'Data Structures', 4, 2, 'major', 2, ['CSCI-UA 101'], [], None),
        ('CORE-UA 201', 'Physical Science', 4, 2, 'sci', None, [], [], None),
        ('FREN-UA 2', 'Elementary French II', 4, 2, 'huss', None, ['FREN-UA 1'], [], None),
        ('CORE-UA 710', 'Expressive Culture', 4, 2, 'huss', None, [], [], None),
        ('CSCI-UA 201', 'Computer Systems Organization', 4, 3, 'major', 3, ['CSCI-UA 102'], [], None),
        ('CORE-UA 301', 'Life Science', 4, 3, 'sci', None, [], [], None),
        ('FREN-UA 11', 'Intermediate French I', 4, 3, 'huss', None, ['FREN-UA 2'], [], None),
        ('CORE-UA 610', 'Societies and the Social Sciences', 4, 3, 'huss', None, [], [], None),
        ('MATH-UA 120', 'Discrete Mathematics', 4, 4, 'math', 1, [], [], 'key'),
        ('CSCI-UA 202', 'Operating Systems', 4, 4, 'major', 4, ['CSCI-UA 201'], [], None),
        ('MATH-UA 140', 'Linear Algebra', 4, 4, 'math', 2, ['MATH-UA 121'], [], None),
        ('CSCI-UA 310', 'Basic Algorithms', 4, 4, 'major', None, [], [], 'ghost'),
        ('CSCI-UA 310', 'Basic Algorithms', 4, 5, 'major', 3, ['CSCI-UA 102', 'MATH-UA 120', 'MATH-UA 121'], [], None),
        ('CSCI-UA 453', 'Theory of Computation', 4, 5, 'major', 4, ['CSCI-UA 102', 'MATH-UA 120'], [], None),
        ('CSCI-UA 479', 'Data Management and Analysis', 4, 5, 'major', 4, ['CSCI-UA 102'], [], None),
        ('CSCI-UA 473', 'Fundamentals of Machine Learning', 4, 6, 'major', 4, ['CSCI-UA 310', 'MATH-UA 140'], [], None),
        ('CSCI-UA 467', 'Applied Internet Technology', 4, 6, 'major', 4, ['CSCI-UA 201'], [], None),
        ('ELEC-UA 1', 'Free Elective', 4, 6, 'free', None, [], [], None),
        ('CSCI-UA 421', 'Numerical Computing', 4, 7, 'major', 4, ['CSCI-UA 102', 'MATH-UA 140'], [], None),
        ('CSCI-UA 480', 'Special Topics: Computer Vision', 4, 7, 'major', 4, ['CSCI-UA 310'], [], None),
        ('ELEC-UA 2', 'Free Elective', 4, 7, 'free', None, [], [], None),
        ('MATH-UA 131', 'Mathematics for Economics I', 4, -1, 'math', 0, [], ['MATH-UA 121'], 'alt'),
    ])

# ------------------------------------------------- NYU Tandon: Mechanical (BS)
PROGRAMS['nyu-me'] = dict(
    school='NYU', program='MECHANICAL ENG BS · TANDON', tab='Mechanical Engineering',
    unit='credits', abbr='cr', total=131, grad='Spring 2028', year='SOPHOMORE',
    terms=NYU_TERMS, tiers=['FIRST YEAR', 'MATH & PHYSICS', 'ENGINEERING SCIENCE',
                            'MECHANICS & THERMAL', 'DESIGN & CAPSTONE'],
    key='ME-UY 2213', keyname='Statics',
    headline="Register for ME-UY 2213 — Mechanics of Materials and Machine Design are both waiting on it.",
    blurb="Statics is the gate into the mechanics sequence. Until it clears, Mechanics of Materials will not register, and Machine Design and the Structures Practicum behind it slide with it.",
    courses=tandon_core(('ME-UY 1012', 'Introduction to Mechanical Engineering', 2, 1, 'major', 1, [], [], None)) + [
        ('CM-UY 1003', 'General Chemistry for Engineers', 3, 0, 'sci', None, [], [], None),
        ('CS-UY 1113', 'Problem Solving and Programming I', 3, 1, 'major', 1, [], [], None),
        ('MA-UY 2034', 'Linear Algebra and Differential Equations', 4, 2, 'math', 2, ['MA-UY 1124'], [], None),
        ('PH-UY 2023', 'Electricity, Magnetism, & Fluids', 3, 2, 'sci', 2, ['PH-UY 1013'], [], None),
        ('HUSS-UY 1', 'Humanities & Social Sciences Elective', 4, 2, 'huss', None, [], [], None),
        ('MA-UY 2114', 'Calculus III: Multi-Dimensional Calculus', 4, 3, 'math', 2, ['MA-UY 1124'], [], None),
        ('ME-UY 2123', 'Engineering Design Methods', 3, 3, 'major', 2, ['EG-UY 1004'], [], None),
        ('ME-UY 2813', 'Introduction to Materials Science', 3, 3, 'major', 2, ['CM-UY 1003'], [], None),
        ('HUSS-UY 2', 'Humanities & Social Sciences Elective', 4, 3, 'huss', None, [], [], None),
        ('ME-UY 2213', 'Statics', 3, 4, 'major', 2, ['PH-UY 1013', 'MA-UY 1124'], [], 'key'),
        ('ME-UY 2223', 'Dynamics', 3, 4, 'major', 3, ['ME-UY 2213'], [], None),
        ('ME-UY 3333', 'Thermodynamics', 3, 4, 'major', 3, ['PH-UY 1013', 'MA-UY 2034'], [], None),
        ('ME-UY 3213', 'Mechanics of Materials', 3, 4, 'major', None, [], [], 'ghost'),
        ('ME-UY 3213', 'Mechanics of Materials', 3, 5, 'major', 3, ['ME-UY 2213'], [], None),
        ('ME-UY 3313', 'Fluid Mechanics', 3, 5, 'major', 3, ['ME-UY 2213', 'MA-UY 2114'], [], None),
        ('ME-UY 3513', 'Measurement Systems', 3, 5, 'major', 3, ['PH-UY 2023'], [], None),
        ('ME-UY 3811', 'Materials Science Laboratory', 1, 5, 'major', None, ['ME-UY 2813'], [], None),
        ('ME-UY 3233', 'Machine Design', 3, 6, 'major', 4, ['ME-UY 3213'], [], None),
        ('ME-UY 3413', 'Automatic Control', 3, 6, 'major', 4, ['ME-UY 2223', 'MA-UY 2034'], [], None),
        ('ME-UY 4313', 'Heat Transfer', 3, 6, 'major', 4, ['ME-UY 3313', 'ME-UY 3333'], [], None),
        ('ME-UY 4103', 'Senior Design I', 3, 6, 'major', 4, ['ME-UY 2123', 'ME-UY 3213'], [], None),
        ('ME-UY 4214', 'Finite Element Modeling, Design and Analysis', 4, 7, 'major', 4, ['ME-UY 3213'], [], None),
        ('ME-UY 4113', 'Senior Design II', 3, 7, 'major', 4, ['ME-UY 4103'], [], None),
        ('HUSS-UY 3', 'Humanities & Social Sciences Elective', 4, 7, 'huss', None, [], [], None),
        ('FREE-UY 1', 'Free Elective', 3, 7, 'free', None, [], [], None),
    ])

# ----------------------------------------------------- NYU Tandon: Civil (BS)
PROGRAMS['nyu-ce'] = dict(
    school='NYU', program='CIVIL ENG BS · TANDON', tab='Civil Engineering',
    unit='credits', abbr='cr', total=129, grad='Spring 2028', year='SOPHOMORE',
    terms=NYU_TERMS, tiers=['FIRST YEAR', 'MATH & PHYSICS', 'STRUCTURAL SCIENCE',
                            'CIVIL SYSTEMS', 'CAPSTONE & ELECTIVES'],
    key='CE-UY 2112', keyname='Structural Statics',
    headline="Register for CE-UY 2112 — Strength of Materials and Analysis of Determinate Structures are both waiting on it.",
    blurb="Structural Statics is the gate into the structures sequence. Until it clears, Strength of Materials will not register, and Structural Engineering behind it slides a year.",
    courses=tandon_core(('CE-UY 1002', 'Intro to Civil and Environmental Engineering', 2, 1, 'major', 1, [], [], None)) + [
        ('CM-UY 1003', 'General Chemistry for Engineers', 3, 0, 'sci', None, [], [], None),
        ('CS-UY 1113', 'Problem Solving and Programming I', 3, 1, 'major', 1, [], [], None),
        ('MA-UY 2034', 'Linear Algebra and Differential Equations', 4, 2, 'math', 2, ['MA-UY 1124'], [], None),
        ('PH-UY 2023', 'Electricity, Magnetism, & Fluids', 3, 2, 'sci', 2, ['PH-UY 1013'], [], None),
        ('CE-UY 2533', 'Construction Project Management', 3, 2, 'major', 2, [], [], None),
        ('HUSS-UY 1', 'Humanities & Social Sciences Elective', 4, 2, 'huss', None, [], [], None),
        ('MA-UY 2224', 'Probability and Statistics for Engineers', 4, 3, 'math', 2, ['MA-UY 1124'], [], None),
        ('CE-UY 2213', 'Fluid Mechanics and Hydraulics', 3, 3, 'major', 3, ['PH-UY 1013'], [], None),
        ('CE-UY 2343', 'Transportation Engineering', 3, 3, 'major', 3, [], [], None),
        ('HUSS-UY 2', 'Humanities & Social Sciences Elective', 4, 3, 'huss', None, [], [], None),
        ('CE-UY 2112', 'Structural Statics', 2, 4, 'major', 2, ['PH-UY 1013', 'MA-UY 1124'], [], 'key'),
        ('CE-UY 3223', 'Fundamentals of Environmental Engineering', 3, 4, 'major', 3, ['CM-UY 1003'], [], None),
        ('CE-UY 3013', 'Computing in Civil Engineering', 3, 4, 'major', 3, ['CS-UY 1113'], [], None),
        ('CE-UY 2143', 'Analysis of Determinate Structures', 3, 4, 'major', None, [], [], 'ghost'),
        ('CE-UY 2122', 'Strength of Materials', 2, 5, 'major', 3, ['CE-UY 2112'], [], None),
        ('CE-UY 2143', 'Analysis of Determinate Structures', 3, 5, 'major', 3, ['CE-UY 2112'], [], None),
        ('CE-UY 3243', 'Water Resources Engineering', 3, 5, 'major', 3, ['CE-UY 2213'], [], None),
        ('CE-UY 3183', 'Structural Engineering', 3, 6, 'major', 4, ['CE-UY 2143', 'CE-UY 2122'], [], None),
        ('CE-UY 3153', 'Geotechnical Engineering', 3, 6, 'major', 4, ['CE-UY 2122'], [], None),
        ('CE-UY 3163', 'Materials for Built Environment', 3, 6, 'major', 4, ['CE-UY 2122'], [], None),
        ('CE-UY 4092', 'Leadership, Business, Policy & Ethics', 2, 7, 'major', 4, [], [], None),
        ('CE-UY 4803', 'Civil Engineering Capstone', 3, 7, 'major', 4, ['CE-UY 3183', 'CE-UY 3153'], [], None),
        ('HUSS-UY 3', 'Humanities & Social Sciences Elective', 4, 7, 'huss', None, [], [], None),
        ('FREE-UY 1', 'Free Elective', 3, 7, 'free', None, [], [], None),
    ])

# -------------------------------------------------- NYU Tandon: Computer (BS)
PROGRAMS['nyu-cpe'] = dict(
    school='NYU', program='COMPUTER ENG BS · TANDON', tab='Computer Engineering',
    unit='credits', abbr='cr', total=128, grad='Spring 2028', year='SOPHOMORE',
    terms=NYU_TERMS, tiers=['FIRST YEAR', 'PROGRAMMING & MATH', 'CIRCUITS & LOGIC',
                            'ARCHITECTURE', 'DESIGN PROJECT'],
    key='ECE-UY 2004', keyname='Fundamentals of Electric Circuits',
    headline="Register for ECE-UY 2004 — Fundamentals of Electronics I and Embedded Systems are both waiting on it.",
    blurb="Fundamentals of Electric Circuits is the gate into the hardware sequence. Until it clears, Electronics I will not register, and the embedded systems work behind it slides a year.",
    courses=[
        ('MA-UY 1024', 'Calculus I for Engineers', 4, 0, 'math', 0, [], [], None),
        ('CS-UY 1114', 'Intro to Programming & Problem Solving', 4, 0, 'major', 0, [], [], None),
        ('EG-UY 1004', 'Introduction to Engineering and Design', 4, 0, 'major', 0, [], [], None),
        ('EXPOS-UY 1', 'Writing as Inquiry', 4, 0, 'huss', None, [], [], None),
        ('MA-UY 1124', 'Calculus II for Engineers', 4, 1, 'math', 1, ['MA-UY 1024'], [], None),
        ('PH-UY 1013', 'Mechanics', 3, 1, 'sci', 1, ['MA-UY 1024'], [], None),
        ('CS-UY 1134', 'Data Structures and Algorithms', 4, 1, 'major', 1, ['CS-UY 1114'], [], None),
        ('ECE-UY 1002', 'Intro to Electrical and Computer Engineering', 2, 1, 'major', 1, [], [], None),
        ('MA-UY 2034', 'Linear Algebra and Differential Equations', 4, 2, 'math', 2, ['MA-UY 1124'], [], None),
        ('PH-UY 2023', 'Electricity, Magnetism, & Fluids', 3, 2, 'sci', 2, ['PH-UY 1013'], [], None),
        ('CS-UY 2124', 'Object Oriented Programming', 4, 2, 'major', 2, ['CS-UY 1134'], [], None),
        ('EXPOS-UY 22', 'Advanced Writing for Engineers', 4, 2, 'huss', None, ['EXPOS-UY 1'], [], None),
        ('MA-UY 2314', 'Discrete Mathematics', 4, 3, 'math', 2, ['MA-UY 1124'], [], None),
        ('ECE-UY 2204', 'Digital Logic and State Machine Design', 4, 3, 'major', 2, ['ECE-UY 1002'], [], None),
        ('MA-UY 2114', 'Calculus III', 4, 3, 'math', 2, ['MA-UY 1124'], [], None),
        ('ECE-UY 2004', 'Fundamentals of Electric Circuits', 4, 4, 'major', 2, ['PH-UY 2023', 'MA-UY 2034'], [], 'key'),
        ('CS-UY 2214', 'Computer Architecture and Organization', 4, 4, 'major', 3, ['CS-UY 2124', 'ECE-UY 2204'], [], None),
        ('MA-UY 2224', 'Probability and Statistics for Engineers', 4, 4, 'math', 3, ['MA-UY 1124'], [], None),
        ('ECE-UY 3114', 'Fundamentals of Electronics I', 4, 4, 'major', None, [], [], 'ghost'),
        ('ECE-UY 3114', 'Fundamentals of Electronics I', 4, 5, 'major', 3, ['ECE-UY 2004'], [], None),
        ('ECE-UY 4144', 'Intro to Embedded Systems Design', 4, 5, 'major', 4, ['ECE-UY 2204', 'CS-UY 2214'], [], None),
        ('ECE-UY 4001', 'ECE Professional Development & Presentation', 1, 5, 'major', None, [], [], None),
        ('ECE-UY 4913', 'Design Project I', 3, 6, 'major', 4, ['ECE-UY 4144', 'ECE-UY 3114'], [], None),
        ('HUSS-UY 1', 'Humanities & Social Sciences Elective', 4, 6, 'huss', None, [], [], None),
        ('FREE-UY 1', 'Free Elective', 4, 6, 'free', None, [], [], None),
        ('ECE-UY 4923', 'Design Project II', 3, 7, 'major', 4, ['ECE-UY 4913'], [], None),
        ('HUSS-UY 2', 'Humanities & Social Sciences Elective', 4, 7, 'huss', None, [], [], None),
        ('FREE-UY 2', 'Free Elective', 4, 7, 'free', None, [], [], None),
    ])

# ------------------------------------------------ NYU Tandon: Electrical (BS)
PROGRAMS['nyu-ee'] = dict(
    school='NYU', program='ELECTRICAL ENG BS · TANDON', tab='Electrical Engineering',
    unit='credits', abbr='cr', total=128, grad='Spring 2028', year='SOPHOMORE',
    terms=NYU_TERMS, tiers=['FIRST YEAR', 'MATH & PHYSICS', 'CIRCUITS & LOGIC',
                            'SIGNALS & FIELDS', 'DESIGN PROJECT'],
    key='ECE-UY 2004', keyname='Fundamentals of Electric Circuits',
    headline="Register for ECE-UY 2004 — Fundamentals of Electronics I and Signals and Systems are both waiting on it.",
    blurb="Fundamentals of Electric Circuits is the gate into the whole electrical sequence. Until it clears, Electronics I will not register, and Signals and Systems behind it slides a year.",
    courses=[
        ('MA-UY 1024', 'Calculus I for Engineers', 4, 0, 'math', 0, [], [], None),
        ('CS-UY 1114', 'Intro to Programming & Problem Solving', 4, 0, 'major', 0, [], [], None),
        ('EG-UY 1004', 'Introduction to Engineering and Design', 4, 0, 'major', 0, [], [], None),
        ('EXPOS-UY 1', 'Writing as Inquiry', 4, 0, 'huss', None, [], [], None),
        ('MA-UY 1124', 'Calculus II for Engineers', 4, 1, 'math', 1, ['MA-UY 1024'], [], None),
        ('PH-UY 1013', 'Mechanics', 3, 1, 'sci', 1, ['MA-UY 1024'], [], None),
        ('ECE-UY 1002', 'Intro to Electrical and Computer Engineering', 2, 1, 'major', 1, [], [], None),
        ('EXPOS-UY 22', 'Advanced Writing for Engineers', 4, 1, 'huss', None, ['EXPOS-UY 1'], [], None),
        ('PH-UY 2023', 'Electricity, Magnetism, & Fluids', 3, 2, 'sci', 2, ['PH-UY 1013'], [], None),
        ('ECE-UY 2204', 'Digital Logic and State Machine Design', 4, 2, 'major', 2, ['ECE-UY 1002'], [], None),
        ('MA-UY 1044', 'Linear Algebra', 4, 2, 'math', 2, ['MA-UY 1124'], [], None),
        ('HUSS-UY 1', 'Humanities & Social Sciences Elective', 4, 2, 'huss', None, [], [], None),
        ('MA-UY 2114', 'Calculus III: Multi-Dimensional Calculus', 4, 3, 'math', 2, ['MA-UY 1124'], [], None),
        ('CS-UY 2163', 'Introduction to Programming in C', 3, 3, 'major', 2, ['CS-UY 1114'], [], None),
        ('ECE-UY 2233', 'Introduction to Probability', 3, 3, 'math', 3, ['MA-UY 1124'], [], None),
        ('HUSS-UY 2', 'Humanities & Social Sciences Elective', 4, 3, 'huss', None, [], [], None),
        ('ECE-UY 2004', 'Fundamentals of Electric Circuits', 4, 4, 'major', 2, ['PH-UY 2023', 'MA-UY 1044'], [], 'key'),
        ('MA-UY 4204', 'Ordinary Differential Equations', 4, 4, 'math', 3, ['MA-UY 2114'], [], None),
        ('ECE-UY 4001', 'ECE Professional Development & Presentation', 1, 4, 'major', None, [], [], None),
        ('ECE-UY 3114', 'Fundamentals of Electronics I', 4, 4, 'major', None, [], [], 'ghost'),
        ('ECE-UY 3114', 'Fundamentals of Electronics I', 4, 5, 'major', 3, ['ECE-UY 2004'], [], None),
        ('ECE-UY 3054', 'Signals and Systems', 4, 5, 'major', 3, ['ECE-UY 2004', 'MA-UY 4204'], [], None),
        ('ECE-UY 3604', 'Electromagnetic Waves', 4, 6, 'major', 4, ['PH-UY 2023', 'MA-UY 2114'], [], None),
        ('ECE-UY 4913', 'Design Project I', 3, 6, 'major', 4, ['ECE-UY 3114', 'ECE-UY 3054'], [], None),
        ('HUSS-UY 3', 'Humanities & Social Sciences Elective', 4, 6, 'huss', None, [], [], None),
        ('ECE-UY 4923', 'Design Project II', 3, 7, 'major', 4, ['ECE-UY 4913'], [], None),
        ('HUSS-UY 4', 'Humanities & Social Sciences Elective', 4, 7, 'huss', None, [], [], None),
        ('FREE-UY 1', 'Free Elective', 4, 7, 'free', None, [], [], None),
    ])

# --------------------------------------- NYU Tandon: Chemical & Biomolecular
PROGRAMS['nyu-cbe'] = dict(
    school='NYU', program='CHEMICAL ENG BS · TANDON', tab='Chemical & Biomolecular Eng',
    unit='credits', abbr='cr', total=128, grad='Spring 2028', year='SOPHOMORE',
    terms=NYU_TERMS, tiers=['FIRST YEAR', 'CHEMISTRY & MATH', 'PROCESS ANALYSIS',
                            'TRANSPORT & KINETICS', 'DESIGN & LABORATORY'],
    key='CBE-UY 2124', keyname='Analysis of Chemical and Biomolecular Processes',
    headline="Register for CBE-UY 2124 — Thermodynamics and Heat and Mass Transport are both waiting on it.",
    blurb="Analysis of Chemical and Biomolecular Processes is the gate into the core sequence. Until it clears, Thermodynamics will not register, and Separations and Kinetics behind it slide a year.",
    courses=tandon_core(('CBE-UY 1002', 'Introduction to CBE', 2, 1, 'major', 1, [], [], None)) + [
        ('CM-UY 1003', 'General Chemistry for Engineers', 3, 0, 'sci', 0, [], [], None),
        ('BMS-UY 1003', 'Introduction to Cell and Molecular Biology', 3, 1, 'sci', 1, [], [], None),
        ('CM-UY 2213', 'Organic Chemistry I', 3, 2, 'sci', 2, ['CM-UY 1003'], [], None),
        ('MA-UY 2034', 'Linear Algebra and Differential Equations', 4, 2, 'math', 2, ['MA-UY 1124'], [], None),
        ('PH-UY 2023', 'Electricity, Magnetism, & Fluids', 3, 2, 'sci', 2, ['PH-UY 1013'], [], None),
        ('CM-UY 2223', 'Organic Chemistry II', 3, 3, 'sci', 3, ['CM-UY 2213'], [], None),
        ('CM-UY 3714', 'Physical Chemistry I', 4, 3, 'sci', 3, ['CM-UY 1003', 'MA-UY 1124'], [], None),
        ('MA-UY 2114', 'Calculus III', 4, 3, 'math', 2, ['MA-UY 1124'], [], None),
        ('CBE-UY 2233', 'Chemical Engineering Computation', 3, 3, 'major', 2, ['MA-UY 2034'], [], None),
        ('CBE-UY 2124', 'Analysis of Chemical and Biomolecular Processes', 4, 4, 'major', 2, ['CM-UY 1003', 'MA-UY 1124'], [], 'key'),
        ('CBE-UY 3173', 'Polymeric Materials', 3, 4, 'major', 3, ['CM-UY 2213'], [], None),
        ('HUSS-UY 1', 'Humanities & Social Sciences Elective', 4, 4, 'huss', None, [], [], None),
        ('CBE-UY 3153', 'Thermodynamics', 3, 4, 'major', None, [], [], 'ghost'),
        ('CBE-UY 3153', 'Thermodynamics', 3, 5, 'major', 3, ['CBE-UY 2124'], [], None),
        ('CBE-UY 3313', 'Heat and Mass Transport', 3, 5, 'major', 3, ['CBE-UY 2124', 'MA-UY 2114'], [], None),
        ('CBE-UY 3323', 'Fluid Mechanics', 3, 5, 'major', 3, ['CBE-UY 2124'], [], None),
        ('CBE-UY 3233', 'Separations', 3, 6, 'major', 4, ['CBE-UY 3153', 'CBE-UY 3313'], [], None),
        ('CBE-UY 3223', 'Kinetics and Reactor Design', 3, 6, 'major', 4, ['CBE-UY 3153'], [], None),
        ('CBE-UY 4143', 'Process Dynamics and Control', 3, 6, 'major', 4, ['CBE-UY 3313'], [], None),
        ('CBE-UY 4113', 'Engineering Laboratory I', 3, 7, 'major', 4, ['CBE-UY 3313'], [], None),
        ('CBE-UY 4163', 'Process Design I', 3, 7, 'major', 4, ['CBE-UY 3233', 'CBE-UY 3223'], [], None),
        ('HUSS-UY 2', 'Humanities & Social Sciences Elective', 4, 7, 'huss', None, [], [], None),
    ])

# ---------------------------------------------- NYU Tandon: Environmental (BS)
PROGRAMS['nyu-enve'] = dict(
    school='NYU', program='ENVIRONMENTAL ENG BS · TANDON', tab='Environmental Engineering',
    unit='credits', abbr='cr', total=129, grad='Spring 2028', year='SOPHOMORE',
    terms=NYU_TERMS, tiers=['FIRST YEAR', 'MATH & SCIENCE', 'ENVIRONMENTAL CORE',
                            'WATER & TREATMENT', 'CAPSTONE & ELECTIVES'],
    key='CE-UY 2213', keyname='Fluid Mechanics and Hydraulics',
    headline="Register for CE-UY 2213 — Water Resources Engineering and Hydrology are both waiting on it.",
    blurb="Fluid Mechanics and Hydraulics is the gate into the water sequence. Until it clears, Water Resources Engineering will not register, and the treatment courses behind it slide a year.",
    courses=tandon_core(('CE-UY 1002', 'Intro to Civil and Environmental Engineering', 2, 1, 'major', 1, [], [], None)) + [
        ('CM-UY 1003', 'General Chemistry for Engineers', 3, 0, 'sci', 0, [], [], None),
        ('CS-UY 1113', 'Problem Solving and Programming I', 3, 1, 'major', 1, [], [], None),
        ('MA-UY 2034', 'Linear Algebra and Differential Equations', 4, 2, 'math', 2, ['MA-UY 1124'], [], None),
        ('PH-UY 2023', 'Electricity, Magnetism, & Fluids', 3, 2, 'sci', 2, ['PH-UY 1013'], [], None),
        ('BMS-UY 1003', 'Introduction to Cell and Molecular Biology', 3, 2, 'sci', 2, [], [], None),
        ('URB-UY 2334', 'Environmental Studies', 4, 2, 'huss', None, [], [], None),
        ('MA-UY 2224', 'Probability and Statistics for Engineers', 4, 3, 'math', 2, ['MA-UY 1124'], [], None),
        ('CE-UY 2112', 'Structural Statics', 2, 3, 'major', 2, ['PH-UY 1013'], [], None),
        ('CE-UY 3223', 'Fundamentals of Environmental Engineering', 3, 3, 'major', 3, ['CM-UY 1003'], [], None),
        ('URB-UY 3834', 'Environmental Policy', 4, 3, 'huss', None, ['URB-UY 2334'], [], None),
        ('CE-UY 2213', 'Fluid Mechanics and Hydraulics', 3, 4, 'major', 2, ['PH-UY 1013', 'MA-UY 1124'], [], 'key'),
        ('CE-UY 2253', 'Hydrology', 3, 4, 'major', 3, ['CE-UY 2213'], [], None),
        ('CE-UY 3013', 'Computing in Civil Engineering', 3, 4, 'major', 3, ['CS-UY 1113'], [], None),
        ('CE-UY 3243', 'Water Resources Engineering', 3, 4, 'major', None, [], [], 'ghost'),
        ('CE-UY 3243', 'Water Resources Engineering', 3, 5, 'major', 3, ['CE-UY 2213'], [], None),
        ('CE-UY 3263', 'Environmental Chemistry', 3, 5, 'major', 3, ['CE-UY 3223'], [], None),
        ('CE-UY 3233', 'Water and Wastewater Treatment', 3, 5, 'major', 4, ['CE-UY 3223'], [], None),
        ('CE-UY 3273', 'Air Pollution Control', 3, 6, 'major', 4, ['CE-UY 3223'], [], None),
        ('CE-UY 4092', 'Leadership, Business, Policy & Ethics', 2, 6, 'major', None, [], [], None),
        ('HUSS-UY 1', 'Humanities & Social Sciences Elective', 4, 6, 'huss', None, [], [], None),
        ('CE-UY 4863', 'Environmental Engineering Capstone', 3, 7, 'major', 4, ['CE-UY 3243', 'CE-UY 3233'], [], None),
        ('HUSS-UY 2', 'Humanities & Social Sciences Elective', 4, 7, 'huss', None, [], [], None),
        ('FREE-UY 1', 'Free Elective', 3, 7, 'free', None, [], [], None),
    ])

# ---------------------------------------------------------------- CMU CS (BS)
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


# --------------------------------------------------------------------------- #
# Inferred-prerequisite notes (sidecar so the tuple tables stay 9-wide).
# These are prerequisites collapsed from CMU's published OR-lists or inferred from
# sample-sequence order; the seeds carry them as needs_review + review_note.
# --------------------------------------------------------------------------- #
REVIEW_NOTES = {
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
