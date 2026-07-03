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
    # Phase 2B (P7) — a roster member is 'unemployed' but no reason/since-when is captured →
    # ask why and since when (household-income texture). One clarify covers all such members.
    'unemployment_detail_unknown': {'fact': 'income'},
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
    # Phase 2C (P2) — the same PROOF request generalised to a working non-parent roster earner
    # (guardian / elder brother / elder sister): the sponsor counts the FULL household income.
    'guardian_income_proof_missing': {'member': 'guardian', 'doc_type': 'salary_slip'},
    'brother_income_proof_missing': {'member': 'brother', 'doc_type': 'salary_slip'},
    'sister_income_proof_missing': {'member': 'sister', 'doc_type': 'salary_slip'},
    # S2 — every salary slip on file is older than ~3 months → ask for a current one.
    'income_doc_stale': {'doc_type': 'salary_slip'},
    # Phase 2A (P5b/D1) — a working member declared an informal wage, but the household has no
    # valid STR and no supporting doc yet → ask for ONE flexible proof (an income_support_doc:
    # employer/wage letter, bank statements, or a community/penghulu letter). Household-level,
    # uncapped — clears when declared_income_gaps() empties (a support doc arrives, or a valid STR).
    'declared_income_evidence_missing': {'doc_type': 'income_support_doc'},
    # Phase 2B (P7) — an 'unemployed' member has no EPF on file → a soft, OPTIONAL request to
    # upload it (an all-zeros / lapsed EPF corroborates the unemployment). Uncapped; clears when
    # every unemployed member has an EPF (or none are unemployed). Never a gate.
    'unemployment_epf_missing': {'doc_type': 'epf'},
}
_MEMBER_PROOF_CODE = {
    'father': 'father_income_proof_missing', 'mother': 'mother_income_proof_missing',
    'guardian': 'guardian_income_proof_missing', 'brother': 'brother_income_proof_missing',
    'sister': 'sister_income_proof_missing',
}
# Only a PARENT slot can be blank (→ a status clarify); other-members always carry an occupation.
_PARENT_STATUS_CODE = {'father': 'father_status_unknown', 'mother': 'mother_status_unknown'}

# Priority order when capping — most material to a fundable profile first. The utility
# consistency queries sit LAST (a completeness gap matters more to a fundable profile).
_CLARIFY_ORDER = [
    # Household-income completeness first — the most material to a fundable B40 profile.
    'father_status_unknown', 'mother_status_unknown',
    'unemployment_detail_unknown',
    'course_unspecified', 'sibling_level_unknown', 'sibling_tertiary_funding',
    'reporting_date_unknown',
    'device_status_unknown', 'transport_cost_unknown',
    'utility_holder_unknown', 'utility_address_mismatch',
]

# The student is not the reviewer: a long list suppresses responses. Cap to the few
# most material (design §4).
MAX_CLARIFY = 3


def _gap_sets(application):
    """The current STEP-1 completeness gap set + the per-member proof-wanted set — the shared,
    side-effect-free computation behind ``sync_check2_queries`` and ``clarify_overflow_count``.
    ``gaps`` = clarify-able + status codes; ``proof_wanted`` = the (uncapped) doc-request codes."""
    from .income_engine import (
        utility_holder_unknown, utility_address_mismatch, household_status_gaps,
        stale_income_proof, sibling_tertiary_funding_unknown, declared_income_gaps,
        unemployment_detail_gap, unemployment_epf_gap,
    )
    from .pathway_engine import offer_reporting_date_unknown
    gaps = {g['code'] for g in completeness_gaps(application)}
    # Utility-bill consistency (whose bill / address differs) — same helpers the officer flags use.
    if utility_holder_unknown(application):
        gaps.add('utility_holder_unknown')
    if utility_address_mismatch(application):
        gaps.add('utility_address_mismatch')
    if sibling_tertiary_funding_unknown(application):   # sibling in tertiary → funding clarify
        gaps.add('sibling_tertiary_funding')
    if offer_reporting_date_unknown(application):       # readable offer, no parseable report date
        gaps.add('reporting_date_unknown')
    if unemployment_detail_gap(application):            # 'unemployed' member, no reason/since
        gaps.add('unemployment_detail_unknown')
    # Full-household-income completeness: a blank-slot PARENT → a status CLARIFY; any earning roster
    # member with no income doc → a PROOF doc request (uncapped).
    proof_wanted = set()
    for g in household_status_gaps(application):
        if g['need'] == 'status':
            gaps.add(_PARENT_STATUS_CODE[g['member']])   # only father/mother reach 'status'
        else:                                            # 'proof' — any roster earner
            proof_wanted.add(_MEMBER_PROOF_CODE[g['member']])
    if stale_income_proof(application):
        proof_wanted.add('income_doc_stale')
    if declared_income_gaps(application):                # declared informal income, no STR + no doc
        proof_wanted.add('declared_income_evidence_missing')
    if unemployment_epf_gap(application):                # 'unemployed' member, no EPF (optional)
        proof_wanted.add('unemployment_epf_missing')
    return gaps, proof_wanted


