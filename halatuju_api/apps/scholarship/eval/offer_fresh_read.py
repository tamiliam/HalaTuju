"""Today's AI offer reader on the LOCAL letter files — measured (offer exact-read S3, 2026-11-01).

A HAND-RUN, PAID measurement (Gemini), never a test. It reads the gitignored offer corpus
(`fixtures/offer_letters_2026-11-01/`: real PII, README.md) and writes ONE gitignored cache per
letter, `snapshots/<key>.fresh.json`, plus a run log `offer_fresh_read.log` in the same corpus
folder. It prints keys, field names, models, token counts and costs — NEVER a value. Committed
tests: `tests/test_offer_fresh_read.py` (synthetic twins, a fake Gemini client, no network).

THE CALL — exactly the production AI read, imported, never copied. `vision._run_field_extraction_impl`
reads an offer the deterministic reader does not lock with
    vision.extract_document_fields('', 'offer_letter', image=<file bytes>, content_type=<type>)
and that is the ONE function this tool calls, on the local file's bytes. Inside it, unchanged:
`_as_image_for_gemini` (a PDF → page 1 PNG), the offer prompt + `_WARNING_VOICE` +
`_DOC_HINTS['offer_letter']`, `_FIELD_SCHEMAS['offer_letter']`, `_call_gemini_json` (the
`profile_engine.MODEL_CASCADE`, temperature 0.1, the JSON schema), `_drop_expected_warnings` and
`_sanitize_extracted_fields`. `extract_document_fields` itself persists nothing; the only write on
its path is the usage meter (`usage.record_usage` → a `UsageEvent` row). So, for the run only:
  * `usage.record_usage` is REPLACED by a recorder — the meter's own arguments are kept in the cache
    (`meter`), which is how this tool shows what the live meter would have stored;
  * every database query is REFUSED (a `connection.execute_wrapper` that raises), and
    `vision._fetch_image_bytes` (Storage) raises — neither is ever reached, the guards prove it;
  * `google.genai.Client` is wrapped so each response's `usage_metadata` is kept: input
    (`prompt_token_count`), output (`candidates_token_count`), THINKING (`thoughts_token_count`),
    total, and the input split by modality (`prompt_tokens_details`).
Never `reextract_document`, `run_field_extraction_for_document` or anything that saves. The
recording client, the guards and the price table live in `offer_fresh_gemini.py`.

THE CACHE `<key>.fresh.json` — loadable by the scorer with `--read file:.fresh.json`:
  fields     the read, the same shape as a stored `vision_fields.fields` (capture 'ai')
  warnings, error, capture ('ai_fresh')
  model      the model whose answer was used (the cascade's), or null on an error
  calls      every Gemini call made for the letter: model, model_version, the token counts, cost
  usage      the letter's token totals; cost_usd / cost_myr
  meter      what `usage.record_usage` was called with (the live meter's figures)
  versions   git HEAD of this checkout, sha256 of vision.py, of the prompt actually sent, of the
             offer schema; the google-genai SDK version (there is no offer reader version yet — S4)
  image      the mime type and pixel size Gemini was shown
A letter is cached when Gemini answered (billed), or when no call could be made (no image). A
letter whose every call RAISED (nothing billed) is not cached, so a re-run tries it again.

COST — US$ per 1M tokens, Gemini API paid tier, standard (not batch), from
https://ai.google.dev/gemini-api/docs/pricing (read 2026-11-01): 2.5 Flash input 0.30, output 2.50;
2.5 Flash-Lite input 0.10, output 0.40; the page prices output "including thinking tokens", so
thinking is billed at the output rate — priced here as its own line. RM at 4.4 per US$ (a fixed
planning rate, not a live one).

STOP. A 402 (prepaid credit out) or a 429 (rate / quota) from ANY model stops the WHOLE run at once:
no retry and no fall-through to the next model in the cascade (production would fall through; a
measurement must not quietly change model). The letter is not cached; the log names the model
and the code. Exit 3.

THE ESTIMATE (`--dry-run`): counts, and a cost — no Gemini call, nothing written. Image tokens: the
MEASURED 258 per image (`IMAGE_TOKENS_MEASURED`; the documented tiling rule on
https://ai.google.dev/gemini-api/docs/tokens over-estimated ~11x for these letters); prompt + schema
text at ~4 characters a token; output 300 and thinking 500 / 1,500 / 3,000 (low / mid / high, the
roadmap's range). When fresh caches already exist it also projects from their MEASURED mean cost
per letter — the figure to quote.

THE LIVE METER: on the pilot `usage.gemini_tokens` stored prompt and candidate counts only, NOT
`thoughts_token_count` (billed at the output rate); older caches' `meter` beside `usage` shows that
gap. Since A1.12 (TD-459) the meter's output is candidates + thoughts.

THE NEW READER (offer exact-read S4). Since S4 `extract_document_fields` hands an offer to
`offer_reader.read_offer`: up to 3 pages, one image each at high media resolution, plus a digital
PDF's text layer, a new schema (`campus`, `reporting_venue`, `programme_code`) and the version stamp.
`--reader new` (the default) runs it and caches `<key>.fresh_s4.json`; `--reader current` names
S3's caches `<key>.fresh.json` (the page-1 reader, which this checkout no longer holds), so it is
read-only: `--compare` / `--costs` / `--dry-run`, never a paid read. `--compare --reader new`
scores stored, current and new on the letters holding both caches; `--costs` prints per letter the
tokens (input / output / thinking) and cost of current beside new. Same guards as above.

Usage (from halatuju_api/):
  python -I apps/scholarship/eval/offer_fresh_read.py --split all --dry-run
  python -I apps/scholarship/eval/offer_fresh_read.py --keys K1,K2 [--force]
  python -I apps/scholarship/eval/offer_fresh_read.py --split dev [--limit N]
  python -I apps/scholarship/eval/offer_fresh_read.py --compare [--split all]   # fresh vs stored
  python -I apps/scholarship/eval/offer_fresh_read.py --keys K1,K2 --reader new   # S4, paid
  python -I apps/scholarship/eval/offer_fresh_read.py --compare --reader new [--costs]
  add --eval-dir DIR for a checkout without the corpus; --env-file for the key's .env
"""
import argparse
import datetime
import glob
import hashlib
import io
import json
import math
import os
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))      # halatuju_api/
if _API_ROOT not in sys.path:                  # run as a script with -I: reach the app package
    sys.path.insert(0, _API_ROOT)
