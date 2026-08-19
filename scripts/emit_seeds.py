#!/usr/bin/env python3
"""Emit one backend seed file per program from the curricula tuple tables.

    data/<program-id>.json   for all nine programs

Program ids are the frontend keys (nyu-cs, cmu-cs, …) — identity, no mapping table.
Status, offerings, the group buckets and the snapshot all come from the shared
derivation in curricula.py, the same functions emit_frontend.py uses, so the seed
JSON and the JS SCHOOLS block cannot drift.

Two requirement models are emitted, distinctly:
  * ``groups``       — derived from the ``g`` field; reproduces the frontend REQS.
  * ``requirements`` — real explicit/any_of matchers, present only where authored.
                       The seven engineering programs have none, so they get an empty
                       list and ``needs_requirements: true`` — never invented rules.

Deterministic: running twice changes no bytes.
"""

import json

import curricula as C
from curricula import (CODE, TITLE, CR, TERM, GROUP, TIER, REQ, ANTI, FLAG, REVIEW_NOTES)

DATA_DIR = C.repo_root() / 'data'


def _degree(P: dict) -> str:
    return 'BA' if ' BA ' in f" {P['program']} " else 'BS'


def _program_name(P: dict) -> str:
    return f"{P['tab']}, {'B.A.' if _degree(P) == 'BA' else 'B.S.'}"


def _catalog_year(P: dict) -> str:
    return '2026' if P['school'] == 'NYU' else '2025'


def course_dict(program_id: str, P: dict, c: tuple) -> dict:
    """One seed course row. ``s`` and ``offering`` are generated, not authored."""
    code, title, cr, t, g, tier, req, anti, flag = c
    d: dict = {
        'c': code, 'n': title, 'cr': cr, 't': t,
        's': C.status_of(P, t, flag), 'g': g,
    }
    if flag == 'ghost':
        d['ghost'] = 1
        d['note'] = f"DEFERRED — NEEDS {P['key']} FIRST"
    elif tier is not None:
        d['tier'] = tier
        d['req'] = list(req)
        d['anti'] = list(anti)
    else:
        d['gen'] = 1
        d['req'] = list(req)
        d['anti'] = list(anti)
    if flag == 'key':
        d['key'] = 1
    if flag == 'alt':
        d['alt'] = 1
    d['offering'] = C.offering_of(code, tier)
    d['offering_source'] = 'derived'
    note = REVIEW_NOTES.get(program_id, {}).get(code)
    d['needs_review'] = note is not None
    d['review_note'] = note
    return d


def seed_payload(program_id: str, P: dict) -> dict:
    reqs = P.get('requirements') or []
    return {
        'school': P['school'],
        'program': {
            'id': program_id,
            'name': _program_name(P),
            'degree': _degree(P),
            'catalog_year': _catalog_year(P),
            'unit_label': P['unit'],
            'unit_abbr': P['abbr'],
            'total_units': P['total'],
            'tab': P['tab'],
            'tiers': list(P['tiers']),
            'grad': P['grad'],
            'year': P['year'],
            'key': P['key'],
            'keyname': P['keyname'],
            'headline': P['headline'],
            'blurb': P['blurb'],
            'snapshot': C.snapshot_of(P),
            'needs_requirements': len(reqs) == 0,
        },
        'terms': [
            {'index': i, 'key': k, 'label': l, 'tag': tag, 'status': st}
            for i, (k, l, tag, st) in enumerate(P['terms'])
        ],
        'groups': C.derive_groups(P),
        'requirements': reqs,
        'courses': [course_dict(program_id, P, c) for c in P['courses']],
    }


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    written = set()
    for key, P in C.PROGRAMS.items():
        payload = seed_payload(key, P)
        path = DATA_DIR / f'{key}.json'
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        written.add(path.name)
    # drop any stale seed files no longer backed by a program (e.g. the old ids)
    removed = []
    for path in DATA_DIR.glob('*.json'):
        if path.name not in written:
            removed.append(path.name)
            path.unlink()
    msg = f'emit_seeds: wrote {len(written)} seeds -> {DATA_DIR.name}/'
    if removed:
        msg += f' (removed stale: {", ".join(sorted(removed))})'
    print(msg)


if __name__ == '__main__':
    main()
