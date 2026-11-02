"""Today's FREE offer readers replayed on the cached OCR text (offer exact-read S2, 2026-11-01).

A HAND-RUN measurement, never a test: it reads the gitignored offer corpus (README.md) and writes
one gitignored cache per letter, `snapshots/<key>.replay.json`. It makes NO paid call — no Vision,
no Gemini — and writes nothing anywhere else. It prints keys, field names and counts, never a value.
Committed tests: `tests/test_offer_replay.py` (synthetic twins).

THE TEXT production would feed the readers (`vision.ocr_document_full`): a digital PDF's text layer
(all pages — the cache `<key>.ocr.txt` of meta `path: text_layer`); otherwise Vision on PAGE 1 only
(`pages[0].text` of `<key>.ocr.words.json`, meta `path: vision`); an earlier capture (meta
`path: earlier_vision`) is already page 1 only. `capture_ocr.py --corpus` makes these caches.

THE READERS, exactly as `vision._run_field_extraction_impl` runs them on that text:
  * `offer_exact.exact_read(text, from_text_layer, page1_layer, profile_nric)` (S5: the ONE entry point) — a
    LOCK (STPM / matriculation / polytechnic, the offer title and every required field read, no
    guard tripped, the IC kept by `offer_ic.guard_nric` against the profile IC in `context.json`) or
    None (production then asks Gemini). A digital PDF's page-1 layer (from the corpus PDF) is the
    identity's text. A lock is MERGED over the stored read as a production re-run does
    (`offer_exact.merge_over`: the parser's own keys whole, the dates merge-preserve).
  * `genuineness.assess('offer_letter', ocr_text=text)` — only when the text is not blank (a blank
    read is OUR failure → no signal), stored in production's `authenticity` shape.

THE CACHE `<key>.replay.json` — loadable by the scorer with `--read file:.replay.json`:
  fields         a lock: the merged read; a fallback: the STORED read, standing in for the Gemini
                 read the replay does not make (`replay.fields_source` says which)
  capture        `deterministic` (a lock) | `ai_stand_in` (a fallback: the stored read) | `no_text`
  authenticity   production's shape, or null (blank text)
  replay         outcome (locked | fallback | no_text), text_route, text_chars, detected_family,
                 empty_required, guard, parser_fields (the parser's own read, or null),
                 fields_source, offer_parser_version, genuineness_model_version

THE FAMILY is the scorer's (`offer_read_check.offer_family`): the answer's `family` when an answer
names one, else from the stored read — so the known-format counts here match the scorer's.

THE KNOWN-FORMAT MISS REASON — for a letter whose family is a fixed format (STPM / matriculation /
polytechnic) that does not lock, one rule-based category (`miss_reason`):
  no_text           production's page has under 25 characters of text
  other             the text never names the family ("TINGKATAN ENAM" / "MATRIKULASI" /
                    "POLITEKNIK") — not the standard letter (a portal page, a slip, a scan of
                    something else)
  layout_variant    the family is named but the parser's issuer marker or the offer title is absent
                    (S5: a portal page / slip naming the family lands here); or the input is
                    a TEXT PDF (clean text) and a required field is empty or a guard tripped; or a
                    required field's anchor label is absent from the text (the letter is worded
                    differently)
  photo_ocr_noise   the input was read by Vision (photo / scanned PDF), the issuer was detected and
                    the failed field's anchor labels ARE in the text — the template matches, the
                    OCR'd values or their line order did not pair; or a guard tripped on Vision text
                    (guard `ic_guard`: the IC guard blanked the parser's IC, so it did not lock)

Usage:  python -I apps/scholarship/eval/offer_replay.py [--eval-dir DIR] [--write] [--json]
        (without --write it prints the counts and writes nothing)
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))      # halatuju_api/
if _API_ROOT not in sys.path:                  # run as a script with -I: reach the app package
    sys.path.insert(0, _API_ROOT)
from apps.scholarship import offer_parse
from apps.scholarship.offer_exact import exact_read, merge_over, page1_text_layer
from apps.scholarship.eval import offer_read_check as orc
from apps.scholarship.genuineness import assess
from apps.scholarship.genuineness.bands import stored_status
from apps.scholarship.genuineness.results_doc import MODEL_VERSION

REPLAY_SUFFIX = '.replay.json'
MIN_TEXT = 25
KNOWN = orc.KNOWN_FORMAT_FAMILIES
MISS_REASONS = ('no_text', 'photo_ocr_noise', 'layout_variant', 'other')
_FAMILY_WORD = {'stpm': r'TINGKATAN\s+ENAM', 'matriculation': r'MATRIKULASI',
                'polytechnic': r'POLITEKNIK'}
#: The label each required field is anchored on, per family (what `offer_parse` reads it from).
_ANCHORS = {
    'stpm': {'candidate_name': r'^\s*NAMA\b', 'candidate_nric': r'KAD\s*PENGENALAN|\d{6}[- ]?\d{2}',
             'intake': r'\bTAHUN\s+20\d{2}', 'programme': r'TINGKATAN\s+ENAM'},
    'matriculation': {'candidate_name': r'\b(?:BIN|BINTI|A\s*/\s*[LP])\b',
                      'candidate_nric': r'\bK\s*/\s*P\b|\d{6}[- ]?\d{2}', 'intake': r'\bSESI\b',
                      'programme': r'MATRIKULASI'},
    'polytechnic': {'candidate_name': r'\(\s*\d{6}', 'candidate_nric': r'\d{6}[- ]?\d{2}',
                    'intake': r'\bSESI', 'programme': r'^\s*PROGRAM\s*:?\s*$'},
}


# ── The text production reads ────────────────────────────────────────────────────────────────
def _read_cache(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return json.load(fh) if path.endswith('.json') else fh.read()


def production_text(snap, key):
    """(text, route): route is text_layer | vision | earlier_vision | none (no cache)."""
    meta = _read_cache(os.path.join(snap, key + '.ocr.meta.json')) or {}
    route = meta.get('path') or 'none'
    if route == 'vision':
        pages = (_read_cache(os.path.join(snap, key + '.ocr.words.json')) or {}).get('pages') or []
        return ((pages[0].get('text') or '') if pages else ''), route
    if route in ('text_layer', 'earlier_vision'):
        return _read_cache(os.path.join(snap, key + '.ocr.txt')) or '', route
    return '', 'none'


def input_kind3(eval_dir, key, route):
    """photo | scanned_pdf | text_pdf | unknown — the letter file plus how its text was read."""
    kind = orc.input_kind(eval_dir, key)
    if kind == 'pdf':
        return 'text_pdf' if route == 'text_layer' else 'scanned_pdf'
    return kind


# ── The readers ──────────────────────────────────────────────────────────────────────────────
def page1_of(eval_dir, key, route):
    """The page-1 text production hands the Exact read's identity (`offer_exact`): a digital PDF's
    page-1 layer, read from the corpus's own PDF (free); '' for a Vision read (its text IS page 1)."""
    if route != 'text_layer':
        return ''
    path = os.path.join(eval_dir, 'fixtures', 'offer_letter', key + '.pdf')
    if not os.path.exists(path):
        return ''
    with open(path, 'rb') as fh:
        return page1_text_layer(fh.read(), 'application/pdf')


