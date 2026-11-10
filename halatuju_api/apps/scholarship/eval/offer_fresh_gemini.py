"""The guarded production Gemini read and its cost, for `offer_fresh_read.py` (offer exact-read S3).

Split out of `offer_fresh_read.py` (the file-size rule); that module's docstring is the full
description. Here:
  * the PRICE table and the cost arithmetic (input / output / thinking priced separately);
  * a RECORDING wrapper around `google.genai.Client`: every `generate_content` call's model,
    `model_version`, `usage_metadata` (input, output, thinking, total, input by modality) and
    cost; a 402 / 429 raises `StopRun` (a BaseException, so the production cascade cannot catch
    it and fall through to the next model);
  * `guarded_production_read`: the patches for one run — the wrapped client, the usage meter
    replaced by a recorder (no `UsageEvent` row), Storage and every database query refused.
"""
import contextlib
import hashlib
import json
import os
import re
from collections import Counter
from unittest import mock

USD_TO_MYR = 4.4
PRICE_SOURCE = 'https://ai.google.dev/gemini-api/docs/pricing (paid tier, standard; read 2026-11-01)'
#: US$ per 1,000,000 tokens. Thinking is billed as output ("Output price (including thinking tokens)").
PRICES = {
    'gemini-2.5-flash': {'input': 0.30, 'output': 2.50, 'thinking': 2.50},
    'gemini-2.5-flash-lite': {'input': 0.10, 'output': 0.40, 'thinking': 0.40},
}
STOP_CODES = (402, 429)
#: MEASURED 2026-11-01 (S3 pilot, 10 letters, images 540x1204 up to 2114x2992 px, photos and
#: PDF page renders): gemini-2.5-flash reported IMAGE = 258 prompt tokens for EVERY image — one
#: tile, whatever the size (the documented tiling rule does not apply to this call's default
#: media resolution). The estimate uses the measurement, not the documented rule.
IMAGE_TOKENS_MEASURED = 258
#: MEASURED 2026-11-01 (S4 probe, one SYNTHETIC 1654x2339 A4 page, gemini-2.5-flash): IMAGE = 258
#: tokens at the default and at MEDIA_RESOLUTION_MEDIUM, 3,354 at MEDIA_RESOLUTION_HIGH (the S4
#: reader's setting — "pan and scan"). The S4 estimate uses this per page image shown.
IMAGE_TOKENS_HIGH_A4 = 3354


class StopRun(BaseException):
    """A 402 / 429. A BaseException on purpose: `_call_gemini_json` catches `Exception` to walk
    its cascade, and this must NOT be caught there — the whole run stops at once."""

    def __init__(self, model, code, message):
        super().__init__(f'{model}: {code}')
        self.model, self.code, self.message = model, code, message


class DatabaseRefused(BaseException):
    """Raised by the run's database guard on ANY query (never expected)."""


# ── Cost ─────────────────────────────────────────────────────────────────────────────────────
def price_for(model):
    """The price row for a model name ('models/' prefix and a version suffix tolerated): the
    exact PRICES key, else the longest one the name starts with. None when unknown."""
    name = str(model or '').split('/')[-1]
    if name in PRICES:
        return PRICES[name]
    hits = [k for k in PRICES if name.startswith(k + '-')]
    return PRICES[max(hits, key=len)] if hits else None


def call_cost_usd(model, input_tokens, output_tokens, thinking_tokens):
    """{input, output, thinking, total} in US$, or None for a model with no price."""
    p = price_for(model)
    if p is None:
        return None
    parts = {'input': (input_tokens or 0) * p['input'] / 1e6,
             'output': (output_tokens or 0) * p['output'] / 1e6,
             'thinking': (thinking_tokens or 0) * p['thinking'] / 1e6}
    parts['total'] = parts['input'] + parts['output'] + parts['thinking']
    return parts


def usd_to_myr(usd):
    return usd * USD_TO_MYR


