"""Does the higher-results STPM genuineness check (STPM exact-read S3, MODEL_VERSION 1.11.0) judge the
REAL corpus as the owner ruled? The sibling of `stpm_parse_check.py`: a HAND-RUN measurement, never a
test. It reads the gitignored `results_split` caches in `snapshots/` (PII; README.md) and feeds each
one's OCR text to `genuineness.stpm_doc.stpm_higher_genuineness`, as production does.

Prints per layout family how many score genuine / suspect / not_<type> / unscored ("not checked"),
then the three checks the owner's rulings make:
  * ruling 1A — every checker page and every STPM-reading fake (a checker page) reads not_<type>;
  * ruling A — a printout of the MPM results web page, in any form (PDF, picture, scan), reads genuine;
  * ruling 2A — every certified copy reads genuine;
  * no Matriculation / Diploma / Asasi / SPM / MUET / SPVM / other document is scored at all.
Prints keys, layouts and counts only — never a name, an IC, a grade or a serial. Exits non-zero
when any ruling check fails.

Usage:  python apps/scholarship/eval/stpm_genuineness_check.py
"""
import collections
import os
import sys

from stpm_parse_check import CONTROLS, STPM, _load, keys, production_input


def _outcome(g):
    if not g:
        return 'unscored'
    s = g['status']
    return 'not_type' if s.startswith('not_') else s


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.abspath(os.path.join(here, '..', '..', '..')))   # halatuju_api/
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'halatuju.settings.development')
    import django
    django.setup()
    from apps.scholarship.genuineness.stpm_doc import stpm_higher_genuineness
    from apps.scholarship.results_kind import detect

    if not keys('stpm_cert') and not keys('stpm_slip'):
        print('No STPM caches in snapshots/ - this measurement needs the local corpus.')
        return 2
    by_layout = collections.defaultdict(collections.Counter)
    failures = []
    for folder in STPM + CONTROLS:
        for key in keys(folder):
            exp = _load(key, '.expect.json') or {}
            text = production_input(key)[0]
            g = stpm_higher_genuineness(text)
            out = _outcome(g)
            layout = exp.get('layout') or folder
            by_layout[layout][out] += 1
            want = None
            if layout == 'checker_page' or (layout == 'fake' and detect(text) == 'stpm'):
                want, rule = 'not_type', '1A checker page'
            elif exp.get('online_print'):
                want, rule = 'genuine', 'A portal printout'
            elif exp.get('certified_copy'):
                want, rule = 'genuine', '2A certified copy'
            elif folder in CONTROLS:
                want, rule = 'unscored', 'not STPM'
            if want is not None:
                ok = out == want
                print(f'{key:<34} {rule:<24} {out:<9} {"ok" if ok else "FAIL"}')
                if not ok:
                    failures.append(key)
    print()
    for layout in sorted(by_layout):
        print(f'{layout:<14} ' + '  '.join(f'{k}={v}' for k, v in sorted(by_layout[layout].items())))
    print(f'\nruling checks failed: {len(failures)}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
