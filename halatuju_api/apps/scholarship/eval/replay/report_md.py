"""The report writer (design 5): the parent's compared rows as the owner's markdown skeleton.

Sections: counts per engine family; A (expected) by ruling with up to two example cases each; B
(unexplained) per engine and field; C (could not run) and N (noise) per engine; the PENDING list. Every
value it prints is already scrubbed (case keys are ids, fields and ruling ids are codes); it adds no new
value of its own. The owner's sign-off lines are left blank for the owner.
"""
from collections import Counter, defaultdict

from . import parent, rulings
from .adapters import FAMILY

EXAMPLES = 2


def _case_label(key):
    return '/'.join(str(k) for k in key)


def tally(rows):
    """{'counts', 'a', 'b', 'c', 'n'} from parent.compare_sides rows."""
    counts = defaultdict(Counter)
    a, b = defaultdict(list), defaultdict(list)
    c, n = Counter(), Counter()
    for engine, key, outcome, old, new in rows:
        family = FAMILY.get(engine, 'other')
        counts[family]['records'] += 1
        if outcome == 'differs':
            klass, ids = parent.explain(engine, old, new)
            counts[family]['A' if klass == 'expected' else 'B'] += 1
            if klass == 'expected':
                for rid in ids:
                    a[rid].append(_case_label(key))
            else:
                for field in parent.changed_fields(old, new):
                    b[(engine, field)].append(_case_label(key))
        elif outcome == 'could_not_run':
            counts[family]['C'] += 1
            c[engine] += 1
        elif outcome == 'noise':
            counts[family]['N'] += 1
            n[engine] += 1
        else:
            counts[family]['same'] += 1
    return {'counts': counts, 'a': a, 'b': b, 'c': c, 'n': n}


def render(rows, *, old_commit='', new_commit=''):
    d = tally(rows)
    out = ['# Replay report', '', f'Old tree {old_commit}, new tree {new_commit}.', '', '## Counts', '',
           '| Family | Records | Same | A | B | C | N |', '|---|---|---|---|---|---|---|']
    for fam in sorted(d['counts']):
        k = d['counts'][fam]
        out.append(f"| {fam} | {k['records']} | {k['same']} | {k['A']} | {k['B']} | {k['C']} | {k['N']} |")
    out += ['', '## A - expected (an owner ruling explains it)', '']
    if not d['a']:
        out.append('None.')
    for rid in sorted(d['a']):
        cases = sorted(d['a'][rid])
        cite = rulings.BY_ID[rid].citation if rid in rulings.BY_ID else ''
        out.append(f'- **{rid}** ({len(cases)}): {cite}. Examples: {", ".join(cases[:EXAMPLES])}')
    out += ['', '## B - unexplained (the owner looks at each)', '']
    if not d['b']:
        out.append('None.')
    else:
        out += ['| Engine | Field | Records | Examples |', '|---|---|---|---|']
        for (engine, field) in sorted(d['b']):
            cases = sorted(d['b'][(engine, field)])
            out.append(f'| {engine} | {field} | {len(cases)} | {", ".join(cases[:EXAMPLES])} |')
    out += ['', '## C - could not run', '']
    out += [f'- {e}: {d["c"][e]}' for e in sorted(d['c'])] or ['None.']
    out += ['', '## N - noise (the new tree disagreed with itself)', '']
    out += [f'- {e}: {d["n"][e]}' for e in sorted(d['n'])] or ['None.']
    out += ['', '## Pending (not shipped: differences are B)', '']
    out += [f'- {pid}: {text}' for pid, text in rulings.PENDING]
    out += ['', '## Owner sign-off', '', '- Reviewed by:', '- Date:', '']
    return '\n'.join(out)
