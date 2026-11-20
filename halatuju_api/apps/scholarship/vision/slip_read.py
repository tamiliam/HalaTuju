"""The SPM results-slip AI read: 3.8 Flash only, every answer checked, one retry (OCR-first S5).

The slip is read deterministically first (`field_extraction._read_results_slip`); this is the AI
fallback when neither the certificate parser nor the word-box read locks. Until S5 that fallback
stayed on 2.5 Flash, because in the paid eval 3.8 Flash wrote malformed grades on 26 of 98 slips
("Aplus", stray JSON, tab and CJK characters). SPM grades feed eligibility, so the rule here is:

  * the model list is 3.8 Flash ONLY (`slip_read_models`) — a 2.5 model is never called for a
    slip, and an empty list refuses the read rather than fall back to the default cascade;
  * the schema asks for a closed grade enum with every key required (`schemas.py`), and every
    answer is still CHECKED here: each grade must clean (`sanitize.clean_slip_grade`) to one of
    the academic engine's grades, and each subject / band must carry no stray characters;
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


def slip_read_models() -> list:
    """The slip read's models: `profile_engine.MODEL_CASCADE` with every 2.5 model taken out
    (today `['gemini-3.8-flash']`). Read live, so the AI registry shows what the read uses."""
    from ..profile_engine import MODEL_CASCADE
    return [m for m in MODEL_CASCADE if 'gemini-2.5' not in str(m)]


def check_slip_answer(data):
    """One parsed slip answer → ``(cleaned, problems)``. ``cleaned`` is the answer with every
    grade, subject and band in its plain spelling (None when the answer is unusable); ``problems``
    lists what was wrong, empty for a good answer. An empty results list is a good answer (the
    slip may show no table) — the academic engine then has nothing to confirm."""
    if not isinstance(data, dict):
        return None, ['the answer is not an object']
    results = data.get('results')
    if not isinstance(results, list):
        return None, ['no results list']
    problems, rows = [], []
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
        rows.append({**row, 'subject': subject, 'grade': grade, 'band': band})
    for key in ('candidate_name', 'exam'):
        if data.get(key) is not None and not isinstance(data.get(key), str):
            problems.append(f'{key} is not text')
    if problems:
        return None, problems
    return {**data, 'results': rows}, []


def read_slip_checked(call, models=None) -> dict:
    """Run the slip read through ``call(models)`` (one `_call_gemini_json` answer) and return
    ``{fields, warnings, error}`` as `extract_document_fields` does, plus ``slip_calls`` (1 or 2)
    on a good read. At most `MAX_CALLS` calls, every one on ``models`` (default
    `slip_read_models()`), never a 2.5 model."""
    models = list(slip_read_models() if models is None else models)
    if not models or any('gemini-2.5' in str(m) for m in models):
        return {'fields': {}, 'warnings': [], 'error': cascade_failure(
            [('slip read', 'no 3.8 model to read the slip with; 2.5 is never used for a slip')])}
    failures = []
    for attempt in range(1, MAX_CALLS + 1):
        data = call(models)
        if isinstance(data, dict) and '_error' in data:
            err = str(data['_error'] or '')
            if not err.startswith(DOCUMENT_FAILED):
                return {'fields': {}, 'warnings': [], 'error': err}   # our side: no retry here
            failures.append((models[0], err[len(DOCUMENT_FAILED):].lstrip(': ')[:200]))
            continue
        cleaned, problems = check_slip_answer(data)
        if cleaned is None:
            failures.append((models[0], f'{MALFORMED_SLIP}: ' + '; '.join(problems[:5])))
            continue
        warnings = _drop_expected_warnings(DOC_TYPE, cleaned.pop('warnings', []) or [])
        fields = _sanitize_extracted_fields(DOC_TYPE, cleaned)
        return {'fields': fields, 'warnings': warnings, 'error': '', 'slip_calls': attempt}
    return {'fields': {}, 'warnings': [], 'error': document_failure(failures)}
