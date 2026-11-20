"""OCR-first S5 gate: the SPM results-slip AI read on 3.8 Flash, scored before it goes live.

S5 moved the slip's AI fallback off 2.5 Flash onto 3.8 Flash ONLY (`vision/slip_read.py`: a closed
grade enum with every key required, every answer checked, one 3.8 retry, a malformed answer a
failed read). The roadmap's gate: re-read the cached slips and the answer key on 3.8; 3.8 must score
AT LEAST AS WELL AS 2.5 on the answer key, with 0 malformed grades. The paid part needs the owner's
yes.

MODES
  (default) --dry-run, FREE: every corpus slip goes through the production read
      (`vision.extract_document_fields(..., 'results_slip', image=...)`) with the model seam MOCKED —
      a synthetic answer, malformed on every 4th slip so the retry runs too. No network (the genai
      client refuses), no key, no database, nothing written. Then prints the live run's expected call
      count and estimated cost.
  --live, PAID (owner's yes): the same read on the real 3.8 Flash, inside
      `offer_fresh_gemini.guarded_production_read` (a 402 / 429 stops the whole run, every database
      query and Storage are refused). Cache first: `<eval-dir>/slip_s5/<key>.json`; a cached slip
      is never read again unless --force; a service failure (503, 404 model, …) is NOT cached.
      --max-usd (default 4.00) stops the run at its cap (exit 5); a call that reports no token
      counts, or a call on a model with no price row, stops it too (exit 4), since the cap could
      not be kept. Every stop prints the summary line (slips read, US$ counted, service failures
      not cached) first.
  --score, FREE: reads those caches and scores them beside the STORED read
      (`snapshots/<key>.json`), on the typed-grade answer key: wrong grades (`compare_academics`
      `mismatched`), "please check" rows, refusals, and malformed grades (must be 0).

THE ANSWER KEY. By default the grades each student TYPED (`applicants.json` profile `grades`), for
the corpus slips; `--answer-key FILE` (JSON `{slip key: {subject code: grade}}`) replaces it with the
reviewer-confirmed 137-slip key once that is exported (a database read: not this script's job). A
key slip with no image in `fixtures/results_slip/` is counted and listed as missing, never read.

THE BASELINE. The stored read of a corpus slip is the 2.5 AI read only where its `capture` is 'ai'
or absent (older reads); 'deterministic' rows are the parser's. `--score` prints both, and judges the
gate on the AI-read subset.

Counts only, never a name or a grade, are printed. Synthetic tests: `tests/test_slip_s5_gate.py`.

Usage (from halatuju_api/):
  python -I apps/scholarship/eval/slip_s5_gate.py --eval-dir <corpus eval dir>             # free
  python -I apps/scholarship/eval/slip_s5_gate.py --eval-dir <dir> --live --max-usd 4      # PAID
  python -I apps/scholarship/eval/slip_s5_gate.py --eval-dir <dir> --score [--answer-key F]
"""
import argparse
import glob
import json
import os
import sys
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))      # halatuju_api/
if _API_ROOT not in sys.path:                  # run as a script with -I: reach the app package
    sys.path.insert(0, _API_ROOT)

DEFAULT_ENV_FILE = os.path.join(os.path.dirname(_API_ROOT), '.env')
CACHE_DIR = 'slip_s5'
DOC_TYPE = 'results_slip'
_CONTENT_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.pdf': 'application/pdf'}
#: The roadmap's cost base (S0 dry run): US$2.04 for 479 documents on 2.5 Flash, about US$0.004 per
#: call. 3.8 Flash is ASSUMED to cost at most twice that (no published price row yet).
USD_PER_CALL_25 = 0.004
USD_PER_CALL_38_MAX = 2 * USD_PER_CALL_25
#: The price row the live run's cost meter uses for 3.8 Flash: 2x the 2.5 Flash row (ASSUMED, as
#: above). Replace it with the published price before the run if one exists.
PRICE_38_ASSUMED = {'input': 0.60, 'output': 5.00, 'thinking': 5.00}
#: The roadmap's slip count for S5: the 98 cached slips plus the 137-slip answer key.
ROADMAP_SLIPS = 98 + 137
#: --live stopped at its --max-usd cap: slips are left unread, so the run is not a success.
EXIT_CAP = 5
EXIT_CODES = ('exit codes: 0 done; 2 nothing read (no corpus, unknown keys, no key, or a slip model '
              'off the allow-list); 3 a 402 / 429 stopped --live; 4 a --live call reported no token '
              'counts or had no price row; 5 --live stopped at its --max-usd cap (slips left unread)')
