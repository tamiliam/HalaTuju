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
# frontend resolves the question copy from ``scholarship.actionCentre.item.<code>``
# — the shared Action-Centre item namespace, NOT a `check2.query` namespace (which does
# not exist; corrected V5 #14).
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
    # S2 — a sibling in tertiary → which institution + course (or where they work), how funded /
    # what they earn (household burden + the not-double-funded picture). Non-sensitive clarify.
    'sibling_tertiary_funding': {'fact': 'income'},
    # A sibling still in SCHOOL → which school + what standard/form (household texture; the #130 gap
    # was that only the tertiary sibling was ever asked about). One-line, non-sensitive clarify.
    'sibling_school_detail': {'fact': 'income'},
    # Informal / self-employed earner (fisherman, hawker, e-hailing…) with no payslip/EPF on file →
    # ASK FIRST before demanding a document: does he get a payslip / contribute to EPF, and roughly
    # what does he earn a month? (owner 2026-07-08, the #130 fisherman dead-end). One clarify covers
    # every such member; a formal salary-slip/EPF request is deliberately NOT raised for them.
    'informal_income_detail': {'fact': 'income'},
    # #117 (owner 2026-07-14) — a retired / unable-to-work parent may draw a PENSION or benefit that
    # is currently invisible to the means test (retired sits in NON_EARNING → never asked). ASK FIRST:
    # does he draw a pension / benefit, and roughly how much? One clarify covers all such members; the
    # proof (a *_pension_proof_missing doc request) follows only on an explicit "yes".
    'pension_amount_unknown': {'fact': 'income'},
    # S3 — the offer letter carries no readable reporting/registration date → ask when (and
    # where) the student must report. One-line, non-sensitive, pathway-fact.
    'reporting_date_unknown': {'fact': 'pathway'},
    # Phase 2B (P7) — a roster member is 'unemployed' but no reason/since-when is captured →
    # ask why and since when (household-income texture). One clarify covers all such members.
    'unemployment_detail_unknown': {'fact': 'income'},
    # V4 — promoted human ask-themes (audit §E). One-line, non-sensitive, factual clarifies.
    'deceased_parent_detail':     {'fact': 'income'},   # a roster member is deceased
    'informal_work_detail':       {'fact': 'income'},   # a declared informal wage — own-account/employer + avg
    'household_roster_undercount':{'fact': 'income'},   # stated size > described (who else is at home?)
    'other_scholarships_followup':{'fact': 'income'},   # other scholarships listed — status/amount
    # High utility spend — POINT-BLANK, states the amount (owner 2026-07-08). Two variants: against
    # the declared income (default) OR against STR status (an STR household). Both carry params.
    'high_utility_expense':       {'fact': 'income'},   # vs declared/slip income
    'high_utility_expense_str':   {'fact': 'income'},   # vs STR status
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
    # #117 — a retired/unable PARENT who (the student confirmed) draws a pension → ask for the
    # statement. NO new doc type + NO migration: it reuses the salary_slip slot, whose extraction
    # prompt already states it accepts "a government benefit / pension statement … which counts as
    # household income too" (vision.py). Separate codes purely so the copy can say *pension
    # statement*, not *salary slip*. Clears when any income evidence for that parent appears.
    'father_pension_proof_missing': {'member': 'father', 'doc_type': 'salary_slip'},
    'mother_pension_proof_missing': {'member': 'mother', 'doc_type': 'salary_slip'},
    # S2 — every salary slip on file is older than ~3 months → ask for a current one.
    'income_doc_stale': {'doc_type': 'salary_slip'},
    # Phase 2A (P5b/D1) — a working member declared an informal wage, but the household has no
    # valid STR and no supporting doc yet → ask for ONE flexible proof (an income_support_doc:
    # employer/wage letter, bank statements, or a community/penghulu letter). Household-level,
    # uncapped — clears when declared_income_gaps() empties (a support doc arrives, or a valid STR).
    'declared_income_evidence_missing': {'doc_type': 'income_support_doc'},
    # Per-member EPF request (soft, OPTIONAL) — a member (employed with a payslip but no EPF, OR
    # 'unemployed' where an all-zeros/lapsed EPF corroborates it) has no EPF on file. Per-member so
    # the request is TAGGED to that person: an EPF belongs to a specific member, and a memberless
    # request landed the upload BLANK-tagged (the #63 leak). Clears when that member's EPF arrives.
    'father_epf_missing':   {'member': 'father', 'doc_type': 'epf'},
    'mother_epf_missing':   {'member': 'mother', 'doc_type': 'epf'},
    'guardian_epf_missing': {'member': 'guardian', 'doc_type': 'epf'},
    'brother_epf_missing':  {'member': 'brother', 'doc_type': 'epf'},
    'sister_epf_missing':   {'member': 'sister', 'doc_type': 'epf'},
    # DEPRECATED (2026-07-04) — the memberless EPF requests, replaced by the per-member codes above.
    # Kept in DOC_SPECS ONLY so an existing OPEN item auto-resolves (never re-added to proof_wanted).
    'unemployment_epf_missing': {'doc_type': 'epf'},
    'epf_statement_missing':    {'doc_type': 'epf'},
    # V4 — promoted human ask-themes (audit §E). All soft doc-requests (uncapped), gap-detected in
    # income_engine, auto-resolved when the gap clears.
    'school_leaving_cert_missing': {'doc_type': 'school_leaving_cert', 'fact': 'academic'},  # SPM-track, no slip
    'semester_result_missing':     {'doc_type': 'semester_result', 'fact': 'academic'},      # continuing student
    # Per-bill utility re-upload (owner 2026-07-08): each bill that is missing / stale / undated /
    # unreadable → its own request. Clears when a clean, current bill of that type supersedes it.
    'water_bill_recheck':       {'doc_type': 'water_bill'},
    'electricity_bill_recheck': {'doc_type': 'electricity_bill'},
    # DEPRECATED (2026-07-08) — the either-or 'neither bill' request, replaced by the two per-bill
    # recheck codes above. Kept in DOC_SPECS ONLY so an existing OPEN item auto-resolves.
    'utility_bill_missing':         {'doc_type': 'water_bill'},
}
_MEMBER_EPF_CODE = {
    'father': 'father_epf_missing', 'mother': 'mother_epf_missing',
    'guardian': 'guardian_epf_missing', 'brother': 'brother_epf_missing', 'sister': 'sister_epf_missing',
}
_MEMBER_PROOF_CODE = {
    'father': 'father_income_proof_missing', 'mother': 'mother_income_proof_missing',
    'guardian': 'guardian_income_proof_missing', 'brother': 'brother_income_proof_missing',
    'sister': 'sister_income_proof_missing',
}
# #117 — the pension-statement request per parent (only father/mother can be retired/unable here).
_MEMBER_PENSION_CODE = {
    'father': 'father_pension_proof_missing', 'mother': 'mother_pension_proof_missing',
}
# Only a PARENT slot can be blank (→ a status clarify); other-members always carry an occupation.
_PARENT_STATUS_CODE = {'father': 'father_status_unknown', 'mother': 'mother_status_unknown'}

