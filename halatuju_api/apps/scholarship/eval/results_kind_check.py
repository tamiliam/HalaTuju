"""What kind does `results_kind` read on every REAL results document? (Matric/Diploma M1)

A HAND-RUN measurement, never a test: it reads the gitignored `results_split` / `results_slip` OCR
caches in `snapshots/` (`<key>.ocr.txt`, PII; README.md) and, where the corpus holds one,
production's STORED read of the same upload (`higher_results__` / `matric_asasi_diploma__` /
`results_slip__a<app>__d<doc>.json`). The committed tests use synthetic text
(`tests/test_results_kind_issuers.py`); this script is how a human checks them against the real pages.

Per document: the folder's kind (the owner's sort), `detect` on the OCR text, and
`detect_from_fields` on the stored read. WRONG = a different kind than the folder's (the failure that
must never happen: "cannot tell" is never a disagreement). Folders with no single kind (fake, muet,
spvm, other, and `results_slip`, which also holds misfiled STPM pages) are listed, never scored.
Prints keys, folders and kind codes only - never a name, an IC or a grade. Exits non-zero on WRONG.

Before / after a change: ``--code <another halatuju_api folder>`` imports `results_kind` from that
checkout instead of this one (e.g. a worktree on main), so the two runs can be compared.

``--snapshots <folder>`` reads another checkout's caches (a worktree holds none).

Usage:  python apps/scholarship/eval/results_kind_check.py [--code PATH] [--snapshots PATH] [--quiet]
"""
import glob
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, 'snapshots')
#: The folder → the kind every page in it IS (the owner's sort, README "results_split corpus").
EXPECT = {'matric': 'matric', 'diploma': 'diploma', 'asasi': 'asasi', 'stpm_cert': 'stpm',
          'stpm_slip': 'stpm', 'spm_cert': 'spm', 'spm_slip': 'spm'}
LISTED = ('fake', 'muet', 'spvm', 'other', 'results_slip')
STORED = ('higher_results', 'matric_asasi_diploma', 'results_slip')


def cached_keys(folder):
    return sorted(os.path.basename(p)[:-len('.ocr.txt')]
                  for p in glob.glob(os.path.join(SNAP, folder + '__*.ocr.txt')))


def stored_fields(key):
    """Production's stored read of this key's upload, or None (a split page's read is the whole
    combined upload's, so it is not this page's and is skipped)."""
    m = re.search(r'__a(\d+)__d(\d+)$', key)
    if not m:
        return None
    for pre in STORED:
        path = os.path.join(SNAP, f'{pre}__a{m.group(1)}__d{m.group(2)}.json')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as fh:
                vf = (json.load(fh) or {}).get('vision_fields') or {}
            f = vf.get('fields')
            return f if isinstance(f, dict) and f else None
    return None


def score(got, want):
    if not want:
        return 'listed'
    return 'ok' if got == want else ('cannot_tell' if not got else 'WRONG')


def main(argv):
    global SNAP
    SNAP = argv[argv.index('--snapshots') + 1] if '--snapshots' in argv else SNAP
    code =argv[argv.index('--code') + 1] if '--code' in argv else os.path.abspath(
        os.path.join(HERE, '..', '..', '..'))
    sys.path.insert(0, code)
    from apps.scholarship.results_kind import detect, detect_from_fields   # pure: no Django
    quiet = '--quiet' in argv
    text_tally, field_tally, unread, wrong = Counter(), Counter(), 0, 0
    for folder in list(EXPECT) + list(LISTED):
        for key in cached_keys(folder):
            with open(os.path.join(SNAP, key + '.ocr.txt'), encoding='utf-8') as fh:
                text = fh.read()
            if not text.strip():
                unread += 1
            want = EXPECT.get(folder, '')
            got = detect(text)
            f = stored_fields(key)
            got_f = detect_from_fields(f) if f is not None else None
            s_text = score(got, want)
            s_f = score(got_f, want) if got_f is not None else 'no_read'
            text_tally[(folder, s_text, got)] += 1
            field_tally[(folder, s_f, got_f)] += 1
            wrong += (s_text == 'WRONG') + (s_f == 'WRONG')
            if not quiet and (folder in ('matric', 'diploma', 'asasi') or 'WRONG' in (s_text, s_f)):
                print(f'{key:<32} {folder:<10} text={got!r:<10} {s_text:<12} fields={got_f!r:<10} {s_f}')
    for title, tally in (('OCR text (`detect`)', text_tally), ('stored read (`detect_from_fields`)', field_tally)):
        print(f'\n-- {title}')
        for (folder, verdict, got), n in sorted(tally.items(), key=lambda kv: (kv[0][0], kv[0][1], str(kv[0][2]))):
            print(f'   {folder:<12} {verdict:<12} {got!r:<10} {n}')
    print(f'\ncould not read (empty OCR text): {unread} · WRONG: {wrong} · code: {code}')
    return 1 if wrong else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
