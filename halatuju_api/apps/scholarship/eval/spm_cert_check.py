"""Does the SPM CERTIFICATE reader (`spm_cert_parse`) read the REAL SPM certificates? (2026-10-28)

A HAND-RUN measurement, never a test: it reads the `results_split` caches in `snapshots/` and the
files in `fixtures/results_split/` — gitignored PII (README.md), absent from the deploy build. The
committed tests use synthetic twins (`tests/test_certificate_parser.py`).

Each document is fed the way production feeds `vision._run_field_extraction_impl`: a Vision read as
page 1's text + word boxes; a digital PDF as its text layer + the PDF bytes (the reader takes the
text layer's own character boxes). The expected answers are `<key>.expect_spm.json`, written by
hand from each page image (name, IC digits, exam year, printed count, subjects + grades).

Per certificate: EXACT (every field equal), FALLBACK (None → Gemini) or WRONG (a hit with a field
that differs — the failure that must never happen), with the differing field NAMES only. Every
control (SPM slips, STPM, Matriculation, Diploma, Asasi, MUET, SPVM, other, fakes) must return
None. Prints keys, counts and field names — never a name, an IC or a grade. Exits non-zero on any
WRONG or any accepted control.

Usage:  python apps/scholarship/eval/spm_cert_check.py
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, 'snapshots')
FIX = os.path.join(HERE, 'fixtures', 'results_split')
CONTROLS = ('spm_slip', 'stpm_cert', 'stpm_slip', 'fake', 'matric', 'diploma', 'asasi', 'muet',
            'spvm', 'other')


def _load(key, suffix):
    path = os.path.join(SNAP, key + suffix)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read() if suffix.endswith('.txt') else json.load(fh)


def production_input(folder, key):
    """(text, words, pdf bytes) as `_run_field_extraction_impl` hands them to the reader."""
    meta = _load(key, '.ocr.meta.json') or {}
    if meta.get('path') == 'vision':
        pages = (_load(key, '.ocr.words.json') or {}).get('pages') or [{}]
        return pages[0].get('text') or '', pages[0].get('words') or [], None
    files = glob.glob(os.path.join(FIX, folder, key + '.*'))
    with open(files[0], 'rb') as fh:
        return _load(key, '.ocr.txt') or '', None, fh.read()


def _letters(s):
    return ' '.join(re.sub(r'[^A-Z ]', '', str(s or '').upper()).split())


def differing_fields(got, exp):
    out = []
    if _letters(got.get('candidate_name')) != _letters(exp.get('name')):
        out.append('name')
    if re.sub(r'\D', '', got.get('nric') or '') != exp.get('nric'):
        out.append('nric')
    if not str(got.get('exam') or '').endswith(str(exp.get('exam_year'))):
        out.append('exam_year')
    want = [(s['subject'], s['grade']) for s in exp.get('subjects') or []]
    have = [(s['subject'], s['grade']) for s in got.get('results') or []]
    if [w[0] for w in want] != [h[0] for h in have]:
        out.append('subjects')
    elif want != have:
        out.append('grades')
    return out


def keys(folder):
    return sorted(os.path.basename(p)[:-len('.ocr.txt')]
                  for p in glob.glob(os.path.join(SNAP, folder + '__*.ocr.txt')))


def main():
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))   # halatuju_api/
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'halatuju.settings.development')
    import django
    django.setup()
    from apps.scholarship.spm_cert_parse import parse_spm_cert

    if not keys('spm_cert'):
        print(f'No SPM certificate caches in {SNAP} - this measurement needs the local corpus.')
        return 2
    tally = {'EXACT': 0, 'FALLBACK': 0, 'WRONG': 0}
    for key in keys('spm_cert'):
        exp = _load(key, '.expect_spm.json')
        if not exp:
            print(f'{key:<34} NO EXPECTED ANSWER')
            continue
        got = parse_spm_cert(*production_input('spm_cert', key))
        if got is None:
            verdict, why = 'FALLBACK', ''
        else:
            diff = differing_fields(got, exp)
            verdict, why = ('WRONG', ','.join(diff)) if diff else ('EXACT', '')
        tally[verdict] += 1
        print(f'{key:<34} {verdict:<8} {why}')
    print(f'-- spm_cert: {tally}\n')
    checked = accepted = 0
    for folder in CONTROLS:
        for key in keys(folder):
            checked += 1
            if parse_spm_cert(*production_input(folder, key)) is not None:
                accepted += 1
                print(f'{key:<34} CONTROL ACCEPTED')
    print(f'controls accepted: {accepted} of {checked}')
    return 1 if (tally['WRONG'] or accepted) else 0


if __name__ == '__main__':
    sys.exit(main())