from apps.scholarship.eval import offer_read_check as orc
# The guarded client and the cost live in offer_fresh_gemini (split for size); re-exported here.
from apps.scholarship.eval.offer_fresh_gemini import (
    IMAGE_TOKENS_HIGH_A4, IMAGE_TOKENS_MEASURED, PRICE_SOURCE, PRICES, STOP_CODES, USD_TO_MYR, DatabaseRefused,
    StopRun, _refuse_db, call_cost_usd, error_code, guarded_production_read,
    bootstrap_django, image_tokens_estimate, load_gemini_key, price_for, print_costs, prompt_of,
    sha256_text, usage_of, usd_to_myr)

__all__ = ['IMAGE_TOKENS_HIGH_A4', 'IMAGE_TOKENS_MEASURED', 'PRICE_SOURCE', 'PRICES', 'STOP_CODES', 'USD_TO_MYR',
           'DatabaseRefused', 'StopRun', '_refuse_db', 'call_cost_usd', 'error_code',
           'guarded_production_read', 'image_tokens_estimate', 'price_for', 'usage_of',
           'usd_to_myr', 'read_letters', 'estimate', 'compare', 'main']

FRESH_SUFFIX = '.fresh.json'
#: The readers this tool knows: `current` = S3's page-1 reader (caches only), `new` = S4's reader.
#: `s4` = the S4 reader as first built (2.0.0, caches only); `new` = this checkout's reader (2.1.0+,
#: the review fixes: page 1 alone, the IC guard), cached apart so no earlier cache is ever overwritten.
READERS = {'current': FRESH_SUFFIX, 's4': '.fresh_s4.json', 's4b': '.fresh_s4b.json',
           's4c': '.fresh_s4c.json', 'new': '.fresh_s4d.json'}
