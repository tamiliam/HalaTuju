"""The SPM results-slip AI read: 3.8 Flash only, every answer checked, one retry (OCR-first S5).

The slip is read deterministically first (`field_extraction._read_results_slip`); this is the AI
fallback when neither the certificate parser nor the word-box read locks. Until S5 that fallback
stayed on 2.5 Flash, because in the paid eval 3.8 Flash wrote malformed grades on 26 of 98 slips
("Aplus", stray JSON, tab and CJK characters). SPM grades feed eligibility, so the rule here is:

  * the model list is an ALLOW-list: only "gemini-3.8-flash" (or a numbered / preview name of it,
    never a Lite, image, TTS or other variant) may read a slip
    (`slip_read_models`) — a 2.5 (or any other) model is never called for a slip, and an empty
    list refuses the read (a service error, 'review_manually') rather than fall back;
  * the schema asks for a closed grade enum with every key required (`schemas.py`), and every
    answer is still CHECKED here: each grade must clean (`sanitize.clean_slip_grade`) to one of
    the academic engine's grades, each subject / band must carry no stray characters, a row's
    Malay band (its band field, or band words glued to the subject) may not say a different grade
    from its letter, a subject may not name a grade (a band word or a lone letter anywhere in it)
    other than its letter, one subject may not carry two different grades, and at least one row must
    show a grade or band. Only the known keys are kept (name, exam, results, warnings; subject,
    grade, band per row);
  * a malformed answer, or an answer the model could not produce (DOCUMENT_FAILED), is asked ONCE
    more on 3.8; a service failure (our side — rate limit, outage) is not retried here;
  * still malformed after the retry → a failed read (DOCUMENT_FAILED, stored 'unreadable', the
    same verdict as any unparseable answer). A wrong grade is never stored; a refusal is safe.
"""

import re

from ..gemini import cascade_failure, document_failure
from ..read_errors import DOCUMENT_FAILED
from .sanitize import (_drop_expected_warnings, _sanitize_extracted_fields, clean_slip_grade,
                       clean_slip_text)

DOC_TYPE = 'results_slip'
#: The reason stored with a slip answer that failed the check (the retry's too).
MALFORMED_SLIP = 'MALFORMED_SLIP_ANSWER'
#: How many times the slip is asked in all: the first read and at most one retry.
MAX_CALLS = 2
#: The ONLY model that may read a slip (an allow-list: a new or renamed model is refused until it
#: is named here, never let through because it is not "2.5").
SLIP_MODEL = 'gemini-3.8-flash'
#: The keys kept from a model answer; anything else the model adds is dropped.
_TOP_KEYS = ('candidate_name', 'exam', 'results', 'warnings')
_ROW_KEYS = ('subject', 'grade', 'band')


#: Review round 3: the whole lowercased name must be 3.8 Flash itself, a numbered version
#: ("-001") or a preview, optionally dated ("-preview-11-2026"). Anything else after "flash"
#: ("-lite", "-8b", "-image", "-tts", "-thinking-exp", "-preview-tts") is a different model.
#: Review round 4 (LOW-4): a dated preview is month-day ("-05-20") or month-year ("-11-2026")
#: exactly, as Gemini names them; a three-digit tail or month 13 is not a 3.8 Flash name.
_SLIP_MODEL_RE = re.compile(r'gemini-3\.8-flash(?:-[0-9]{3}|-preview'
                            r'(?:-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01]|20[0-9]{2}))?)?')


def is_slip_model(model) -> bool:
    """True only for 3.8 Flash itself, a numbered version or a (dated) preview of it, matched on
    the lowercased name as a whole (`_SLIP_MODEL_RE`). Review round 2 refused prefix look-alikes
    ("gemini-3.80", "gemini-3.81-pro", "gemini-3.8"); round 3 also refuses every other variant
    ("-LITE", "-8b", "-image", "-tts", "-thinking-exp")."""
    return isinstance(model, str) and _SLIP_MODEL_RE.fullmatch(model.lower()) is not None


def slip_read_models() -> list:
    """The slip read's models: the models of `profile_engine.MODEL_CASCADE` on the allow-list
    (today `['gemini-3.8-flash']`). Read live, so the AI registry shows what the read uses."""
    from ..profile_engine import MODEL_CASCADE
    return [m for m in MODEL_CASCADE if is_slip_model(m)]


