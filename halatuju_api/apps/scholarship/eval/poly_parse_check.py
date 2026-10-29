"""Does the polytechnic Diploma Exact reader (`poly_diploma_parse`) read the REAL corpus? (M3)

A HAND-RUN measurement, never a test: it reads the gitignored `results_split` caches in
`snapshots/` (PII; README.md). The committed tests use synthetic twins
(`tests/test_poly_diploma_parse.py`). Each document is fed the way production feeds
`higher_results.extract` (`stpm_parse_check.production_input`: a text layer whole, a Vision read as
page 1 + word boxes).

Per Diploma page: EXACT, FALLBACK (None → Gemini) or WRONG (a hit with a field that differs — must
never happen), with field NAMES only. Every control — every other corpus folder, Matriculation,
STPM, SPM and the SPM slip corpus included — must return None. Prints keys, counts and field names
only. Exits non-zero on any WRONG or any accepted control.

Usage:  python apps/scholarship/eval/poly_parse_check.py [--snapshots PATH]
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTROLS = ('matric', 'asasi', 'stpm_cert', 'stpm_slip', 'spm_cert', 'spm_slip', 'fake', 'muet',
            'spvm', 'other', 'results_slip')
#: The cache readers' one home (`stpm_parse_check._load` / `production_input`), bound in `main`.
_io = None


def _sq(s):
    return re.sub(r'[^A-Z0-9]', '', str(s or '').upper())


def poly_differences(got, exp):
    """The expected fields the hit read differently (names only). The reader returns the rows a
    sum proves (credit > 0): the label's `zero_credit` rows (hand-read off the image) are not compared."""
    out = [f for f, g, e in (('name', got.get('candidate_name'), exp.get('name')),
                             ('nric', got.get('nric'), exp.get('nric')),
                             ('cgpa', got.get('cgpa'), exp.get('cgpa')),
                             ('institution', got.get('institution'), exp.get('institution')))
           if _sq(g) != _sq(e)]
    want = [(_sq(s['subject']), s['grade']) for s in exp.get('subjects') or []
            if _sq(s['subject']) not in {_sq(z) for z in exp.get('zero_credit') or []}]
    have = [(_sq(s['subject']), s['grade']) for s in got.get('results') or []]
    if [w[0] for w in want] != [h[0] for h in have]:
        out.append('subjects')
    elif want != have:
        out.append('grades')
    return out


def folder_keys(folder):
    return sorted(os.path.basename(p)[:-len('.ocr.txt')]
                  for p in glob.glob(os.path.join(_io.SNAP, folder + '__*.ocr.txt')))


def main(argv):
    global _io
    sys.path.insert(0, HERE)
    import stpm_parse_check
    _io = stpm_parse_check
    if '--snapshots' in argv:
        _io.SNAP = argv[argv.index('--snapshots') + 1]
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))   # halatuju_api/
    from apps.scholarship.poly_diploma_parse import read_poly_transcript as parse

    keys = folder_keys('diploma')
    if not keys:
        print(f'No Diploma caches in {_io.SNAP} - this measurement needs the local corpus.')
        return 2
    tally = {'EXACT': 0, 'FALLBACK': 0, 'WRONG': 0}
    for key in keys:
        exp = _io._load(key, '.expect.json') or {}
        got = parse(*_io.production_input(key))
        if got is None:
            verdict, why = 'FALLBACK', ''
        else:
            diff = poly_differences(got, exp)
            verdict, why = ('WRONG', ','.join(diff)) if diff else ('EXACT', '')
        tally[verdict] += 1
        print(f'{key:<30} {exp.get("issuer_class", ""):<12} {verdict:<8} {why}')
    print(f'-- diploma: {tally}\n')
    checked = accepted = 0
    for folder in CONTROLS:
        for key in folder_keys(folder):
            checked += 1
            if parse(*_io.production_input(key)) is not None:
                accepted += 1
                print(f'{key:<30} CONTROL ACCEPTED')
    print(f'controls accepted: {accepted} of {checked}')
    return 1 if (tally['WRONG'] or accepted) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
