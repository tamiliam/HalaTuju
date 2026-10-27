"""Income DECLARATION forms — recognised so they can never pass as a payslip (owner ruling 2026-10-27).

#374: a self-filled "Borang Pengesahan Pendapatan" (a parent's own income statement, NELAYAN RM800) went
into the salary-slip slot and the salary scorer read it `genuine` / `govt` 0.79 — the form's sector field
("Kumpulan Perkhidmatan", "Tentera / Polis") matched a civil-service marker and three wage labels did the
rest — so the income fact went CERTAIN on a statement nobody had approved.

A declaration is recognised by its TITLE wording, from the OCR text, in either income slot (`salary_slip`,
`income_support_doc`). It is scored `suspect` with `doc_seen='declaration'` — never genuine, never a
payslip family — and whether it COUNTS is a separate question asked of what the read found on it: an
issuing body (header) and an approver (a named / titled person who signed or stamped it) —
`income_declaration.declaration_missing`. Pure + deterministic; never raises.
"""
from .results_doc import _any_token, _norm_fold_upper_alnum

DECLARATION = 'declaration'

#: Title wording of an income declaration / confirmation form (Malay and English), plus the declarant's
#: own oath ("saya mengaku", "I hereby declare") — a form whose title the OCR missed still says that, and
#: a payslip never does. Matched as normalised phrases, so "Borang Pengesahan Pendapatan" and "SURAT
#: PENGESAHAN PENDAPATAN" both hit the first.
DECLARATION_MARKERS = [
    'PENGESAHAN PENDAPATAN', 'AKUAN PENDAPATAN', 'PENGISYTIHARAN PENDAPATAN', 'PERAKUAN PENDAPATAN',
    'AKUAN BERKANUN', 'AKUAN SUMPAH', 'STATUTORY DECLARATION', 'INCOME DECLARATION',
    'DECLARATION OF INCOME', 'CONFIRMATION OF INCOME', 'INCOME CONFIRMATION',
    'SAYA MENGAKU', 'DENGAN INI MENGAKU', 'DENGAN INI MENGISYTIHARKAN', 'HEREBY DECLARE',
]


def is_declaration_text(ocr_text: str) -> bool:
    """True when the OCR text carries an income-declaration title (`DECLARATION_MARKERS`)."""
    return _any_token(DECLARATION_MARKERS, _norm_fold_upper_alnum(ocr_text or ''))


def declaration_genuineness(model_version: str) -> dict:
    """The stored score of a recognised declaration: `suspect` (never genuine — owner: a declared amount
    is never Certain), `doc_seen`/`family` 'declaration'. Shaped like `salary_doc.salary_genuineness`."""
    return {'status': 'suspect', 'family': DECLARATION, 'probability': 0.5,
            'reason': 'income declaration form — counts only with an issuing body and an approver',
            'model_version': model_version, 'markers': {}}


def income_doc_genuineness(ocr_text: str, doc_type: str) -> dict:
    """The genuineness read of an income document's OCR text, by slot: a salary slip is scored by the
    salary model (which recognises a declaration first); a supporting document is scored ONLY when it is
    a declaration (`{}` otherwise — a ketua kampung / employer letter has no fingerprint, no signal)."""
    from .salary_doc import MODEL_VERSION, salary_genuineness
    if doc_type == 'salary_slip':
        return salary_genuineness(ocr_text)
    return declaration_genuineness(MODEL_VERSION) if is_declaration_text(ocr_text) else {}
