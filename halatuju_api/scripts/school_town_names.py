"""Same-name schools carry their town (owner, 2026-10-31) — the checked-in transform.

WHAT IT DOES. 79 names are used by more than one school in the national secondary list (184 rows;
"SMK CONVENT" is in nine towns). Two names are the SAME when they match with case, punctuation and
spacing ignored ("SMK ST. ANTHONY" / "SMK ST ANTHONY", "SMK METHODIST (ACS)" / "SMK METHODIST ACS";
review 2, 2026-10-31). For ONLY those names, a school's name in our data becomes
"<NAME>, <TOWN>" — "SMK CONVENT, TAIPING" — so the name a student picks, and that we store, says
WHICH school it is. Every other name is left byte-identical. The rule is NATIONAL: a Form 6 centre
whose name is shared anywhere in the secondary list carries its town too, even if it is the only
centre with that name.

THE SOURCE is the MOE directory `docs/SenaraiSekolahWeb_April2026.xlsx` (KODSEKOLAH → BANDARSURAT,
the postal town). Both lists join on the MOE code. If two shared rows ever still clash with the town
added, the PPD is used instead for those rows (none do, April 2026).

IT WRITES THREE FILES and changes nothing else:
  - halatuju-web/src/data/secondary-schools.json   — the "name" line of each shared row, in place;
  - halatuju-web/src/data/stpm-schools.json        — the same;
  - halatuju_api/apps/scholarship/same_name_schools.py — the full disambiguated names, which the
    server's `school_names.school_name_core` uses to drop the town again when it COMPARES a record
    with a document (owner: match the school name only). Generated; never edit by hand.

IT IS SAFE TO RE-RUN. A name already carrying its town is recognised and recomputed, so a second
run writes the same bytes. Every other line of each JSON file (and its line endings) is kept as is;
the script re-reads what it wrote and checks that.

WHY A PLAIN SCRIPT, not a management command: it needs no database and no Django, only the two data
files and the workbook — the same shape as the other scripts here. It needs `openpyxl`, which is a
dev dependency (requirements-dev.txt).

    cd halatuju_api && python scripts/school_town_names.py
"""
import collections
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
WORKBOOK = os.path.join(ROOT, 'docs', 'SenaraiSekolahWeb_April2026.xlsx')
SECONDARY = os.path.join(ROOT, 'halatuju-web', 'src', 'data', 'secondary-schools.json')
STPM = os.path.join(ROOT, 'halatuju-web', 'src', 'data', 'stpm-schools.json')
SERVER_SET = os.path.join(ROOT, 'halatuju_api', 'apps', 'scholarship', 'same_name_schools.py')


def read_moe():
    """{MOE code: (name, town, ppd)} from the workbook's main sheet."""
    import openpyxl
    wb = openpyxl.load_workbook(WORKBOOK, read_only=True)
    rows = wb['SenaraiSekolahWeb'].iter_rows(values_only=True)
    head = next(rows)
    at = {k: head.index(k) for k in ('KODSEKOLAH', 'NAMASEKOLAH', 'BANDARSURAT', 'PPD')}
    out = {}
    for r in rows:
        code = r[at['KODSEKOLAH']]
        if code:
            out[code] = (str(r[at['NAMASEKOLAH']] or '').strip(),
                         ' '.join(str(r[at['BANDARSURAT']] or '').split()).upper(),
                         ' '.join(str(r[at['PPD']] or '').split()).upper())
    return out


def norm(name):
    """A name as a reader compares it: case, punctuation and spacing ignored — "SMK ST. ANTHONY" is
    "SMK ST ANTHONY", "SMK METHODIST (ACS)" is "SMK METHODIST ACS" (review 2, 2026-10-31)."""
    return ' '.join(re.sub(r'[^A-Z0-9]+', ' ', name.upper().replace("'", '')).split())


def bare_name(row, moe):
    """The MOE name of a row, whether or not a previous run already added its town."""
    name, town, ppd = moe[row['code']]
    if row['name'] in (name, f'{name}, {town}', f'{name}, {ppd}'):
        return name
    sys.exit(f"{row['code']}: name {row['name']!r} is neither the MOE name {name!r} nor it with a "
             'town or PPD — the data has drifted from the workbook; stop and look.')


