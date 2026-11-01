"""Make the offer-letter HELD-OUT split, reproducibly (offer exact-read S1, 2026-11-01).

The held-out letters are the ones no reader change may be tuned on: the scorer
(`offer_read_check.py`) is run on them once per reader round. The rule:

  pool     = letters NOT in the old local corpus (`fixtures/offer_letter/`, matched by doc id
             `__d<id>`) AND whose stored read is the AI reader's (`capture='ai'`). The
             fixed-format reader's locks (`capture='deterministic'`) are already measured by the
             stpm/matric/poly parse checks and are not hand-labelled in S1 (owner steer).
  strata   = (family, programme) — family from the stored read (`offer_read_check.offer_family`),
             programme from `programme_by_key.csv`.
  quota    = TARGET letters shared over the strata in proportion to their size (largest
             remainder); a stratum of 2+ letters gets at least 1. Fewer when the pool is smaller.
  draw     = `random.Random(f'{SEED}:{family}:{programme}').sample(sorted keys, quota)`.
  dev      = every other key.

It reads keys, the stored family and capture, and the programme — nothing else — and writes
`offer_split.json` (keys only, PII-free, committed). `--check` re-derives it and exits 1 on any
difference; with neither flag it prints the counts.

Usage:  python -I apps/scholarship/eval/offer_split.py [--write | --check] [--eval-dir DIR]
"""
import argparse
import json
import os
import random
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))      # halatuju_api/
if _API_ROOT not in sys.path:                  # run as a script with -I: reach the app package
    sys.path.insert(0, _API_ROOT)
from apps.scholarship.eval import offer_read_check as orc

SEED = 20261101
TARGET = 90
OLD_CORPUS_DIR = os.path.join(HERE, 'fixtures', 'offer_letter')
RULE = ('pool = letters not in the old corpus (fixtures/offer_letter, by doc id) whose stored read '
        "is the AI reader's (capture ai; deterministic locks are covered by the parse checks); "
        'strata = (family, programme); quota = TARGET shared by largest remainder, min 1 for a '
        "stratum of 2+; draw = random.Random('SEED:family:programme').sample(sorted keys, quota); "
        'dev = every other key')


def old_doc_ids(old_dir=OLD_CORPUS_DIR):
    if not os.path.isdir(old_dir):
        return set()
    return {m.group(1) for n in os.listdir(old_dir) for m in [re.search(r'__d(\d+)', n)] if m}


def split_rows(eval_dir, old_ids):
    """[{key, family, programme, capture, seen_before}] — the only facts the split reads."""
    programmes = orc.programme_by_key(eval_dir)
    rows = []
    for key in orc.offer_keys(eval_dir):
        vf = orc.stored_vision_fields(eval_dir, key)
        doc = re.search(r'__d(\d+)$', key)
        rows.append({'key': key, 'family': orc.offer_family(vf),
                     'programme': programmes.get(key, 'unknown'),
                     'capture': str(vf.get('capture') or 'none'),
                     'seen_before': bool(doc and doc.group(1) in old_ids)})
    return rows


def allocate(sizes, target):
    """{stratum: quota} — largest remainder, min 1 for a stratum of 2+, never above its size."""
    total = sum(sizes.values())
    target = min(target, total)
    if not total:
        return {}
    exact = {s: n * target / total for s, n in sizes.items()}
    quota = {s: int(v) for s, v in exact.items()}
    for s in sorted(exact, key=lambda s: (-(exact[s] - quota[s]), s))[:target - sum(quota.values())]:
        quota[s] += 1
    for s in sorted(sizes):
        if sizes[s] >= 2 and quota[s] == 0:
            donor = max(sorted(quota), key=lambda d: (quota[d], sizes[d]))
            if quota[donor] > 1:
                quota[donor] -= 1
                quota[s] = 1
    return quota


def build_split(rows, seed=SEED, target=TARGET):
    """The split dict for `offer_split.json` (deterministic for the same rows)."""
    pool = [r for r in rows if not r['seen_before'] and r['capture'] == 'ai']
    by_stratum = {}
    for r in pool:
        by_stratum.setdefault(f"{r['family']}|{r['programme']}", []).append(r['key'])
    quota = allocate({s: len(k) for s, k in by_stratum.items()}, target)
    heldout = []
    for s in sorted(by_stratum):
        family, programme = s.split('|', 1)
        rng = random.Random(f'{seed}:{family}:{programme}')
        heldout += rng.sample(sorted(by_stratum[s]), quota.get(s, 0))
    return {
        'about': 'Offer letters read exactly - the held-out split. Keys only (PII-free). Made by '
                 'offer_split.py; re-derive with --check. Every key not listed is dev.',
        'rule': RULE, 'seed': seed, 'target': target,
        'letters': len(rows), 'seen_before': sum(1 for r in rows if r['seen_before']),
        'deterministic_unseen': sum(1 for r in rows if not r['seen_before']
                                    and r['capture'] == 'deterministic'),
        'pool': len(pool), 'heldout_count': len(heldout),
        'strata': {s: {'pool': len(by_stratum[s]), 'heldout': quota.get(s, 0)}
                   for s in sorted(by_stratum)},
        'heldout': sorted(heldout),
    }


def _print_counts(split):
    print(f"letters {split['letters']} | seen before {split['seen_before']} | unseen deterministic "
          f"(not drawn) {split['deterministic_unseen']} | pool {split['pool']} | "
          f"held out {split['heldout_count']} (target {split['target']}, seed {split['seed']})")
    fam, prog = Counter(), Counter()
    for s, c in split['strata'].items():
        family, programme = s.split('|', 1)
        fam[family] += c['heldout']
        prog[programme] += c['heldout']
        print(f"  {s:<44} pool {c['pool']:>3}  held out {c['heldout']:>3}")
    print('  by family:    ' + '  '.join(f'{k} {v}' for k, v in sorted(fam.items())))
    print('  by programme: ' + '  '.join(f'{k} {v}' for k, v in sorted(prog.items())))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--eval-dir', default=orc.DEFAULT_EVAL_DIR)
    ap.add_argument('--old-dir', default=OLD_CORPUS_DIR)
    ap.add_argument('--out', default=orc.SPLIT_PATH)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    rows = split_rows(args.eval_dir, old_doc_ids(args.old_dir))
    if not rows:
        print(f'No offer letters in {args.eval_dir} - the split needs the local corpus.')
        return 2
    split = build_split(rows)
    _print_counts(split)
    if args.write:
        with open(args.out, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(split, fh, indent=1, sort_keys=True)
            fh.write('\n')
        print(f'written: {args.out}')
    if args.check:
        committed = orc.read_json_file(args.out) or {}
        same = committed == split
        print('matches the committed split' if same else 'DIFFERS from the committed split')
        return 0 if same else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
