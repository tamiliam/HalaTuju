"""Pathway (offer-letter) verification — the student-facing clinical check.

Mirrors ``academic_engine`` for the results slip: a single pure source
(``student_offer_check``) that the FE OfferLetterChecklist AND Cikgu Gopal both
consume, so the checklist and the coach can never disagree. Reads ONLY the
student's own document + profile (never admin data).

Two real identity checks — **Name** and **IC** (the IC is the strong one; names can
coincide, the NRIC can't) — plus a set of surfaced **data points** (programme,
institution, issuer, offer date, intake, address) the officer eyeballs. The
programme/institution can legitimately differ from what the student declared at
apply time (they may have changed their plan), so those are NOT hard checks.
"""
from __future__ import annotations

from .vision import name_match, nric_match


def _name_status(candidate: str, profile_name: str, extracted: bool) -> str:
    """'match' / 'partial' / 'mismatch' / 'unreadable' / 'pending'."""
    if not candidate:
        return 'unreadable' if extracted else 'pending'
    if not profile_name:
        return 'pending'           # nothing on file to check against
    return name_match(candidate, profile_name)


def _ic_status(candidate_nric: str, profile_nric: str, extracted: bool) -> str:
    """'match' / 'mismatch' / 'unreadable' / 'pending'."""
    if not candidate_nric:
        return 'unreadable' if extracted else 'pending'
    if not profile_nric:
        return 'pending'
    return 'match' if nric_match(candidate_nric, profile_nric) else 'mismatch'


def student_offer_check(doc) -> dict:
    """The clinical read of ONE offer letter against the student's own profile.

    Returns ``{name, ic}`` (each a status above) + the surfaced data-point strings
    ``{candidate_name, candidate_nric, programme, institution, issuer, offer_date,
    intake, address}``."""
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    sv = vf.get('student_verdict')
    f = vf.get('fields', {}) if isinstance(vf.get('fields'), dict) else {}
    # 'review_manually' = Gemini was skipped (rate-limited) → genuinely not extracted.
    extracted = bool(sv) and sv != 'review_manually'

    profile = getattr(getattr(doc, 'application', None), 'profile', None)
    pname = getattr(profile, 'name', '') or ''
    pnric = getattr(profile, 'nric', '') or ''

    cn = (f.get('candidate_name') or '').strip()
    cnric = (f.get('candidate_nric') or '').strip()
    return {
        'name': _name_status(cn, pname, extracted),
        'ic': _ic_status(cnric, pnric, extracted),
        'candidate_name': cn,
        'candidate_nric': cnric,
        'programme': (f.get('programme') or '').strip(),
        'institution': (f.get('institution') or '').strip(),
        'issuer': (f.get('issuer') or '').strip(),
        'offer_date': (f.get('offer_date') or '').strip(),
        'intake': (f.get('intake') or '').strip(),
        'address': (f.get('candidate_address') or '').strip(),
    }
