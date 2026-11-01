"""Offer letters — the FAILURE MAP (offer exact-read S2, 2026-11-01).

A HAND-RUN measurement, never a test: it reads the gitignored offer corpus (README.md) and prints,
for any split with answers, WHERE a read fails and WHAT KIND of failure it is. It prints keys,
field names and counts — NEVER a value. Committed tests: `tests/test_offer_failure_map.py`
(synthetic twins).

THE GRID — per core field (`offer_read_check.CORE`), wrong / missing / extra, in total and by:
family; pages (from the answer: 1 / 2 / 3+); input kind (photo / scanned_pdf / text_pdf — a PDF is
a text PDF when its OCR cache came from the text layer); the stored capture (ai / deterministic);
the stored reader version (`det <offer parser version>`, or `ai unversioned` — the AI read carries
none); the stored genuineness model version.

THE FAILURE KINDS — one kind per failing field (the first rule that matches, in this order), plus
two letter-level kinds. Rule-based; each rule reads only the answer, the read, the letter's page
count and its cached OCR page texts, and says what it checks:

  institution
    institution = reporting venue        the read names a venue word (DEWAN, BANGUNAN, KOMPLEKS,
                                         AUDITORIUM, DATARAN, STADIUM, GELANGGANG, PANGGUNG, ARAS,
                                         BILIK, KOLEJ KEDIAMAN, TEMPAT) the printed line lacks
    institution = issuer                 the read equals the answer's issuer (tidied)
    institution keeps part of the line   the read is a strict part of the printed line (tidied)
    institution adds to the line         the printed line is a strict part of the read
    institution names a campus / branch / college the line does not
                                         the read has KAMPUS / CAMPUS / CAWANGAN / BRANCH / KOLEJ /
                                         COLLEGE / PUSAT / CENTRE that the printed line lacks
    institution = the university, the line names a campus / college
                                         the read says UNIVERSITI / UNIVERSITY, the printed line not
  programme
    programme keeps a code               the read carries a code token (3+ characters mixing letters
                                         and digits, e.g. "UH6481001", "DKM1") the answer lacks
    programme = PISMP wrapper            PISMP family and the read says PISMP / PROGRAM where the
                                         answer (the degree title) does not
    programme keeps part / adds words    one is a strict part of the other (tidied)
  intake
    intake drops Semester                the answer says SEMESTER (or SEM), the read does not
    intake keeps only a year             the read is only a year or YYYY/YYYY; the answer has more
  reporting_date (missing or wrong)
    reporting date = offer date          the read's date equals the answer's offer date
    reporting date only on page 2+       the answer's date is in a page 2+ text, not in page 1
    reporting date on page 2+ (not captured)   multi-page letter, page 1 lacks the date and the
                                         later pages were never OCR'd (an earlier page-1 capture)
    reporting date on page 1             the answer's date is in page 1's text, the read missed it
    reporting date not in the OCR text   no captured page text holds the answer's date
  nric
    nric on page 1 / nric not in the OCR text   whether the answer's 12 digits are in page 1's text
  any other failure                      "<field> wrong" / "<field> missing" / "<field> extra"

  letter-level
    known format not locked              STPM / matriculation / polytechnic letter, not fully
                                         exact, that today's fixed-format reader does not lock
    real offer judged not genuine        answer yes / conditional, the read's genuineness is not
                                         `genuine` (an `unchecked` TVET issuer is no signal, skipped)
    not an offer judged genuine          answer portal_page / not_offer, the genuineness `genuine`

THE TAG — each failure is tagged against today's free readers (`snapshots/<key>.replay.json`,
made by `offer_replay.py --write`):
  old read      today's fixed-format reader locks the letter and gets the field right (or today's
                genuineness now agrees with the answer) — a re-read fixes it
  today too     today's fixed-format reader locks and still fails it (or today's genuineness still
                disagrees) — a reader fix is needed
  ai, S3        today the letter still goes to Gemini — whether today's prompt repeats it is S3's
  untagged      no replay cache for the letter

Usage:  python -I apps/scholarship/eval/offer_failure_map.py [--split dev|heldout|all]
            [--eval-dir DIR] [--read stored|file:<suffix>] [--keys] [--json]
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))      # halatuju_api/
if _API_ROOT not in sys.path:                  # run as a script with -I: reach the app package
    sys.path.insert(0, _API_ROOT)
from apps.scholarship.eval import offer_read_check as orc
from apps.scholarship.eval import offer_replay
from apps.scholarship.genuineness.bands import stored_authenticity, stored_status

FAIL = ('wrong', 'missing', 'extra')
TAGS = ('old read', 'today too', 'ai, S3', 'untagged')
_VENUE_RE = re.compile(r'\b(DEWAN|BANGUNAN|KOMPLEKS|AUDITORIUM|DATARAN|STADIUM|GELANGGANG|PANGGUNG|'
                       r'ARAS|BILIK|KOLEJ KEDIAMAN|TEMPAT)\b')
_PLACE_RE = re.compile(r'\b(KAMPUS|CAMPUS|CAWANGAN|BRANCH|KOLEJ|COLLEGE|PUSAT|CENTRE|CENTER)\b')
_UNI_RE = re.compile(r'\b(UNIVERSITI|UNIVERSITY)\b')
#: A code token: 3+ characters mixing letters and digits ("UH6481001", "DKM1", "CB123").
_CODE_RE = re.compile(r'\b(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)[A-Z0-9]{3,}\b')
_YEAR_ONLY_RE = re.compile(r'^(20\d{2})(\s+20\d{2})?$')
_MON = r'(?:' + '|'.join(sorted(orc._MONTHS, key=len, reverse=True)) + r')'
_DATE_IN_TEXT = (
    re.compile(r'\b\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*(?:\d{4}|\d{2})\b'),
    re.compile(r'\b20\d{2}\s*-\s*\d{1,2}\s*-\s*\d{1,2}\b'),
    re.compile(r'\b\d{1,2}(?:HB|ST|ND|RD|TH)?\s*(?:-|HINGGA|HINGGALAH|DAN|&|TO|UNTIL)?\s*(?:\d{1,2}\s*)?'
               + _MON + r'\s*,?\s*20\d{2}\b'),
)


# ── Facts about a letter ─────────────────────────────────────────────────────────────────────
def pages_bucket(pages):
    if not isinstance(pages, int) or pages < 1:
        return 'unknown'
    return '3+' if pages >= 3 else str(pages)


def page_texts(eval_dir, key):
    """(texts per page in order, complete). `complete` is False when only page 1 was captured."""
    snap = os.path.join(eval_dir, 'snapshots')
    meta = offer_replay._read_cache(os.path.join(snap, key + '.ocr.meta.json')) or {}
    route = meta.get('path')
    if route == 'vision':
        pages = (offer_replay._read_cache(os.path.join(snap, key + '.ocr.words.json')) or {}).get('pages') or []
        return [p.get('text') or '' for p in pages], True
    if route == 'earlier_vision':
        return [offer_replay._read_cache(os.path.join(snap, key + '.ocr.txt')) or ''], False
    if route == 'text_layer':
        import glob
        hits = sorted(glob.glob(os.path.join(eval_dir, 'fixtures', 'offer_letter', key + '.*')))
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            return [(p.extract_text() or '') for p in PdfReader(hits[0]).pages], True
        except (PyPdfError, OSError, ValueError, KeyError, IndexError, TypeError):
            return [], False   # a broken file (or none) has no page texts
    return [], False


def dates_in(text):
    """Every date in a text, as `tidy_date` writes it (a range: its first day)."""
    up = unicodedata.normalize('NFKD', text or '').upper()
    return {orc.tidy_date(m.group(0)) for rx in _DATE_IN_TEXT for m in rx.finditer(up)}


def stored_versions(stored_vf):
    fields = stored_vf.get('fields') or {}
    capture = str(stored_vf.get('capture') or 'none')
    reader = (f"det {fields.get('_offer_parser_version') or 'unversioned'}" if capture == 'deterministic'
              else f'{capture} unversioned')
    gen = str(stored_authenticity(stored_vf).get('model_version') or 'none')
    return reader, gen


# ── Failure kinds ────────────────────────────────────────────────────────────────────────────
def field_kind(field, outcome, answer, read, family, pages=None, texts=(), complete=True):
    """The failure kind for one failing core field (rules in the module docstring)."""
    pairs = orc._pairs(answer, read or {}, family)
    want_raw, got_raw, tidy = pairs[field]
    want, got = tidy(want_raw) if want_raw is not None else '', tidy(got_raw)
    if outcome == 'extra':
        return f'{field} extra'
    if field == 'institution' and outcome == 'wrong':
        if _VENUE_RE.search(got) and not _VENUE_RE.search(want):
            return 'institution = reporting venue'
        if answer.get('issuer') and got == orc.tidy_text(answer['issuer']):
            return 'institution = issuer'
        if f' {got} ' in f' {want} ':
            return 'institution keeps part of the line'
        if f' {want} ' in f' {got} ':
            return 'institution adds to the line'
        if set(_PLACE_RE.findall(got)) - set(_PLACE_RE.findall(want)):
            return 'institution names a campus / branch / college the line does not'
        if _UNI_RE.search(got) and not _UNI_RE.search(want):
            return 'institution = the university, the line names a campus / college'
    if field == 'programme' and outcome == 'wrong':
        if set(_CODE_RE.findall(got)) - set(_CODE_RE.findall(want)):
            return 'programme keeps a code'
        if family == 'pismp' and re.search(r'\b(PISMP|PROGRAM)\b', got) and not re.search(
                r'\b(PISMP|PROGRAM)\b', want):
            return 'programme = PISMP wrapper'
        if f' {got} ' in f' {want} ':
            return 'programme keeps part of the title'
        if f' {want} ' in f' {got} ':
            return 'programme adds words'
    if field == 'intake' and outcome == 'wrong':
        if re.search(r'\bSEM(ESTER)?\b', orc.tidy_text(want_raw)) and not re.search(
                r'\bSEM(ESTER)?\b', orc.tidy_text(got_raw)):
            return 'intake drops Semester'
        if _YEAR_ONLY_RE.match(got) and not _YEAR_ONLY_RE.match(want):
            return 'intake keeps only a year'
    if field == 'reporting_date':
        if outcome == 'wrong' and answer.get('offer_date') and got == orc.tidy_date(answer['offer_date']):
            return 'reporting date = offer date'
        on_p1 = bool(texts) and want in dates_in(texts[0])
        later = any(want in dates_in(t) for t in texts[1:])
        if not on_p1 and later:
            return 'reporting date only on page 2+'
        if not on_p1 and not complete and isinstance(pages, int) and pages >= 2:
            return 'reporting date on page 2+ (not captured)'
        if on_p1:
            return f'reporting date on page 1 ({outcome})'
        return f'reporting date not in the OCR text ({outcome})'
    if field == 'nric' and outcome in ('wrong', 'missing'):
        digits = orc.tidy_nric(want_raw)
        p1 = re.sub(r'\D', '', texts[0]) if texts else ''
        return f"nric {'on page 1' if digits and digits in p1 else 'not in the page-1 OCR text'} ({outcome})"
    return f'{field} {outcome}'


def genuineness_kind(answer, status):
    """'real offer judged not genuine' / 'not an offer judged genuine' / None."""
    said = answer.get('is_offer_letter')
    if said in ('yes', 'conditional') and status not in ('genuine', 'unchecked'):
        return 'real offer judged not genuine'
    if said in ('portal_page', 'not_offer') and status == 'genuine':
        return 'not an offer judged genuine'
    return None


def field_tag(field, answer, family, replay):
    """TAGS[...] for one failing field, against today's replay (module docstring)."""
    if not replay:
        return 'untagged'
    if (replay.get('replay') or {}).get('outcome') != 'locked':
        return 'ai, S3'
    outcome = orc.score_letter(answer, replay.get('fields') or {}, family)[field]
    return 'old read' if outcome in orc.RIGHT else 'today too'