def print_costs(rows, out=print, names=('current', 'new')):
    t = ('input_tokens', 'output_tokens', 'thinking_tokens')
    out(f"{'key':<30}{'pages':>6}{'text':>6} | {names[0]} in/out/think US$  | {names[1]} in/out/think US$")
    tot = [Counter(), Counter()]
    for k, cur, new, pages, text in rows:
        cells = []
        for i, u in enumerate((cur, new)):
            cells.append('/'.join(str(u.get(x) or 0) for x in t) + f" {u.get('cost_usd') or 0:.5f}")
            for x in (*t, 'cost_usd'):
                tot[i][x] += u.get(x) or 0
        out(f'{k:<30}{pages or 0:>6}{text or 0:>6} | {cells[0]:<26}| {cells[1]}')
    n = len(rows)
    for name, c in zip(names, tot if n else ()):
        out(f"{name}: {n} letters, mean in {c['input_tokens'] / n:.0f} out {c['output_tokens'] / n:.0f} "
            f"think {c['thinking_tokens'] / n:.0f}, US${c['cost_usd'] / n:.5f}/letter "
            f"(RM{usd_to_myr(c['cost_usd'] / n):.4f}); total US${c['cost_usd']:.4f}")


def image_tokens_estimate(width, height, media_resolution=None):
    """Image prompt tokens for --dry-run, per image: the measured 258 (see above), or the measured
    A4 page at high media resolution when the read asks for it (S4)."""
    return IMAGE_TOKENS_HIGH_A4 if media_resolution == 'MEDIA_RESOLUTION_HIGH' else IMAGE_TOKENS_MEASURED


# ── The recording Gemini client ──────────────────────────────────────────────────────────────
def error_code(exc):
    """The HTTP status of a provider error: `.code` / `.status_code`, else a 402/429 or
    RESOURCE_EXHAUSTED named in the message. None when unknown."""
    for attr in ('code', 'status_code'):
        v = getattr(exc, attr, None)
        if isinstance(v, int) and not isinstance(v, bool):
            return v
    msg = str(exc)
    m = re.search(r'\b(402|429)\b', msg)
    if m:
        return int(m.group(1))
    return 429 if 'RESOURCE_EXHAUSTED' in msg else None