#: --live stopped because the cap could not be kept (no token counts, or no price row).
EXIT_BLIND = 4


# ── The corpus ───────────────────────────────────────────────────────────────────────────────
def slip_files(eval_dir):
    """{key: image path} for every slip fixture (`results_slip__aN__dN.<jpg|png|pdf>`)."""
    out = {}
    for path in sorted(glob.glob(os.path.join(eval_dir, 'fixtures', DOC_TYPE, f'{DOC_TYPE}__*'))):
        stem, ext = os.path.splitext(os.path.basename(path))
        if ext.lower() in _CONTENT_TYPES:
            out[stem] = path
    return out


def _load_json(path, default):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def answer_key(eval_dir, key_file=None):
    """{slip key: {subject code: grade}}: the file given, else the typed grades of each corpus slip's
    applicant (`applicants.json`, keyed by the N of `results_slip__aN__dN`)."""
    if key_file:
        data = _load_json(key_file, {})
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    applicants = _load_json(os.path.join(eval_dir, 'applicants.json'), {})
    out = {}
    for key in slip_files(eval_dir):
        app_id = key.split('__')[1][1:] if key.count('__') >= 2 else ''
        grades = ((applicants.get(app_id) or {}).get('profile') or {}).get('grades')
        if isinstance(grades, dict) and grades:
            out[key] = grades
    return out


def stored_read(eval_dir, key):
    """(fields, capture) of the stored read in `snapshots/<key>.json`; ({}, None) when absent."""
    vf = (_load_json(os.path.join(eval_dir, 'snapshots', f'{key}.json'), {}) or {}).get('vision_fields') or {}
    fields = vf.get('fields') if isinstance(vf.get('fields'), dict) and not vf.get('error') else {}
    return fields, vf.get('capture')


# ── Reading ──────────────────────────────────────────────────────────────────────────────────
def read_one(extract, path):
    """One slip through the production AI read (`extract_document_fields`, image path)."""
    with open(path, 'rb') as fh:
        data = fh.read()
    ct = _CONTENT_TYPES[os.path.splitext(path)[1].lower()]
    return extract('', DOC_TYPE, image=data, content_type=ct)


def synthetic_answer(n):
    """The dry run's mocked model answer for the n-th call: a made-up two-subject slip; every 4th
    call's answer is malformed ("Aplus}") so the retry path runs."""
    grade = 'Aplus}' if n % 4 == 0 else 'A'
    return {'candidate_name': 'CALON CONTOH', 'exam': 'SPM',
            'results': [{'subject': 'BAHASA MELAYU', 'grade': grade, 'band': 'CEMERLANG TINGGI'},
                        {'subject': 'SEJARAH', 'grade': 'B+', 'band': 'KEPUJIAN TERTINGGI'}],
            'warnings': []}


def dry_run(eval_dir, keys, out=print):
    """Every slip through the real read with the seam mocked; returns the counts."""
    from apps.scholarship import vision
    files = slip_files(eval_dir)
    calls, models_seen = [], set()

    def fake_seam(prompt, schema, **kw):
        models_seen.update(kw.get('models') or ['<default cascade>'])
        calls.append(1)
        return synthetic_answer(len(calls))

    def no_network(*a, **k):
        raise AssertionError('slip_s5_gate dry run: the genai client was reached')

    counts = {'slips': 0, 'read_ok': 0, 'failed_read': 0, 'retried': 0}
    with mock.patch.object(vision, '_call_gemini_json', fake_seam), \
            mock.patch('google.genai.Client', no_network):
        for key in keys:
            res = read_one(vision.extract_document_fields, files[key])
            counts['slips'] += 1
            counts['read_ok' if not res.get('error') else 'failed_read'] += 1
            counts['retried'] += res.get('slip_calls') == 2
    counts['mock_calls'] = len(calls)
    counts['models_seen'] = sorted(models_seen)
    return counts


def estimate(n_slips):
    """The live run's expected calls (one per slip, two when the retry runs) and cost range."""
    return {'slips': n_slips, 'calls_min': n_slips, 'calls_max': 2 * n_slips,
            'usd_low': round(n_slips * USD_PER_CALL_25, 2),
            'usd_high': round(2 * n_slips * USD_PER_CALL_38_MAX, 2)}


