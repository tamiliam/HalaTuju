"""Offer letters read exactly — the scorer (offer exact-read S1, 2026-11-01).

A HAND-RUN measurement, never a test: it reads the gitignored offer corpus
(`fixtures/offer_letters_2026-11-01/`: real PII, README.md) and prints the exact-read score of a
READ against hand-written correct answers. The committed tests use synthetic twins
(`tests/test_offer_read_scorer.py`). It prints keys, field names and counts — NEVER a value.

THE ANSWER FILE — `<eval-dir>/snapshots/<key>.offer_expect.json`, one per letter (gitignored PII).
Every key below must be present; a field the letter does not print is JSON `null`, explicitly:

  candidate_name          the offered student's name, as printed
  candidate_nric          their IC, as printed
  institution_as_printed  the institution's NAME only, as printed (owner 2026-11-01: the
                          institution and the campus are TWO fields)
  institution_campus      the campus / branch, as printed, or null. One printed line holding both
                          ("UiTM KAMPUS KOTA KINABALU") is split: "UiTM" + "KAMPUS KOTA KINABALU"
  programme               the programme / course title, as printed; PISMP: the degree title
                          ("Ijazah Sarjana Muda Perguruan"), as for any university (owner 2026-11-01)
  stream                  STPM "Bidang" or matriculation "Jurusan" (null for other families)
  specialisation          PISMP "Bidang Pengkhususan" (null for other families)
  intake                  the session / intake, as printed WITH its label (owner 2026-11-01:
                          "Sesi 1-2026/2027", "Ambilan 2026"); the scorer drops the label
  reporting_date          the report / registration date (a range: its first day)
  offer_date              the date the letter was issued (not the print date)
  issuer                  the body that issued the letter
  duration                study duration, as printed  — written, never scored (decision D3)
  fees                    fees, as printed            — written, never scored (decision D3)
  is_offer_letter         yes | conditional | portal_page | not_offer | unsure
  pages                   int, the number of pages in the file
  unsure_fields           list of the field names above the labeller is not sure of
  labeller_note           short, or null — no personal data beyond the fields
  family                  OPTIONAL — one of FAMILIES; when absent/null the family is derived from
                          the stored read (`authenticity.doc_seen`, UiTM by its name)

THE SCORE. Core fields (decision D2): name, nric, institution, programme, intake, reporting_date.
`programme` is family-specific: STPM / matriculation → `stream` vs the read's `stream`; every
other family, PISMP included → `programme` vs the read's `programme` (owner 2026-11-01: PISMP's
programme is the degree title). `institution` is the answer's `institution_as_printed` (the name
only) vs the read's `institution`. offer_date, issuer, campus and specialisation are scored too
but are NOT core. `campus` is the answer's `institution_campus` vs the read's `campus`, on every
letter (a null campus read blank is blank_correct); today's reader has no `campus` field, so a
printed campus scores `missing` — the honest baseline. specialisation (vs the read's
`bidang_pengkhususan`) only on letters whose answer has one, and its % is over those letters.
Per field:

  exact          both present and equal after tidying
  blank_correct  the letter does not print it (answer null) and the read is blank
  missing        the letter prints it, the read is blank
  wrong          both present, not equal after tidying
  extra          the letter does not print it, the read has a value

A letter is FULLY EXACT when every core field is exact or blank_correct.

TIDYING (and nothing more — there is NO fuzzy matching: one letter different is `wrong`):
text → accents dropped, upper case, apostrophes removed, any other punctuation → a space, spaces
collapsed. NRIC → digits only. Dates → "D Mon YYYY" from DD/MM/YYYY (also - or .; a two-digit
year is 20YY), YYYY-MM-DD, or "D Month YYYY" with a Malay or English month, after dropping a
weekday, a time and anything in brackets; anything unparseable is compared as tidied text.
Intake (the answer keeps its label as printed; the scorer strips it only to compare) → tidied
text with the labels "Sesi / Sesi Akademik / Sesi Mula / Session / Academic Session / Ambilan /
Pengambilan / Intake" dropped from the START and from the END ("JUNE 2026 INTAKE" = "INTAKE JUNE
2026" = "JUNE 2026"; a label mid-line stays), then a leading "Tahun" dropped when a 4-digit year
follows, and Malay/English month names written as the English 3 letters. "Semester 1" /
"Semester Pertama" is content, not a label (a read that drops it is a real miss), and so is a
session number: "SESI I : 2026/2027" tidies to "I 2026 2027", not "2026 2027".
Institution and campus → ONE trailing bracketed acronym (2-12 letters/digits/&.-, e.g.
"(UniSZA)") dropped, then tidied text.

THE SPLIT. `offer_split.json` (committed, keys only; made by `offer_split.py`) lists the held-out
letters: drawn only from letters NOT in the old corpus whose stored read is the AI reader's
(`capture='ai'`) — the fixed-format reader's locks are covered by the stpm/matric/poly parse
checks and are not hand-labelled in S1. Every other key is dev.

THE KNOWN-FORMAT-AI COUNT. Printed whatever the split and whether or not answers exist: letters
whose family is a fixed format (STPM, matriculation, polytechnic) but whose stored read came
from the AI reader, by family, input kind and programme — likely cheap wins for S5.

THE READ. Default `stored`: the production read in `snapshots/<key>.json` (`vision_fields.fields`).
`--read file:<suffix>` reads `snapshots/<key><suffix>` instead (S3's fresh reads), a JSON with
`fields` (or `vision_fields.fields`) and optionally `capture`.

Usage:  python -I apps/scholarship/eval/offer_read_check.py [--split heldout|dev|all]
            [--eval-dir DIR] [--read stored|file:<suffix>] [--json]
"""
import argparse
import csv
import glob
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
from apps.scholarship.genuineness.bands import stored_authenticity   # the one reader (TD-293)