def check_slip_answer(data):
    """One parsed slip answer → ``(cleaned, problems)``. ``cleaned`` is the answer with every
    grade, subject and band in its plain spelling and only the known keys (None when the answer
    is unusable); ``problems`` lists what was wrong, empty for a good answer. An answer with no
    rows, or no grade or band on any row, is a bad answer: a results slip always shows a table."""
    # Review round 2: the duplicate check keys a row exactly as the typed-vs-slip comparison does
    # (`read_slip`'s band-word split, then `academic_compare._compare_key`, which folds the English
    # names onto the Malay ones), so any two rows the comparison would merge are checked here.
    from ..academic_compare import _compare_key
    from ..academic_engine import _band_to_grade, _split_band
    if not isinstance(data, dict):
        return None, ['the answer is not an object']
    results = data.get('results')
    if not isinstance(results, list):
        return None, ['no results list']
    problems, rows, seen, implied_of = [], [], {}, {}
    for i, row in enumerate(results, start=1):
        if not isinstance(row, dict) or 'subject' not in row or 'grade' not in row:
            problems.append(f'row {i}: not a subject / grade pair')
            continue
        subject, band = clean_slip_text(row.get('subject')), _clean_band(row.get('band'))
        grade = clean_slip_grade(row.get('grade'))
        if subject is None or band is None:
            problems.append(f'row {i}: stray characters')
        if grade is None:
            problems.append(f'row {i}: grade outside the SPM grade set')
        if subject is None or band is None or grade is None:
            continue
        if not (subject or grade or band):
            continue                               # a blank row: nothing read, nothing claimed
        if not subject:
            problems.append(f'row {i}: a grade with no subject')
            continue
        # Review round 3: the Malay band says the grade a second time, and `read_slip` lets the
        # band WIN over the letter. So a band (the band field, or band words glued to the subject)
        # that says a different grade from the row's letter is a bad answer, never a stored grade.
        stem, glued = _split_band(subject)
        said = {g for g in (_band_to_grade(band), glued) if g}
        if len(said) > 1 or (grade and said and grade not in said):
            problems.append(f'row {i}: the band says a different grade from the letter')
            continue
        # Review round 4: a band word or a lone grade INSIDE the subject ("SEJARAH C", "SEJARAH
        # KEPUJIAN (ELEKTIF)") is a grade the trailing-band split never sees; one that is not the
        # row's letter (or a row with no letter) is a bad answer, never a stored grade.
        if _grades_named_in(stem) - {grade}:
            problems.append(f'row {i}: the subject names a grade the letter does not say')
            continue
        implied = _band_to_grade(band) or glued    # `read_slip`'s own order: band field, then glued
        key = _compare_key(stem)
        if key in seen:
            first = seen[key]
            if not _same_reading(first, implied_of[key], grade, band, implied):
                problems.append(f'row {i}: the same subject as an earlier row with a different grade')
            elif band and not first['band']:
                first['band'] = band               # the duplicate carries the band the first lacked
                implied_of[key] = implied_of[key] or implied
            continue
        seen[key], implied_of[key] = {'subject': subject, 'grade': grade, 'band': band}, implied
        rows.append(seen[key])
    if not problems and not any(r['grade'] or r['band'] for r in rows):
        problems.append('no grade or band read on any row')
    for key in ('candidate_name', 'exam'):
        if data.get(key) is not None and not isinstance(data.get(key), str):
            problems.append(f'{key} is not text')
    if problems:
        return None, problems
    cleaned = {k: data[k] for k in _TOP_KEYS if k in data}
    return {**cleaned, 'results': rows}, []


def _clean_band(raw):
    """A band cell as `clean_slip_text` gives it, except the schema's blank word (`SLIP_BLANK`,
    any case or spacing) is '' (short-check LOW-1): "BLANK" is no band, so a slip whose rows say
    only that is not a good read."""
    from .schemas import SLIP_BLANK
    band = clean_slip_text(raw)
    return '' if band and ''.join(band.split()).upper() == SLIP_BLANK else band


#: Review round 4: the subject text is cut into words at spaces and the punctuation a slip row
#: prints round a cell ("SEJARAH (C)", "SEJARAH, C"). Not at a hyphen: it is the minus of "A-",
#: and "AL-QURAN" stays one word.
_SUBJECT_WORDS = re.compile(r'[\s(),;:/|]+')
#: Short-check LOW-2: the piece of a word after its last hyphen or dot ("SEJARAH-A", "SEJARAH.A",
#: "SEJARAH-A-" keeps its minus). A grade-shaped piece there is a grade glued to the subject;
#: "AL-QURAN", "E-DAGANG" and "B. MELAYU" leave a piece that is not.
_GLUED_TAIL = re.compile(r'[-.]([^-.]*-?)$')
#: A word shaped like a grade that is not an SPM grade ("C-", "B-", "F"): it still names a grade,
#: so it is refused, never read past.
_GRADE_SHAPED = re.compile(r'[A-G][+-]?|TH[+-]', re.IGNORECASE)
#: What `_grades_named_in` gives for a grade-shaped word outside the SPM set: never a row's letter.
_NOT_A_GRADE = '?'