PAID_READERS = ('new',)
#: compare: the reads shown for each --reader, oldest first.
COMPARE_READS = {'current': ('stored', 'fresh'), 's4': ('stored', 'fresh', 's4'),
                 's4c': ('stored', 'fresh', 's4', 's4c'), 'new': ('stored', 's4c', 's4d')}
_COMPARE_SUFFIX = {'fresh': READERS['current'], 's4': READERS['s4'], 's4b': READERS['s4b'],
                   's4c': READERS['s4c'], 's4d': READERS['new']}
LOG_NAME = 'offer_fresh_read.log'
DOC_TYPE = 'offer_letter'
#: Exit codes: 0 done, 2 no corpus / bad arguments, 3 stopped on a 402/429, 4 calls failed.
EXIT_STOPPED = 3
EXIT_FAILED = 4
_CONTENT_TYPE = {'pdf': 'application/pdf', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                 'png': 'image/png', 'webp': 'image/webp', 'heic': 'image/heic',
                 'heif': 'image/heif'}
#: Dry-run assumptions (see the module docstring).
EST_OUTPUT = 300
EST_THINKING = {'low': 500, 'mid': 1500, 'high': 3000}
EST_MODEL = 'gemini-2.5-flash'


# ── The corpus ───────────────────────────────────────────────────────────────────────────────
def letter_file(eval_dir, key):
    hits = sorted(p for p in glob.glob(os.path.join(eval_dir, 'fixtures', DOC_TYPE, key + '.*'))
                  if not p.endswith('.gitkeep'))
    return hits[0] if hits else None


def content_type_for(path):
    return _CONTENT_TYPE.get(os.path.splitext(path)[1].lstrip('.').lower(), 'application/octet-stream')


def answered_keys(eval_dir):
    return [k for k in orc.offer_keys(eval_dir)
            if os.path.exists(os.path.join(eval_dir, 'snapshots', k + orc.ANSWER_SUFFIX))]


def select_keys(eval_dir, *, split='all', keys=None, limit=None, split_file=orc.SPLIT_PATH):
    """The letters to read: `keys` as given, else the ANSWERED letters of the split; sorted;
    `limit` keeps the first N."""
    if keys:
        out = sorted(set(keys))
    else:
        heldout = orc.load_heldout(split_file)
        out = [k for k in answered_keys(eval_dir)
               if split == 'all' or (split == 'heldout') == (k in heldout)]
    return out[:limit] if limit else out


def fresh_path(eval_dir, key, suffix=FRESH_SUFFIX):
    return os.path.join(eval_dir, 'snapshots', key + suffix)


def _git_head():
    try:
        return subprocess.run(['git', '-C', HERE, 'rev-parse', 'HEAD'], capture_output=True,
                              text=True, timeout=20).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _file_sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def code_versions():
    """What identifies the reader run: git, file and schema hashes, and (S4) the offer reader version."""
    from apps.scholarship import offer_reader, vision
    try:
        from google import genai
        sdk = getattr(genai, '__version__', None)
    except ImportError:
        sdk = None
    schema = vision._FIELD_SCHEMAS.get(DOC_TYPE)
    return {'git_head': _git_head(), 'vision_py_sha256': _file_sha(vision.__file__),
            'schema_sha256': sha256_text(json.dumps(schema, sort_keys=True, default=str)),
            'genai_sdk': sdk, 'offer_reader_version': offer_reader.OFFER_READER_VERSION,
            'offer_reader_py_sha256': _file_sha(offer_reader.__file__)}


def _one_image(img, mime):
    facts = {'mime': mime, 'bytes': len(img), 'width': None, 'height': None}
    try:
        from PIL import Image
        with Image.open(io.BytesIO(img)) as im:
            facts['width'], facts['height'] = im.size
    except (OSError, ValueError):   # a size is a nicety for the estimate
        pass
    return facts


def image_facts(data, content_type):
    """{mime, width, height, bytes} of the FIRST image Gemini is shown, plus (S4) `pages` — one such
    dict per image — and `text_layer_chars`: production's own input assembly
    (`offer_reader.offer_inputs`). None when nothing can be shown."""
    from apps.scholarship import offer_reader
    shown = offer_reader.offer_inputs(data, content_type)
    if not shown['images']:
        return None
    pages = [_one_image(img, mime) for img, mime in shown['images']]
    return {**pages[0], 'pages': pages, 'text_layer_chars': len(shown['text_layer'])}