def clarify_overflow_count(application):
    """V3 (#7): how many clarify-able gaps are currently CROWDED OUT by the ``MAX_CLARIFY`` cap
    — surfaced as a cockpit note ("N more queries waiting") so a capped-out higher-priority query
    is visible to the officer. 0 before submit, once querying is locked, or when nothing is
    crowded out. ``reporting_date_unknown`` is uncapped, so it never counts as crowded out."""
    from .services import querying_locked
    if application.profile_completed_at is None or querying_locked(application):
        return 0
    gaps, _ = _gap_sets(application)
    existing = {r.code: r for r in
                application.resolution_items.filter(source='check2', kind='clarify')}
    open_now = sum(1 for r in existing.values() if r.status == 'open')
    slots = max(MAX_CLARIFY - open_now, 0)
    pending = [c for c in _CLARIFY_ORDER
               if c in gaps and c != 'reporting_date_unknown'
               and (c not in existing or existing[c].status != 'open')]
    return max(len(pending) - slots, 0)


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

    # V3 (#6): once the interview is concluded the case is LOCKED — no NEW queries may be raised
    # (and no notify email may invite an answer the resolve endpoint now refuses). We still run the
    # reconcile so an already-open item whose gap cleared auto-resolves (housekeeping), but every
    # CREATE / RE-OPEN below is gated on `not locked`. Existing doc requests stay answerable (an
    # upload still resolves them); only clarifies close post-lock — see decisions.md.
    from .services import querying_locked
    locked = querying_locked(application)

    gaps, proof_wanted = _gap_sets(application)

    existing = {r.code: r for r in application.resolution_items.filter(source='check2')}
    now = timezone.now()
    # Track whether a NEW student-visible check2 item is created this pass → re-notify (all
    # source='check2' items are student-visible when the flag is on; see views._student_visible).
    raised_student_visible = False

    # Uncapped PROOF doc-requests (design decision #1): create when wanted + absent,
    # auto-resolve when the parent's income gap clears. V2 (#4): these are DOC-KIND items and are
    # RE-RAISABLE — a resolved doc-request whose gap RE-FIRES (a stale slip replaced by another
    # stale one; the proof removed) is re-opened, not left silently closed. (Only doc-kind items;
    # the CLARIFY queries below stay once-ever — a typed answer isn't re-asked.)
    for code, spec in DOC_SPECS.items():
        item = existing.get(code)
        if code in proof_wanted:
            if item is None and not locked:      # V3 (#6): no NEW request post-lock
                try:
                    # V1 (F2/F3): member-tag the doc request so the Action-Centre upload lands
                    # tagged to the RIGHT household member. Without this, a model doc-request stored
                    # no `household_member` (unlike officer requests), so on the SALARY route the
                    # upload landed BLANK-tagged — it could never count as that member's evidence
                    # (`_cluster_docs` is strict-tag on salary) yet auto-resolved by doc_type and was
                    # never re-asked (~29 blank-tagged prod docs, the "Earner's IC" mislabel root).
                    # The FE (ActionCentre.tsx onFile) already forwards item.params.household_member.
                    params = {'household_member': spec['member']} if spec.get('member') else {}
                    ResolutionItem.objects.create(
                        application=application, source='check2', code=code,
                        fact='income', kind='doc', doc_type=spec['doc_type'], params=params)
                    raised_student_visible = True
                except IntegrityError:
                    pass
            elif item is not None and item.status == 'resolved' and not locked:
                # V2 (#4): the gap re-fired after a resolve → RE-OPEN and re-notify. Clears the
                # stale resolving doc/text so the student is asked for a fresh one. V3 (#6): not
                # post-lock — a concluded case doesn't re-ask.
                item.status = 'open'
                item.resolved_by = ''
                item.resolved_at = None
                item.resolution_text = ''
                item.resolution_doc = None
                item.save(update_fields=['status', 'resolved_by', 'resolved_at',
                                         'resolution_text', 'resolution_doc'])
                raised_student_visible = True
        elif item is not None and item.status == 'open':
            item.status = 'resolved'                 # auto-resolve always (housekeeping, even locked)
            item.resolved_by = 'system'
            item.resolved_at = now
            item.save(update_fields=['status', 'resolved_by', 'resolved_at'])

    # V3 (#7): the clarify cap now counts only CONCURRENTLY OPEN clarifies (a waived/resolved one
    # frees a slot), so a few soft queries can't PERMANENTLY crowd out a higher-priority
    # income-story question. reporting_date_unknown is carved OUT of the cap (a sponsor-profile
    # input of equal standing). V3 (#6): no NEW clarify is raised once querying is locked. A
    # crowded-out higher-priority gap is surfaced to the officer via clarify_overflow_count().
    raised = sum(1 for r in existing.values() if r.kind == 'clarify' and r.status == 'open')
    if not locked:
        for code in _CLARIFY_ORDER:
            if code not in gaps or code in existing:
                continue
            uncapped = (code == 'reporting_date_unknown')
            if not uncapped and raised >= MAX_CLARIFY:
                continue          # crowded out — the cockpit note flags it; keep scanning for the
                                  # uncapped reporting_date_unknown, which must never be crowded out
            try:
                ResolutionItem.objects.create(
                    application=application, source='check2', code=code,
                    fact=CLARIFY_SPECS[code]['fact'], kind='clarify',
                )
                if not uncapped:
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
