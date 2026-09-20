"""The verdict audit: what the officer decided, the QC gate, reopening, and the metrics.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from apps.courses.models import PartnerAdmin
from .. import pool
from .. import reopen as reopen_service
from ..verdict_engine import build_verdict
from ..models import ScholarshipApplication, SponsorProfile
from ..profile_engine import generate_anon_blurb, refine_sponsor_profile
from ..serializers_admin import AdminApplicationDetailSerializer
from ..services import AssignmentError, admin_reject, assign_reviewer

from .base import _AdminBase


# ⚠ THE PACKAGE'S name, spelled out — never `__name__`. A submodule logger reads
# `apps.scholarship.views_admin.<module>` and drops every audit line it carries out
# of the Cloud Logging scrape metric. Guarded by `AuditLoggerNameTest` (H11).
logger = logging.getLogger('apps.scholarship.views_admin')


# ── S5: verdict audit / override capture ─────────────────────────────────────

_OFFICER_FACT_VALUES = {'pass', 'fail', ''}
_OFFICER_OVERALL_VALUES = {'accept', 'decline', 'hold', ''}


class AdminRecordVerdictView(_AdminBase):
    """POST .../<pk>/record-verdict/ — the officer records their four-fact verdict in
    the review cockpit. Snapshots the AI's verdict (build_verdict) as-decided + stores
    the officer's own decision + reason (the override-rate evidence). When ``finalise``
    is truthy AND a draft profile + a submitted interview exist, it also runs the Phase-D
    refine to produce the final profile in the same action (reusing AdminFinaliseProfileView's
    preconditions; never duplicates the engine). Reviewer/super only."""
    def post(self, request, pk):
        app, admin, err = self._require_open_case(request, pk)
        if err:
            return err

        raw = request.data.get('officer_verdict')
        if not isinstance(raw, dict):
            return Response({'error': 'officer_verdict object required', 'code': 'verdict_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        from ..audit import FACTS
        officer_verdict = {}
        for fact in FACTS:
            val = (raw.get(fact) or '')
            if val not in _OFFICER_FACT_VALUES:
                return Response({'error': f'bad value for {fact}', 'code': 'bad_verdict'},
                                status=status.HTTP_400_BAD_REQUEST)
            officer_verdict[fact] = val
        overall = (raw.get('overall') or '')
        if overall not in _OFFICER_OVERALL_VALUES:
            return Response({'error': 'bad overall', 'code': 'bad_verdict'},
                            status=status.HTTP_400_BAD_REQUEST)
        officer_verdict['overall'] = overall

        # Guard: a RECORDED verdict must assess all four facts (Pass/Fail). The cockpit's
        # "Save verdict & generate final profile" path used to stamp verdict_decided_at with
        # blank facts, locking the panel on an incomplete decision (app #4, 2026-06-02). This
        # single backend gate can't be bypassed by any UI.
        incomplete = [f for f in FACTS if officer_verdict[f] not in ('pass', 'fail')]
        if incomplete:
            return Response(
                {'error': 'Assess all four checks (Pass/Fail) before recording the decision.',
                 'code': 'verdict_incomplete', 'facts': incomplete},
                status=status.HTTP_400_BAD_REQUEST)

        # ⚠ STAMP THE PREDICTOR WITH ITS SNAPSHOT, IN THE SAME BREATH. The two are one fact: what
        # the AI said, and which engine said it. Splitting them (stamping elsewhere, or later)
        # re-creates the gap this exists to close — a snapshot whose generation is unknowable.
        from ..verdict_engine import VERDICT_ENGINE_VERSION
        app.ai_verdict_snapshot = build_verdict(app)
        app.ai_verdict_engine_version = VERDICT_ENGINE_VERSION
        app.officer_verdict = officer_verdict
        app.verdict_reason = (request.data.get('reason') or '').strip()
        app.verdict_decided_by = getattr(admin, 'email', '') or ''
        app.verdict_decided_at = timezone.now()
        verdict_fields = [
            'ai_verdict_snapshot', 'ai_verdict_engine_version', 'officer_verdict',
            'verdict_reason', 'verdict_decided_by', 'verdict_decided_at',
        ]

        # Standardised assistance (owner decision 2026-06-29): the amount is fixed by the
        # pathway, not chosen by the reviewer. On APPROVE, auto-apply the proposed amount —
        # but only when unset, so a SUPER's manual override (set-award endpoint) survives a
        # re-record. When the verdict confidently disqualifies (offer_not_official /
        # income_above_b40_line) the proposal is None, so award_amount STAYS unset — a super
        # may set a value if the system has erred. On DECLINE, clear it. See
        # apps.scholarship.award; reuse the verdict just snapshotted, don't recompute.
        from .. import award as award_rule
        if overall == 'accept':
            if app.award_amount is None:
                proposed = award_rule.proposed_award_amount(app, verdict=app.ai_verdict_snapshot)
                if proposed is not None:
                    app.award_amount = proposed
                    verdict_fields.append('award_amount')
        else:
            if app.award_amount is not None:
                app.award_amount = None
                verdict_fields.append('award_amount')

        # Optionally finalise the sponsor profile from the interview. The Gemini refine call runs
        # OUTSIDE the transaction (never hold a DB lock across a network call); its writes are then
        # committed atomically WITH the verdict so the two can't half-apply (TD audit 2026-06-14).
        finalise_result = None
        sp_to_save = None
        if request.data.get('finalise'):
            sp = SponsorProfile.objects.filter(application=app).first()
            if sp is None or not sp.current_markdown.strip():
                finalise_result = {'ok': False, 'code': 'no_draft'}
            else:
                session = (app.interview_sessions.filter(status='submitted')
                           .order_by('-submitted_at').first())
                if session is None:
                    finalise_result = {'ok': False, 'code': 'no_interview'}
                else:
                    result = refine_sponsor_profile(
                        app, draft=sp.current_markdown, session=session,
                        language=request.data.get('language'))
                    if 'error' in result:
                        finalise_result = {'ok': False, 'code': 'engine_error'}
                    else:
                        sp.final_markdown = result['markdown']
                        sp.final_model_used = result.get('model_used', '')
                        sp.prompt_version = result.get('prompt_version', '')
                        sp.finalised_at = timezone.now()
                        # One profile: the final IS the sponsor/pool version. Mirror it onto the
                        # pool fields so the (already PII-redacted) final is what a sponsor reads.
                        sp.anon_markdown = result['markdown']
                        sp.anon_model_used = result.get('model_used', '')
                        sp.anon_generated_at = timezone.now()
                        # PREPARE the pool card blurb now (ready for when QC clears the case)
                        # but DO NOT publish here. Publishing — the single point a student
                        # becomes sponsor-visible — is bound to the QC-Accept transition
                        # (→ 'recommended', see AdminQcDecisionView + pool.publish_profile_to_pool);
                        # a case AWAITING QC is never shown to sponsors. The blurb is still built
                        # only for a clean APPROVE, so a declined/leaking profile builds nothing.
                        leaks = pool.scan_profile_pii(
                            result['markdown'], getattr(app, 'profile', None))
                        if overall == 'accept' and not leaks:
                            # The ≤20-word CARD blurb (card-strict — stricter than the
                            # profile). Generated from the already-anonymous markdown, then
                            # backstopped by the STRICT identifier scan; on any leak/empty
                            # leave it blank so the card falls back to the course alone.
                            blurb = generate_anon_blurb(app, result['markdown'])
                            sp.anon_blurb = blurb if (
                                blurb and not pool.scan_anon_for_identifiers(
                                    blurb, getattr(app, 'profile', None))
                            ) else ''
                        sp_to_save = sp
                        # published:False ALWAYS here — QC-Accept publishes. Kept in the payload
                        # so the FE messages "ready for QC", never "published to sponsors".
                        finalise_result = {'ok': True, 'published': False, 'leaks': leaks}

        with transaction.atomic():
            app.save(update_fields=verdict_fields)
            if sp_to_save is not None:
                sp_to_save.save()
            # If this re-records a REOPENED decision, that's a real correction
            # (counting model B) — close the audit row + clear the reopened flag.
            # Publishing is NOT done here — it is bound to QC-Accept (the case re-enters
            # AWAITING QC after verify-accept, and QC re-publishes on clearance).
            reopen_service.close_reopen_with_change(app)

        data = AdminApplicationDetailSerializer(app).data
        data['finalise_result'] = finalise_result
        return Response(data)


class AdminReopenDecisionView(_AdminBase):
    """POST .../<pk>/reopen-decision/ {reason} — SUPER-ONLY. Reverse a recorded
    decision to correct a reviewer error: holds the sponsor profile from the pool
    (unpublishes), opens a DecisionReopen audit row attributed to the assigned
    reviewer, and unlocks the decision panel + reviewer dropdown. A reason is
    required (a reopen asserts a reviewer error)."""
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
        try:
            reopen_service.reopen_decision(
                app, by_admin=admin, reason=request.data.get('reason'))
        except reopen_service.ReopenError as e:
            return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminSubmitDeclineView(_AdminBase):
    """POST .../<pk>/submit-decline/ — the reviewer sends a DECLINE verdict to QC.

    The RECOMMEND path routes through verify-accept (identity + hard-completeness gate) into
    AWAITING QC. A decline has no such gate — an incomplete or failing applicant is exactly who
    gets declined — so this is the decline's lightweight equivalent: with a recorded decline
    verdict on file, move the case to 'interviewed' (AWAITING QC). QC then CONFIRMS the decline
    (→ rejected + student email, 24h cool-off) or REOPENS it (→ back to the reviewer). The
    rejection + student email happen only at QC-confirm, never here (owner 2026-07-19)."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        ov = app.officer_verdict if isinstance(app.officer_verdict, dict) else {}
        if ov.get('overall') != 'decline' or app.verdict_decided_at is None:
            return Response(
                {'error': 'Record a decline verdict before sending to QC.',
                 'code': 'no_decline_verdict'}, status=status.HTTP_400_BAD_REQUEST)
        if app.status not in ('shortlisted', 'profile_complete', 'interviewing', 'interviewed'):
            return Response(
                {'error': 'Only a live in-review application can be sent to QC.',
                 'code': 'bad_status'}, status=status.HTTP_400_BAD_REQUEST)
        app.status = 'interviewed'   # AWAITING QC (the recorded decline verdict distinguishes it)
        app.save(update_fields=['status'])
        logger.info('AUDIT submit_decline admin_id=%s app_id=%s', admin.id, pk)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminQcDecisionView(_AdminBase):
    """POST .../<pk>/qc-decision/ {decision: 'accept'|'reopen'|'reject', comments?, override_reason?} —
    the QC gate on an AWAITING-QC ('interviewed') case. QC = a `qc`-role admin or super (never
    the reviewer).
      accept → 'interviewed' → 'recommended' (the case becomes pool-eligible). SOFT FLOOR
               (V5 #5, owner decision 1): refused (400 verdict_gap_floor + the red facts) while
               any verdict fact is 'gap' — a red income fact must not reach sponsors unexamined.
               A `super` may pass the floor by providing `override_reason`, which is RECORDED
               (qc_override_reason/_by/_at) — advisory model, but the override leaves a trail.
      reopen → require `comments` (what was missing/the gaps); reopen the decision back to the
               reviewer ('interviewing', reopened banner + DecisionReopen audit) and email the
               assigned reviewer the comments.
      reject → (owner 2026-07-19) QC OUTRIGHT rejection of a recommend the QC won't uphold — the
               one-click form of today's manual reopen→decline. Require `comments` (the QC's reason,
               shared with the reviewer). Records the SAME audited trail as the manual path (a
               DecisionReopen row carrying the reason, closed as a correction) then declines as
               'interview' with the 24h QC cool-off; the reviewer gets the "rejected by QC" email
               (distinct from the "returned for revision" one)."""
    def post(self, request, pk):
        app, admin, err = self._require_qc(request, pk)
        if err:
            return err
        decision = (request.data.get('decision') or '').strip()
        if decision == 'accept':
            # The QC ACCEPT decision means "uphold the reviewer's recorded verdict". For a DECLINE
            # verdict that is a rejection, not a recommendation — QC is the second pair of eyes on
            # BOTH outcomes (owner 2026-07-19). No gap floor here (a declined case is EXPECTED to
            # have red facts) and a shorter 24h cool-off (already two-person-vetted). Bucket
            # 'interview' (reviewed but not selected); the decline email fires now, embargoed.
            ov = app.officer_verdict if isinstance(app.officer_verdict, dict) else {}
            if ov.get('overall') == 'decline':
                from datetime import timedelta
                from django.conf import settings as _settings
                hours = getattr(_settings, 'DECLINE_QC_COOLOFF_HOURS', 24)
                try:
                    admin_reject(app, admin, 'interview', cooloff=timedelta(hours=hours))
                except ValueError:
                    return Response({'error': 'This case cannot be declined from its current state.',
                                     'code': 'bad_status'}, status=status.HTTP_400_BAD_REQUEST)
                app.refresh_from_db()
                logger.info('AUDIT qc_confirm_decline admin_id=%s app_id=%s', admin.id, pk)
                return Response(AdminApplicationDetailSerializer(app).data)
            # Reporting-date stop (owner 2026-07-23): a case cannot be accepted without a settled
            # reporting date. Deliberately an ABSOLUTE stop, unlike the red-fact floor below —
            # there is no override, because the honest remedy is to record the date, not to wave
            # the case through. Three things silently default off a missing date: the bursary
            # SIZE (a continuing student is committed RM3,000 instead of RM1,000), payment
            # eligibility, and the semester-result request. QC clears it by reopening the case so
            # the reviewer can enter the date (AdminReportingDateView) — hence the box shows at
            # 'interviewing' / on a reopen, not here.
            if app.reporting_date is None:
                return Response(
                    {'error': 'This student has no reporting date. Reopen the case so the '
                              'reviewer can record it, then accept.',
                     'code': 'reporting_date_required'},
                    status=status.HTTP_400_BAD_REQUEST)
            gap_facts = [f['fact'] for f in build_verdict(app) if f['status'] == 'gap']
            update_fields = ['status']
            if gap_facts:
                override = (request.data.get('override_reason') or '').strip()
                # _require_qc already gated this endpoint to a `super` or a `qc`; either may pass
                # the red-fact floor by RECORDING a reason (owner decision 2026-07-08 — the QC
                # gains the override, previously super-only). The reason is stored + audited below.
                if not override:
                    return Response(
                        {'error': 'A verdict fact is still red — resolve it or reopen to the '
                                  'reviewer. A QC or super admin may override with a recorded reason.',
                         'code': 'verdict_gap_floor', 'facts': gap_facts},
                        status=status.HTTP_400_BAD_REQUEST)
                app.qc_override_reason = override
                app.qc_override_by = getattr(admin, 'email', '') or ''
                app.qc_override_at = timezone.now()
                update_fields += ['qc_override_reason', 'qc_override_by', 'qc_override_at']
                logger.info('AUDIT qc_gap_override admin_id=%s app_id=%s facts=%s',
                            admin.id, pk, ','.join(gap_facts))
            app.status = 'recommended'
            # Capture WHO QC-accepted (the second pair of eyes), distinct from the reviewer's
            # verdict — the cockpit shows "…accepted by {QC}". Stamped every accept (a reopen →
            # re-accept re-attributes to the accepting QC).
            app.recommended_by = getattr(admin, 'email', '') or ''
            update_fields.append('recommended_by')
            if app.stamp_first('recommended_at'):
                update_fields.append('recommended_at')
            app.save(update_fields=update_fields)
            # Publishing is bound HERE: a QC-cleared 'recommended' case is the SINGLE point a
            # student becomes sponsor-visible (the reviewer's verdict only PREPARES the profile).
            # Idempotent + PII-backstopped; a no-op if there's nothing ready to publish.
            pool.publish_profile_to_pool(app)
            logger.info('AUDIT qc_accept admin_id=%s app_id=%s', admin.id, pk)
            return Response(AdminApplicationDetailSerializer(app).data)
        if decision == 'reopen':
            comments = (request.data.get('comments') or '').strip()
            if not comments:
                return Response(
                    {'error': 'Say what was missing so the reviewer can fix it.',
                     'code': 'comments_required'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                reopen_service.reopen_decision(app, by_admin=admin, reason=comments)
            except reopen_service.ReopenError as e:
                return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
            reviewer = app.assigned_to
            if reviewer is not None and getattr(reviewer, 'email', ''):
                from ..emails import send_qc_returned_email
                name = getattr(getattr(app, 'profile', None), 'name', '') or ''
                send_qc_returned_email(
                    to_email=reviewer.email,
                    reviewer_name=getattr(reviewer, 'name', ''),
                    ref=pool.pool_ref(app.id),
                    applicant_name=name,
                    qc_comments=comments,
                )
            logger.info('AUDIT qc_reopen admin_id=%s app_id=%s', admin.id, pk)
            return Response(AdminApplicationDetailSerializer(app).data)
        if decision == 'reject':
            # QC OUTRIGHT rejection (owner 2026-07-19): the QC won't uphold the reviewer's recommend
            # and won't bounce it back — it's rejected here. Collapses today's manual two-step
            # (reopen-with-reason → decline) into one action, producing the IDENTICAL audit trail:
            # a DecisionReopen row carrying the QC's reason (rendered as "↩ Reopened by {QC} — …"),
            # closed as a real correction, then a decline bucketed 'interview' with the 24h QC
            # cool-off. The reviewer gets the "rejected by QC" email (not "returned for revision").
            comments = (request.data.get('comments') or '').strip()
            if not comments:
                return Response(
                    {'error': 'Say why you are rejecting so the reviewer has your reason.',
                     'code': 'comments_required'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                reopen_service.reopen_decision(app, by_admin=admin, reason=comments)
            except reopen_service.ReopenError as e:
                return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
            reopen_service.close_reopen_with_change(app)   # a real correction (reviewer overruled)
            from datetime import timedelta
            from django.conf import settings as _settings
            hours = getattr(_settings, 'DECLINE_QC_COOLOFF_HOURS', 24)
            try:
                admin_reject(app, admin, 'interview', cooloff=timedelta(hours=hours))
            except ValueError:
                return Response({'error': 'This case cannot be rejected from its current state.',
                                 'code': 'bad_status'}, status=status.HTTP_400_BAD_REQUEST)
            app.refresh_from_db()
            reviewer = app.assigned_to
            if reviewer is not None and getattr(reviewer, 'email', ''):
                from ..emails import send_qc_rejected_email
                name = getattr(getattr(app, 'profile', None), 'name', '') or ''
                send_qc_rejected_email(
                    to_email=reviewer.email,
                    reviewer_name=getattr(reviewer, 'name', ''),
                    ref=pool.pool_ref(app.id),
                    applicant_name=name,
                    qc_comments=comments,
                )
            logger.info('AUDIT qc_reject admin_id=%s app_id=%s', admin.id, pk)
            return Response(AdminApplicationDetailSerializer(app).data)
        return Response({'error': 'bad_decision', 'code': 'bad_decision'},
                        status=status.HTTP_400_BAD_REQUEST)


class AdminCancelReopenView(_AdminBase):
    """POST .../<pk>/cancel-reopen/ — SUPER-ONLY. Close a reopen with NO change:
    restore the profile to its prior published state and re-lock the panel. Does
    NOT count as a reviewer correction (counting model B)."""
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
        try:
            reopen_service.cancel_reopen(app)
        except reopen_service.ReopenError as e:
            return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminVerdictMetricsView(_AdminBase):
    """GET .../verdict-metrics/?cohort=<id> — the override-rate roll-up ("how good is
    the AI"): across applications whose verdict the officer has recorded, how often did
    the human disagree with the AI's assertion, per fact. Read-only aggregate; any admin."""
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        from ..audit import override_metrics
        # org-fence: _org_scoped applied below (fences the metrics roll-up).
        qs = (ScholarshipApplication.objects
              .filter(verdict_decided_at__isnull=False)
              .only('ai_verdict_snapshot', 'ai_verdict_engine_version',
                    'officer_verdict', 'cohort_id'))
        qs = self._org_scoped(qs, admin)   # super global
        cohort = request.query_params.get('cohort')
        if cohort:
            qs = qs.filter(cohort_id=cohort)
        # ⚠ TRIPLES, NOT PAIRS — the engine version rides with the prediction it produced, so the
        # roll-up can say which generations it is averaging (`engine_versions` in the response).
        rows = ((a.ai_verdict_snapshot, a.officer_verdict, a.ai_verdict_engine_version) for a in qs)
        return Response(override_metrics(rows))


class AdminAssignReviewerView(_AdminBase):
    """POST .../applications/<pk>/assign/ — (re)assign a reviewer (F7). SUPER or the
    organisation's ORG_ADMIN, audited. Body `{reviewer_id}` (null/''/0 = unassign). The
    first assignment of an unassigned app is gated on is_ready_for_assignment; reassign/
    unassign of an already-assigned app is allowed any time. Every change writes an
    AssignmentEvent. The application is org-fenced via _scoped_application; a non-super
    caller may only assign an ACTIVE reviewer in their OWN org (never a super, never
    cross-org)."""

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (self.has_role(admin, 'super') or admin.role == 'org_admin'):
            return self._deny_role()
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err

        reviewer_id = request.data.get('reviewer_id')
        reviewer = None
        if reviewer_id not in (None, '', 0):
            reviewer = PartnerAdmin.objects.filter(pk=reviewer_id, is_active=True).first()
            if reviewer is None:
                return Response({'error': 'No such active admin.', 'code': 'bad_assignee'},
                                status=status.HTTP_400_BAD_REQUEST)
            if not self.has_role(admin, 'super') and (
                    reviewer.role != 'reviewer'
                    or reviewer.owning_organisation_id != admin.owning_organisation_id):
                # An org_admin assigns only their OWN org's reviewers — never a super, a
                # cross-org target, or a senior role. Same shape as an unknown assignee.
                return Response({'error': 'No such active admin.', 'code': 'bad_assignee'},
                                status=status.HTTP_400_BAD_REQUEST)
        try:
            assign_reviewer(app, reviewer=reviewer, by_admin=admin)
        except AssignmentError as e:
            return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(app).data)
