"""Sibling detail, the unemployed members, what EPF says about unemployment, and the
school-leaving certificate gap.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
import datetime

from .freshness import _INCOME_DOC_CURRENT_MONTHS
from .identity_checks import _cluster_docs
from .relationships import _MEMBER_ORDER
from .salary_figures import _doc_fields, epf_no_employer
from .utilities import _parse_billing_month


def sibling_tertiary_funding_unknown(application):
    """True when the student has a sibling in tertiary education — the reviewer's recurring
    "which institution + course is your sibling at (or if working, where), and how is it funded /
    what do they earn?" query (household burden + the not-double-funded picture). A one-line,
    non-sensitive question. (Fires on the count; the bundled copy invites all angles at once — the
    flat Check-2 queue has no branch-on-answer follow-up, owner 2026-07-08.)"""
    return (getattr(application, 'siblings_in_tertiary', None) or 0) > 0


def sibling_school_detail_unknown(application):
    """True when the student has a sibling still in SCHOOL — ask which school and what standard/form
    (household texture the counts alone don't capture). Distinct from the tertiary funding clarify;
    the two fire independently when a household has a sibling in each (the #130 gap: only the tertiary
    sibling was ever asked about)."""
    return (getattr(application, 'siblings_in_school', None) or 0) > 0


# ── Unemployment detail (Phase 2B, P7) ───────────────────────────────────────
def _member_occupation(application, member):
    """The roster occupation CODE for a member: father/mother from their own column;
    guardian/brother/sister from the first matching ``other_family_members`` entry. '' if
    unknown. (Mirrors how family.earning_members reads the roster.)"""
    if member == 'father':
        return (getattr(application, 'father_occupation', '') or '').strip()
    if member == 'mother':
        return (getattr(application, 'mother_occupation', '') or '').strip()
    for m in (getattr(application, 'other_family_members', None) or []):
        if isinstance(m, dict) and m.get('role') == member:
            return (m.get('occupation', '') or '').strip()
    return ''


def unemployed_members(application):
    """Roster members (father/mother/guardian/brother/sister) whose occupation is 'unemployed'."""
    return [m for m in _MEMBER_ORDER if _member_occupation(application, m) == 'unemployed']


def epf_confirms_unemployment(application, member, today=None):
    """True when an EPF statement on file for *member* corroborates unemployment: the employer
    number is all-zeros ('No. Majikan 000000000' — the deterministic signal, same as
    ``_epf_monthly_salary`` → 0.0), OR — best-effort, ONLY when a last-contribution date reads
    — the last contribution is older than ~3 months (no recent employment). Soft; never a gate.
    (``statement_date`` is deliberately NOT used for the age test — it's the issue date, not a
    contribution date, so it would misfire.)"""
    if today is None:
        today = datetime.date.today()
    for epf in _cluster_docs(application, member, 'epf'):
        f = _doc_fields(epf)
        if epf_no_employer(f):
            return True
        ym = _parse_billing_month(f.get('last_contribution'))
        if ym and (today.year - ym[0]) * 12 + (today.month - ym[1]) > _INCOME_DOC_CURRENT_MONTHS:
            return True
    return False


def unemployment_status(application, member):
    """The unemployment picture for a roster member, for Check-2 queries + the reviewer:
    ``{unemployed, has_detail, has_epf, epf_corroborated}``. ``unemployed`` = the roster
    occupation is 'unemployed'; ``has_detail`` = a reason or since-when is captured in
    ``income_nonearning``. Soft throughout — never blocks (P3: trust the student)."""
    unemployed = _member_occupation(application, member) == 'unemployed'
    if not unemployed:
        return {'unemployed': False, 'has_detail': False, 'has_epf': False, 'epf_corroborated': False}
    detail = (getattr(application, 'income_nonearning', None) or {}).get(member) or {}
    has_detail = bool(isinstance(detail, dict) and (detail.get('reason') or detail.get('since')))
    return {
        'unemployed': True,
        'has_detail': has_detail,
        'has_epf': _cluster_docs(application, member, 'epf').exists(),
        'epf_corroborated': epf_confirms_unemployment(application, member),
    }


def unemployment_detail_gap(application):
    """True when a roster member is 'unemployed' but no reason/since is captured for them —
    the Check-2 clarify ("tell us why, and since when")."""
    return any(not unemployment_status(application, m)['has_detail']
               for m in unemployed_members(application))


def unemployment_epf_members(application):
    """'unemployed' members with no EPF statement on file — the per-member (soft, optional) Check-2
    doc-request to upload it for corroboration. Per-member so the request is TAGGED to that person
    (an EPF belongs to a specific member; a memberless request lands blank-tagged)."""
    return [m for m in unemployed_members(application)
            if not _cluster_docs(application, m, 'epf').exists()]


def unemployment_epf_gap(application):
    """True when any 'unemployed' member has no EPF on file (boolean form of
    ``unemployment_epf_members``)."""
    return bool(unemployment_epf_members(application))


def unemployment_corroborated_members(application):
    """Unemployed members whose EPF corroborates the unemployment — soft reviewer evidence."""
    return [m for m in unemployed_members(application) if epf_confirms_unemployment(application, m)]


# ── V4: promote the nine recurring HUMAN ask-themes into model queries (audit §E;
#      owner decision 2 + conservative raise-conditions confirmed 2026-07-03). Each is soft:
#      a doc-request (uncapped) or a one-line clarify (capped), never a gate. Conditions are
#      deliberately CONSERVATIVE (under-ask) — tune against the prod cohort post-deploy. ─────
_NON_EARNING_OCC = frozenset({'unemployed', 'homemaker', 'deceased', 'no_contact', ''})


def _docs_or_none(application):
    return getattr(application, 'documents', None)


def _has_read_doc(docs, doc_type):
    """A doc of this type that field-extracted OK (``student_verdict='ok'``) is on file — so a
    blank/wrong upload doesn't clear a V4 academic request (consistency with V1's read-requirement:
    a doc must READ to count, not merely be present)."""
    for d in docs.filter(doc_type=doc_type, superseded_at__isnull=True):
        if (getattr(d, 'vision_fields', None) or {}).get('student_verdict', '') == 'ok':
            return True
    return False


def school_leaving_cert_gap(application):
    """A post-SPM (SPM-track) applicant whose academic record can't be read from a results slip →
    ask for a school-leaving certificate (surat berhenti sekolah / testimonial) to corroborate.
    CONSERVATIVE: fires ONLY when there's no results slip on file (not for every post-SPM
    applicant). Clears when a leaving cert that READ OR a results slip is present."""
    prof = getattr(application, 'profile', None)
    if (getattr(prof, 'exam_type', 'spm') or 'spm') != 'spm':
        return False
    docs = _docs_or_none(application)
    if docs is None or _has_read_doc(docs, 'school_leaving_cert'):
        return False
    return not docs.filter(doc_type='results_slip', superseded_at__isnull=True).exists()
