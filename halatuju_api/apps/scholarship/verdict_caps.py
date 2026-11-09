"""The INCOME fact's flat genuineness cap, moved out of ``verdict_engine``.

⚠ WHY THIS IS A MODULE (audit sprint A3.4, 2026-11-10). ``verdict_engine.py`` was on the
oversize ledger at 941 lines. The flat cap — which documents may lower a fact, the wrong-type STR
exception and ``_apply_genuineness_caps`` itself — moved here whole and unchanged.
``verdict_engine._apply_genuineness_caps`` is kept as a seam, because ``build_verdict`` and the
genuineness tests call it by that name.

``_suspect_genuineness`` STAYS in ``verdict_engine``: ``verdict_ladder`` imports it from there at
load time. It is reached here through the module (``_ve._suspect_genuineness``), so a patch on the
``verdict_engine`` name still reaches the cap, as it did before the move. ``income_engine`` is
still imported inside ``_str_wrong_type``, so a patch at its source still lands.
"""
from __future__ import annotations

from . import verdict_engine as _ve
from .verdict_engine import _latest_doc


# Which documents feed each fact's genuineness FLAT CAP. As of the 2026-07-07 ladder, identity,
# academic and pathway use `_apply_genuineness_ladder` instead (a graded step, not a flat cap), so
# only INCOME remains on the flat cap — computed per-route (see `_income_genuineness_docs`), only the
# docs REQUIRED to prove income can cap it.
_FACT_GENUINENESS_DOCS: dict = {}


def _income_genuineness_docs(application):
    """Documents whose genuineness may lower the INCOME verdict — ONLY the docs REQUIRED to prove
    income on the application's route. Optional corroboration (EPF, salary slip) never caps the
    verdict: a dodgy optional doc still raises the officer ``document_not_genuine`` flag / a
    Check-2 query, but the route's own required proof decides the verdict.

    - STR route → the STR (+ the birth certificate when the earner is the mother, the required
      relationship proof). A future-dated / typed *optional* EPF does NOT cap.
    - Salary route → the required salary slip isn't fingerprintable and EPF is optional, so no
      fingerprint-driven income cap applies."""
    route = (getattr(application, 'income_route', '') or '').lower()
    if route == 'str':
        docs = ['str']
        if (getattr(application, 'income_earner', '') or '').lower() == 'mother':
            docs.append('birth_certificate')
        return docs
    return []


def _fact_genuineness_docs(application, fact_name):
    if fact_name == 'income':
        return _income_genuineness_docs(application)
    return _FACT_GENUINENESS_DOCS.get(fact_name, [])


def _str_wrong_type(application):
    """True when the latest STR doc is a GENUINE document of the WRONG kind in the STR slot (a
    payslip / SARA letter / SALINAN) — its currency state is 'wrong_type'. Used to suppress the
    misleading "not a genuine original" genuineness caveat (str-proof-spec.md §4)."""
    from .income_engine import student_str_check
    d = _latest_doc(application, 'str')
    if d is None:
        return False
    sc = student_str_check(d)
    return bool(sc and sc.get('current_status') == 'wrong_type')


def _apply_genuineness_caps(application, facts):
    """Soft post-cap (Sprint 2): a suspect/wrong-type feeding document lowers a fact from 'verified' to
    'review' and adds a `document_not_genuine` caveat (`verdict_ladder.doc_caveat`) — the AI is less
    certain. NEVER moves a fact to 'gap'/fail, never upgrades; only once the genuineness check ran."""
    for fact in facts:
        dts = _fact_genuineness_docs(application, fact['fact'])
        # A wrong_type STR — a GENUINE non-STR document in the STR slot (a payslip, a SARA letter) —
        # is already explained by the str_not_current('wrong_type') item; the genuineness "may not be
        # a genuine original" caveat is misleading (the doc IS genuine, just the wrong KIND), so don't
        # double-flag it. (str-proof-spec.md §4.)
        if 'str' in dts and _str_wrong_type(application):
            dts = [d for d in dts if d != 'str']
        # Same principle for a wrong-type RELATIONSHIP doc (#27): the specific re-upload ticket
        # (birth_cert_not_genuine / guardianship_letter_not_genuine) already explains it — don't
        # stack the generic officer-only caveat on top.
        specific = {i['code'] for i in fact['unresolved']}
        if specific & {'birth_cert_not_genuine', 'birth_cert_unreadable'}:
            dts = [d for d in dts if d != 'birth_certificate']
        if specific & {'guardianship_letter_not_genuine', 'guardianship_letter_unreadable'}:
            dts = [d for d in dts if d != 'guardianship_letter']
        if not dts or specific & {'document_not_genuine', 'higher_results_not_results'}:
            continue
        st = _ve._suspect_genuineness(application, dts)
        if st:
            if fact['status'] == 'verified':
                fact['status'] = 'review'
            from .verdict_ladder import doc_caveat        # ruling D: an offer letter is "not a results document"
            fact['unresolved'].append(doc_caveat(application, dts, st))
    return facts
