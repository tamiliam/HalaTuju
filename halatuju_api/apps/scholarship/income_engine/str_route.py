"""The STR route: the words a decision letter uses, the currency and recognised sources, the
recipient-to-household match, proof quality, and the student-facing STR check.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

import re

from .buckets import _name_bucket, _nric_bucket
from .identity_checks import _member_ic_doc, chain_verified_earner
from .relationships import _MEMBER_ORDER


_STR_REJECTED_WORDS = ('tolak', 'tidak layak', 'gagal', 'reject')
# Positive STR approval signals. 'lulus' also matches 'diLULUSkan'. NOTE: SARA's 'Layak' is
# deliberately NOT here — SARA (Sumbangan Asas Rahmah) is a different programme from STR, and the
# STR status on the MySTR portal is 'Lulus', never 'Layak'. (#5b SARA≠STR, 2026-06-11)
_STR_APPROVED_WORDS = ('lulus', 'approve')
_STR_YEAR_RE = re.compile(r'(20\d{2})')
# The three genuine MySTR proof formats (docs/scholarship/str-proof-spec.md). Anything else — a
# SALINAN / application copy, a SARA letter, a salary slip, a random doc — is classified 'unknown'
# by the extractor and is NOT an STR proof at all.
_STR_RECOGNISED_SOURCES = ('letter', 'semakan_status', 'dashboard')


# The RED band of the STR-currency ladder — states where the doc on file positively fails
# to prove a current STR (wrong kind of document, rejected, unreadable status, or a previous
# year's). Code-health S4 #13: this tuple is THE shared source of truth — the 8b4686b1
# state-split left three consumers (the cluster coach, the re-upload reconcile, the
# submission blocker) each carrying its own stale subset, so the two WORST states
# (wrong_type/unreadable) were silently treated as fine by some of them.
# NB 'unreadable' is deliberately NOT here: it is AMBER per the spec (the status token
# didn't read — misread ≠ disproven), and a never-scanned legacy doc also reads
# 'unreadable', so blocking on it would gate consent on our own extraction backlog.
STR_RED_STATES = ('wrong_type', 'rejected', 'stale')
# The student coach nudges on the fixable non-green states too (an unreadable status →
# re-upload cleanly; a dateless 'unconfirmed' approval → a dated proof confirms the cycle).
STR_COACH_STATES = STR_RED_STATES + ('unreadable', 'unconfirmed')


def _str_currency(status_raw, year_str, cohort_year, source_type=''):
    """Structured STR currency state for the verdict (docs/scholarship/str-proof-spec.md). The
    FORMAT GATE runs first: a document that is not one of the three genuine MySTR proofs is
    ``wrong_type`` — never softened to ``unconfirmed``.

      'rejected'    — a clear negative status (Ditolak / Tidak Layak / Gagal) → RED.
      'wrong_type'  — NOT a recognised STR proof (``source_type='unknown'``: a SALINAN / SARA
                      letter / salary slip / other). NOT an STR at all → RED; the income verdict
                      falls through to the salary route.
      'unreadable'  — a recognised format but the approval status did NOT read AND no current-cycle
                      date is shown, so approval can't be confirmed → AMBER (Unsure). NB not a claim
                      the page is cropped — the status token may simply have been misread.
      'stale'       — approved, but a readable year OLDER than the cohort year (STR is annual) → AMBER.
      'unconfirmed' — a recognised format, approved (Lulus), but NO date to pin the cycle
                      (dashboard / collapsed Semakan) → BLUE (probably current).
      'current'     — a recognised format, approved, DATED current (letter date / Semakan payment
                      date ≥ cohort year) → GREEN.

    The STR model is exactly Name · IC · Status · Year (owner 2026-07-07). Only two questions
    decide currency: **Status** — is it approved? (a readable "Lulus"/"diluluskan"; on a dashboard/
    Semakan the "Lulus" IS shown); and **Year** — is it for the current cycle? proven by a DATE (the
    letter date, or a Maklumat-Pembayaran credit date), NEVER by an amount. The approved/paid AMOUNT
    is ignored entirely — it varies without meaning and a prior-year figure is irrelevant (this
    RETIRES the old paid-amount rescue: a misread approval no longer greens off a number; a readable
    "Lulus" is required, else the doc reads 'unreadable' and a re-read / interview settles it).

    A dateless approved STR is not GREEN: a year-old dashboard/Semakan screenshot also shows
    "Lulus", so without a date we can't confirm the cycle (→ BLUE, confirm at interview / open
    Maklumat Pembayaran). A blank/legacy ``source_type`` (extracted before classification) is
    TOLERATED — it falls through to the status assessment rather than being forced to wrong_type;
    a re-run repopulates it."""
    s = (status_raw or '').lower()
    st = (source_type or '').strip().lower()
    if any(w in s for w in _STR_REJECTED_WORDS):
        return 'rejected'
    if st == 'unknown':
        return 'wrong_type'          # not a genuine STR proof at all (SALINAN / SARA / payslip / …)
    if not any(w in s for w in _STR_APPROVED_WORDS):
        return 'unreadable'          # no readable "Lulus"/"diluluskan" → STR approval can't be confirmed
    # SURFACE CEILING (owner 2026-07-07): a DASHBOARD confirms APPROVAL but is a self-service snapshot
    # that cannot certify the cycle to certainty — its max band is Probable. So an approved dashboard
    # caps at 'unconfirmed' (BLUE) regardless of any date read. Only the LETTER (dated) and the
    # SEMAKAN STATUS (dated Maklumat-Pembayaran) can reach 'current' (GREEN / Certain).
    if st == 'dashboard':
        return 'unconfirmed'
    # Letter / Semakan / blank-legacy. The Year question: a DATE (letter date / Maklumat-Pembayaran
    # credit date) pins the cycle. No date → unconfirmed (BLUE); prior-year → stale (AMBER);
    # current-or-later → current (GREEN).
    m = _STR_YEAR_RE.search(year_str or '')
    if not m:
        return 'unconfirmed'
    if cohort_year and int(m.group(1)) < int(cohort_year):
        return 'stale'
    return 'current'


def _str_recipient_household_match(application, name, nric, tagged_member=''):
    """Exhaustively match an STR recipient's NAME and NRIC — INDEPENDENTLY — against every
    parent/guardian (and any other roster member) whose IC is on file. Returns
    ``(name_status, nric_status, member)``.

    A genuine STR is a HOUSEHOLD benefit and the letter can carry either spouse's name/IC
    (owner 2026-07-07: "match the STR against ANY parent/guardian; only when ALL attempts fail is
    it breached"), so we try everyone — not just the declared earner — and each field settles on
    its own: a recipient whose NAME hits the father and whose NRIC hits the mother is a clean
    household match on BOTH (e.g. #45). 'match' iff the field hits any member's IC; 'mismatch' iff
    at least one IC was compared and none hit; 'no_ref' when there was nothing to compare against.
    ``member`` resolves to the name-matched member (preferred), else the nric-matched member, else
    the tagged/earner fallback."""
    members = list(dict.fromkeys([m for m in ([tagged_member] + list(_MEMBER_ORDER)) if m]))
    name_hit = nric_hit = None
    name_seen = nric_seen = False
    for m in members:
        ic = _member_ic_doc(application, m)
        if ic is None:
            continue
        ic_name = (getattr(ic, 'vision_name', '') or '').strip()
        ic_nric = (getattr(ic, 'vision_nric', '') or '').strip()
        if ic_name:
            name_seen = True
            if name_hit is None and _name_bucket(name, ic_name) == 'match':
                name_hit = m
        if ic_nric:
            nric_seen = True
            if nric_hit is None and _nric_bucket(nric, ic_nric) == 'match':
                nric_hit = m
    name_status = 'match' if name_hit else ('mismatch' if (name and name_seen) else 'no_ref')
    nric_status = 'match' if nric_hit else ('mismatch' if (nric and nric_seen) else 'no_ref')
    return name_status, nric_status, (name_hit or nric_hit or tagged_member or '')


# STR-proof QUALITY ranking for the upload keep-better guard (owner: #83 wrong-type, #30 dashboard
# < Semakan). A re-upload must never displace a live proof of STRICTLY HIGHER quality with a thinner
# one. Quality is a tuple (currency_rank, source_rank), CURRENCY FIRST — so #112 is correctly NOT a
# regression: its live Lulus DASHBOARD (unconfirmed) outranks the older 'Dalam Proses Rayuan'
# SEMAKAN (unreadable approval) on currency, which dominates the source tiebreak. The source tier
# only decides ties (both Lulus + dateless): a Semakan (shows the payment-dates page → can reach
# 'current') carries MORE than a Dashboard (home totals, capped at 'unconfirmed'), which carries
# more than an unrecognised page.
_STR_CURRENCY_RANK = {'current': 4, 'unconfirmed': 3, 'stale': 2, 'unreadable': 1, 'wrong_type': 0}
_STR_SOURCE_RANK = {'letter': 3, 'semakan_status': 2, 'dashboard': 1}


def str_proof_quality(doc):
    """A comparable (currency_rank, source_rank) quality tuple for an STR proof — HIGHER is better.
    Returns ``None`` for a non-STR doc OR a 'rejected' read: a genuine Ditolak is NEWS (a real
    negative status), so it must ALWAYS replace, never be kept out by the guard."""
    sc = student_str_check(doc)
    if not sc:
        return None
    cs = sc.get('current_status', '')
    if cs == 'rejected':
        return None
    vf = getattr(doc, 'vision_fields', None)
    src = (((vf.get('fields') or {}).get('source_type') or '') if isinstance(vf, dict) else '')
    return (_STR_CURRENCY_RANK.get(cs, 0), _STR_SOURCE_RANK.get(src.strip().lower(), 0))


def student_str_check(doc):
    """For an STR document: the recipient facts (name · NRIC · status · year) matched against the
    HOUSEHOLD — every parent/guardian's IC, on name OR nric independently — plus whether it's
    CURRENT (this cohort year + approved). Returns ``{name, nric, status, year, member,
    name_status, nric_status, current_status, ic_present}`` or None for a non-STR doc.

    name_status / nric_status: 'match' | 'mismatch' | 'no_ref' (household-level — see
    ``_str_recipient_household_match``). current_status: the STR-currency ladder (``_str_currency``)."""
    if getattr(doc, 'doc_type', '') != 'str':
        return None
    app = doc.application
    # Where the recipient resolves when neither name nor nric hits an IC: the declared earner on
    # the STR route, else the doc's own member tag.
    tagged = ((getattr(app, 'income_earner', '') or '').strip()
              or (getattr(doc, 'household_member', '') or '').strip())

    vf = doc.vision_fields if isinstance(getattr(doc, 'vision_fields', None), dict) else {}
    f = vf.get('fields', {}) if isinstance(vf.get('fields', {}), dict) else {}
    name = (f.get('recipient_name', '') or '').strip()
    nric = (f.get('recipient_nric', '') or '').strip()
    status = (f.get('status', '') or '').strip()
    year = (f.get('year', '') or '').strip()

    name_status, nric_status, member = _str_recipient_household_match(app, name, nric, tagged)
    # IC-NUMBER chain (#9): a BC↔STR IC-number match confirms the recipient is the verified earner,
    # regardless of a wrong/absent card in the slot. (Currency below is a separate test — a
    # confirmed recipient can still hold a stale/rejected STR.)
    if member and chain_verified_earner(app, member):
        name_status = nric_status = 'match'

    cohort_year = getattr(getattr(app, 'cohort', None), 'year', None)
    ic = _member_ic_doc(app, member) if member else None
    return {
        'name': name, 'nric': nric, 'status': status, 'year': year,
        'member': member, 'name_status': name_status, 'nric_status': nric_status,
        'current_status': _str_currency(status, year, cohort_year, f.get('source_type', '')),
        'ic_present': ic is not None,
    }
