"""
Check 2 — STEP 2: turn the STEP-1 submission review into a CONSOLIDATED query stream
on the existing ``ResolutionItem`` model (design ``check2-design.md`` §4).

Two kinds are added by Check 2:
  - ``clarify`` — an AI-raised, one-line, **non-sensitive** question for the STUDENT
    (Action Centre + email). Capped to the few most material so the queue doesn't
    suppress responses or burn the SLA clock.
  - ``human`` — reserved for items the AI triages to the human **reviewer**, never
    shown to the student. (The reviewer's broader suggested-questions list — the
    anomalies + interview gaps — is surfaced separately in the cockpit, so STEP 2
    does not duplicate it here.)

AI clarify queries carry ``source='check2'`` so the verdict-driven
``resolution.sync_resolution_items`` (which only reconciles ``source='system'``)
never touches them. A clarify query resolves on the student's typed answer, which
becomes a verified "resolved query answer" the profile generator may assert (§3).

**Triage (design §4).** Only *factual, one-line, non-sensitive* STEP-1 completeness
gaps become student clarify queries. Subjective / sensitive / motivational gaps
(``motivation_missing``) are the reviewer's, not the student's.
"""
from django.db import IntegrityError
from django.utils import timezone

from .models import ResolutionItem
from .submission_review import completeness_gaps

# Completeness-gap code → clarify-query spec. The gap code IS the query code (the
# frontend resolves the question copy from ``scholarship.check2.query.<code>``).
CLARIFY_SPECS = {
    'course_unspecified':     {'fact': 'pathway'},
    'sibling_level_unknown':  {'fact': 'income'},
    'device_status_unknown':  {'fact': 'other'},
    'transport_cost_unknown': {'fact': 'other'},
    # #8 — utility-bill consistency (NOT completeness gaps; sourced from the income engine
    # in `sync_check2_queries`). One-line, non-sensitive, factual → a fair student query.
    'utility_holder_unknown':   {'fact': 'income'},
    'utility_address_mismatch': {'fact': 'income'},
    # Full-household-income completeness (reviewer-query automation S1): a parent whose slot
    # is BLANK → ask their work/status (the "why one earner" question). Sourced from the income
    # engine (parent_income_gaps), not a completeness gap. The PROOF case (earning parent, no
    # payslip) is a DOC request handled separately below — uncapped (design decision #1).
    'father_status_unknown':    {'fact': 'income'},
    'mother_status_unknown':    {'fact': 'income'},
    # S2 — a sibling in tertiary → which institution + how funded / on aid (household burden +
    # the not-double-funded picture). One-line, non-sensitive → a fair student clarify.
    'sibling_tertiary_funding': {'fact': 'income'},
    # S3 — the offer letter carries no readable reporting/registration date → ask when (and
    # where) the student must report. One-line, non-sensitive, pathway-fact.
    'reporting_date_unknown': {'fact': 'pathway'},
    # 'motivation_missing' is intentionally NOT here — motivation is reviewer texture
    # (§7), not a one-line factual answer.
}

# Full-household-income PROOF requests (kind='doc') — an earning parent with no income
# document on file. Doc requests sit OUTSIDE MAX_CLARIFY (design decision #1, 2026-06-29):
# uploading a payslip is not a "question", so it never suppresses the clarify queue.
# code → {member, doc_type}. The gap clears when ANY income evidence for that parent appears.
DOC_SPECS = {
    'father_income_proof_missing': {'member': 'father', 'doc_type': 'salary_slip'},
    'mother_income_proof_missing': {'member': 'mother', 'doc_type': 'salary_slip'},
    # S2 — every salary slip on file is older than ~3 months → ask for a current one.
    'income_doc_stale': {'doc_type': 'salary_slip'},
}
_PARENT_PROOF_CODE = {'father': 'father_income_proof_missing', 'mother': 'mother_income_proof_missing'}
_PARENT_STATUS_CODE = {'father': 'father_status_unknown', 'mother': 'mother_status_unknown'}

# Priority order when capping — most material to a fundable profile first. The utility
# consistency queries sit LAST (a completeness gap matters more to a fundable profile).
_CLARIFY_ORDER = [
    # Household-income completeness first — the most material to a fundable B40 profile.
    'father_status_unknown', 'mother_status_unknown',
    'course_unspecified', 'sibling_level_unknown', 'sibling_tertiary_funding',
    'reporting_date_unknown',
    'device_status_unknown', 'transport_cost_unknown',
    'utility_holder_unknown', 'utility_address_mismatch',
]

# The student is not the reviewer: a long list suppresses responses. Cap to the few
# most material (design §4).
MAX_CLARIFY = 3