def _token_count(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def usage_of(resp):
    """The token counts of a genai response (None where the API did not report one)."""
    md = getattr(resp, 'usage_metadata', None)
    out = {'input_tokens': None, 'output_tokens': None, 'thinking_tokens': None,
           'total_tokens': None, 'cached_tokens': None, 'input_by_modality': {}}
    if md is None:
        return out
    out.update(input_tokens=_token_count(getattr(md, 'prompt_token_count', None)),
               output_tokens=_token_count(getattr(md, 'candidates_token_count', None)),
               thinking_tokens=_token_count(getattr(md, 'thoughts_token_count', None)),
               total_tokens=_token_count(getattr(md, 'total_token_count', None)),
               cached_tokens=_token_count(getattr(md, 'cached_content_token_count', None)))
    for d in getattr(md, 'prompt_tokens_details', None) or []:
        modality = getattr(d, 'modality', None)
        name = str(getattr(modality, 'value', modality) or 'unknown')
        out['input_by_modality'][name] = _token_count(getattr(d, 'token_count', None))
    return out


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def package_sha(module):
    """One sha over every .py file of a package, in name order (the vision package is many files)."""
    h = hashlib.sha256()
    d = os.path.dirname(module.__file__)
    for name in sorted(n for n in os.listdir(d) if n.endswith(".py")):
        h.update(name.encode("utf-8"))
        with open(os.path.join(d, name), "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()


def prompt_of(contents):
    """The text part of a `generate_content` contents (a string, or [image part, prompt])."""
    if isinstance(contents, str):
        return contents
    return next((c for c in (contents or []) if isinstance(c, str)), '')


class _RecordingModels:
    def __init__(self, inner, calls):
        self._inner, self._calls = inner, calls

    def generate_content(self, *, model, contents, config=None, **kw):
        prompt = prompt_of(contents)
        res = getattr(config, 'media_resolution', None)
        rec = {'model': model, 'prompt_sha256': sha256_text(prompt), 'prompt_chars': len(prompt),
               'images': 0 if isinstance(contents, str) else sum(not isinstance(c, str) for c in contents or []),
               'media_resolution': (str(getattr(res, 'value', res)) if res is not None else None)}
        try:
            resp = self._inner.generate_content(model=model, contents=contents, config=config, **kw)
        except Exception as e:   # any provider error: recorded, then re-raised to the cascade
            code = error_code(e)
            rec.update(answered=False, error=type(e).__name__, code=code,
                       message=' '.join(str(e).split())[:300])
            self._calls.append(rec)
            if code in STOP_CODES:
                raise StopRun(model, code, rec['message']) from None
            raise
        rec.update(answered=True, model_version=getattr(resp, 'model_version', None),
                   **usage_of(resp))
        try:
            json.loads(resp.text)
            rec['json_ok'] = True
        except (TypeError, ValueError):
            rec['json_ok'] = False
        cost = call_cost_usd(model, rec['input_tokens'], rec['output_tokens'],
                             rec['thinking_tokens'])
        rec['cost_usd'] = cost['total'] if cost else None
        rec['cost_parts_usd'] = cost
        self._calls.append(rec)
        return resp


class _RecordingClient:
    def __init__(self, inner, calls):
        # Hold the real client: a genai.Client that is garbage-collected CLOSES its HTTP session,
        # and `.models` alone does not keep it alive ("the client has been closed").
        self._inner = inner
        self.models = _RecordingModels(inner.models, calls)


def _refuse_db(execute, sql, params, many, context):
    raise DatabaseRefused('offer_fresh_read: a database query was attempted and refused')


@contextlib.contextmanager
def guarded_production_read(client_factory, calls, meter):
    """Patches for ONE run: the genai client is wrapped (`calls` gets each call's record), the
    usage meter records into `meter` instead of the database, Storage and every database query
    raise. Yields the production `extract_document_fields`."""
    from django.db import connections
    from apps.scholarship import usage, vision

    def _client(*args, **kwargs):
        return _RecordingClient(client_factory(*args, **kwargs), calls)

    def _meter(service, **kw):
        meter.append({'service': service, 'model': kw.get('model', ''),
                      'input_tokens': kw.get('input_tokens'),
                      'output_tokens': kw.get('output_tokens')})

    def _no_storage(*a, **k):
        raise AssertionError('offer_fresh_read: Storage was reached')

    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch('google.genai.Client', _client))
        stack.enter_context(mock.patch.object(usage, 'record_usage', _meter))
        stack.enter_context(mock.patch.object(vision, '_fetch_image_bytes', _no_storage))
        for alias in connections:
            stack.enter_context(connections[alias].execute_wrapper(_refuse_db))
        yield vision.extract_document_fields


# ── Bootstrap for the script (moved from offer_fresh_read.py for the file-size rule) ─────────────
def load_gemini_key(env_file):
    """GEMINI_API_KEY from `env_file` into os.environ — never printed. True when found."""
    if os.environ.get('GEMINI_API_KEY'):
        return True
    if not os.path.exists(env_file):
        return False
    with open(env_file, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line.startswith('GEMINI_API_KEY='):
                os.environ['GEMINI_API_KEY'] = line.split('=', 1)[1].strip().strip('"').strip("'")
                return bool(os.environ['GEMINI_API_KEY'])
    return False


def bootstrap_django():
    """Development settings on a local SQLite (any DATABASE_URL / DB_HOST removed first) — and
    the run refuses every query anyway."""
    for name in ('DATABASE_URL', 'DB_HOST'):
        os.environ.pop(name, None)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'halatuju.settings.development'
    import django
    django.setup()
