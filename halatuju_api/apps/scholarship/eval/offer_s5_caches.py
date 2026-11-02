"""The S5 dry-run caches — what the Exact read 2.0.0 would store, per corpus letter (offer exact-read S5).

A HAND-RUN step before the production dry run, never a test: it reads the gitignored corpus and writes one
gitignored cache per letter, `snapshots/<key>.s5_exact.json`, for `offer_s4_dry_run.py --suffix
.s5_exact.json`. Free (cached text, no Vision, no Gemini, no database). Prints keys and counts only.

Which letters (any split):
  * every letter the S5 Exact path LOCKS on the text production feeds it (`offer_exact.exact_read`, the
    profile IC from `context.json`): ``{"s5": "locked", "fields": <the lock merged over the corpus's stored
    read (`snapshots/<key>.json` vision_fields.fields, the live read when the corpus was fetched)>}``. The dry
    run does NOT use these fields: it re-derives the lock against the LIVE row with the PRODUCTION profile IC
    (the IC guard needs it, and the corpus copy may be stale); they are kept to read by hand;
  * every letter whose STORED read is an Exact read (`capture='deterministic'`) that S5 does NOT lock — a live
    re-read would go to the AI reader, which this cannot run: ``{"s5": "fallback", "fallback_guess": ...,
    "fields": ...}`` — the corpus's AI read 2.3.0 (`<key>.fresh_s4d.json`, guess `ai_2.3.0_cache`) when it has
    one, else the stored read unchanged (guess `stored_unchanged_no_ai_read`). A GUESS, flagged in the dry run.

Usage:  python -I apps/scholarship/eval/offer_s5_caches.py --eval-dir <corpus> [--write]
        (without --write it prints the counts and writes nothing)
"""
import argparse
import json
import logging
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)
from apps.scholarship.eval import offer_read_check as orc
from apps.scholarship.eval import offer_replay as rp
from apps.scholarship.offer_exact import exact_read, merge_over
from apps.scholarship.offer_parse import PARSER_VERSION

SUFFIX = '.s5_exact.json'
AI_SUFFIX = '.fresh_s4d.json'


def s5_cache(eval_dir, key, profile_nric=''):
    """The cache record for one letter, or None (neither an S5 lock nor a stored Exact read)."""
    snap = os.path.join(eval_dir, 'snapshots')
    vf = orc.stored_vision_fields(eval_dir, key)
    stored = vf.get('fields') if isinstance(vf.get('fields'), dict) else {}
    text, route = rp.production_text(snap, key)
    ex = exact_read(text, from_text_layer=route == 'text_layer', page1_layer=rp.page1_of(eval_dir, key, route),
                    profile_nric=profile_nric)
    base = {'offer_parser_version': PARSER_VERSION, 'text_route': route,
            'stored_capture': str(vf.get('capture') or 'none')}
    if ex is not None:
        return {**base, 's5': 'locked', 'fields': merge_over(stored, ex['fields']),
                'nric_check_eval': ex['offer_reader_inputs']['nric_check']}
    if vf.get('capture') != 'deterministic':
        return None
    ai = orc.read_json_file(os.path.join(snap, key + AI_SUFFIX))
    if ai is not None:
        return {**base, 's5': 'fallback', 'fallback_guess': 'ai_2.3.0_cache', 'fields': ai.get('fields') or {}}
    return {**base, 's5': 'fallback', 'fallback_guess': 'stored_unchanged_no_ai_read', 'fields': stored}


def build(eval_dir, write=False):
    context = orc.read_json_file(os.path.join(eval_dir, 'context.json')) or {}
    counts, keys = Counter(), {}
    for key in orc.offer_keys(eval_dir):
        rec = s5_cache(eval_dir, key, (context.get(key) or {}).get('profile_nric') or '')
        if rec is None:
            continue
        counts[rec['s5'] + (':' + rec['fallback_guess'] if rec['s5'] == 'fallback' else '')] += 1
        keys.setdefault(rec['s5'], []).append(key)
        if write:
            with open(os.path.join(eval_dir, 'snapshots', key + SUFFIX), 'w', encoding='utf-8') as fh:
                json.dump(rec, fh, ensure_ascii=False, indent=1, sort_keys=True)
    return counts, keys


def main(argv=None, out=print):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--eval-dir', default=orc.DEFAULT_EVAL_DIR)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args(argv)
    logging.getLogger('pypdf').setLevel(logging.ERROR)
    if not orc.offer_keys(args.eval_dir):
        out(f'No offer letters in {args.eval_dir} - this step needs the local corpus.')
        return 2
    counts, keys = build(args.eval_dir, write=args.write)
    out(f"S5 dry-run caches ({SUFFIX}, offer_parse {PARSER_VERSION}) | "
        f"{'written' if args.write else 'NOT written (add --write)'}: "
        + '  '.join(f'{k} {v}' for k, v in sorted(counts.items())))
    out('fallback keys: ' + ' '.join(keys.get('fallback', [])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
