"""TD-319 — an EPF statement whose contribution table the in-house reader cannot read asks Gemini.

The KWSP parser (`doc_parse_epf._parse_epf`) recognises a Penyata Ahli and reads its name, NRIC,
employer number and balance deterministically. When it cannot read the CARUMAN SEMASA table it
says so honestly — ``contribution_status='unknown'`` with no figures — and until 2026-10-01 that
result was KEPT, so the statement never carried a contribution and
`income_engine.salary_figures._epf_monthly_salary` had nothing to estimate a salary from.

**The owner's ruling (2026-10-01, docs/decisions.md):** *"allow."* — a statement the in-house
reader reports as ``unknown`` goes to Gemini for the contribution fields, a paid call per such
statement and only for those. Statements already stored are NOT re-read by this (a separate
batch, only if the owner asks for it).

The rules, each tested in ``tests/test_epf_contribution_fallback.py``:

* Only an ``epf`` reading whose ``contribution_status`` is exactly ``'unknown'`` is sent. A
  statement the parser read (``has`` / ``zero``) never costs a call.
* Only the CONTRIBUTION fields are taken from Gemini, and only when its own reading is ``has`` or
  ``zero``; the deterministic name, NRIC, employer number, balance and address always stand.
* Gemini failing (an error, or its own ``unknown``) leaves the deterministic reading exactly as it
  was — no figure, still ``unknown``, still ``capture='deterministic'``.
* When Gemini's figures do land, ``capture`` is ``'ai'``: the figures that decide the salary
  estimate came from the model, and the officer's capture chip should say so.

Never raises: the extraction it is handed never raises, and anything unexpected leaves the
deterministic reading in place.
"""

#: The fields that describe the contribution table — the only ones Gemini may supply here.
CONTRIBUTION_FIELDS = (
    'contribution_status', 'monthly_contribution', 'last_contribution', 'months_counted',
    'employer_contribution_total', 'employee_contribution_total',
)

#: A Gemini reading of the table worth taking. Its own 'unknown' adds nothing.
_READ = ('has', 'zero')


def deterministic_or_epf_fallback(doc_type: str, parsed: dict, ocr_text: str, extract) -> dict:
    """The extraction result for a deterministic ``parsed`` reading — with an unread EPF
    contribution table filled from ``extract(ocr_text, 'epf')`` (Gemini) when it can read it.

    ``extract`` is `vision.extract_document_fields`, passed in so this module does not import
    `vision` (it is imported BY it) and so a test patching the name in `vision` reaches it.
    """
    ex = {'fields': parsed, 'warnings': [], 'error': '', 'capture': 'deterministic'}
    if doc_type != 'epf' or (parsed or {}).get('contribution_status') != 'unknown':
        return ex
    try:
        ai = extract(ocr_text, 'epf')
        got = (ai or {}).get('fields') or {}
        if (ai or {}).get('error') or str(got.get('contribution_status') or '').strip() not in _READ:
            return ex
        taken = {k: str(got[k]).strip() for k in CONTRIBUTION_FIELDS
                 if str(got.get(k) or '').strip()}
    except Exception:   # a fallback must never cost the reading it falls back from
        return ex
    return {'fields': {**parsed, **taken}, 'warnings': list((ai or {}).get('warnings') or []),
            'error': '', 'capture': 'ai'}
