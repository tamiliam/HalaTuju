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

import re

from .vision import name_match, nric_match


# ── Lenient offer-vs-declared pathway matcher ────────────────────────────────
# The student declares a *specific* college/programme at apply time (via the
# eligibility filter, or a pre-U school/track). The offer letter names the same
# two facts. We compare them leniently: an offer counts as "matching" the
# declaration unless it is TOTALLY off (a different place / a different field),
# because catalogue names and printed offer-letter wording differ in harmless
# ways ("KM Melaka" vs "Kolej Matrikulasi Melaka"). We only flag a real clash —
# SMK Temerloh vs SMK Mentakab, Asasi Pertanian vs Asasi Pintar, Dip Horticulture
# vs Dip Electricity at the same UPM — so the student is never nagged on a match.

# Words that carry NO distinguishing signal — institution-type, qualification-type,
# and connectors. Field words (pertanian/pintar/sains/electricity…) and place names
# (melaka/temerloh/mentakab…) are deliberately NOT here: those are what distinguish.
_GENERIC_TOKENS = frozenset({
    # institution type
    'kolej', 'college', 'matrikulasi', 'smk', 'sekolah', 'menengah', 'kebangsaan',
    'kampus', 'campus', 'universiti', 'university', 'uni', 'politeknik', 'polytechnic',
    'institut', 'institute', 'pusat', 'akademi', 'academy', 'tinggi', 'harian',
    'jabatan', 'fakulti', 'faculty', 'school',
    # qualification / pathway type
    'asasi', 'foundation', 'diploma', 'ijazah', 'sarjana', 'muda', 'degree', 'bachelor',
    'program', 'programme', 'sijil', 'certificate', 'persediaan', 'pengajian',
    'tingkatan', 'form', 'stpm', 'matrik', 'pra',
    # connectors / filler
    'of', 'in', 'the', 'dan', 'and', 'di', 'ke', 'dengan', 'untuk', 'bagi',
    'with', 'for',
})


def _distinctive_tokens(text: str) -> set:
    """The place/field tokens that actually distinguish one offer from another:
    lowercase words 3+ chars, excluding pure digits and the generic stopwords."""
    if not text:
        return set()
    toks = re.split(r'[^a-z0-9]+', text.lower())
    return {t for t in toks if len(t) > 2 and not t.isdigit() and t not in _GENERIC_TOKENS}


def _field_status(declared: str, offer: str) -> str:
    """Compare one field (institution OR programme): 'match' (share a distinctive
    token), 'clash' (both distinctive, none shared), or 'unknown' (one side has
    nothing distinctive to compare)."""
    d = _distinctive_tokens(declared)
    o = _distinctive_tokens(offer)
    if not d or not o:
        return 'unknown'
    return 'match' if (d & o) else 'clash'


def offer_pathway_match(declared_programme: str, declared_institution: str,
                        offer_programme: str, offer_institution: str) -> str:
    """'match' / 'mismatch' / 'unknown' for an offer vs the declared pathway.

    A clash on EITHER the institution or the programme makes it a mismatch (the
    offer is for a genuinely different place or field). Otherwise a shared
    distinctive token on either side makes it a match. 'unknown' means there was
    nothing specific enough to compare (the student declared only a pathway type,
    or the offer body didn't read) — treated as no-conflict downstream."""
    inst = _field_status(declared_institution, offer_institution)
    prog = _field_status(declared_programme, offer_programme)
    if inst == 'clash' or prog == 'clash':
        return 'mismatch'
    if inst == 'match' or prog == 'match':
        return 'match'
    return 'unknown'


def _declared_pathway(application) -> tuple:
    """The student's declared (programme, institution) from the apply-form fields.
    Prefers the structured ``chosen_programme`` (eligibility-filter pick), falling
    back to the pre-U school/track for STPM/Matriculation. Either may be ''."""
    cp = getattr(application, 'chosen_programme', None)
    cp = cp if isinstance(cp, dict) else {}
    prog = (cp.get('course_name') or '').strip()
    inst = (cp.get('institution') or '').strip()
    if not inst:
        inst = (getattr(application, 'pre_u_institution', '') or '').strip()
    if not prog:
        prog = (getattr(application, 'pre_u_track', '') or '').strip()
    return prog, inst


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
    programme = (f.get('programme') or '').strip()
    institution = (f.get('institution') or '').strip()

    # Reconcile the offer against what the student declared at apply time. Lenient:
    # only a genuine clash (different place / field) is 'mismatch' — a naming quirk
    # is 'match', and 'unknown' when there's nothing specific declared to compare.
    application = getattr(doc, 'application', None)
    decl_prog, decl_inst = _declared_pathway(application) if application is not None else ('', '')
    pathway = offer_pathway_match(decl_prog, decl_inst, programme, institution)

    return {
        'name': _name_status(cn, pname, extracted),
        'ic': _ic_status(cnric, pnric, extracted),
        'candidate_name': cn,
        'candidate_nric': cnric,
        'programme': programme,
        'institution': institution,
        'issuer': (f.get('issuer') or '').strip(),
        'offer_date': (f.get('offer_date') or '').strip(),
        'intake': (f.get('intake') or '').strip(),
        'address': (f.get('candidate_address') or '').strip(),
        # Offer-vs-declared reconciliation (Check-1 pathway).
        'pathway': pathway,                       # 'match' | 'mismatch' | 'unknown'
        'declared_programme': decl_prog,
        'declared_institution': decl_inst,
    }