def live_run(eval_dir, keys, *, client_factory, force=False, max_usd=4.0, out=print):
    """PAID. Reads each uncached slip on 3.8 Flash and caches the answer; returns an exit code."""
    from apps.scholarship.eval import offer_fresh_gemini as ofg
    from apps.scholarship.read_errors import is_ai_service_error
    from apps.scholarship.vision.slip_read import is_slip_model, slip_read_models
    models = slip_read_models()
    if not models or not all(is_slip_model(m) for m in models):
        out(f'STOP: the slip read models are {models} - 3.8 only expected. Nothing read.')
        return 2
    files, spent, read, unpriced, not_cached = slip_files(eval_dir), 0.0, 0, 0, 0
    os.makedirs(os.path.join(eval_dir, CACHE_DIR), exist_ok=True)

    def summary():
        out(f'Read {read} slips on {models}, US${spent:.4f} (3.8 priced at the ASSUMED row unless '
            f'PRICES has one); {not_cached} service failure(s) not cached.')

    with mock.patch.dict(ofg.PRICES, {m: ofg.PRICES.get(m) or PRICE_38_ASSUMED for m in models}):
        for key in keys:
            cache = os.path.join(eval_dir, CACHE_DIR, f'{key}.json')
            if os.path.exists(cache) and not force:
                continue
            stop = ofg.cap_stop_line([{'usage': {'cost_usd': spent, 'unpriced_calls': unpriced}}], max_usd)
            if stop:
                summary()                    # review round 3: the counts before the stop line
                out(stop)
                # review round 2: a capped run is not a finished run; round 3: a call with no price
                # row is the "cap cannot be kept" stop (4), as the docstring says, not the cap (5)
                return EXIT_BLIND if unpriced else EXIT_CAP
            calls, meter = [], []
            try:
                with ofg.guarded_production_read(client_factory, calls, meter) as extract:
                    res = read_one(extract, files[key])
            except ofg.StopRun as e:
                out(f'STOP: {e.model} answered {e.code} - the run ends here ({read} slips read)')
                return 3
            answered = [c for c in calls if c.get('answered')]
            spent += sum(c.get('cost_usd') or 0.0 for c in answered)
            unpriced += sum(1 for c in answered if c.get('cost_usd') is None)
            read += 1
            if is_ai_service_error(res.get('error')):
                not_cached += 1          # our side failed (503, 404 model, …): read again next run
            else:                        # a real read, or a real bad-answer refusal
                with open(cache, 'w', encoding='utf-8') as fh:
                    json.dump({'result': res, 'calls': calls, 'models': models}, fh, indent=1, sort_keys=True)
            blind = sum(1 for c in answered
                        if c.get('input_tokens') is None or c.get('output_tokens') is None)
            if blind:
                summary()
                out(f'STOP: {blind} call(s) reported no token counts - the cap US${max_usd:.2f} cannot '
                    f'be kept ({read} slips read, US${spent:.4f} counted) - nothing more read')
                return EXIT_BLIND
    summary()
    return 0


# ── Scoring (free) ───────────────────────────────────────────────────────────────────────────
def score_read(fields, typed):
    """{refused, malformed, wrong, check, accurate} for one read against one answer."""
    from apps.scholarship.academic_engine import compare_academics, read_slip
    from apps.scholarship.vision.sanitize import SLIP_GRADES
    if not isinstance(fields, dict) or not isinstance(fields.get('results'), list):
        return {'refused': 1, 'malformed': 0, 'wrong': 0, 'check': 0, 'accurate': 0}
    rows = [r for r in fields['results'] if isinstance(r, dict)]
    malformed = sum(1 for r in rows if (r.get('grade') or '') not in (*SLIP_GRADES, ''))
    cmp = compare_academics(typed, read_slip(SimpleNamespace(vision_fields={'fields': fields})))
    return {'refused': 0, 'malformed': malformed, 'wrong': len(cmp.get('mismatched') or []),
            'check': len(cmp.get('uncertain') or []), 'accurate': int(bool(cmp.get('accurate')))}