def genuineness_tag(answer, replay):
    if not replay:
        return 'untagged'
    today = stored_status(replay) or 'no_signal'
    return 'today too' if genuineness_kind(answer, today) else 'old read'


# ── The run ──────────────────────────────────────────────────────────────────────────────────
def _read_auth(eval_dir, key, spec):
    if spec == 'stored':
        return stored_status(orc.stored_vision_fields(eval_dir, key))
    data = orc.read_json_file(os.path.join(eval_dir, 'snapshots', key + spec[len('file:'):])) or {}
    return stored_status(data) or stored_status(data.get('vision_fields'))


def failure_map(eval_dir, split, read_spec='stored', split_file=orc.SPLIT_PATH):
    """{grid, kinds, letters} — keys, field names and counts only."""
    rows = orc.letter_rows(eval_dir, orc.offer_keys(eval_dir), orc.read_source(read_spec),
                           orc.load_heldout(split_file))
    rows = [r for r in orc.rows_in_split(rows, split) if r['answer'] is not None and not r['problems']]
    dims = ('family', 'pages', 'input_kind', 'stored_capture', 'stored_reader_version',
            'stored_genuineness_version')
    grid = {'total': {f: Counter() for f in orc.CORE}}
    by = {d: defaultdict(lambda: {f: Counter() for f in orc.CORE}) for d in dims}
    letters_in = {d: Counter() for d in dims}
    kinds = defaultdict(lambda: {'count': 0, 'tags': Counter(), 'keys': []})
    for r in rows:
        key, answer, family = r['key'], r['answer'], r['family']
        snap = os.path.join(eval_dir, 'snapshots')
        replay = orc.read_json_file(os.path.join(snap, key + offer_replay.REPLAY_SUFFIX))
        stored_vf = orc.stored_vision_fields(eval_dir, key)
        reader_v, gen_v = stored_versions(stored_vf)
        _text, route = offer_replay.production_text(snap, key)
        facts = {'family': family, 'pages': pages_bucket(answer.get('pages')),
                 'input_kind': offer_replay.input_kind3(eval_dir, key, route),
                 'stored_capture': r['stored_capture'], 'stored_reader_version': reader_v,
                 'stored_genuineness_version': gen_v}
        outcomes = orc.score_letter(answer, r['read'], family)
        texts, complete = page_texts(eval_dir, key)
        for d in dims:
            letters_in[d][facts[d]] += 1
        for f in orc.CORE:
            o = outcomes[f]
            if o not in FAIL:
                continue
            grid['total'][f][o] += 1
            for d in dims:
                by[d][facts[d]][f][o] += 1
            kind = field_kind(f, o, answer, r['read'], family, answer.get('pages'), texts, complete)
            k = kinds[kind]
            k['count'] += 1
            k['tags'][field_tag(f, answer, family, replay)] += 1
            k['keys'].append(key)
        locked_today = ((replay or {}).get('replay') or {}).get('outcome') == 'locked'
        if family in orc.KNOWN_FORMAT_FAMILIES and not orc.fully_exact(outcomes) and not locked_today:
            k = kinds['known format not locked']
            k['count'] += 1
            k['tags']['today too' if replay else 'untagged'] += 1
            k['keys'].append(key)
        gk = genuineness_kind(answer, _read_auth(eval_dir, key, read_spec) or 'no_signal')
        if gk:
            k = kinds[gk]
            k['count'] += 1
            k['tags'][genuineness_tag(answer, replay)] += 1
            k['keys'].append(key)
    ranked = sorted(kinds.items(), key=lambda kv: (-kv[1]['count'], kv[0]))
    return {
        'split': split, 'read': read_spec, 'letters': len(rows),
        'grid': {f: {o: grid['total'][f][o] for o in FAIL} for f in orc.CORE},
        'by': {d: {str(g): {'letters': letters_in[d][g],
                            **{f: {o: c[f][o] for o in FAIL} for f in orc.CORE}}
                   for g, c in sorted(by[d].items(), key=lambda kv: str(kv[0]))}
               for d in dims},
        'letters_by': {d: dict(sorted((str(g), n) for g, n in letters_in[d].items())) for d in dims},
        'kinds': [{'kind': name, 'count': v['count'], 'tags': {t: v['tags'][t] for t in TAGS if v['tags'][t]},
                   'keys': sorted(v['keys'])} for name, v in ranked],
    }