# Priority order when capping — most material to a fundable profile first. The utility
# consistency queries sit LAST (a completeness gap matters more to a fundable profile).
_CLARIFY_ORDER = [
    # Household-income completeness first — the most material to a fundable B40 profile.
    'father_status_unknown', 'mother_status_unknown',
    'informal_income_detail',              # informal earner ask-first — replaces a dead-end doc demand
    'pension_amount_unknown',              # #117 — retired/unable parent's pension, ask-first
    'unemployment_detail_unknown',
    # V4 — income-story texture (audit §E) sits high, above the comfort items.
    'deceased_parent_detail', 'informal_work_detail', 'household_roster_undercount',
    'other_scholarships_followup',
    'course_unspecified', 'sibling_level_unknown', 'sibling_tertiary_funding',
    'sibling_school_detail',
    'reporting_date_unknown',
    'device_status_unknown', 'transport_cost_unknown',
    'utility_holder_unknown', 'utility_address_mismatch',
    'high_utility_expense', 'high_utility_expense_str',   # consumption signal, lowest priority
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
        unemployment_detail_gap, unemployment_epf_members,
        # V4 — promoted human ask-themes (audit §E).
        school_leaving_cert_gap, semester_result_gap, employed_epf_members,
        deceased_parent_detail_gap, informal_work_detail_gap, household_roster_undercount,
        other_scholarships_followup_gap,
        # Owner 2026-07-08 — informal-aware income asks + sibling-in-school clarify.
        member_is_informal, informal_income_detail_gap, informal_payslip_claimed,
        sibling_school_detail_unknown,
        # #117 (owner 2026-07-14) — retired/unable parent's pension, ask-first then proof.
        pension_context, pension_members, pension_claimed,
        # Owner 2026-07-16 — the STR route must not stop us getting the household's salary picture:
        # a FORMAL working STR-recipient parent's own salary slip is still requested.
        str_earner_income_document_gap,
        # Owner 2026-07-08 — per-bill utility recheck + point-blank high-usage query.
        utility_bill_recheck, high_utility_expense_context,
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
    if sibling_school_detail_unknown(application):      # sibling in school → school + standard/form
        gaps.add('sibling_school_detail')
    if informal_income_detail_gap(application):         # informal earner, no doc → ask-first clarify
        gaps.add('informal_income_detail')
    if pension_context(application) is not None:        # #117 — retired/unable parent → ask-first pension
        gaps.add('pension_amount_unknown')
    if offer_reporting_date_unknown(application):       # readable offer, no parseable report date
        gaps.add('reporting_date_unknown')
    if unemployment_detail_gap(application):            # 'unemployed' member, no reason/since
        gaps.add('unemployment_detail_unknown')
    # V4 — the five promoted CLARIFY themes.
    if deceased_parent_detail_gap(application):
        gaps.add('deceased_parent_detail')
    if informal_work_detail_gap(application):
        gaps.add('informal_work_detail')
    if household_roster_undercount(application):
        gaps.add('household_roster_undercount')
    if other_scholarships_followup_gap(application):
        gaps.add('other_scholarships_followup')
    # High utility spend → a POINT-BLANK student query stating the amount (owner 2026-07-08). Two
    # variants: an STR household is asked against its STR status, else against the declared income.
    high_ctx = high_utility_expense_context(application)
    if high_ctx is not None:
        gaps.add('high_utility_expense_str' if high_ctx.get('on_str') else 'high_utility_expense')
    # Full-household-income completeness: a blank-slot PARENT → a status CLARIFY; any earning roster
    # member with no income doc → a PROOF doc request (uncapped).
    proof_wanted = set()
    for g in household_status_gaps(application):
        if g['need'] == 'status':
            gaps.add(_PARENT_STATUS_CODE[g['member']])   # only father/mother reach 'status'
        elif member_is_informal(application, g['member']) and not informal_payslip_claimed(application):
            # Informal / self-employed earner: no payslip/EPF to demand (owner 2026-07-08). The
            # ASK-FIRST clarify (informal_income_detail) + the flexible income-support-doc path
            # (declared_income_evidence_missing) carry them instead of a dead-end doc request.
            #
            # UNLESS the student has told us otherwise (#126, 2026-07-13). The suppression is keyed
            # on the OCCUPATION CODE, so it used to be permanent: #126's father is a 'driver'
            # (informal), the student answered "he has a payslip, I should upload it?" — and the
            # request stayed suppressed forever. We asked, he answered, and we ignored him. Once he
            # claims a payslip, the request re-opens and the evidence chain resumes.
            pass
        else:                                            # 'proof' — a formal earner, no income doc
            proof_wanted.add(_MEMBER_PROOF_CODE[g['member']])
    # Owner 2026-07-16 — the STR settles the means test but must not silence the household's income
    # asks. A FORMAL working STR-recipient parent (retired→pension above/below, informal→ask-first
    # clarify) whose own salary slip we never requested → request it, so the sponsor profile carries
    # the complete salary picture. Soft doc request; auto-resolves once their slip/EPF lands.
    str_salary_earner = str_earner_income_document_gap(application)
    if str_salary_earner:
        proof_wanted.add(_MEMBER_PROOF_CODE[str_salary_earner])
    if stale_income_proof(application):
        proof_wanted.add('income_doc_stale')
    if declared_income_gaps(application):                # declared informal income, no STR + no doc
        proof_wanted.add('declared_income_evidence_missing')
    # Per-member EPF requests (employed-with-payslip OR unemployed) — union, one per member, TAGGED.
    for m in set(employed_epf_members(application)) | set(unemployment_epf_members(application)):
        code = _MEMBER_EPF_CODE.get(m)
        if code:
            proof_wanted.add(code)
    # #117 — a retired/unable parent whom the student CONFIRMED draws a pension (answered the
    # pension clarify "yes") → ask for the statement (reuses the salary_slip slot). Ask-first→proof
    # (#126): nothing is demanded until the student says there is a pension to evidence.
    for m in pension_members(application):
        if pension_claimed(application, m):
            proof_wanted.add(_MEMBER_PENSION_CODE[m])
    # V4 — the four promoted DOC-REQUEST themes.
    if school_leaving_cert_gap(application):
        proof_wanted.add('school_leaving_cert_missing')
    if semester_result_gap(application):
        proof_wanted.add('semester_result_missing')
    # Per-bill utility re-upload (owner 2026-07-08): each of water / electricity that is missing,
    # stale (>3mo / undated), or unreadable → its OWN re-upload request, so 'both bills, current,
    # clear' is enforced in logic (replaces the either-or utility_bill_missing).
    recheck = utility_bill_recheck(application)
    if 'water_bill' in recheck:
        proof_wanted.add('water_bill_recheck')
    if 'electricity_bill' in recheck:
        proof_wanted.add('electricity_bill_recheck')
    return gaps, proof_wanted


def _clarify_params(application, code):
    """Params frozen onto a clarify at creation so its copy can quote live figures. Only the
    high-utility queries carry any (owner 2026-07-08 — state the amount + the income/STR basis);
    every other clarify is static, so this returns {}. Computed once (a clarify is once-ever), so
    the figures reflect the bills on file when the query was raised."""
    if code in ('high_utility_expense', 'high_utility_expense_str'):
        from .income_engine import high_utility_expense_context
        ctx = high_utility_expense_context(application) or {}
        params = {}
        if ctx.get('amount') is not None:
            params['amount'] = ctx['amount']
        if code == 'high_utility_expense' and ctx.get('income') is not None:
            params['income'] = ctx['income']         # the STR variant references status, not a figure
        return params
    if code == 'informal_income_detail':
        # Name the member(s) + declared occupation the student already gave in 'My Family', so the
        # ask reflects what we know rather than a generic prompt (owner 2026-07-08).
        from .income_engine import informal_income_context
        return informal_income_context(application)
    if code == 'pension_amount_unknown':
        # #117 — name the retired/unable parent(s) so the copy is specific, not generic.
        from .income_engine import pension_context
        return pension_context(application) or {}
    return {}


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
    # "Waiting" = a clarify-able gap that could STILL be asked but is crowded out by the cap. A
    # clarify is once-ever: once an item exists (open OR already answered / waived) it is NEVER
    # re-raised (see sync_check2_queries: `code in existing → skip`). So only a gap with NO item yet
    # can be waiting — counting an ANSWERED clarify whose gap persists as "waiting" was the bug that
    # left a spurious "N more waiting" note on cases where every query was already answered (#36).
    pending = [c for c in _CLARIFY_ORDER
               if c in gaps and c != 'reporting_date_unknown' and c not in existing]
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
    # The MACHINE may only ask during the Completed stage (owner, 2026-07-13). From `interviewing`
    # onward only an officer may raise a query — the reviewer owns the case, and shouldn't be
    # competing with auto-generated questions landing in the student's Action Centre mid-interview.
    # Only CREATE / RE-OPEN is gated; the auto-resolve housekeeping below runs at every stage.
    from .services import auto_queries_allowed
    may_ask = auto_queries_allowed(application)

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
            if item is None and may_ask:         # machine asks only in the Completed stage
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
                        fact=spec.get('fact', 'income'), kind='doc',
                        doc_type=spec['doc_type'], params=params)
                    raised_student_visible = True
                except IntegrityError:
                    pass
            elif item is not None and item.status == 'resolved' and may_ask:
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
    # input of equal standing). No NEW clarify is raised outside the Completed stage. A
    # crowded-out higher-priority gap is surfaced to the officer via clarify_overflow_count().
    raised = sum(1 for r in existing.values() if r.kind == 'clarify' and r.status == 'open')
    if may_ask:
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
                    params=_clarify_params(application, code),
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

    # The one-tap household-size confirmation (the roster describes more people than the stated
    # size) — also a 'confirm' outside the clarify cap.
    if _sync_household_size_confirm(application, existing, now):
        raised_student_visible = True

    if raised_student_visible:
        # A new student-visible query/doc-request appeared after the one-time notify →
        # re-announce it via the batched hourly sweep (local import avoids a circular import).
        from .services import bump_query_notify_on_new_item
        bump_query_notify_on_new_item(application)

    return application.resolution_items.filter(source='check2', status='open')


