"""How do the Matriculation / polytechnic genuineness lists (M4) judge the REAL corpus?

A HAND-RUN measurement, never a test: it reads the gitignored OCR caches in `snapshots/` (PII;
README.md) as production feeds the scorer (`stpm_parse_check.production_input`: a text layer whole,
a scan's page 1). The committed tests use synthetic twins (`tests/test_matric_poly_doc.py`).

Prints, per folder: the status `matric_poly_higher_genuineness` gives each page (what the
higher-results slot would store), and the RAW probability of every page on each list — the
controls' maximum is the margin below the 0.35 suspect floor. Keys, statuses and numbers only.
M4b (owner rulings 2026-10-29; positive evidence only, review B1): a NON-FINAL page (a semester
result slip, a polytechnic's portal screen, a transcript printing an in-progress status) is stored "unchecked" with its `doc_seen` (the final
transcript is still owed); a Matriculation offer letter `not_matric_result`. Exits non-zero if a
FINAL transcript (its gates + its completion status) is not genuine, or a control is "genuine".

Usage:  python apps/scholarship/eval/matric_poly_genuineness_check.py [--snapshots PATH]
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDERS = ('matric', 'diploma', 'asasi', 'stpm_cert', 'stpm_slip', 'spm_cert', 'spm_slip', 'fake', 'muet',
           'spvm', 'other', 'results_slip', 'offer_letter')
_io = None


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
    from apps.scholarship.genuineness.matric_poly_doc import (
        MATRIC_TRANSCRIPT_SIGNATURES, POLY_TRANSCRIPT_SIGNATURES, _complete_final, _in_progress,
        matric_poly_higher_genuineness)
    from apps.scholarship.genuineness.results_doc import _norm_fold_upper_alnum, _score_list

    bad = 0
    for folder in FOLDERS:
        tally, top = {}, {'matric': 0.0, 'poly': 0.0}
        for key in folder_keys(folder):
            text = _io.production_input(key)[0]
            tn = _norm_fold_upper_alnum(text)
            pm = _score_list(MATRIC_TRANSCRIPT_SIGNATURES, tn, False, False)['probability']
            pp = _score_list(POLY_TRANSCRIPT_SIGNATURES, tn, False, False)['probability']
            sg = matric_poly_higher_genuineness(text)
            st = sg.get('status', '-') + (f" ({sg['type']})" if sg.get('status') not in (None, 'genuine') else '')
            tally[st] = tally.get(st, 0) + 1
            # A whole final transcript (even bundled with a slip / the portal) must score genuine.
            if (_complete_final(text, tn, 'matric') or _complete_final(text, tn, 'diploma')) and st != 'genuine':
                bad += 1
                print(f'  FINAL TRANSCRIPT NOT GENUINE {key} {st}')
            if 'not_final' in st and not _in_progress(text):          # review B1: positive evidence only
                bad += 1
                print(f'  TRANSCRIPT RULED NON-FINAL WITHOUT AN IN-PROGRESS STATUS {key}')
            if folder in ('matric', 'diploma'):
                print(f'  {key:<32} matric p={pm:.2f} poly p={pp:.2f} -> {st}')
            else:
                top = {'matric': max(top['matric'], pm), 'poly': max(top['poly'], pp)}
                if st == 'genuine':
                    bad += 1
                    print(f'  CONTROL SCORED GENUINE {key}')
        extra = '' if folder in ('matric', 'diploma') else f"  max raw p: matric {top['matric']:.2f}, poly {top['poly']:.2f}"
        print(f'{folder:<14} {tally}{extra}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