def new_names(rows, moe, shared):
    """Each row's name under the rule; the PPD replaces the town where the town still clashes."""
    names = []
    for r in rows:
        name, town, _ppd = moe[r['code']]
        names.append(f'{name}, {town}' if name in shared and town else name)
    clash = {n for n, c in collections.Counter(map(norm, names)).items() if c > 1}
    for i, r in enumerate(rows):
        name, _town, ppd = moe[r['code']]
        if name in shared and norm(names[i]) in clash:
            print(f"  {r['code']}: '{names[i]}' still clashes — using the PPD: '{name}, {ppd}'")
            names[i] = f'{name}, {ppd}'
    return names


def rewrite(path, rows, names):
    """Replace the "name" value of each changed row in place; every other byte stays."""
    raw = open(path, 'rb').read()
    nl = b'\r\n' if b'\r\n' in raw else b'\n'
    lines = raw.split(nl)
    at = [i for i, ln in enumerate(lines) if ln.lstrip().startswith(b'"name":')]
    if len(at) != len(rows):
        sys.exit(f'{path}: {len(at)} "name" lines for {len(rows)} rows — not the expected layout.')
    for i, r, new in zip(at, rows, names):
        old_v = json.dumps(r['name'], ensure_ascii=False).encode('utf-8')
        new_v = json.dumps(new, ensure_ascii=False).encode('utf-8')
        if lines[i].count(old_v) != 1:
            sys.exit(f'{path}: line {i + 1} does not hold {old_v!r}.')
        lines[i] = lines[i].replace(old_v, new_v)
    out = nl.join(lines)
    open(path, 'wb').write(out)
    again = json.loads(out.decode('utf-8'))
    assert [a['name'] for a in again] == names, f'{path}: re-read names differ'
    assert [{**a, 'name': ''} for a in again] == [{**r, 'name': ''} for r in rows], f'{path}: other fields moved'


def write_server_set(full_names):
    body = ''.join(f'    {json.dumps(n, ensure_ascii=False)}: {json.dumps(st, ensure_ascii=False)},\n'
                   for n, st in sorted(full_names.items()))
    text = (
        '"""GENERATED by halatuju_api/scripts/school_town_names.py — do not edit by hand.\n\n'
        'Every school name in our lists that carries its town because another school shares the name\n'
        '(owner, 2026-10-31): "<NAME>, <TOWN>", with the state the list gives it. `school_names` reads\n'
        'it to compare a record with a document on the school NAME only, and to tell a letter that adds\n'
        'only our town, a postcode or our state. A drift test keeps it equal to the web lists.\n'
        '"""\n\n'
        f'SAME_NAME_SCHOOL_STATES = {{\n{body}}}\n\n'
        'SAME_NAME_SCHOOLS = frozenset(SAME_NAME_SCHOOL_STATES)\n')
    open(SERVER_SET, 'w', encoding='utf-8', newline='\n').write(text)


def main():
    moe = read_moe()
    secondary = json.load(open(SECONDARY, encoding='utf-8'))
    stpm = json.load(open(STPM, encoding='utf-8'))
    for r in secondary + stpm:
        if r['code'] not in moe:
            sys.exit(f"{r['code']} ({r['name']}) is not in the workbook.")
    # Shared = another school's name is the SAME once case, punctuation and spacing are ignored.
    counts = collections.Counter(norm(bare_name(r, moe)) for r in secondary)
    shared = {bare_name(r, moe) for r in secondary + stpm if counts[norm(bare_name(r, moe))] > 1}
    full = {}
    for path, rows in ((SECONDARY, secondary), (STPM, stpm)):
        for r in rows:
            bare_name(r, moe)
        names = new_names(rows, moe, shared)
        dupes = [n for n, c in collections.Counter(map(norm, names)).items() if c > 1]
        if dupes:
            sys.exit(f'{path}: names still shared after the rule: {dupes[:5]}')
        rewrite(path, rows, names)
        full.update({n: r['state'] for r, n in zip(rows, names) if moe[r['code']][0] in shared})
        print(f'{os.path.relpath(path, ROOT)}: {sum(moe[r["code"]][0] in shared for r in rows)} '
              f'of {len(rows)} rows carry their town')
    write_server_set(full)
    print(f'{len(shared)} shared names; {len(full)} disambiguated names -> '
          f'{os.path.relpath(SERVER_SET, ROOT)}')


if __name__ == '__main__':
    main()