# The pathway STUDENT queries mirrored from the verdict — both student-visible (source='check2', NOT
# in resolution.RESOLUTION_SPECS, so they never become a hidden 'system' item): 'pathway_confirm'
# (one-tap "is this where you're going?") + 'pathway_undeclared' (an ambiguous offer we can't pin —
# the student picks their exact course on the profile page). code → kind. Owner 2026-07-15.
_PATHWAY_QUERY_KINDS = {'pathway_confirm': 'confirm', 'pathway_undeclared': 'explanation'}


def _sync_pathway_confirm(application, existing, now):
    """Reconcile the Check-2 pathway student queries (``pathway_confirm`` + ``pathway_undeclared``)
    from the live verdict. Routed through Check 2 (``source='check2'``) so the flag governs
    visibility + the email; the student answers in place (Yes → ``confirm_pathway`` writes their final
    pathway for the confirm; picking a course on the profile page clears the undeclared one). The
    verdict engine detects the state; here we only mirror it into the student queue + auto-resolve
    each once the verdict no longer raises it. The verdict raises AT MOST ONE of the two at a time."""
    from .models import ApplicantDocument
    raised = False
    # Both queries require an offer letter — skip the verdict compute (and its cost) otherwise; a
    # lingering item after the offer is gone is closed below.
    verdict_params = {code: None for code in _PATHWAY_QUERY_KINDS}
    if ApplicantDocument.objects.filter(
            application=application, doc_type='offer_letter', superseded_at__isnull=True).exists():
        from .verdict_engine import build_verdict
        for fact in build_verdict(application):
            if fact['fact'] != 'pathway':
                continue
            for it in fact['unresolved']:
                if it['code'] in verdict_params:
                    verdict_params[it['code']] = it.get('params', {})
    for code, kind in _PATHWAY_QUERY_KINDS.items():
        params, item = verdict_params[code], existing.get(code)
        if params is not None and item is None:
            try:
                ResolutionItem.objects.create(
                    application=application, source='check2', code=code,
                    fact='pathway', kind=kind, params=params)
                raised = True   # a new student-visible query appeared → caller re-notifies
            except IntegrityError:
                pass  # created concurrently — fine
        elif params is None and item is not None and item.status == 'open':
            # No longer raised (confirmed / course picked / offer replaced) → close the question.
            item.status = 'resolved'
            item.resolved_by = 'system'
            item.resolved_at = now
            item.save(update_fields=['status', 'resolved_by', 'resolved_at'])
    return raised