# ── One letter, the run ──────────────────────────────────────────────────────────────────────
def _totals(calls):
    answered = [c for c in calls if c.get('answered')]
    tot = {k: sum(c.get(k) or 0 for c in answered)
           for k in ('input_tokens', 'output_tokens', 'thinking_tokens', 'total_tokens')}
    costs = [c.get('cost_usd') for c in answered]
    tot['cost_usd'] = sum(c for c in costs if c is not None) if answered else 0.0
    tot['unpriced_calls'] = sum(1 for c in costs if c is None)
    tot['cost_myr'] = usd_to_myr(tot['cost_usd'])
    return tot


def read_one(eval_dir, key, extract, calls, meter, versions):
    """Run the production read on one local letter → the cache record (not yet written)."""
    path = letter_file(eval_dir, key)
    if path is None:
        return {'key': key, 'fields': {}, 'warnings': [], 'error': 'no letter file',
                'capture': 'ai_fresh', 'model': None, 'calls': [], 'meter': [], 'image': None}
    with open(path, 'rb') as fh:
        data = fh.read()
    ct = content_type_for(path)
    start_calls, start_meter = len(calls), len(meter)
    ex = extract('', DOC_TYPE, image=data, content_type=ct, **offer_context(eval_dir, key))
    mine, metered = calls[start_calls:], meter[start_meter:]
    used = [c for c in mine if c.get('answered') and c.get('json_ok')]
    rec = {
        'key': key, 'fields': ex.get('fields') or {}, 'warnings': ex.get('warnings') or [],
        'error': ex.get('error') or '', 'capture': 'ai_fresh',
        'model': (used[-1]['model'] if used and not ex.get('error') else None),
        'calls': mine, 'usage': _totals(mine), 'meter': metered,
        'image': image_facts(data, ct), 'input_file_ext': os.path.splitext(path)[1].lstrip('.').lower(),
        'versions': {**versions, 'prompt_sha256': (mine[0]['prompt_sha256'] if mine else None)},
        'offer_reader_version': ex.get('offer_reader_version'),
        'offer_reader_inputs': ex.get('offer_reader_inputs'), 'raw_identity': ex.get('_raw_identity'),
        'prices_usd_per_million': PRICES, 'price_source': PRICE_SOURCE, 'usd_to_myr': USD_TO_MYR,
        'read_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
    }
    return rec


def offer_context(eval_dir, key):
    """What production hands the reader's IC guard (`vision._offer_context`): the profile's IC from the
    corpus's `context.json` and the page-1 text production holds (`<key>.ocr.txt`: the text layer or
    the Vision OCR of page 1). Never printed."""
    ctx = (orc.read_json_file(os.path.join(eval_dir, 'context.json')) or {}).get(key) or {}
    ocr = os.path.join(eval_dir, 'snapshots', key + '.ocr.txt')
    text = ''
    if os.path.exists(ocr):
        with open(ocr, encoding='utf-8') as fh:
            text = fh.read()
    return {'profile_nric': ctx.get('profile_nric') or '', 'page1_ocr': text}


def _should_cache(rec):
    """Cache when Gemini answered (billed) or no call could be made; not when every call raised."""
    calls = rec['calls']
    return (not calls) or any(c.get('answered') for c in calls)


def _write_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def _append_log(log_path, entry):
    entry = {'ts': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
             **entry}
    with open(log_path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(entry, sort_keys=True) + '\n')


def _log_entry(rec, outcome):
    """A log line: key, outcome, per-call model / codes / tokens / cost — never a value."""
    return {'key': rec['key'], 'outcome': outcome, 'model': rec.get('model'),
            'error_kind': (rec.get('error') or '').split(':')[0][:60] or None,
            'calls': [{k: c.get(k) for k in ('model', 'model_version', 'answered', 'json_ok',
                                              'code', 'error', 'input_tokens', 'output_tokens',
                                              'thinking_tokens', 'total_tokens', 'cost_usd')}
                      for c in rec.get('calls') or []],
            'meter': rec.get('meter'), 'cost_usd': (rec.get('usage') or {}).get('cost_usd')}


