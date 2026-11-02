"""Does the Exact offer reader read the REAL offer corpus right? (offer exact-read S5, 2026-11-03)

A HAND-RUN measurement, never a test: it reads the gitignored offer corpus (`README.md`; real PII) and
prints keys, field names and counts — NEVER a value. Committed tests: `tests/test_offer_parse_check.py`
(synthetic twins). No paid call, nothing written.

Each letter is fed what production feeds the Exact read (`offer_exact.exact_offer_read`): the text
(`offer_replay.production_text` — a digital PDF's text layer, else Vision page 1), the page-1 text (a
digital PDF's page-1 layer, read here from the corpus's own PDF, free) and the profile IC
(`context.json`, for the IC guard). Per letter, one outcome:

  EXACT           a lock whose core fields (name, NRIC, institution, programme — stream for STPM /
                  matriculation —, intake, reporting date) are all exact or blank_correct
  INCOMPLETE      a lock with a core field the letter prints and the lock left blank (the merge keeps
                  the prior read's value there), none wrong
  WRONG           a lock with a core field `wrong` or `extra` against the answer — must never happen
  CONTROL-LOCKED  a lock on a letter whose answer family is not STPM / matriculation / polytechnic, or
                  whose `is_offer_letter` is portal_page / not_offer — must never happen
  FALLBACK        no lock (→ the AI reader)
  UNANSWERED      a lock on a letter with no answer (counted, not scored)

The offer date is scored but is not core (its wrong count is printed). By split, family and input kind.

THE PIPELINE (`--base`, default `.fresh_s4d.json` = the AI reader 2.3.0): the production read — the lock
merged over the AI read (`offer_exact.merge_over`), else the AI read — scored fully exact per split, on the
letters that hold a base read (the acceptance numbers: dev ≥ 89/126, held-out ≥ 63/90).

THE STORED EXACT READS: letters whose stored read is `capture='deterministic'`, how many re-lock today
(the 21 at-risk reads of the S5 plan), the keys that do not.

Usage:  python -I apps/scholarship/eval/offer_parse_check.py [--split dev|heldout|all] [--eval-dir DIR]
            [--base SUFFIX] [--json]
Exits 1 on any WRONG or CONTROL-LOCKED letter in the split.
"""
import argparse
import json
import logging
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))      # halatuju_api/
if _API_ROOT not in sys.path:                  # run as a script with -I: reach the app package
    sys.path.insert(0, _API_ROOT)
from apps.scholarship import offer_parse
from apps.scholarship.eval import offer_read_check as orc
from apps.scholarship.eval import offer_replay as rp
from apps.scholarship.offer_exact import exact_offer_read, merge_over

OUTCOMES = ('EXACT', 'INCOMPLETE', 'WRONG', 'CONTROL-LOCKED', 'FALLBACK', 'UNANSWERED')
BAD = ('WRONG', 'CONTROL-LOCKED')
NOT_OFFER = ('portal_page', 'not_offer')
DEFAULT_BASE = '.fresh_s4d.json'


def classify(answer, family, fields):
    """(outcome, core fields not right, offer_date outcome) for one letter. `fields` None = no lock."""
    if fields is None:
        return 'FALLBACK', [], None
    if not isinstance(answer, dict):
        return 'UNANSWERED', [], None
    if family not in orc.KNOWN_FORMAT_FAMILIES or answer.get('is_offer_letter') in NOT_OFFER:
        return 'CONTROL-LOCKED', [], None
    sc = orc.score_letter(answer, fields, family)
    bad = sorted(f for f in orc.CORE if sc[f] in ('wrong', 'extra'))
    if bad:
        return 'WRONG', bad, sc['offer_date']
    missing = sorted(f for f in orc.CORE if sc[f] == 'missing')
    return ('INCOMPLETE' if missing else 'EXACT'), missing, sc['offer_date']


def check_corpus(eval_dir, base=DEFAULT_BASE, split_file=orc.SPLIT_PATH):
    """Per key: {key, split, family, kind, stored_capture, outcome, fields_bad, offer_date,
    pipeline_exact (None = no base read)}."""
    snap = os.path.join(eval_dir, 'snapshots')
    context = orc.read_json_file(os.path.join(eval_dir, 'context.json')) or {}
    heldout = orc.load_heldout(split_file)
    rows = []
    for key in orc.offer_keys(eval_dir):
        vf = orc.stored_vision_fields(eval_dir, key)
        answer, problems = orc._read_answer(eval_dir, key)
        answer = answer if isinstance(answer, dict) and not problems else None
        family = orc.offer_family(vf, answer)
        text, route = rp.production_text(snap, key)
        ex = exact_offer_read(text, page1_text=rp.page1_of(eval_dir, key, route),
                              profile_nric=(context.get(key) or {}).get('profile_nric') or '')
        fields = ex['fields'] if ex else None
        outcome, bad, od = classify(answer, family, fields)
        base_read = orc.read_json_file(os.path.join(snap, key + base)) if base else None
        pipe = None
        if answer and base_read is not None:
            ai = base_read.get('fields') or (base_read.get('vision_fields') or {}).get('fields') or {}
            read = merge_over(ai, fields) if fields else ai
            pipe = orc.fully_exact(orc.score_letter(answer, read, family))
        rows.append({'key': key, 'split': 'heldout' if key in heldout else 'dev', 'family': family,
                     'kind': rp.input_kind3(eval_dir, key, route),
                     'stored_capture': str(vf.get('capture') or 'none'), 'outcome': outcome,
                     'fields_bad': bad, 'offer_date': od, 'pipeline_exact': pipe,
                     'nric_check': (ex or {}).get('offer_reader_inputs', {}).get('nric_check')})
    return rows


