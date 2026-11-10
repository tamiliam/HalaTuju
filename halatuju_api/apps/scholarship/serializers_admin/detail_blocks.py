"""The computed-block getters of the cockpit payload (verdict, award, agreement, household, interview, nudge and the rest)."""

from .interviews import InterviewSessionSerializer, interview_schedule_payload
from .names import _admin_name_by_email


class ServesTheDetailBlocks:
    """The computed blocks of the cockpit payload. Moved out of AdminApplicationDetailSerializer unchanged (audit A3.7)."""

    def get_officer_requests(self, obj):
        from ..services import officer_requests_state
        return officer_requests_state(obj)

    def get_disbursements(self, obj):
        from ..disbursement import disbursement_dict
        return [disbursement_dict(d) for d in obj.disbursements.all()]

    def get_has_file(self, obj):
        from ..maintenance_scope import has_file
        return has_file(obj)

    def get_maintenance_controls(self, obj):
        """S3 review M1: a PAYABLE student with no file (awarded + wallet id, not yet activated) is held
        from the COCKPIT, since no scholar file exists. `can_hold` needs the viewer (context 'admin'):
        None when the caller passed none — the screen keeps its last answer; the door re-judges."""
        from ..maintenance import can_set_substate
        admin = self.context.get('admin')
        from ..payments import may_prepare
        return {'can_set_substate': can_set_substate(obj),
                'can_hold': may_prepare(admin) if admin is not None else None}

    def get_paid_to_date(self, obj):
        from .. import payments
        return str(payments.paid_to_date(obj))

    def _verdict(self, obj):
        """Compute the four-fact verdict ONCE per serialised application — get_verdict,
        get_proposed_award_amount and get_award_disqualifier all share it."""
        cached = getattr(obj, '_cached_verdict', None)
        if cached is None:
            from ..verdict_engine import build_verdict
            cached = build_verdict(obj)
            obj._cached_verdict = cached
        return cached

    def get_proposed_award_amount(self, obj):
        from ..award import proposed_award_amount
        amount = proposed_award_amount(obj, verdict=self._verdict(obj))
        return None if amount is None else str(amount)

    def get_award_disqualifier(self, obj):
        from ..award import verdict_disqualifier
        return verdict_disqualifier(self._verdict(obj)) or None

    def get_assigned_to_corrections(self, obj):
        from ..reopen import reviewer_correction_count
        return reviewer_correction_count(obj.assigned_to)

    def get_bursary_agreement_enabled(self, obj):
        from django.conf import settings
        return bool(getattr(settings, 'BURSARY_AGREEMENT_ENABLED', False))

    def get_bursary_agreement(self, obj):
        from django.conf import settings
        if not getattr(settings, 'BURSARY_AGREEMENT_ENABLED', False):
            return None
        from ..agreement_guard import live_agreement     # A1.13: a withdrawal's voided row is none
        if (agreement := live_agreement(obj)) is None:
            return None
        from ..serializers import BursaryAgreementSerializer
        return BursaryAgreementSerializer(agreement).data

    def get_decision_reopen_reason(self, obj):
        if obj.decision_reopened_at is None:
            return ''
        from ..reopen import open_reopen
        row = open_reopen(obj)
        return row.reason if row else ''

    def get_last_decision_reopen(self, obj):
        from ..reopen import latest_reopen
        row = latest_reopen(obj)
        if row is None:
            return None
        return {
            'reopened_by': row.reopened_by,
            'reopened_by_name': _admin_name_by_email(row.reopened_by),
            'reviewer_name': row.reviewer.name if row.reviewer else '',
            'reason': row.reason,
            'created_at': row.created_at,
            'resulted_in_change': row.resulted_in_change,
        }

    def get_anomalies(self, obj):
        """S16 Phase A: deterministic pre-interview flag list. Pure rules,
        no LLM calls. Returns ``[]`` when nothing flags. Identity NRIC/name
        mismatches are deduped out (the verdict + caveat own them)."""
        from ..anomaly_engine import detect_anomalies
        return [a for a in detect_anomalies(obj)
                if a['code'] not in self._DEDUPED_ANOMALIES]

    def get_household_check(self, obj):
        """Document-vs-stated reconciliation for the cockpit income/size verified ticks
        (2026-07-15). Non-mutating: reports what the documents/roster say and whether they
        corroborate the student's stated figures — the reviewer reconciles a mismatch."""
        from .. import income_engine
        size = income_engine.household_size_accounted(obj)
        # `confirmed`: the student answered the household_size_confirm Check-2 query (Yes, the roster
        # count is right). The cockpit then shows the roster count with a tick + "Declared: M" and
        # uses it for per-capita — a non-mutating display switch, never a rewrite of the stated size.
        size = {**size, 'confirmed': obj.resolution_items.filter(
            code='household_size_confirm', resolved_by='student').exists()}
        return {
            'income': income_engine.household_income_reconciliation(obj),
            'size': size,
        }

    def get_income_shown(self, obj):
        """The per-earner income answer the cockpit reads instead of re-deriving evidence from
        document presence (TD-262 chunks 2+3). One entry per roster member code — the officer's
        panel draws a member as soon as a document is TAGGED to them, which can be someone the
        wizard never listed, so narrowing this to the declared working members would leave the
        panel without an answer for exactly the earner an officer is looking at."""
        from ..income_engine import _MEMBER_ORDER
        from ..income_shown import income_shown_map
        return income_shown_map(obj, _MEMBER_ORDER)

    def get_chosen_programme(self, obj):
        """Serve the stored chosen_programme, but fill a BLANK institution for a multi-campus
        POLY diploma from the student's live offer (the selection tree offers only a programme, so
        the offer is the sole campus source — owner 2026-07-17). Read-time so it can't go stale
        waiting for a re-run/backfill; catalogue-validated + poly-only in the helper, and it never
        overwrites a non-blank institution. The write-side merge still fills the STORED value on
        offer upload; this guarantees the cockpit is right even when that hasn't fired yet."""
        from .. import offer_pathway as op
        cp = obj.chosen_programme if isinstance(obj.chosen_programme, dict) else {}
        if (cp.get('course_id') or '').startswith('POLY-') and not (cp.get('institution') or '').strip():
            inst = op.poly_institution_from_live_offer(obj)
            if inst:
                return {**cp, 'institution': inst}
        return cp

    def get_chosen_programme_display(self, obj):
        """The {title, stream} display split (card_display.programme_split): PISMP shows the constant
        degree as the title + the bidang as the stream; STPM/Matric carry the track; else stream=''."""
        from .. import card_display
        return card_display.programme_split(obj)

    def get_interview_agenda(self, obj):
        """The interviewer's folded Check-3 agenda — anomalies + the 'needs interview' verdict
        ambers + a standing Motivation & grit section. Open Check-2 queries / doc-requests are NOT
        echoed here (owner 2026-07-06); they stay in Check-2 Outstanding. ``[{code, kind, params}]``."""
        from ..views_admin import interview_agenda_full
        return interview_agenda_full(obj)

    def get_verdict(self, obj):
        """S1 verification verdict: the four-fact rollup the coordinator audits
        (identity / academic / income / pathway). Pure deterministic engine, no
        LLM calls — mirrors get_anomalies."""
        return self._verdict(obj)

    def get_submission_review(self, obj):
        """Check 2 STEP 1: the deterministic facts ledger + completeness gaps +
        consistency flags. Pure rules, no LLM — mirrors get_verdict / get_anomalies."""
        from ..submission_review import submission_review
        return submission_review(obj)

    def get_query_sla(self, obj):
        """Check 2 STEP 2/3: the query SLA clock for the cockpit — deadline, whether it
        lapsed, open clarify-query count, days left, whether the app is ready for
        assignment, and whether it's proceeding WITH queries still open (the
        'ready-with-open-queries' reviewer flag, design §5)."""
        from ..services import is_ready_for_assignment, query_sla
        from ..check2_queries import clarify_overflow_count
        sla = query_sla(obj)
        ready = is_ready_for_assignment(obj)
        return {
            'deadline': sla['deadline'],
            'lapsed': sla['lapsed'],
            'open_count': sla['open_count'],
            'days_left': sla['days_left'],
            'ready_for_assignment': ready,
            'proceeding_with_open_queries': ready and sla['open_count'] > 0,
            # V3 (#7): higher-priority clarify gaps crowded out by the cap right now — the cockpit
            # shows "N more queries waiting" so a capped-out query is visible to the officer.
            'clarify_overflow': clarify_overflow_count(obj),
        }

    def get_funding_estimate(self, obj):
        """Check 2: the deterministic per-pathway funding-need estimate (the gap after
        government coverage) for award sizing. Pure rules, no LLM."""
        from ..funding_estimate import estimate_funding
        return estimate_funding(obj)

    def get_resolution_items(self, obj):
        """S3 resolution queue: sync the system tickets against the live verdict AND
        the Check-2 AI clarify queries, then return the OPEN items (system + officer +
        check2) so the officer sees exactly what the student still owes. Idempotent."""
        from django.db.models import Q
        from ..resolution import sync_resolution_items
        from ..check2_queries import sync_check2_queries
        from ..serializers import ResolutionItemSerializer
        sync_resolution_items(obj)
        sync_check2_queries(obj)
        # Open items (awaiting the student) PLUS items the student has answered that no
        # officer has actioned yet (status='resolved', resolved_by='student'). The latter
        # surface in the cockpit WITH their answer so the officer can review and Accept
        # (re-stamps resolved_by → officer, leaving the queue) or Ask again (reopen).
        queue = obj.resolution_items.filter(
            Q(status='open') | Q(status='resolved', resolved_by='student')
        )  # ordered -created_at
        return ResolutionItemSerializer(queue, many=True).data

    def get_completeness(self, obj):
        """Phase C: the 7-part completeness breakdown, so the admin can see
        exactly which steps a student still owes (drives the accept-gate UI)."""
        from ..services import application_completeness
        return application_completeness(obj)

    def get_consent_blockers(self, obj):
        """The exact gate that must clear before a shortlisted student can submit — the SAME
        list the consent POST enforces (missing/mismatched docs, offer-not-official, an
        incomplete section, an IC identity issue). Lets the cockpit answer "why can't this
        student submit yet?" instead of the owner guessing. Empty = ready to submit."""
        from ..services import consent_blockers
        return consent_blockers(obj)

    def get_nudge(self, obj):
        """The "you haven't submitted yet" reminder state for the cockpit button — applicable /
        sent_at / available / available_at (see nudge.nudge_state). Server is the single source
        of truth; the FE only renders it."""
        from ..nudge import nudge_state
        return nudge_state(obj)

    def get_interview_session(self, obj):
        """Phase C: the latest interview session (draft or submitted), or None."""
        session = obj.interview_sessions.first()  # ordering = -created_at
        return InterviewSessionSerializer(session).data if session else None

    def get_interview_schedule(self, obj):
        """Interview booking state + proposed slots (reviewer view → includes the
        reviewer's other-student busy times so the propose grid greys them out)."""
        return interview_schedule_payload(obj, include_reviewer_busy=True)