def sync_check2_queries(application):
    """Reconcile the Check-2 AI clarify queries with the live STEP-1 completeness gaps.
    Idempotent + race-safe, mirroring ``resolution.sync_resolution_items``:

      - a clarify-able gap with no item yet → create an OPEN clarify item (capped)
      - an OPEN clarify item whose gap cleared → auto-resolve it (the data arrived)
      - an answered (resolved) item → left as-is (never re-asked)

    Gated on submission (``profile_completed_at``), same as the verdict queue. Returns
    the open Check-2 items. The cap counts every clarify code ever raised, so the
    student is never asked more than ``MAX_CLARIFY`` distinct questions in total.
    """
    if application.profile_completed_at is None:
        return ResolutionItem.objects.none()

    gaps = {g['code'] for g in completeness_gaps(application)}
    # #8 — fold in the utility-bill consistency checks (same income-engine helpers the
    # officer pre-interview flags use), so a 'whose bill is this?' / 'address differs'
    # query is raised + auto-resolved on the same reconcile loop as the completeness gaps.
    from .income_engine import (
        utility_holder_unknown, utility_address_mismatch, parent_income_gaps,
        stale_income_proof, sibling_tertiary_funding_unknown,
    )
    if utility_holder_unknown(application):
        gaps.add('utility_holder_unknown')
    if utility_address_mismatch(application):
        gaps.add('utility_address_mismatch')
    # S2 — a sibling in tertiary → the funding clarify (capped, with the other clarifies).
    if sibling_tertiary_funding_unknown(application):
        gaps.add('sibling_tertiary_funding')
    # S3 — a readable offer with no parseable reporting date → ask when/where to report.
    from .pathway_engine import offer_reporting_date_unknown
    if offer_reporting_date_unknown(application):
        gaps.add('reporting_date_unknown')
    # Full-household-income completeness (S1). A blank-slot parent → a status CLARIFY (folded
    # into the capped gap set below); an earning parent with no payslip → a PROOF doc request
    # (reconciled separately, uncapped). Collect the wanted proof/doc codes here.
    proof_wanted = set()
    for g in parent_income_gaps(application):
        if g['need'] == 'status':
            gaps.add(_PARENT_STATUS_CODE[g['member']])
        else:  # 'proof'
            proof_wanted.add(_PARENT_PROOF_CODE[g['member']])
    # S2 — every salary slip is stale → an uncapped doc-request for a current one.
    if stale_income_proof(application):
        proof_wanted.add('income_doc_stale')

    existing = {r.code: r for r in application.resolution_items.filter(source='check2')}
    now = timezone.now()
    # Track whether a NEW student-visible check2 item is created this pass → re-notify (all
    # source='check2' items are student-visible when the flag is on; see views._student_visible).
    raised_student_visible = False

    # Uncapped PROOF doc-requests (design decision #1): create when wanted + absent,
    # auto-resolve when the parent's income gap clears.
    for code, spec in DOC_SPECS.items():
        if code in proof_wanted and code not in existing:
            try:
                ResolutionItem.objects.create(
                    application=application, source='check2', code=code,
                    fact='income', kind='doc', doc_type=spec['doc_type'])
                raised_student_visible = True
            except IntegrityError:
                pass
        item = existing.get(code)
        if item is not None and item.status == 'open' and code not in proof_wanted:
            item.status = 'resolved'
            item.resolved_by = 'system'
            item.resolved_at = now
            item.save(update_fields=['status', 'resolved_by', 'resolved_at'])

    raised = sum(1 for r in existing.values() if r.kind == 'clarify')
    for code in _CLARIFY_ORDER:
        if code not in gaps or code in existing:
            continue
        if raised >= MAX_CLARIFY:
            break
        try:
            ResolutionItem.objects.create(
                application=application, source='check2', code=code,
                fact=CLARIFY_SPECS[code]['fact'], kind='clarify',
            )
            raised += 1
            raised_student_visible = True
        except IntegrityError:
            pass  # created concurrently — fine

    for code, item in existing.items():
        if item.status == 'open' and item.kind == 'clarify' and code not in gaps:
            item.status = 'resolved'
            item.resolved_by = 'system'
            item.resolved_at = now
            item.save(update_fields=['status', 'resolved_by', 'resolved_at'])

    # The one-tap pathway confirmation (offer differs from the declared course) — a
    # 'confirm', NOT a clarify, so it sits outside the MAX_CLARIFY cap and the gap loop.
    if _sync_pathway_confirm(application, existing, now):
        raised_student_visible = True

    if raised_student_visible:
        # A new student-visible query/doc-request appeared after the one-time notify →
        # re-announce it via the batched hourly sweep (local import avoids a circular import).
        from .services import bump_query_notify_on_new_item
        bump_query_notify_on_new_item(application)

    return application.resolution_items.filter(source='check2', status='open')


def _sync_pathway_confirm(application, existing, now):
    """Reconcile the Check-2 ``pathway_confirm`` item (one-tap "is this offer your final
    course?") from the live verdict. Routed through Check 2 (``source='check2'``) so the
    flag governs visibility + the email and the student answers Yes in place
    (``confirm_pathway`` writes their final pathway). The clash itself is detected by the
    verdict engine; here we only mirror it into the student queue + auto-resolve it once
    the offer is confirmed or changed so it no longer clashes."""
    from .models import ApplicantDocument
    item = existing.get('pathway_confirm')
    # A clash can only exist when there's an offer letter — skip the verdict compute (and
    # its cost) otherwise. If a confirm lingers after the offer is gone, close it below.
    params = None
    if ApplicantDocument.objects.filter(application=application, doc_type='offer_letter').exists():
        from .verdict_engine import build_verdict
        for fact in build_verdict(application):
            if fact['fact'] != 'pathway':
                continue
            for it in fact['unresolved']:
                if it['code'] == 'pathway_confirm':
                    params = it.get('params', {})
    if params is not None and item is None:
        try:
            ResolutionItem.objects.create(
                application=application, source='check2', code='pathway_confirm',
                fact='pathway', kind='confirm', params=params,
            )
            return True   # a new student-visible confirm was raised → caller re-notifies
        except IntegrityError:
            pass  # created concurrently — fine
    elif params is None and item is not None and item.status == 'open':
        # The clash cleared (offer confirmed / replaced) → close the question.
        item.status = 'resolved'
        item.resolved_by = 'system'
        item.resolved_at = now
        item.save(update_fields=['status', 'resolved_by', 'resolved_at'])
    return False