def parser_diagnosis(text, route='vision', page1_layer='', profile_nric=''):
    """Why the Exact read locks or not — {detected, titled, empty_required, guard, locked, fields}.
    The parser's own walk (`offer_parse.diagnose`), then `offer_exact.exact_read` as production derives
    its inputs (a text-layer ``route`` reads the identity from ``page1_layer``): guard `no_page1_layer`
    when that page has none, `ic_guard` when the IC guard refuses the parser's IC. Never a copy of the rules."""
    from_layer = route == 'text_layer'
    d = offer_parse.diagnose(text, page1_layer if from_layer else None)
    ex = exact_read(text, from_text_layer=from_layer, page1_layer=page1_layer, profile_nric=profile_nric)
    guard = ('no_page1_layer' if from_layer and not (page1_layer or '').strip() and d['locked'] else
             d['guard'] or ('ic_guard' if d['locked'] and ex is None else None))
    return {'detected': d['family'], 'titled': d['titled'], 'empty_required': d['empty_required'],
            'guard': guard, 'locked': ex is not None, 'fields': ex['fields'] if ex else None}


def replay_letter(text, route, stored_fields, profile_nric='', page1_layer=''):
    """The replay record for one letter (see the module docstring)."""
    stored_fields = stored_fields if isinstance(stored_fields, dict) else {}
    usable = len((text or '').strip()) >= MIN_TEXT
    diag = (parser_diagnosis(text, route, page1_layer, profile_nric) if usable else
            {'detected': '', 'titled': False, 'empty_required': [], 'guard': None, 'locked': False,
             'fields': None})
    if diag['locked']:
        outcome, capture, source = 'locked', 'deterministic', 'parser_merged_over_stored'
        fields = merge_over(stored_fields, diag['fields'])
    else:
        outcome = 'fallback' if usable else 'no_text'
        capture = 'ai_stand_in' if usable else 'no_text'
        source, fields = 'stored_stand_in', dict(stored_fields)
    return {
        'fields': fields, 'capture': capture, 'authenticity': authenticity_of(text),
        'replay': {'outcome': outcome, 'text_route': route, 'text_chars': len(text or ''),
                   'detected_family': diag['detected'] or None, 'titled': diag['titled'],
                   'empty_required': diag['empty_required'], 'guard': diag['guard'],
                   'parser_fields': diag['fields'], 'fields_source': source,
                   'offer_parser_version': offer_parse.PARSER_VERSION,
                   'genuineness_model_version': MODEL_VERSION},
    }


