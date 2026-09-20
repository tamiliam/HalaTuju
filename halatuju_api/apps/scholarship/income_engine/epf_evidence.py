"""The semester-result gap, and the EPF corroboration of employment.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from .identity_checks import _cluster_docs
from .informal import informal_payslip_claimed, member_is_informal
from .occupation import _NON_EARNING_OCC, _docs_or_none, _has_read_doc, _member_occupation


# The post-SPM pathways that run MULTI-YEAR (owner 2026-07-08): a student who joined one of these
# in a PREVIOUS year is a continuing student and owes their latest semester result (CGPA).
# Matriculation and Asasi are 10-MONTH programmes — a past intake there means COMPLETED, not
# continuing, so no semester-result request applies.
_MULTI_YEAR_PATHWAYS = frozenset({'stpm', 'pismp', 'poly', 'university'})


def semester_result_gap(application):
    """A CONTINUING student with no current-semester result slip that READ on file → ask for the
    latest CGPA. Continuing means (owner 2026-07-08, post-SPM focus):
      * the chosen pathway is MULTI-YEAR (STPM / PISMP / Poly / UA diploma — `_MULTI_YEAR_PATHWAYS`)
        AND the offer's normalised ``reporting_date`` is a year OLDER than the cohort (the same
        past-intake signal the continuing-STPM award rule uses); Matric/Asasi (10-month) excluded —
        a past intake there = completed, a different conversation; or
      * the legacy arm: the student applied with STPM credentials (``exam_type='stpm'`` — in Form 6
        by definition; the programme currently processes post-SPM applicants, so this rarely fires).
    Clears when a ``semester_result`` field-extracts."""
    docs = _docs_or_none(application)
    if docs is None or _has_read_doc(docs, 'semester_result'):
        return False
    prof = getattr(application, 'profile', None)
    if (getattr(prof, 'exam_type', '') or '') == 'stpm':
        return True
    pathway = (getattr(application, 'chosen_pathway', '') or '').strip().lower()
    if pathway not in _MULTI_YEAR_PATHWAYS:
        return False
    # Shared with the award rule (pathway_engine.started_before_cohort) — this used to read
    # `reporting_date` directly, the same duplicated test, and so was silently wrong for the same
    # students: #123 (continuing STPM, NULL date) was never asked for his semester result.
    from ..pathway_engine import started_before_cohort
    return started_before_cohort(application)


def _doc_authenticity(doc):
    """The stored genuineness result for a document ({} when unscored)."""
    vf = getattr(doc, 'vision_fields', None)
    return (vf.get('authenticity') or {}) if isinstance(vf, dict) else {}


def slip_epf_evidence(application, member):
    """Does this member's PAYSLIP show a KWSP/EPF deduction? → 'yes' | 'no' | 'unknown'.

    The slip answers the question we were guessing at (owner, 2026-07-14). A KWSP line means the
    earner contributes, so an EPF statement exists and is worth asking for. A slip we have READ that
    shows no KWSP line means he doesn't contribute — asking for the statement would be another dead
    end, the very thing the ask-first rule exists to prevent.

    'unknown' when no slip has been scored (a legacy doc, or a read that failed): we cannot tell, so
    the caller keeps today's behaviour rather than silently dropping a legitimate ask. Only a
    POSITIVE read of a slip with no KWSP line suppresses.
    """
    seen = False
    for doc in _cluster_docs(application, member, 'salary_slip'):
        markers = ((_doc_authenticity(doc) or {}).get('markers') or {})
        if 'kwsp' not in markers:
            continue                      # unscored, or scored before the marker existed
        seen = True
        if markers.get('kwsp'):
            return 'yes'                  # any slip showing KWSP settles it
    return 'no' if seen else 'unknown'


def employed_epf_members(application):
    """Members with a salary slip but no EPF on file → the per-member OPTIONAL request for the EPF
    as standard corroboration (mirrors ``unemployment_epf_members``). Per-member so the request is
    TAGGED to that person (an EPF belongs to a specific member; a memberless request lands
    blank-tagged). Soft; never a gate.

    The ask is driven by the PAYSLIP first (owner, 2026-07-14) — the document knows, the job title
    only guesses:

      slip shows a KWSP line   → ASK. He contributes; the statement exists.
      slip read, no KWSP line  → DON'T. He doesn't contribute; the request would dead-end.
      slip not scored (legacy) → fall back to the occupation heuristic: skip an informal earner
                                 unless the student has told us he does have a payslip/EPF.

    The occupation gate is the FALLBACK now, not the rule. As the rule it meant #126's father — a
    'driver' — would never be asked for his EPF even once his payslip arrived: the same suppression
    that trapped him, biting one step later.
    """
    docs = _docs_or_none(application)
    if docs is None:
        return []
    out = []
    claimed = informal_payslip_claimed(application)
    # #117 side-finding: this loop was ('father', 'mother') only, so the per-member codes
    # guardian_epf_missing / brother_epf_missing / sister_epf_missing (already in _MEMBER_EPF_CODE)
    # were UNREACHABLE — a working sibling/guardian with a payslip but no EPF was never asked. Widen
    # to the whole roster, exactly as household_status_gaps (line ~2013) already does.
    members = ['father', 'mother']
    seen = set()
    for m in (getattr(application, 'other_family_members', None) or []):
        if isinstance(m, dict):
            role = m.get('role', '')
            if role in ('guardian', 'brother', 'sister') and role not in seen:
                seen.add(role)
                members.append(role)
    for member in members:
        occ = _member_occupation(application, member)
        if not occ or occ in _NON_EARNING_OCC:
            continue
        has_slip = docs.filter(doc_type='salary_slip', household_member__in=[member, ''],
                               superseded_at__isnull=True).exists()
        has_epf = docs.filter(doc_type='epf', household_member__in=[member, ''],
                              superseded_at__isnull=True).exists()
        if not has_slip or has_epf:
            continue
        evidence = slip_epf_evidence(application, member)
        if evidence == 'no':
            continue                      # the slip says he doesn't contribute — don't dead-end him
        if evidence == 'unknown' and member_is_informal(application, member) and not claimed:
            continue                      # can't read the slip → the old ask-first caution stands
        out.append(member)
    return out


def employed_epf_gap(application):
    """True when any employed parent has a salary slip but no EPF (boolean form of
    ``employed_epf_members``)."""
    return bool(employed_epf_members(application))
