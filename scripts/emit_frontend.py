#!/usr/bin/env python3
"""Emit the frontend `SCHOOLS = {...}` block from the curricula tuple tables and
splice it into build/template.html. Run `scripts/rebuild.py embed` afterward to fold
that into the bundled `Compass Planner.html`.

Deterministic: the block is a pure function of curricula.PROGRAMS, so running twice
changes no bytes. Status, the REQS buckets and the snapshot all come from the shared
derivation in curricula.py — the same functions emit_seeds.py uses — so the JS and the
seed JSON cannot drift.
"""

import curricula as C
from curricula import (CODE, TITLE, CR, TERM, GROUP, TIER, REQ, ANTI, FLAG)


def js_str(s: str) -> str:
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"' if "'" in s else "'" + s + "'"


def js_list(items) -> str:
    return '[' + ','.join("'" + i + "'" for i in items) + ']'


def build(key: str, P: dict) -> str:
    cs = P['courses']
    tot = C.derived_totals(P)
    groups = C.derive_groups(P)

    L = []
    L.append(f"  '{key}': {{\n")
    L.append("  META: {\n")
    L.append(f"    school:'{P['school']}', program:'{P['program']}', tab:{js_str(P['tab'])},\n")
    L.append(f"    unitLabel:'{P['unit']}', unitAbbr:'{P['abbr']}', doneCr:{tot['doneCr']}, "
             f"totalCr:{tot['totalCr']}, inProgCr:{tot['inProgCr']}, behindCr:{tot['behindCr']}, "
             f"pct:{tot['pct']},\n")
    L.append(f"    gradTerm:'{P['grad']}', classYear:'{P['year']}',\n")
    L.append(f"    keyCode:'{P['key']}', keyName:{js_str(P['keyname'])},\n")
    L.append(f"    headline:{js_str(P['headline'])},\n")
    L.append(f"    blurb:{js_str(P['blurb'])},\n")
    L.append(f"    snapshot:{js_str(C.snapshot_of(P))}\n")
    L.append("  },\n\n")
    L.append("  TIERS: [" + ','.join(js_str(t) for t in P['tiers']) + "],\n\n")
    L.append("  TERMS: [\n")
    for k, l, tag, st in P['terms']:
        L.append(f"    {{k:'{k}', l:'{l}', short:'{k}', tag:{js_str(tag)}, st:'{st}'}},\n")
    L[-1] = L[-1].rstrip(',\n') + '\n'
    L.append("  ],\n\n")
    L.append("  REQS: [\n")
    for grp in groups:
        L.append(f"    {{ name:{js_str(grp['name'])}, d:{grp['done']}, p:{grp['in_progress']}, "
                 f"tot:{grp['total']}, count:{js_str(grp['count'])}, "
                 f"missing:{js_list(grp['missing'])} }},\n")
    L[-1] = L[-1].rstrip(',\n') + '\n'
    L.append("  ],\n\n")
    L.append("  COURSES: [\n")
    for c in cs:
        st = C.status_of(P, c[TERM], c[FLAG])
        row = f"    {{c:'{c[CODE]}', n:{js_str(c[TITLE])}, cr:{c[CR]}, t:{c[TERM]}, s:'{st}', g:'{c[GROUP]}'"
        if c[FLAG] == 'ghost':
            row += f", ghost:1, note:'DEFERRED — NEEDS {P['key']} FIRST'"
        else:
            if c[TIER] is not None:
                row += f", tier:{c[TIER]}"
            else:
                row += ", gen:1"
            if c[TIER] is not None:
                row += f", req:{js_list(c[REQ])}, anti:{js_list(c[ANTI])}"
            if c[FLAG] == 'key':
                row += ", key:1"
            if c[FLAG] == 'alt':
                row += ", alt:1"
        row += "},\n"
        L.append(row)
    L[-1] = L[-1].rstrip(',\n') + '\n'
    L.append("  ]\n\n  }")
    return ''.join(L)


def render() -> str:
    blocks = [build(k, P) for k, P in C.PROGRAMS.items()]
    return "  SCHOOLS = {\n\n" + ',\n\n'.join(blocks) + "\n\n  };\n"


def main() -> None:
    js = render()
    path = C.repo_root() / 'build' / 'template.html'
    s = path.read_text(encoding='utf-8')
    start = s.index('  SCHOOLS = {')
    end = s.index('  // Read through to the active school')
    s = s[:start] + js + '\n' + s[end:]
    path.write_text(s, encoding='utf-8')
    print(f'emit_frontend: wrote {len(C.PROGRAMS)} programs, '
          f'{sum(len(P["courses"]) for P in C.PROGRAMS.values())} course rows -> {path.name}')


if __name__ == '__main__':
    main()