def authenticity_of(text):
    """Production's stored `authenticity` for an offer (vision.py offer branch), or None."""
    if not (text or '').strip():
        return None
    auth = assess('offer_letter', ocr_text=text)
    if not (auth and auth.get('status')):
        return None
    status = 'suspect' if auth['status'] == 'unrecognised' else auth['status']
    out = {'status': status, 'reason': auth.get('reason', ''),
           'doc_seen': auth.get('type') or auth.get('doc_seen', '')}
    if 'probability' in auth:
        out.update({'probability': auth['probability'], 'present': auth['present'],
                    'missing': auth['missing'], 'model_version': auth.get('model_version')})
    return out


def miss_reason(family, text, record, kind):
    """One of MISS_REASONS for a known-format letter that did not lock (rules in the docstring)."""
    rp = record['replay']
    if rp['outcome'] == 'no_text':
        return 'no_text'
    up = (text or '').upper()
    if not re.search(_FAMILY_WORD.get(family, r'(?!)'), up):
        return 'other'
    if not rp['detected_family'] or not rp.get('titled', True):
        return 'layout_variant'
    if kind == 'text_pdf':
        return 'layout_variant'
    if rp['guard']:
        return 'photo_ocr_noise'
    anchors = _ANCHORS.get(rp['detected_family'], {})
    for field in rp['empty_required']:
        pat = anchors.get(field)
        if pat and not re.search(pat, up, re.MULTILINE):
            return 'layout_variant'
    return 'photo_ocr_noise'


# ── The run ──────────────────────────────────────────────────────────────────────────────────
def replay_corpus(eval_dir, write=False):
    """Per key: {key, family, kind, stored_capture, record, reason}. Writes the caches on `write`."""
    snap = os.path.join(eval_dir, 'snapshots')
    context = orc.read_json_file(os.path.join(eval_dir, 'context.json')) or {}
    out = []
    for key in orc.offer_keys(eval_dir):
        vf = orc.stored_vision_fields(eval_dir, key)
        text, route = production_text(snap, key)
        record = replay_letter(text, route, vf.get('fields'),
                               profile_nric=(context.get(key) or {}).get('profile_nric') or '',
                               page1_layer=page1_of(eval_dir, key, route))
        answer, problems = orc._read_answer(eval_dir, key)   # the family, as the scorer takes it
        family = orc.offer_family(vf, answer if isinstance(answer, dict) and not problems else None)
        kind = input_kind3(eval_dir, key, route)
        reason = (miss_reason(family, text, record, kind)
                  if family in KNOWN and record['replay']['outcome'] != 'locked' else None)
        if write:
            with open(os.path.join(snap, key + REPLAY_SUFFIX), 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=1, sort_keys=True)
        out.append({'key': key, 'family': family, 'kind': kind,
                    'stored_capture': str(vf.get('capture') or 'none'), 'record': record,
                    'reason': reason, 'stored_status': stored_status(vf) or 'unscored'})
    return out


def _by(rows, dim):
    table = {}
    for r in rows:
        table.setdefault(str(r[dim]), Counter())[r['record']['replay']['outcome']] += 1
    return {g: dict(sorted(c.items())) for g, c in sorted(table.items())}


