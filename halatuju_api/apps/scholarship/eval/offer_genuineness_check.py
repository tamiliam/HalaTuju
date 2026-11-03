"""Does today's offer GENUINENESS call match the owner's rulings, letter by letter? (offer exact-read S6)

A HAND-RUN measurement, never a test: it reads the gitignored offer corpus (`README.md`; real PII) and
prints keys, statuses, families and counts — NEVER a value read off a letter. Committed tests:
`tests/test_offer_rulings.py` (synthetic twins). No paid call, nothing written.

Each letter is scored exactly as production scores it: `genuineness.assess('offer_letter')` on the text
production feeds (`offer_replay.production_text` — a digital PDF's text layer, else Vision page 1), stored
in production's shape (`offer_replay.authenticity_of`). The EXPECTED status per letter is the committed,
PII-free `offer_genuineness_expect.json` (key → `genuine` / `suspect` / `not_offer_letter` / null for a
letter with no text): the owner's bursary rulings of 2026-11-01 (1-8), 2026-11-03 (Q2 TVET, the
confirmation default), applied to the answers (`is_offer_letter`, family, labeller note) and checked by
the owner on the S1 / S2 pages. One outcome per letter: OK, or MISS (expected X, today Y).

Usage:  python -I apps/scholarship/eval/offer_genuineness_check.py [--split dev|heldout|all]
            [--eval-dir DIR] [--json]
Exits 1 on any MISS in the split.
"""
import argparse
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)
EXPECT_PATH = os.path.join(HERE, 'offer_genuineness_expect.json')


def _orc():
    from apps.scholarship.eval import offer_read_check
    return offer_read_check


def load_expect(path=EXPECT_PATH):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)['expect']


def check(eval_dir, expect, split_file=None):
    """One row per expected letter: {key, split, family, expected, today, seen, ok}."""
    from apps.scholarship.eval.offer_replay import authenticity_of, production_text
    from apps.scholarship.genuineness.offer_rulings import ruling_of     # S6: which ruling set it (learnable)
    orc = _orc()
    split_file = split_file or orc.SPLIT_PATH
    with open(split_file, encoding='utf-8') as fh:
        held = set(json.load(fh)['heldout'])
    snap = os.path.join(eval_dir, 'snapshots')
    rows = []
    for key, want in sorted(expect.items()):
        text, _route = production_text(snap, key)
        auth = authenticity_of(text) or {}
        ans = orc.read_json_file(os.path.join(snap, key + orc.ANSWER_SUFFIX)) or {}
        today = auth.get('status')
        rows.append({'key': key, 'split': 'heldout' if key in held else 'dev',
                     'family': ans.get('family') or '', 'expected': want, 'today': today,
                     'seen': auth.get('doc_seen') or '', 'ruling': ruling_of(auth) or '-', 'ok': today == want})
    return rows


def summarise_genuineness(rows, split):
    from apps.scholarship.genuineness.results_doc import MODEL_VERSION
    rows = [r for r in rows if split == 'all' or r['split'] == split]
    return {'split': split, 'model_version': MODEL_VERSION, 'letters': len(rows),
            'ok': sum(r['ok'] for r in rows),
            'expected': dict(Counter(str(r['expected']) for r in rows)),
            'today': dict(Counter(str(r['today']) for r in rows)),
            'rulings': dict(Counter(f"{r['ruling']}:{r['today']}" for r in rows if r['ruling'] != '-')),
            'misses': [{k: r[k] for k in ('key', 'split', 'family', 'expected', 'today', 'seen', 'ruling')}
                       for r in rows if not r['ok']]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--split', choices=('heldout', 'dev', 'all'), default='dev')
    ap.add_argument('--eval-dir', default=_orc().DEFAULT_EVAL_DIR)
    ap.add_argument('--split-file', default=_orc().SPLIT_PATH)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    s = summarise_genuineness(check(a.eval_dir, load_expect(), a.split_file), a.split)
    if a.json:
        print(json.dumps(s, indent=1))
    else:
        print(f"offer genuineness, split {s['split']}, MODEL {s['model_version']}: "
              f"{s['ok']} / {s['letters']} as ruled")
        print('  expected: ' + '  '.join(f'{k} {v}' for k, v in sorted(s['expected'].items())))
        print('  today:    ' + '  '.join(f'{k} {v}' for k, v in sorted(s['today'].items())))
        print('  set by an S6 ruling: ' + ('  '.join(f'{k} {v}' for k, v in sorted(s['rulings'].items())) or 'none'))
        for m in s['misses']:
            print(f"  MISS {m['key']} ({m['split']}, {m['family'] or '-'}): expected {m['expected']}, "
                  f"today {m['today']} ({m['seen'] or '-'}, ruling {m['ruling']})")
    return 1 if s['misses'] else 0


if __name__ == '__main__':
    sys.exit(main())