DEFAULT_EVAL_DIR = os.path.join(HERE, 'fixtures', 'offer_letters_2026-11-01')
SPLIT_PATH = os.path.join(HERE, 'offer_split.json')
ANSWER_SUFFIX = '.offer_expect.json'
OFFER_KEY_RE = re.compile(r'^(offer_letter__a\d+__d\d+)\.json$')

ANSWER_FIELDS = ('candidate_name', 'candidate_nric', 'institution_as_printed', 'institution_campus',
                 'programme', 'stream', 'specialisation', 'intake', 'reporting_date', 'offer_date',
                 'issuer', 'duration', 'fees', 'is_offer_letter', 'pages', 'unsure_fields',
                 'labeller_note')
IS_OFFER = ('yes', 'conditional', 'portal_page', 'not_offer', 'unsure')
FAMILIES = ('stpm', 'matriculation', 'polytechnic', 'pismp', 'uitm', 'other_university', 'tvet',
            'other')
#: The families the fixed-format reader (`offer_parse.parse_govt_offer`) handles.
KNOWN_FORMAT_FAMILIES = ('stpm', 'matriculation', 'polytechnic')
CORE = ('name', 'nric', 'institution', 'programme', 'intake', 'reporting_date')
#: Scored, not in "fully exact". `campus` on every letter; `specialisation` only where the
#: answer has one.
NOT_CORE = ('offer_date', 'issuer', 'campus', 'specialisation')
OUTCOMES = ('exact', 'blank_correct', 'missing', 'wrong', 'extra')
RIGHT = ('exact', 'blank_correct')

_DOC_SEEN_FAMILY = {'stpm': 'stpm', 'matriculation': 'matriculation', 'polytechnic': 'polytechnic',
                    'pismp': 'pismp', 'ua_offer': 'university'}
_UITM_RE = re.compile(r'\bUITM\b|\bUNIVERSITI TEKNOLOGI MARA\b')
_PHOTO_EXT = ('jpg', 'jpeg', 'png', 'heic', 'heif', 'webp')