def gate_totals(eval_dir, key_file=None):
    """Totals for the S5 3.8 read and the stored read, overall and on the stored-AI subset."""
    key = answer_key(eval_dir, key_file)
    files = slip_files(eval_dir)
    blank = {'slips': 0, 'refused': 0, 'malformed': 0, 'wrong': 0, 'check': 0, 'accurate': 0}
    out = {name: dict(blank) for name in ('s5_all', 'stored_all', 's5_on_ai', 'stored_ai')}
    out['uncached'] = out['key_slips'] = 0
    out['key_missing_image'] = sorted(k for k in key if k not in files)
    for k, typed in key.items():
        if k not in files:
            continue
        out['key_slips'] += 1
        cached = _load_json(os.path.join(eval_dir, CACHE_DIR, f'{k}.json'), None)
        if not cached:
            out['uncached'] += 1
            continue
        res = cached.get('result') or {}
        new = score_read(res.get('fields') if not res.get('error') else None, typed)
        old_fields, capture = stored_read(eval_dir, k)
        old = score_read(old_fields or None, typed)
        lanes = [('s5_all', new), ('stored_all', old)]
        if capture in ('ai', None):
            lanes += [('s5_on_ai', new), ('stored_ai', old)]
        for lane, s in lanes:
            out[lane]['slips'] += 1
            for f, v in s.items():
                out[lane][f] += v
    new, base = out['s5_on_ai'], out['stored_ai']
    out['gate'] = ('PASS' if new['slips'] and new['malformed'] == 0 and out['s5_all']['malformed'] == 0
                   and new['wrong'] <= base['wrong'] and new['accurate'] >= base['accurate']
                   else 'NOT MET' if new['slips'] else 'NO DATA')
    return out


def main(argv=None, *, client_factory=None, out=print):
    # Raw: argparse's wrapping would break "--max-usd" at its hyphen when the epilog grows.
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=EXIT_CODES,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--eval-dir', default=HERE)
    ap.add_argument('--live', action='store_true', help='PAID: read on 3.8 Flash (owner\'s yes)')
    ap.add_argument('--score', action='store_true', help='free: score the caches')
    ap.add_argument('--answer-key', default=None, help='JSON {slip key: {subject code: grade}}')
    ap.add_argument('--keys', default='', help='comma-separated slip keys (default: every slip)')
    ap.add_argument('--force', action='store_true', help='re-read cached slips (PAID)')
    ap.add_argument('--max-usd', type=float, default=4.0)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--env-file', default=DEFAULT_ENV_FILE, help="--live: the .env holding the key")
    args = ap.parse_args(argv)
    files = slip_files(args.eval_dir)
    if not files:
        out(f'No results slips in {args.eval_dir}/fixtures/{DOC_TYPE} - this gate needs the local corpus.')
        return 2
    keys = [k.strip() for k in args.keys.split(',') if k.strip()] or list(files)
    if unknown := [k for k in keys if k not in files]:
        out(f'Unknown slip keys: {len(unknown)}. Nothing read.')
        return 2
    if args.score:
        s = gate_totals(args.eval_dir, args.answer_key)
        s['key_missing_image'] = len(s['key_missing_image'])
        out(json.dumps(s, indent=1, sort_keys=True))
        return 0
    if args.live:
        from django.conf import settings
        if not getattr(settings, 'GEMINI_API_KEY', ''):
            out('GEMINI_API_KEY is not set - nothing read.')
            return 2
        if client_factory is None:
            from google import genai
            client_factory = genai.Client
        return live_run(args.eval_dir, keys, client_factory=client_factory, force=args.force,
                        max_usd=args.max_usd, out=out)
    counts = dry_run(args.eval_dir, keys, out)
    report = {'dry_run': counts, 'live_this_corpus': estimate(len(keys)),
              'live_roadmap_s5': estimate(ROADMAP_SLIPS),
              'assumption': f'US${USD_PER_CALL_25}/call on 2.5 (S0 base); 3.8 at most 2x'}
    if args.json:
        out(json.dumps(report, indent=1, sort_keys=True))
    else:
        e, r = report['live_this_corpus'], report['live_roadmap_s5']
        out(f"Dry run (mocked, free): {counts['slips']} slips, {counts['mock_calls']} mock calls, "
            f"{counts['retried']} retried, {counts['failed_read']} failed reads; models {counts['models_seen']}")
        out(f"Live on this corpus: {e['calls_min']}-{e['calls_max']} calls, about US${e['usd_low']}-{e['usd_high']}")
        out(f"Live, roadmap S5 ({ROADMAP_SLIPS} slips): {r['calls_min']}-{r['calls_max']} calls, "
            f"about US${r['usd_low']}-{r['usd_high']}")
        out(report['assumption'])
    return 0


if __name__ == '__main__':
    _argv = sys.argv[1:]
    if '--live' in _argv:
        from apps.scholarship.eval.offer_fresh_gemini import load_gemini_key
        _env = next((_argv[i + 1] for i, a in enumerate(_argv[:-1]) if a == '--env-file'), DEFAULT_ENV_FILE)
        load_gemini_key(_env)
    from apps.scholarship.eval.offer_fresh_gemini import bootstrap_django
    bootstrap_django()
    sys.exit(main(_argv))
