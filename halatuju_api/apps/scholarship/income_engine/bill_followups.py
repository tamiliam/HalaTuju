"""When a utility bill must be uploaded again, and the re-check that asks for it.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

import datetime

from .occupation import _docs_or_none
from .salary_figures import _doc_fields, _parse_rm
from .utilities import _latest_doc, _utility_currency, utility_check


def utility_bill_gap(application):
    """DEPRECATED (owner 2026-07-08) — superseded by the per-bill ``utility_bill_recheck``. NEITHER
    a water nor an electricity bill on file → ask for one. Kept only for callers that still probe
    the either-or state; Check-2 now uses the per-bill recheck below."""
    docs = _docs_or_none(application)
    return docs is not None and not docs.filter(
        doc_type__in=('water_bill', 'electricity_bill'), superseded_at__isnull=True).exists()


def _bill_needs_upload(application, doc_type, today):
    """Why THIS bill type needs a (re)upload, or '' when the bill on file is usable. Reasons:
    'missing' (none on file), 'address_unreadable' / 'amount_unreadable' (a required field couldn't
    be read), 'stale' (a READABLE date older than the ACCEPT window ~6 months), 'undated' (no readable
    date). We ASK for a bill within 3 months, but only keep RE-ASKING past ``_UTILITY_ACCEPT_MONTHS``:
    a dated bill within ~6 months is accepted as-is and the officer eyeballs the date (owner
    2026-07-09) — a student who can only produce a slightly older bill is never trapped. The UNDATED
    case is re-asked only ONCE, then ACCEPTED (owner 2026-07-09, #130): many Malaysian bills never
    print a machine-readable date, so looping on it traps the student. A HARD address MISMATCH is NOT
    here — that's the separate ``utility_address_mismatch`` clarify."""
    doc = _latest_doc(application, doc_type)
    if doc is None:
        return 'missing'
    facts = utility_check(doc, today)
    if not facts:
        return 'missing'
    if not (facts.get('address') or '').strip():
        return 'address_unreadable'
    if _parse_rm(facts.get('monthly_bill')) is None:
        return 'amount_unreadable'
    cs = facts.get('current_status')
    if cs == 'stale':                       # 'stale' now MEANS >6 months (the accept window is baked
        return 'stale'                      # into _utility_currency) → keep re-asking. 'ageing'
                                            # (3–6mo) is NOT stale → accepted as-is, never re-asked.
    if cs == 'unknown':                     # date unreadable → re-ask ONCE, then accept
        return '' if _undated_clean_bill_attempts(application, doc_type, today) >= 2 else 'undated'
    return ''


def _undated_clean_bill_attempts(application, doc_type, today):
    """How many bills of this type (live + superseded) read CLEAN on holder-address-amount but had
    NO parseable billing date — the student's undated-bill attempts. At >= 2 the recheck stops
    re-asking and accepts the bill (re-ask ONCE, then accept; owner 2026-07-09, #130)."""
    docs = _docs_or_none(application)
    if docs is None:
        return 0
    n = 0
    # all-versions-read: this is the ONE engine read that INTENTIONALLY spans superseded rows — each
    # re-upload supersedes the last, so a live-only count is always <=1 and could never reach the
    # retry threshold. It counts prior ATTEMPTS, never feeds an eligibility verdict. (superseded_at
    # is deliberately not filtered; see the TestStaticReadGuard allow-list.)
    for d in docs.filter(doc_type=doc_type):
        f = _doc_fields(d)
        if (_utility_currency(f, today) == 'unknown'
                and (f.get('address') or '').strip()
                and _parse_rm(f.get('amount')) is not None):
            n += 1
    return n


def utility_bill_recheck(application, today=None):
    """Per-bill re-upload map (owner 2026-07-08): ``{'water_bill'|'electricity_bill': reason}`` for
    each bill that is missing / stale / undated / unreadable. Empty when BOTH bills are on file,
    current, and readable — the 'both bills, current, clear' requirement enforced in logic, not just
    painted on the row. Drives the two per-bill Check-2 re-upload requests; a fresh clean upload
    supersedes the old one and clears its request."""
    if today is None:
        today = datetime.date.today()
    docs = _docs_or_none(application)
    if docs is None:
        return {}
    out = {}
    for dt in ('water_bill', 'electricity_bill'):
        reason = _bill_needs_upload(application, dt, today)
        if reason:
            out[dt] = reason
    return out
