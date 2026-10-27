"""Does the STPM Exact reader (`stpm_parse`) read the REAL STPM corpus? (STPM exact-read S2)

A HAND-RUN measurement, never a test: it reads the `results_split` caches in `snapshots/`
(`<key>.ocr.txt`, `.ocr.words.json`, `.ocr.meta.json`, `.expect.json`), which are gitignored PII
(README.md) and absent from the deploy gate's build. The committed tests use synthetic twins
(`tests/test_stpm_parse.py`); this script is how a human checks the twins still describe the
real documents.

Rule 2 of the grade rule needs the student's own entered grades: they come from the local
gitignored `applicants.json` when it holds them, else only rule 1 applies. Each document is fed the way production feeds `higher_results.extract`: a text-layer PDF as its
whole text with no word boxes; a Vision read as page 1's text + word boxes (production OCRs page 1).

Per STPM document: EXACT (every expected field read and equal), FALLBACK (None → Gemini) or WRONG
(a hit with a field that differs — the failure that must never happen), with the differing field
NAMES only. Every control (SPM, Matriculation, Diploma, Asasi, MUET, SPVM, other, fakes) must
return None. Prints keys, counts and field names — never a name, an IC, a grade or a serial.
Exits non-zero on any WRONG or any accepted control.

Usage:  python apps/scholarship/eval/stpm_parse_check.py
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, 'snapshots')
STPM = ('stpm_cert', 'stpm_slip')
CONTROLS = ('spm_cert', 'spm_slip', 'fake', 'matric', 'diploma', 'asasi', 'muet', 'spvm', 'other')


def _load(key, suffix):
    path = os.path.join(SNAP, key + suffix)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read() if suffix.endswith('.txt') else json.load(fh)


def production_input(key):
    """(text, words) as `ocr_document_full` would hand them over."""
    meta = _load(key, '.ocr.meta.json') or {}
    if meta.get('path') == 'vision':
        pages = (_load(key, '.ocr.words.json') or {}).get('pages') or [{}]
        return pages[0].get('text') or '', pages[0].get('words') or []
    return _load(key, '.ocr.txt') or '', None


def _name(s):
    s = re.sub(r'\s*/\s*', '/', str(s or '').upper())
    return re.sub(r'\s+', ' ', re.sub(r'\s*@\s*', ' @ ', s)).strip()


def _subject(s):
    return re.sub(r'[^A-Z0-9]', '', str(s or '').upper())


def differing_fields(got, exp):
    """The expected fields the hit read differently (names only)."""
    out = []
    if _name(got.get('candidate_name')) != _name(exp.get('name')):
        out.append('name')
    if re.sub(r'\D', '', got.get('nric') or '') != re.sub(r'\D', '', exp.get('nric') or ''):
        out.append('nric')
    if exp.get('index_no') and (got.get('index_no') or '') not in ('', exp['index_no']):
        out.append('index_no')
    if str(got.get('exam_year') or '') != str(exp.get('exam_year') or ''):
        out.append('exam_year')
    if (got.get('cgpa') or '') != (exp.get('pngk') or ''):
        out.append('pngk')
    want = [(_subject(s['subject']), s['grade']) for s in exp.get('subjects') or []]
    have = [(_subject(s['subject']), s['grade']) for s in got.get('results') or []]
    if [w[0] for w in want] != [h[0] for h in have]:
        out.append('subjects')
    elif want != have:
        out.append('grades')
    return out


def keys(folder):
    return sorted(os.path.basename(p)[:-len('.ocr.txt')]
                  for p in glob.glob(os.path.join(SNAP, folder + '__*.ocr.txt')))


def entered_for(key, applicants):
    """The student's own STPM grades for this key's application (`a<id>` in the key), from the
    local gitignored `applicants.json` — what production passes as `entered`. None when absent
    (then only rule 1, cleanly read rows, can pass)."""
    from apps.scholarship.higher_results import entered_lookup
    m = re.search(r'__a(\d+)__', key)
    grades = ((applicants.get(m.group(1)) or {}).get('profile') or {}).get('stpm_grades') if m else None
    return entered_lookup(grades)


def main():
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))   # halatuju_api/
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'halatuju.settings.development')
    import django
    django.setup()
    from apps.scholarship.stpm_parse import parse

    if not keys('stpm_cert') and not keys('stpm_slip'):
        print(f'No STPM caches in {SNAP} - this measurement needs the local corpus.')
        return 2
    path = os.path.join(HERE, 'applicants.json')
    applicants = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
    with_entries = sum(1 for f in STPM for k in keys(f) if entered_for(k, applicants))
    print(f'student-entered STPM grades available for {with_entries} documents (else rule 1 only)\n')
    wrong = accepted = 0
    for folder in STPM:
        tally = {'EXACT': 0, 'FALLBACK': 0, 'WRONG': 0}
        for key in keys(folder):
            exp = _load(key, '.expect.json') or {}
            got = parse(*production_input(key), entered=entered_for(key, applicants))
            if got is None:
                verdict, why = 'FALLBACK', exp.get('layout', '')
            else:
                diff = differing_fields(got, exp)
                verdict, why = ('WRONG', ','.join(diff)) if diff else ('EXACT', '')
            tally[verdict] += 1
            print(f'{key:<34} {verdict:<8} {why}')
        wrong += tally['WRONG']
        print(f'-- {folder}: {tally}\n')
    checked = 0
    for folder in CONTROLS:
        for key in keys(folder):
            checked += 1
            if parse(*production_input(key)) is not None:
                accepted += 1
                print(f'{key:<34} CONTROL ACCEPTED')
    print(f'controls accepted: {accepted} of {checked}')
    return 1 if (wrong or accepted) else 0


if __name__ == '__main__':
    sys.exit(main())