def _sync_household_size_confirm(application, existing, now):
    """Reconcile the ``household_size_confirm`` STUDENT query (a one-tap 'confirm', like
    ``pathway_confirm``). Raised when the itemised roster OUTNUMBERS the stated household size
    (``household_size_shortfall`` — the per-capita denominator may be too small, so income looks
    overstated): we ask the student "you listed N people but entered a size of M — is N right?".

    Non-mutating: a student 'Yes' resolves the query (``resolved_by='student'``) and the cockpit then
    shows the roster count with a tick + "Declared: M" (per the household_check ``confirmed`` flag);
    we NEVER rewrite the stated size. Because confirming does not change the size, the over-count
    persists — so once the student has confirmed we must NOT re-ask (guard on the student-resolved
    item). If the over-count later disappears (the student edited their size/roster), an unanswered
    query auto-closes."""
    from .income_engine import household_size_shortfall
    hs = household_size_shortfall(application)
    item = existing.get('household_size_confirm')
    # Already answered by the student → settled; never re-ask (the over-count still exists by design).
    if item is not None and getattr(item, 'resolved_by', '') == 'student':
        return False
    if hs and item is None:
        try:
            ResolutionItem.objects.create(
                application=application, source='check2', code='household_size_confirm',
                fact='income', kind='confirm',
                params={'described': hs['described'], 'size': hs['size']})
            return True
        except IntegrityError:
            pass  # created concurrently — fine
    elif not hs and item is not None and item.status == 'open':
        item.status = 'resolved'
        item.resolved_by = 'system'
        item.resolved_at = now
        item.save(update_fields=['status', 'resolved_by', 'resolved_at'])
    return False