def read_letters(eval_dir, keys, *, client_factory, force=False, out=print, versions=None,
                 suffix=READERS['new'], max_usd=None):
    """Read each key not yet cached under `suffix` (all with `force`) with this checkout's reader.
    ``max_usd``: stop (exit 3) once the run's measured cost reaches it. Returns (exit code, records)."""
    log_path = os.path.join(eval_dir, LOG_NAME)
    versions = versions if versions is not None else code_versions()
    todo = [k for k in keys if force or not os.path.exists(fresh_path(eval_dir, k, suffix))]
    out(f'offer fresh read | letters: {len(keys)} | cached already (skipped): '
        f'{len(keys) - len(todo)} | to read now: {len(todo)}')
    calls, meter, done, failed = [], [], [], 0
    with guarded_production_read(client_factory, calls, meter) as extract:
        for key in todo:
            try:
                rec = read_one(eval_dir, key, extract, calls, meter, versions)
            except StopRun as stop:
                _append_log(log_path, {'key': key, 'outcome': 'STOPPED', 'model': stop.model,
                                'code': stop.code, 'message': stop.message})
                out(f'STOP {key}: {stop.model} returned {stop.code} - the run is stopped, no '
                    f'retry, nothing cached for this letter (log: {LOG_NAME})')
                _print_calls(done, out)
                return EXIT_STOPPED, done
            if _should_cache(rec):
                _write_json(fresh_path(eval_dir, key, suffix), rec)
                outcome = 'cached_error' if rec['error'] else 'cached'
                done.append(rec)
            else:
                outcome, failed = 'not_cached_all_calls_raised', failed + 1
            _append_log(log_path, _log_entry(rec, outcome))
            out(_call_line(rec, outcome))
            spent = sum((r.get('usage') or {}).get('cost_usd') or 0.0 for r in done)
            if max_usd is not None and spent >= max_usd:
                out(f'STOP: the run has cost US${spent:.4f}, at its cap US${max_usd:.4f} - nothing more read')
                _print_calls(done, out)
                return EXIT_STOPPED, done
    _print_calls(done, out)
    return (EXIT_FAILED if failed else 0), done


def _call_line(rec, outcome):
    u = rec.get('usage') or {}
    models = '>'.join(f"{c['model']}{'' if c.get('answered') else '(x' + str(c.get('code')) + ')'}"
                      for c in rec.get('calls') or []) or '-'
    return (f"  {rec['key']:<34} {outcome:<12} {models:<40} in {u.get('input_tokens', 0):>6} "
            f"out {u.get('output_tokens', 0):>5} think {u.get('thinking_tokens', 0):>6} "
            f"US${u.get('cost_usd', 0.0):.5f}")


def _print_calls(records, out):
    if not records:
        return
    tot = Counter()
    for r in records:
        for k in ('input_tokens', 'output_tokens', 'thinking_tokens'):
            tot[k] += (r.get('usage') or {}).get(k) or 0
    usd = sum((r.get('usage') or {}).get('cost_usd') or 0.0 for r in records)
    out(f"read now: {len(records)} letters | tokens in {tot['input_tokens']} out "
        f"{tot['output_tokens']} thinking {tot['thinking_tokens']} | measured US${usd:.4f} = "
        f"RM{usd_to_myr(usd):.4f} (RM {USD_TO_MYR} per US$) | per letter US${usd / len(records):.5f}")


# ── The estimate ─────────────────────────────────────────────────────────────────────────────
def capture_prompt():
    """The exact prompt + schema the offer read sends, captured through a fake client that
    answers nothing — no network, no meter row."""
    seen = []

    class _Capture:
        def __init__(self, *a, **k):
            self.models = self

        def generate_content(self, *, model, contents, config=None, **kw):
            seen.append((prompt_of(contents), getattr(config, 'response_schema', None)))
            raise RuntimeError('capture only')

    from apps.scholarship import vision
    from django.test.utils import override_settings
    png = _tiny_png()
    with override_settings(GEMINI_API_KEY='capture-only'), \
            guarded_production_read(_Capture, [], []) as extract:
        extract('', DOC_TYPE, image=png, content_type='image/png')
    prompt, schema = seen[0] if seen else ('', vision._FIELD_SCHEMAS.get(DOC_TYPE))
    return prompt, schema


