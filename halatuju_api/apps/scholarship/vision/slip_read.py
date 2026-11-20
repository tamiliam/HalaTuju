"""The SPM results-slip AI read: 3.8 Flash only, every answer checked, one retry (OCR-first S5).

The slip is read deterministically first (`field_extraction._read_results_slip`); this is the AI
fallback when neither the certificate parser nor the word-box read locks. Until S5 that fallback
stayed on 2.5 Flash, because in the paid eval 3.8 Flash wrote malformed grades on 26 of 98 slips
("Aplus", stray JSON, tab and CJK characters). SPM grades feed eligibility, so the rule here is:

  * the model list is an ALLOW-list: only a model named "gemini-3.8…" may read a slip
    (`slip_read_models`) — a 2.5 (or any other) model is never called for a slip, and an empty
    list refuses the read (a service error, 'review_manually') rather than fall back;
  * the schema asks for a closed grade enum with every key required (`schemas.py`), and every
    answer is still CHECKED here: each grade must clean (`sanitize.clean_slip_grade`) to one of
    the academic engine's grades, each subject / band must carry no stray characters, one subject
    may not carry two different grades, and at least one row must show a grade or band. Only the
    known keys are kept (name, exam, results, warnings; subject, grade, band per row);
  * a malformed answer, or an answer the model could not produce (DOCUMENT_FAILED), is asked ONCE
    more on 3.8; a service failure (our side — rate limit, outage) is not retried here;
  * still malformed after the retry → a failed read (DOCUMENT_FAILED, stored 'unreadable', the
    same verdict as any unparseable answer). A wrong grade is never stored; a refusal is safe.
"""

from ..gemini import cascade_failure, document_failure
from ..read_errors import DOCUMENT_FAILED
from .sanitize import (_drop_expected_warnings, _sanitize_extracted_fields, clean_slip_grade,
                       clean_slip_text)

DOC_TYPE = 'results_slip'
#: The reason stored with a slip answer that failed the check (the retry's too).
MALFORMED_SLIP = 'MALFORMED_SLIP_ANSWER'
#: How many times the slip is asked in all: the first read and at most one retry.
MAX_CALLS = 2
#: The ONLY model family that may read a slip (an allow-list: a new or renamed model is refused
#: until it is named here, never let through because it is not "2.5").
SLIP_MODEL_PREFIX = 'gemini-3.8'
#: The keys kept from a model answer; anything else the model adds is dropped.
_TOP_KEYS = ('candidate_name', 'exam', 'results', 'warnings')
_ROW_KEYS = ('subject', 'grade', 'band')


def is_slip_model(model) -> bool:
    return str(model).startswith(SLIP_MODEL_PREFIX)


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
    from ..academic_engine import _slip_key
    if not isinstance(data, dict):
        return None, ['the answer is not an object']
    results = data.get('results')
    if not isinstance(results, list):
        return None, ['no results list']
    problems, rows, seen = [], [], {}
    for i, row in enumerate(results, start=1):
        if not isinstance(row, dict) or 'subject' not in row or 'grade' not in row:
            problems.append(f'row {i}: not a subject / grade pair')
            continue
        subject, band = clean_slip_text(row.get('subject')), clean_slip_text(row.get('band'))
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
        key = _slip_key(subject)
        if key in seen and seen[key] != (grade, band):
            problems.append(f'row {i}: the same subject as an earlier row with a different grade')
            continue
        if key not in seen:
            seen[key] = (grade, band)
            rows.append({'subject': subject, 'grade': grade, 'band': band})
    if not problems and not any(r['grade'] or r['band'] for r in rows):
        problems.append('no grade or band read on any row')
    for key in ('candidate_name', 'exam'):
        if data.get(key) is not None and not isinstance(data.get(key), str):
            problems.append(f'{key} is not text')
    if problems:
        return None, problems
    cleaned = {k: data[k] for k in _TOP_KEYS if k in data}
    return {**cleaned, 'results': rows}, []


def read_slip_checked(call, models=None) -> dict:
    """Run the slip read through ``call(models)`` (one `_call_gemini_json` answer) and return
    ``{fields, warnings, error}`` as `extract_document_fields` does, plus ``slip_calls`` (1 or 2)
    on a good read. At most `MAX_CALLS` calls, every one on ``models`` (default
    `slip_read_models()`), only ever a model on the allow-list."""
    models = list(slip_read_models() if models is None else models)
    if not models or not all(is_slip_model(m) for m in models):
        return {'fields': {}, 'warnings': [], 'error': cascade_failure(
            [('slip read', f'no {SLIP_MODEL_PREFIX} model to read the slip with; no other model '
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