def _table(rows, dim):
    t = defaultdict(Counter)
    for r in rows:
        t[str(r[dim])][r['outcome']] += 1
    return {g: dict(c) for g, c in sorted(t.items())}


def summarise(all_rows, split):
    rows = orc.rows_in_split(all_rows, split)
    locks = [r for r in rows if r['outcome'] not in ('FALLBACK',)]
    piped = [r for r in rows if r['pipeline_exact'] is not None]
    stored_det = [r for r in all_rows if r['stored_capture'] == 'deterministic']
    return {
        'split': split, 'parser_version': offer_parse.PARSER_VERSION, 'letters': len(rows),
        'outcome': {o: sum(1 for r in rows if r['outcome'] == o) for o in OUTCOMES},
        'by_family': _table(rows, 'family'), 'by_input_kind': _table(rows, 'kind'),
        'bad': {r['key']: f"{r['outcome']} {','.join(r['fields_bad'])}".strip()
                for r in rows if r['outcome'] in BAD},
        'incomplete': {r['key']: ','.join(r['fields_bad']) for r in rows if r['outcome'] == 'INCOMPLETE'},
        'offer_date_on_locks': dict(Counter(r['offer_date'] for r in locks if r['offer_date'])),
        'nric_check_on_locks': dict(Counter(r['nric_check'] for r in locks if r['nric_check'])),
        'pipeline': {'letters': len(piped), 'fully_exact': sum(1 for r in piped if r['pipeline_exact'])},
        'locks_whole_corpus': sum(1 for r in all_rows if r['outcome'] != 'FALLBACK'),
        'stored_exact': {'total': len(stored_det),
                         'relock': sum(1 for r in stored_det if r['outcome'] != 'FALLBACK'),
                         'fall_back': sorted(r['key'] for r in stored_det if r['outcome'] == 'FALLBACK')},
    }


def print_summary(s):
    print(f"Offer letters - the Exact read (offer_parse {s['parser_version']}) | split: {s['split']} | "
          f"letters: {s['letters']} | locks, whole corpus: {s['locks_whole_corpus']}")
    print('outcome: ' + '  '.join(f'{o} {n}' for o, n in s['outcome'].items()))
    for label in ('by_family', 'by_input_kind'):
        print(f'\n{label}  ' + ' / '.join(OUTCOMES))
        for g, c in s[label].items():
            print(f'  {g:<18}' + ''.join(f'{c.get(o, 0):>8}' for o in OUTCOMES))
    print(f"\nWRONG / CONTROL-LOCKED ({len(s['bad'])}):")
    for k, v in s['bad'].items():
        print(f'  {k:<34} {v}')
    print(f"INCOMPLETE ({len(s['incomplete'])}): " + '  '.join(f'{k} [{v}]' for k, v in s['incomplete'].items()))
    print('offer date on the locks: ' + '  '.join(f'{k} {v}' for k, v in sorted(s['offer_date_on_locks'].items())))
    print('IC guard on the locks: ' + '  '.join(f'{k} {v}' for k, v in sorted(s['nric_check_on_locks'].items())))
    p = s['pipeline']
    print(f"\npipeline (lock merged over the base read, else the base read): fully exact "
          f"{p['fully_exact']} of {p['letters']}")
    se = s['stored_exact']
    print(f"stored Exact reads (whole corpus): {se['total']} | re-lock today: {se['relock']} | "
          f"fall back: {len(se['fall_back'])} " + ' '.join(se['fall_back']))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--split', choices=('heldout', 'dev', 'all'), default='dev')
    ap.add_argument('--eval-dir', default=orc.DEFAULT_EVAL_DIR)
    ap.add_argument('--split-file', default=orc.SPLIT_PATH)
    ap.add_argument('--base', default=DEFAULT_BASE, help="the AI read under the pipeline ('' for none)")
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    logging.getLogger('pypdf').setLevel(logging.ERROR)      # a damaged corpus PDF's warnings are noise here
    if not orc.offer_keys(args.eval_dir):
        print(f'No offer letters in {args.eval_dir} - this measurement needs the local corpus.')
        return 2
    s = summarise(check_corpus(args.eval_dir, args.base, args.split_file), args.split)
    if args.json:
        print(json.dumps(s, indent=1, sort_keys=True))
    else:
        print_summary(s)
    return 1 if s['bad'] else 0


if __name__ == '__main__':
    sys.exit(main())