def _tiny_png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (8, 8), 'white').save(buf, format='PNG')
    return buf.getvalue()


def estimate(eval_dir, keys, suffix=READERS['new']):
    """Counts and an estimated cost for `keys` read by this checkout's reader — no Gemini call,
    nothing written. Per letter: prompt + schema + its text layer at ~4 characters a token, and
    `image_tokens_estimate` per page image shown (high media resolution: the measured A4 page)."""
    from apps.scholarship import offer_reader
    prompt, schema = capture_prompt()
    text_tokens = math.ceil((len(prompt) + len(json.dumps(schema, default=str))) / 4)
    kinds, no_image, img_tokens, cached = Counter(), 0, [], 0
    for key in keys:
        if os.path.exists(fresh_path(eval_dir, key, suffix)):
            cached += 1
        path = letter_file(eval_dir, key)
        kinds[orc.input_kind(eval_dir, key) if path else 'no_file'] += 1
        if path is None:
            no_image += 1
            continue
        with open(path, 'rb') as fh:
            facts = image_facts(fh.read(), content_type_for(path))
        if not facts or not facts.get('width'):
            no_image += 1
            continue
        # 2.1.0: page 1 alone at high resolution; pages 2-3 (worst case: the later call is made) at the
        # default, plus that call's own prompt.
        later = facts['pages'][1:]
        img_tokens.append(image_tokens_estimate(1, 1, offer_reader.MEDIA_RESOLUTION)
                          + len(later) * IMAGE_TOKENS_MEASURED + (text_tokens if later else 0)
                          + math.ceil(facts['text_layer_chars'] / 4))
    n = len(img_tokens)
    est = {}
    for band, think in EST_THINKING.items():
        cost = sum(call_cost_usd(EST_MODEL, text_tokens + t, EST_OUTPUT, think)['total']
                   for t in img_tokens)
        est[band] = {'thinking_per_letter': think, 'usd': cost, 'myr': usd_to_myr(cost)}
    measured = [orc.read_json_file(fresh_path(eval_dir, k, suffix)) for k in orc.offer_keys(eval_dir)
                if os.path.exists(fresh_path(eval_dir, k, suffix))]
    per = [((m or {}).get('usage') or {}).get('cost_usd') or 0.0 for m in measured]
    return {
        'letters': len(keys), 'cached_already': cached, 'to_read': len(keys) - cached,
        'by_input_kind': dict(sorted(kinds.items())), 'no_image': no_image,
        'calls_estimated': n, 'prompt_text_tokens_est': text_tokens,
        'image_tokens_est_mean': (sum(img_tokens) / n) if n else 0,
        'image_tokens_est_max': max(img_tokens) if n else 0,
        'estimate': est, 'model': EST_MODEL, 'output_per_letter': EST_OUTPUT,
        'measured_letters': len(per),
        'measured_mean_usd_per_letter': (sum(per) / len(per)) if per else None,
    }


def print_estimate(e, out=print):
    out(f"DRY RUN - no Gemini call, nothing written | letters: {e['letters']} | cached already: "
        f"{e['cached_already']} | to read: {e['to_read']}")
    out('  by input kind: ' + '  '.join(f'{k} {v}' for k, v in e['by_input_kind'].items())
        + f"  | no image to show: {e['no_image']}")
    out(f"  per call (estimate): prompt+schema ~{e['prompt_text_tokens_est']} tokens, images + text "
        f"layer ~{e['image_tokens_est_mean']:.0f} tokens (max {e['image_tokens_est_max']}), output "
        f"{e['output_per_letter']}, model {e['model']}")
    for band, b in e['estimate'].items():
        out(f"  {band:<5} thinking {b['thinking_per_letter']:>5}/letter: US${b['usd']:.3f} = "
            f"RM{b['myr']:.3f}  (all {e['calls_estimated']} letters, RM {USD_TO_MYR} per US$)")
    if e['measured_letters']:
        m = e['measured_mean_usd_per_letter']
        out(f"  measured so far: {e['measured_letters']} letters, mean US${m:.5f}/letter -> "
            f"{e['to_read']} still to read ~ US${m * e['to_read']:.3f} = "
            f"RM{usd_to_myr(m * e['to_read']):.3f}; all {e['letters']} ~ US${m * e['letters']:.3f}"
            f" = RM{usd_to_myr(m * e['letters']):.3f}")