# ── Tidying ──────────────────────────────────────────────────────────────────────────────────
_MONTHS = {
    'JANUARI': 'Jan', 'JANUARY': 'Jan', 'JAN': 'Jan', 'FEBRUARI': 'Feb', 'FEBRUARY': 'Feb',
    'FEB': 'Feb', 'MAC': 'Mar', 'MARCH': 'Mar', 'MAR': 'Mar', 'APRIL': 'Apr', 'APR': 'Apr',
    'MEI': 'May', 'MAY': 'May', 'JUN': 'Jun', 'JUNE': 'Jun', 'JULAI': 'Jul', 'JULY': 'Jul',
    'JUL': 'Jul', 'OGOS': 'Aug', 'OGO': 'Aug', 'AUGUST': 'Aug', 'AUG': 'Aug', 'SEPTEMBER': 'Sep',
    'SEPT': 'Sep', 'SEP': 'Sep', 'OKTOBER': 'Oct', 'OCTOBER': 'Oct', 'OKT': 'Oct', 'OCT': 'Oct',
    'NOVEMBER': 'Nov', 'NOV': 'Nov', 'DISEMBER': 'Dec', 'DECEMBER': 'Dec', 'DIS': 'Dec',
    'DEC': 'Dec',
}
_MONTH_BY_NUM = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
_MONTH_RE = re.compile(r'\b(' + '|'.join(sorted(_MONTHS, key=len, reverse=True)) + r')\b')
_WEEKDAY_RE = re.compile(r'\b(ISNIN|SELASA|RABU|KHAMIS|JUMAAT|SABTU|AHAD|MON(?:DAY)?|TUE(?:SDAY)?|'
                         r'WED(?:NESDAY)?|THU(?:RSDAY)?|FRI(?:DAY)?|SAT(?:URDAY)?|SUN(?:DAY)?)\b')
_TIME_RE = re.compile(r'\d{1,2}\s*[.:]\s*\d{2}\s*(?:PAGI|PETANG|TENGAH HARI|MALAM|AM|PM)?')
#: An intake label (on tidied text). Longest first, so "SESI MULA" is not read as "SESI".
_INTAKE_LABEL = (r'(?:SESI AKADEMIK|SESI MULA|SESI|ACADEMIC SESSION|SESSION|PENGAMBILAN|AMBILAN|'
                 r'INTAKE)')
#: Labels at the START ("INTAKE JUNE 2026", "SESI PENGAMBILAN 2026") and at the END ("JUNE 2026
#: INTAKE"); each needs a value beside it, so a bare "INTAKE" stays.
_INTAKE_LABEL_RE = re.compile(r'^(?:' + _INTAKE_LABEL + r'\s+)+')
_INTAKE_TRAILING_LABEL_RE = re.compile(r'(?:\s+' + _INTAKE_LABEL + r')+$')
_INTAKE_TAHUN_RE = re.compile(r'^TAHUN\s+(?=\d{4}\b)')
#: ONE trailing "(ACRONYM)" after some text: 2-12 letters/digits/&.- inside the brackets.
_TRAILING_ACRONYM_RE = re.compile(r'^(.*\S)\s*\([A-Z0-9&.\-]{2,12}\)\s*$', re.IGNORECASE | re.DOTALL)


def tidy_text(value):
    """Accents dropped, upper case, apostrophes removed, other punctuation → space, collapsed."""
    if value is None:
        return ''
    s = unicodedata.normalize('NFKD', str(value))
    s = ''.join(c for c in s if not unicodedata.combining(c)).upper()
    s = re.sub(r"['’‘`]", '', s)
    return re.sub(r'[^A-Z0-9]+', ' ', s).strip()


def tidy_nric(value):
    return re.sub(r'\D', '', str(value or ''))


def _numeric_date(up):
    m = re.search(r'\b(20\d{2})\s*-\s*(\d{1,2})\s*-\s*(\d{1,2})\b', up)          # YYYY-MM-DD
    if m:
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    else:
        m = re.search(r'\b(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4}|\d{2})\b', up)
        if not m:
            return None
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        y = y if len(y) == 4 else '20' + y
    if 1 <= mo <= 12 and 1 <= d <= 31:
        return f'{d} {_MONTH_BY_NUM[mo - 1]} {y}'
    return None


