"""Does the Matriculation Exact reader (`matric_parse`) read the REAL corpus? (Matric/Diploma M2)

A HAND-RUN measurement, never a test: it reads the `results_split` caches in `snapshots/`
(`<key>.ocr.txt`, `.ocr.words.json`, `.ocr.meta.json`, `.expect.json`), which are gitignored PII
(README.md). The committed tests use synthetic twins (`tests/test_matric_parse.py`); this script is
how a human checks the twins still describe the real documents.

Each document is fed the way production feeds `higher_results.extract`: a text-layer PDF as its
whole text with no word boxes; a Vision read as page 1's text + word boxes (production OCRs page 1).

Per Matriculation page: EXACT (every expected field read and equal), FALLBACK (None → Gemini) or
WRONG (a hit with a field that differs — the failure that must never happen), with the differing
field NAMES only. Every control (STPM, SPM, Diploma, Asasi, MUET, SPVM, other, fakes, the SPM slip
corpus) must return None. Prints keys, counts and field names — never a name, an IC or a grade.
Exits non-zero on any WRONG or any accepted control.

Usage:  python apps/scholarship/eval/matric_parse_check.py [--snapshots PATH]
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
#: The cache readers' one home (`stpm_parse_check._load` / `production_input`), bound in `main`.
_io = None

CONTROLS = ('stpm_cert', 'stpm_slip', 'spm_cert', 'spm_slip', 'fake', 'diploma', 'asasi', 'muet',
            'spvm', 'other', 'results_slip')


def _sq(s):
    return re.sub(r'[^A-Z0-9]', '', str(s or '').upper())


def matric_differences(got, exp):
    """The expected fields the hit read differently (names only)."""
    out = [f for f, g, e in (('name', got.get('candidate_name'), exp.get('name')),
                             ('nric', got.get('nric'), exp.get('nric')),
                             ('cgpa', got.get('cgpa'), exp.get('cgpa')),
                             ('institution', got.get('institution'), exp.get('institution')))
           if _sq(g) != _sq(e)]
    want = [(_sq(s['subject']), s['grade']) for s in exp.get('subjects') or []]
    have = [(_sq(s['subject']), s['grade']) for s in got.get('results') or []]
    if [w[0] for w in want] != [h[0] for h in have]:
        out.append('subjects')
    elif want != have:
        out.append('grades')
    return out


def cached_keys(folder):
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
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'halatuju.settings.development')
    import django
    django.setup()
    from apps.scholarship.matric_parse import parse

    keys = cached_keys('matric')
    if not keys:
        print(f'No Matriculation caches in {_io.SNAP} - this measurement needs the local corpus.')
        return 2
    tally = {'EXACT': 0, 'FALLBACK': 0, 'WRONG': 0}
    for key in keys:
        exp = _io._load(key, '.expect.json') or {}
        got = parse(*_io.production_input(key))
        if got is None:
            verdict, why = 'FALLBACK', ''
        else:
            diff = matric_differences(got, exp)
            verdict, why = ('WRONG', ','.join(diff)) if diff else ('EXACT', '')
        tally[verdict] += 1
        print(f'{key:<32} {verdict:<8} {why}')
    print(f'-- matric: {tally}\n')
    checked = accepted = 0
    for folder in CONTROLS:
        for key in cached_keys(folder):
            checked += 1
            if parse(*_io.production_input(key)) is not None:
                accepted += 1
                print(f'{key:<32} CONTROL ACCEPTED')
    print(f'controls accepted: {accepted} of {checked}')
    return 1 if (tally['WRONG'] or accepted) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