# ── Fresh vs stored, per field (counts only) ─────────────────────────────────────────────────
def compare(eval_dir, split='all', split_file=orc.SPLIT_PATH, reader='current'):
    """Per scored field: outcome counts of the STORED read and the fresh read(s), over the answered
    letters of the split that hold every compared cache — the same letters for all. `reader`
    'current': stored vs `fresh` (S3); 'new': stored vs `fresh` (S3) vs `s4`. fixed / broke count
    each read against the one before it."""
    names = COMPARE_READS[reader]
    suffixes = _COMPARE_SUFFIX
    keys = [k for k in select_keys(eval_dir, split=split, split_file=split_file)
            if all(os.path.exists(fresh_path(eval_dir, k, suffixes[n])) for n in names[1:])]
    heldout = orc.load_heldout(split_file)
    reads = {n: orc.letter_rows(eval_dir, keys, orc.stored_read if n == 'stored'
                                else orc.file_read(suffixes[n]), heldout) for n in names}
    fields = (*orc.CORE, *orc.NOT_CORE)
    result = {'split': split, 'letters': len(keys), 'fields': {}, 'fully_exact': {}, 'reads': names,
              'by_split': Counter(r['split'] for r in reads['stored'])}
    changed = Counter()
    per_key = {}
    for name, rows in reads.items():
        tally = {f: Counter() for f in fields}
        fe = 0
        for r in rows:
            if r['answer'] is None or r['problems']:
                continue
            o = orc.score_letter(r['answer'], r['read'], r['family'])
            per_key.setdefault(r['key'], {})[name] = o
            fe += orc.fully_exact(o)
            for f, v in o.items():
                tally[f][v] += 1
        result['fields'][name] = {f: {o: c[o] for o in orc.OUTCOMES} for f, c in tally.items()}
        result['fully_exact'][name] = fe
    for by_read in per_key.values():
        for before, after in zip(names, names[1:]):
            for f in fields:
                s, fr = by_read.get(before, {}).get(f), by_read.get(after, {}).get(f)
                if s is None and fr is None:
                    continue
                sr, frr = s in orc.RIGHT, fr in orc.RIGHT
                changed[(after, f, 'fixed' if frr and not sr else 'broke' if sr and not frr else 'same')] += 1
    result['changed_by_read'] = {a: {f: {k: changed[(a, f, k)] for k in ('fixed', 'broke', 'same')}
                                     for f in fields} for a in names[1:]}
    result['changed'] = result['changed_by_read'][names[-1]]
    result['by_split'] = dict(result['by_split'])
    return result


def print_compare(c, out=print):
    out(f"fresh vs stored | split: {c['split']} | answered letters with a fresh read: "
        f"{c['letters']} " + ' '.join(f'({k} {v})' for k, v in sorted(c['by_split'].items())))
    if not c['letters']:
        return
    names = c.get('reads') or ('stored', 'fresh')
    out('fully exact: ' + '  '.join(f"{n} {c['fully_exact'][n]}" for n in names))
    out(f"  {'field':<15}{'read':<8}" + ''.join(f'{o:>14}' for o in orc.OUTCOMES)
        + f"{'right':>7}{'fixed':>7}{'broke':>7}")
    for f in (*orc.CORE, *orc.NOT_CORE):
        for name in names:
            t = c['fields'][name][f]
            right = t['exact'] + t['blank_correct']
            ch = (c.get('changed_by_read') or {}).get(name, {}).get(f)
            tail = f"{ch['fixed']:>7}{ch['broke']:>7}" if ch else ''
            out(f'  {f:<15}{name:<8}' + ''.join(f'{t[o]:>14}' for o in orc.OUTCOMES)
                + f'{right:>7}' + tail)