def tidy_date(value):
    """A date → 'D Mon YYYY'; an unparseable value → its tidied text."""
    up = unicodedata.normalize('NFKD', str(value or '')).upper()
    numeric = _numeric_date(up)
    if numeric:
        return numeric
    cleaned = re.sub(r'\([^)]*\)', ' ', up)
    cleaned = _WEEKDAY_RE.sub(' ', _TIME_RE.sub(' ', cleaned))
    month, year = _MONTH_RE.search(cleaned), re.search(r'\b(20\d{2})\b', cleaned)
    day = next((int(g.group(1)) for g in re.finditer(r'\b(\d{1,2})(?:ST|ND|RD|TH|HB)?\b', cleaned)
                if 1 <= int(g.group(1)) <= 31), None)
    if month and year and day:
        return f'{day} {_MONTHS[month.group(1)]} {year.group(1)}'
    return tidy_text(value)


def tidy_intake(value):
    """Labels dropped at the start and the end (never mid-line), then a "Tahun" before a year,
    months one way. "SEMESTER 1" and a session number ("SESI I : 2026/2027" → "I 2026 2027")
    stay: they are content."""
    s = _INTAKE_TRAILING_LABEL_RE.sub('', _INTAKE_LABEL_RE.sub('', tidy_text(value)))
    s = _INTAKE_TAHUN_RE.sub('', s)
    return _MONTH_RE.sub(lambda m: _MONTHS[m.group(1)].upper(), s)


def tidy_institution(value):
    """ONE trailing bracketed acronym dropped ("Universiti X (UniSZA)" = "Universiti X"), then
    `tidy_text`. A bracket anywhere else in the line stays."""
    if value is None:
        return ''
    m = _TRAILING_ACRONYM_RE.match(str(value))
    return tidy_text(m.group(1) if m else value)


# ── Family, input kind, the read ────────────────────────────────────────────────────────────
def offer_family(stored_vf, answer=None):
    """The letter's family: the answer's `family` when it names one, else from the stored read."""
    if answer and answer.get('family') in FAMILIES:
        return answer['family']
    stored_vf = stored_vf or {}
    seen = str(stored_authenticity(stored_vf).get('doc_seen') or '')
    fam = _DOC_SEEN_FAMILY.get(seen) or ('tvet' if seen.startswith('tvet') else 'other')
    if fam != 'university':
        return fam
    fields = stored_vf.get('fields') or {}
    blob = tidy_text(f"{fields.get('institution') or ''} {fields.get('issuer') or ''}")
    return 'uitm' if _UITM_RE.search(blob) else 'other_university'


def input_kind(eval_dir, key):
    """pdf | photo | unknown — from the letter file's extension."""
    hits = sorted(glob.glob(os.path.join(eval_dir, 'fixtures', 'offer_letter', key + '.*')))
    if not hits:
        return 'unknown'
    ext = os.path.splitext(hits[0])[1].lstrip('.').lower()
    return 'pdf' if ext == 'pdf' else ('photo' if ext in _PHOTO_EXT else 'unknown')