def replay_summary(rows):
    """Counts only — never a value."""
    kfa = [r for r in rows if r['family'] in KNOWN and r['stored_capture'] == 'ai']
    kfa_locked = [r for r in kfa if r['record']['replay']['outcome'] == 'locked']
    status = Counter((r['stored_status'], (r['record']['authenticity'] or {}).get('status') or 'no_signal')
                     for r in rows)
    return {
        'letters': len(rows),
        'outcome': dict(sorted(Counter(r['record']['replay']['outcome'] for r in rows).items())),
        'by_family': _by(rows, 'family'), 'by_input_kind': _by(rows, 'kind'),
        'text_route': dict(sorted(Counter(r['record']['replay']['text_route'] for r in rows).items())),
        'stored_capture_vs_today': dict(sorted(Counter(
            f"{r['stored_capture']}->{r['record']['replay']['outcome']}" for r in rows).items())),
        'known_format_ai': {
            'total': len(kfa), 'lock_today': len(kfa_locked),
            'lock_today_by_family': dict(sorted(Counter(r['family'] for r in kfa_locked).items())),
            'not_locked_reason': dict(sorted(Counter(r['reason'] for r in kfa if r['reason']).items())),
            'not_locked_reason_by_family': {f: dict(sorted(Counter(
                r['reason'] for r in kfa if r['reason'] and r['family'] == f).items()))
                for f in KNOWN},
            'not_locked_reason_by_input_kind': {k: dict(sorted(Counter(
                r['reason'] for r in kfa if r['reason'] and r['kind'] == k).items()))
                for k in sorted({r['kind'] for r in kfa})},
        },
        'genuineness_stored_vs_today': {f'{a}->{b}': n for (a, b), n in sorted(status.items())},
        # Stored as an Exact read, but today's parser on today's text defers it — why.
        'stored_deterministic_not_locked': dict(sorted(Counter(
            f"{r['family']} {r['kind']}: " + (f"guard {r['record']['replay']['guard']}"
                                              if r['record']['replay']['guard'] else
                                              'empty ' + ','.join(r['record']['replay']['empty_required'])
                                              if r['record']['replay']['empty_required'] else
                                              r['record']['replay']['outcome'])
            for r in rows if r['stored_capture'] == 'deterministic'
            and r['record']['replay']['outcome'] != 'locked').items())),
    }


def print_summary(s, wrote):
    print(f"Offer letters - today's free readers replayed on the cached text | letters: {s['letters']}"
          f" | caches {'written' if wrote else 'NOT written (add --write)'}")
    print('outcome: ' + '  '.join(f'{k} {v}' for k, v in s['outcome'].items()))
    print('text route: ' + '  '.join(f'{k} {v}' for k, v in s['text_route'].items()))
    for label in ('by_family', 'by_input_kind'):
        print(f'\n{label}  (locked / fallback / no_text)')
        for g, c in s[label].items():
            print(f"  {g:<18} {c.get('locked', 0):>4} {c.get('fallback', 0):>9} {c.get('no_text', 0):>8}")
    print('\nstored capture -> today: ' + '  '.join(f'{k} {v}' for k, v in s['stored_capture_vs_today'].items()))
    k = s['known_format_ai']
    print(f"\nknown format, stored read by AI: {k['total']} | lock today: {k['lock_today']} "
          + ' '.join(f'({f} {n})' for f, n in k['lock_today_by_family'].items()))
    print('  not locked, by reason: ' + '  '.join(f'{r} {n}' for r, n in k['not_locked_reason'].items()))
    for f, c in k['not_locked_reason_by_family'].items():
        print(f'    {f:<15} ' + '  '.join(f'{r} {n}' for r, n in c.items()))
    for kd, c in k['not_locked_reason_by_input_kind'].items():
        print(f'    {kd:<15} ' + '  '.join(f'{r} {n}' for r, n in c.items()))
    print('\ngenuineness, stored -> today: '
          + '  '.join(f'{k} {v}' for k, v in s['genuineness_stored_vs_today'].items()))
    print('\nstored as an Exact read, today deferred to Gemini:')
    for k, v in s['stored_deterministic_not_locked'].items():
        print(f'  {v:>4}  {k}')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--eval-dir', default=orc.DEFAULT_EVAL_DIR)
    ap.add_argument('--write', action='store_true', help='write snapshots/<key>.replay.json')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    if not orc.offer_keys(args.eval_dir):
        print(f'No offer letters in {args.eval_dir} - this measurement needs the local corpus.')
        return 2
    s = replay_summary(replay_corpus(args.eval_dir, write=args.write))
    if args.json:
        print(json.dumps(s, indent=1, sort_keys=True))
    else:
        print_summary(s, args.write)
    return 0


if __name__ == '__main__':
    sys.exit(main())