def _grades_named_in(text) -> set:
    """The grades a subject text names anywhere in it: a band word ("KEPUJIAN", "CEMERLANG
    TINGGI", "TIDAK HADIR", modifier optional), a lone grade word ("C", "A+", "Aplus", cleaned by
    `clean_slip_grade`), or a grade-shaped word outside the SPM set (`_NOT_A_GRADE`). The trailing
    band `_split_band` strips is not here; this catches what it leaves INSIDE the subject. Empty for
    a real subject name."""
    from ..academic_engine import _BAND_HEADS, _BAND_MODS, _BAND_TO_GRADE
    words = [w for w in _SUBJECT_WORDS.split(text or '') if w and w != '-']
    out = set()
    for i, word in enumerate(words):
        low, nxt = word.lower(), (words[i + 1].lower() if i + 1 < len(words) else '')
        if low in _BAND_HEADS:
            out.add(_BAND_TO_GRADE[f'{low} {nxt}' if nxt in _BAND_MODS else low])
        elif low == 'tidak' and nxt == 'hadir':
            out.add('TH')
        elif clean_slip_grade(word):
            out.add(clean_slip_grade(word))
        elif _GRADE_SHAPED.fullmatch(word):
            out.add(_NOT_A_GRADE)
        elif (tail := _GLUED_TAIL.search(word)) and tail.group(1):
            piece = tail.group(1)
            if clean_slip_grade(piece):
                out.add(clean_slip_grade(piece))
            elif _GRADE_SHAPED.fullmatch(piece):
                out.add(_NOT_A_GRADE)
    return out


def _same_reading(row, row_implied, grade, band, implied) -> bool:
    """A repeated subject row agrees with the earlier ``row`` (whose band implies ``row_implied``):
    the same letter, and EITHER the bands imply the same grade (with two non-blank band fields the
    same ignoring case and spacing, review round 2) OR one row has no band at all and the other's
    band implies the kept letter (review round 3). A band that implies a different grade is never
    filled in from a duplicate; a different letter, or two different bands, is a real conflict."""
    if row['grade'] != grade:
        return False
    a, b = (' '.join(x.upper().split()) for x in (row['band'], band))
    if row_implied == implied:
        return not a or not b or a == b
    no_band_first, no_band_second = not a and not row_implied, not b and not implied
    return bool(grade) and ((no_band_first and implied == grade) or (no_band_second and row_implied == grade))


def read_slip_checked(call, models=None) -> dict:
    """Run the slip read through ``call(models)`` (one `_call_gemini_json` answer) and return
    ``{fields, warnings, error}`` as `extract_document_fields` does, plus ``slip_calls`` (1 or 2)
    on a good read. At most `MAX_CALLS` calls, every one on ``models`` (default
    `slip_read_models()`), only ever a model on the allow-list."""
    models = list(slip_read_models() if models is None else models)
    if not models or not all(is_slip_model(m) for m in models):
        return {'fields': {}, 'warnings': [], 'error': cascade_failure(
            [('slip read', f'no {SLIP_MODEL} model to read the slip with; no other model '
                           'is used for a slip')])}
    failures = []
    for attempt in range(1, MAX_CALLS + 1):
        data = call(models)
        if isinstance(data, dict) and '_error' in data:
            err = str(data['_error'] or '')
            if not err.startswith(DOCUMENT_FAILED):
                return {'fields': {}, 'warnings': [], 'error': err}   # our side: no retry here
            failures.append(f'try {attempt}: ' + _without_model(err[len(DOCUMENT_FAILED):].lstrip(': '),
                                                                 models)[:200])
            continue
        cleaned, problems = check_slip_answer(data)
        if cleaned is None:
            failures.append(f'try {attempt}: {MALFORMED_SLIP}: ' + '; '.join(problems[:5]))
            continue
        warnings = _drop_expected_warnings(DOC_TYPE, cleaned.pop('warnings', []) or [])
        fields = _sanitize_extracted_fields(DOC_TYPE, cleaned)
        return {'fields': fields, 'warnings': warnings, 'error': '', 'slip_calls': attempt}
    # One entry, so the stored error names the model ONCE ("…: gemini-3.8-flash: try 1: …; try 2: …").
    return {'fields': {}, 'warnings': [], 'error': document_failure([(models[0], '; '.join(failures))])}


def _without_model(msg, models):
    """A seam error already names its model ("gemini-3.8-flash: UNPARSEABLE…"): drop that name."""
    for m in models:
        if msg.startswith(f'{m}: '):
            return msg[len(m) + 2:]
    return msg