def read_json_file(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def stored_vision_fields(eval_dir, key):
    return ((read_json_file(os.path.join(eval_dir, 'snapshots', key + '.json')) or {})
            .get('vision_fields') or {})


def stored_read(eval_dir, key):
    """(fields, capture) of the production read stored in the snapshot."""
    vf = stored_vision_fields(eval_dir, key)
    return vf.get('fields') or {}, str(vf.get('capture') or 'none')


def file_read(suffix):
    """A read source from `snapshots/<key><suffix>` (S3's fresh reads, or any other reader)."""
    def _read(eval_dir, key):
        data = read_json_file(os.path.join(eval_dir, 'snapshots', key + suffix)) or {}
        fields = data.get('fields') or (data.get('vision_fields') or {}).get('fields') or {}
        return fields, str(data.get('capture') or 'file')
    return _read


def read_source(spec):
    if spec == 'stored':
        return stored_read
    if spec.startswith('file:') and len(spec) > len('file:'):
        return file_read(spec[len('file:'):])
    raise ValueError("--read is 'stored' or 'file:<suffix>'")


# ── Scoring ──────────────────────────────────────────────────────────────────────────────────
def _pairs(answer, read, family):
    """{scored field: (answer value, read value, tidy)}. `specialisation` only when the answer
    has one (owner 2026-11-01: PISMP's programme is the degree title, its Bidang is scored apart)."""
    if family in ('stpm', 'matriculation'):
        prog = (answer.get('stream'), read.get('stream'))
    else:
        prog = (answer.get('programme'), read.get('programme'))
    spec = {}
    if answer.get('specialisation') is not None:
        spec = {'specialisation': (answer['specialisation'], read.get('bidang_pengkhususan'),
                                   tidy_text)}
    return {
        'name': (answer.get('candidate_name'), read.get('candidate_name'), tidy_text),
        'nric': (answer.get('candidate_nric'), read.get('candidate_nric'), tidy_nric),
        'institution': (answer.get('institution_as_printed'), read.get('institution'),
                        tidy_institution),
        'campus': (answer.get('institution_campus'), read.get('campus'), tidy_institution),
        'programme': (*prog, tidy_text),
        'intake': (answer.get('intake'), read.get('intake'), tidy_intake),
        'reporting_date': (answer.get('reporting_date'), read.get('reporting_date'), tidy_date),
        'offer_date': (answer.get('offer_date'), read.get('offer_date'), tidy_date),
        'issuer': (answer.get('issuer'), read.get('issuer'), tidy_text),
        **spec,
    }


def field_outcome(expected, got, tidy):
    """One of OUTCOMES. `expected` None = the letter does not print it."""
    want, have = ('' if expected is None else tidy(expected)), tidy(got)
    if not want:
        return 'blank_correct' if not have else 'extra'
    if not have:
        return 'missing'
    return 'exact' if want == have else 'wrong'


def score_letter(answer, read, family):
    """{field: outcome} for every core and not-core field (`specialisation` only when the
    answer has one)."""
    return {f: field_outcome(e, g, t) for f, (e, g, t) in _pairs(answer, read or {}, family).items()}


def fully_exact(outcomes):
    return all(outcomes[f] in RIGHT for f in CORE)


def answer_problems(answer):
    """Field NAMES wrong in an answer file's format (empty = fine)."""
    if not isinstance(answer, dict):
        return ['not_an_object']
    bad = [f'absent:{f}' for f in ANSWER_FIELDS if f not in answer]
    if answer.get('is_offer_letter') not in IS_OFFER:
        bad.append('is_offer_letter')
    pages = answer.get('pages')
    if not (isinstance(pages, int) and not isinstance(pages, bool) and pages >= 1):
        bad.append('pages')
    unsure = answer.get('unsure_fields')
    if not (isinstance(unsure, list) and all(u in ANSWER_FIELDS for u in unsure)):
        bad.append('unsure_fields')
    if answer.get('family') not in (None, *FAMILIES):
        bad.append('family')
    return sorted(set(bad))


# ── The corpus ───────────────────────────────────────────────────────────────────────────────
def offer_keys(eval_dir):
    """Every letter key: snapshots `<key>.json` plus any key that only has an answer."""
    snap = os.path.join(eval_dir, 'snapshots')
    names = sorted(os.listdir(snap)) if os.path.isdir(snap) else []
    out = {m.group(1) for n in names for m in [OFFER_KEY_RE.match(n)] if m}
    out |= {n[:-len(ANSWER_SUFFIX)] for n in names if n.endswith(ANSWER_SUFFIX)}
    return sorted(out)


def programme_by_key(eval_dir):
    path = os.path.join(eval_dir, 'programme_by_key.csv')
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8', newline='') as fh:
        return {r['key']: (r.get('programme') or 'unknown') for r in csv.DictReader(fh)}


def load_heldout(split_path=SPLIT_PATH):
    data = read_json_file(split_path) or {}
    return set(data.get('heldout') or [])


def _read_answer(eval_dir, key):
    """(answer or None, format problems). A file that is not JSON is a problem, not a crash."""
    try:
        answer = read_json_file(os.path.join(eval_dir, 'snapshots', key + ANSWER_SUFFIX))
    except ValueError:
        return {}, ['not_json']
    return answer, (answer_problems(answer) if answer is not None else [])


def letter_rows(eval_dir, keys, read_fn, heldout=()):
    """Per key: the facts the report groups by, the answer (or None) and its format problems."""
    programmes = programme_by_key(eval_dir)
    rows = []
    for key in keys:
        stored_vf = stored_vision_fields(eval_dir, key)
        answer, problems = _read_answer(eval_dir, key)
        read, capture = read_fn(eval_dir, key)
        rows.append({
            'key': key, 'answer': answer, 'problems': problems,
            'family': offer_family(stored_vf, answer if isinstance(answer, dict) else None),
            'input_kind': input_kind(eval_dir, key),
            'capture': capture, 'stored_capture': str(stored_vf.get('capture') or 'none'),
            'programme': programmes.get(key, 'unknown'), 'read': read,
            'split': 'heldout' if key in heldout else 'dev',
        })
    return rows


def rows_in_split(rows, split):
    return list(rows) if split == 'all' else [r for r in rows if r['split'] == split]


def known_format_ai_counts(rows):
    """Letters of a known fixed format whose STORED read came from the AI reader — likely cheap
    S5 wins (the format is known, the exact parser did not lock). Counts only."""
    hit = [r for r in rows if r['family'] in KNOWN_FORMAT_FAMILIES and r['stored_capture'] == 'ai']
    return {
        'total': len(hit),
        'by_family': dict(sorted(Counter(r['family'] for r in hit).items())),
        'by_input_kind': dict(sorted(Counter(r['input_kind'] for r in hit).items())),
        'by_programme': dict(sorted(Counter(r['programme'] for r in hit).items())),
    }


def _tally(scored):
    per_field = {f: Counter() for f in (*CORE, *NOT_CORE)}
    for r in scored:
        for f, o in r['outcomes'].items():
            per_field[f][o] += 1
    return {
        'letters': len(scored), 'fully_exact': sum(1 for r in scored if r['fully_exact']),
        'fields': {f: {o: c[o] for o in OUTCOMES} for f, c in per_field.items()},
    }


def summarise(all_rows, split):
    """The whole report as a dict of keys, field names and counts (no value ever). The
    known-format-AI count is over the WHOLE corpus; everything else over the split."""
    rows = rows_in_split(all_rows, split)
    bad = [r for r in rows if r['problems']]
    scored = []
    for r in rows:
        if r['answer'] is None or r['problems']:
            continue
        outcomes = score_letter(r['answer'], r['read'], r['family'])
        scored.append({**r, 'outcomes': outcomes, 'fully_exact': fully_exact(outcomes)})
    groups = {}
    for dim in ('family', 'input_kind', 'capture', 'programme', 'split', 'is_offer_letter'):
        buckets = defaultdict(list)
        for r in scored:
            buckets[r['answer'].get('is_offer_letter') if dim == 'is_offer_letter'
                    else r[dim]].append(r)
        groups[dim] = {g: _tally(v) for g, v in sorted(buckets.items(), key=lambda kv: str(kv[0]))}
    unsure = Counter(u for r in scored for u in (r['answer'].get('unsure_fields') or []))
    return {
        'split': split, 'letters': len(rows),
        'with_answers': sum(1 for r in rows if r['answer'] is not None),
        'format_problems': {r['key']: r['problems'] for r in sorted(bad, key=lambda x: x['key'])},
        'total': _tally(scored), 'groups': groups,
        'unsure': {'answers': sum(1 for r in scored if r['answer'].get('unsure_fields')),
                   'fields': dict(sorted(unsure.items()))},
        'letters_not_exact': {r['key']: sorted(f for f in CORE if r['outcomes'][f] not in RIGHT)
                              for r in sorted(scored, key=lambda x: x['key'])
                              if not r['fully_exact']},
        'known_format_ai': known_format_ai_counts(all_rows),
    }


# ── Printing ─────────────────────────────────────────────────────────────────────────────────
def _pct(n, d):
    return f'{100.0 * n / d:.1f}%' if d else '-'


def _print_fields(tally, fields):
    """`right` is over the letters the field was scored on (`of`): every letter, except
    `specialisation` (only letters whose answer has one)."""
    print(f"  {'field':<15}" + ''.join(f'{o:>14}' for o in OUTCOMES) + f"{'right':>9}{'of':>6}")
    for f in fields:
        c = tally['fields'][f]
        right, scored = c['exact'] + c['blank_correct'], sum(c.values())
        print(f'  {f:<15}' + ''.join(f'{c[o]:>14}' for o in OUTCOMES)
              + f"{_pct(right, scored):>9}{scored:>6}")


def _print_groups(dim, groups):
    print(f'\nby {dim}  (per core field: right/missing/wrong/extra)')
    print(f"  {'group':<24}{'letters':>8}{'fully exact':>14}  " + '  '.join(CORE))
    for g, t in groups.items():
        cells = []
        for f in CORE:
            c = t['fields'][f]
            cells.append(f"{c['exact'] + c['blank_correct']}/{c['missing']}/{c['wrong']}/{c['extra']}")
        fe = f"{t['fully_exact']} ({_pct(t['fully_exact'], t['letters'])})"
        print(f'  {str(g):<24}{t["letters"]:>8}{fe:>14}  ' + '  '.join(cells))


def _print_known_format_ai(kfa):
    print(f"\nknown format (STPM / matriculation / polytechnic) but the stored read is the AI "
          f"reader's - whole corpus, every split: {kfa['total']}")
    for label in ('by_family', 'by_input_kind', 'by_programme'):
        print(f"  {label:<14}" + '  '.join(f'{k} {v}' for k, v in kfa[label].items()))


def print_report(s, read_spec, eval_dir):
    print(f"Offer letters - exact read | read: {read_spec} | split: {s['split']}")
    print(f"letters in split: {s['letters']} | with answers: {s['with_answers']} | "
          f"answer format problems: {len(s['format_problems'])}")
    for key, probs in s['format_problems'].items():
        print(f'  FORMAT {key:<34} {",".join(probs)}')
    _print_known_format_ai(s['known_format_ai'])
    t = s['total']
    if not t['letters']:
        print(f"\n{t['letters']} letters with answers - nothing to score. Answers are "
              f"<key>{ANSWER_SUFFIX} in {os.path.join(eval_dir, 'snapshots')}.")
        return
    print(f"\nFULLY EXACT (every core field exact or blank_correct): {t['fully_exact']} of "
          f"{t['letters']} ({_pct(t['fully_exact'], t['letters'])})")
    print('\ncore fields')
    _print_fields(t, CORE)
    print('\nnot core (scored, not in fully exact)')
    _print_fields(t, NOT_CORE)
    for dim, groups in s['groups'].items():
        _print_groups(dim, groups)
    print(f"\nanswers with unsure fields: {s['unsure']['answers']}  "
          + '  '.join(f'{k} {v}' for k, v in s['unsure']['fields'].items()))
    print('\nletters not fully exact (core fields not right):')
    for key, fields in s['letters_not_exact'].items():
        print(f'  {key:<34} {",".join(fields)}')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--split', choices=('heldout', 'dev', 'all'), default='heldout')
    ap.add_argument('--eval-dir', default=DEFAULT_EVAL_DIR)
    ap.add_argument('--split-file', default=SPLIT_PATH)
    ap.add_argument('--read', default='stored', help="'stored' or 'file:<suffix>'")
    ap.add_argument('--json', action='store_true', help='the summary as JSON (counts only)')
    args = ap.parse_args(argv)
    read_fn = read_source(args.read)
    all_keys = offer_keys(args.eval_dir)
    if not all_keys:
        print(f'No offer letters in {args.eval_dir} - this measurement needs the local corpus.')
        return 2
    rows = letter_rows(args.eval_dir, all_keys, read_fn, load_heldout(args.split_file))
    summary = summarise(rows, args.split)
    if args.json:
        print(json.dumps(summary, indent=1, sort_keys=True))
    else:
        print_report(summary, args.read, args.eval_dir)
    return 1 if summary['format_problems'] else 0


if __name__ == '__main__':
    sys.exit(main())