# ── Printing ─────────────────────────────────────────────────────────────────────────────────
def print_map(m, show_keys=False):
    print(f"Offer letters - failure map | read: {m['read']} | split: {m['split']} | "
          f"letters with answers: {m['letters']}")
    print('\nper core field (wrong / missing / extra)')
    for f, c in m['grid'].items():
        print(f"  {f:<16}{c['wrong']:>6}{c['missing']:>8}{c['extra']:>7}")
    for d, groups in m['by'].items():
        print(f'\nby {d}  (letters, then per core field w/m/x; groups with no failure are omitted)')
        print(f"  {'group':<28}{'letters':>8}  " + '  '.join(orc.CORE))
        for g, c in groups.items():
            cells = [f"{c[f]['wrong']}/{c[f]['missing']}/{c[f]['extra']}" for f in orc.CORE]
            print(f"  {g:<28}{c['letters']:>8}  " + '  '.join(cells))
        print('  letters per group: ' + '  '.join(f'{g} {n}' for g, n in m['letters_by'][d].items()))
    print('\nfailure kinds, ranked  (count | tagged against today\'s free readers)')
    for k in m['kinds']:
        tags = ', '.join(f'{t} {n}' for t, n in k['tags'].items())
        print(f"  {k['count']:>4}  {k['kind']:<66} {tags}")
        if show_keys:
            print('        ' + ' '.join(k['keys']))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--split', choices=('heldout', 'dev', 'all'), default='dev')
    ap.add_argument('--eval-dir', default=orc.DEFAULT_EVAL_DIR)
    ap.add_argument('--split-file', default=orc.SPLIT_PATH)
    ap.add_argument('--read', default='stored', help="'stored' or 'file:<suffix>'")
    ap.add_argument('--keys', action='store_true', help='list the letter keys under each kind')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    orc.read_source(args.read)   # validates the spec
    if not orc.offer_keys(args.eval_dir):
        print(f'No offer letters in {args.eval_dir} - this measurement needs the local corpus.')
        return 2
    m = failure_map(args.eval_dir, args.split, args.read, args.split_file)
    if args.json:
        print(json.dumps(m, indent=1, sort_keys=True))
    else:
        print_map(m, args.keys)
    return 0


if __name__ == '__main__':
    sys.exit(main())