def costs(eval_dir, keys, pair=('current', 'new')):
    """Per letter holding both caches: (key, ``pair[0]`` usage, ``pair[1]`` usage, pages, text chars)."""
    rows = []
    for k in keys:
        two = [orc.read_json_file(fresh_path(eval_dir, k, READERS[r])) for r in pair]
        if all(two):
            shown = two[1].get('offer_reader_inputs') or {}
            rows.append((k, two[0].get('usage') or {}, two[1].get('usage') or {},
                         shown.get('pages'), shown.get('text_layer_chars')))
    return rows


# ── Bootstrap (the script only — tests never call this) ─────────────────────────────────────
DEFAULT_ENV_FILE = os.path.join(os.path.dirname(_API_ROOT), '.env')


def main(argv=None, *, client_factory=None, out=print):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--eval-dir', default=orc.DEFAULT_EVAL_DIR)
    ap.add_argument('--split-file', default=orc.SPLIT_PATH)
    ap.add_argument('--split', choices=('heldout', 'dev', 'all'), default='all')
    ap.add_argument('--keys', default='', help='comma-separated keys (overrides --split)')
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--force', action='store_true', help='re-read letters already cached (PAID)')
    ap.add_argument('--dry-run', action='store_true', help='counts + estimated cost, no call')
    ap.add_argument('--compare', action='store_true', help='fresh vs stored per field (free)')
    ap.add_argument('--reader', choices=tuple(READERS), default='new',
                    help="new = this checkout's reader (S4, paid); current = S3's caches (read-only)")
    ap.add_argument('--costs', action='store_true', help='per-letter tokens + cost, --against vs new')
    ap.add_argument('--max-usd', type=float, default=None, help='stop once the run has cost this much')
    ap.add_argument('--suffix', default='', help="cache suffix override for a paid read (a pilot's own cache)")
    ap.add_argument('--against', choices=('current', 's4', 's4b', 's4c'), default='current',
                    help='--costs: the earlier reader to put beside the new one')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--env-file', default=DEFAULT_ENV_FILE)
    args = ap.parse_args(argv)
    if not orc.offer_keys(args.eval_dir):
        out(f'No offer letters in {args.eval_dir} - this measurement needs the local corpus.')
        return 2
    if args.compare:
        c = compare(args.eval_dir, args.split, args.split_file, args.reader)
        out(json.dumps(c, indent=1, sort_keys=True)) if args.json else print_compare(c, out)
        return 0
    keys = select_keys(args.eval_dir, split=args.split,
                       keys=[k.strip() for k in args.keys.split(',') if k.strip()],
                       limit=args.limit, split_file=args.split_file)
    if args.costs:
        print_costs(costs(args.eval_dir, keys, (args.against, 'new')), out, (args.against, 'new'))
        return 0
    if args.dry_run:
        e = estimate(args.eval_dir, keys, READERS[args.reader])
        out(json.dumps(e, indent=1, sort_keys=True)) if args.json else print_estimate(e, out)
        return 0
    if args.reader not in PAID_READERS:
        out(f"--reader {args.reader} is S3's cache only: this checkout cannot run that reader.")
        return 2
    if client_factory is None:
        from google import genai
        client_factory = genai.Client
    from django.conf import settings
    if not getattr(settings, 'GEMINI_API_KEY', ''):
        out('GEMINI_API_KEY is not set - nothing read.')
        return 2
    code, _ = read_letters(args.eval_dir, keys, client_factory=client_factory, force=args.force, out=out,
                           suffix=args.suffix or READERS[args.reader], max_usd=args.max_usd)
    return code


if __name__ == '__main__':
    _argv = sys.argv[1:]
    if not any(a in _argv for a in ('--compare', '--costs', '--dry-run')):
        load_gemini_key(next((_argv[i + 1] for i, a in enumerate(_argv[:-1]) if a == '--env-file'),
                             DEFAULT_ENV_FILE))
    bootstrap_django()
    sys.exit(main(_argv))
