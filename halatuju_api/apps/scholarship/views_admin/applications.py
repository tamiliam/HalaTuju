"""Applications: the cockpit list, the detail read, and the officer actions on one application.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from halatuju.pagination import FlexiblePageNumberPagination
from apps.courses.search import apply_people_search
from .. import reopen as reopen_service
from ..document_snapshot import document_snapshot
from ..models import Referee, ScholarshipApplication
from ..serializers import RefereeSerializer
from ..serializers_admin import AdminApplicationDetailSerializer, AdminApplicationListSerializer
from ..services import (
    admin_reject,
    application_completeness,
    cancel_pending_decline,
    org_admin_reject,
    set_reporting_date_by_officer,
)
from ..sponsorship import hold_pending_award

from .base import _AdminBase


# ⚠ THE PACKAGE'S name, spelled out — never `__name__`. A submodule logger reads
# `apps.scholarship.views_admin.<module>` and drops every audit line it carries out
# of the Cloud Logging scrape metric. Guarded by `AuditLoggerNameTest` (H11).
logger = logging.getLogger('apps.scholarship.views_admin')


class AdminApplicationListView(_AdminBase):
    """The B40 Applications list.

    ⚠ `?programme=<code>` NARROWS; IT DOES NOT FENCE, AND IT IS RE-FENCED SERVER-SIDE.
    The breadcrumb's gift switcher is a DISPLAY preference (`lib/programmeScope`) — it travels as
    an explicit request value, never as a header or a cookie, and this view resolves the code
    inside the caller's OWN organisation before it touches an application. A client that ignores
    the parameter reaches exactly the same rows the org fence already allowed. See
    `AdminScopeListView`'s docstring for why that distinction is load-bearing.

    ⚠ AN UNKNOWN OR CROSS-TENANT CODE IS 404, NEVER "show everything". Silently dropping an
    unrecognised narrowing is precisely the defect this sprint fixes — a heading naming one gift
    over another gift's applicants. The house rule elsewhere is the same: not recognised means
    ask, never substitute.

    ⚠ OMITTED IS A REAL ANSWER and it means EVERY gift this caller may see. Reading a list is not
    deciding something, so with several gifts and no choice the honest answer is the wider one —
    unlike the configuration screens, where a wrong silent pick would EDIT the wrong gift.
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        scope = self._b40_scope(admin)
        if scope == 'none':
            return self._deny_role()   # partner has no B40 Applications access

        programme_f = (request.GET.get('programme') or '').strip()
        programme = None
        if programme_f:
            programme = self._programme_by_code(admin, programme_f)
            if programme is None:
                return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        # org-fence: _org_scoped applied immediately below (tenant wall on the list).
        qs = ScholarshipApplication.objects.select_related(
            'profile', 'cohort', 'assigned_to').order_by('-submitted_at')
        qs = self._org_scoped(qs, admin)   # tenant fence (Sprint 3a) — super sees all
        if scope == 'assigned':
            qs = qs.filter(assigned_to=admin)   # reviewer sees only their assigned applicants
        if programme is not None:
            # ⚠ REACH THROUGH THE COHORT TOO — the same predicate `programme_delete_blocker` uses.
            # `ScholarshipApplication.programme` is denormalised at first save and SET ONCE, so a
            # cohort moved between gifts leaves its old applications pointing at the OLD gift.
            # Filtering on the column alone would show a gift's own round as empty. Both sides are
            # single-valued FK chains, so this cannot multiply rows.
            qs = qs.filter(Q(programme=programme) | Q(cohort__programme=programme))
        status_f = request.GET.get('status')
        bucket_f = request.GET.get('bucket')
        source_f = request.GET.get('source')   # referring org chosen at apply
        assigned_f = request.GET.get('assigned')
        # Free-text search across name / NRIC / phone / email — digits-only for phone+NRIC,
        # and email covers notify_email too (most applicants have no contact_email). Shared
        # with the Students directory via apps.courses.search. notify_email is a direct column
        # here (no to-many join) → no distinct needed.
        qs = apply_people_search(
            qs, request.GET.get('q'),
            name='profile__name', nric='profile__nric',
            phone='profile__contact_phone', email='profile__contact_email',
            extra_email='notify_email')
        if status_f:
            qs = qs.filter(status=status_f)
        if bucket_f:
            qs = qs.filter(bucket=bucket_f)
        if source_f:
            qs = qs.filter(profile__referral_source=source_f)
        # Phase C: ?assigned=me|none|<admin_id>
        if assigned_f == 'me':
            qs = qs.filter(assigned_to=admin)
        elif assigned_f == 'none':
            qs = qs.filter(assigned_to__isnull=True)
        elif assigned_f and assigned_f.isdigit():
            qs = qs.filter(assigned_to_id=int(assigned_f))
        # Sorting (?sort=name|merit, ?dir=asc|desc). Default (no sort) = newest
        # submitted first, as before. Name sorts in the DB; merit is COMPUTED (no
        # column), so we materialise the filtered set, sort in Python, then paginate
        # the list (DRF paginates lists fine) — fine at this scale (≈100s of rows).
        sort_f = (request.GET.get('sort') or '').strip()
        desc = (request.GET.get('dir') or '').lower() == 'desc'
        paginator = FlexiblePageNumberPagination()
        if sort_f == 'name':
            qs = qs.order_by('-profile__name' if desc else 'profile__name')
            page = paginator.paginate_queryset(qs, request, view=self)
        elif sort_f == 'source':
            # The referring organisation (Source column) lives on the profile.
            qs = qs.order_by('-profile__referral_source' if desc else 'profile__referral_source')
            page = paginator.paginate_queryset(qs, request, view=self)
        elif sort_f == 'status':
            qs = qs.order_by('-status' if desc else 'status')
            page = paginator.paginate_queryset(qs, request, view=self)
        elif sort_f == 'submitted':
            # Submitted-date column. Default (no sort) is already newest-first; this lets
            # the reviewer flip to oldest-first and back.
            qs = qs.order_by('-submitted_at' if desc else 'submitted_at')
            page = paginator.paginate_queryset(qs, request, view=self)
        elif sort_f == 'merit':
            from ..serializers_admin import _application_merit_score
            rows = sorted(qs, key=lambda a: _application_merit_score(a) or 0, reverse=desc)
            page = paginator.paginate_queryset(rows, request, view=self)
        else:
            page = paginator.paginate_queryset(qs, request, view=self)
        data = AdminApplicationListSerializer(page, many=True).data
        return paginator.envelope(
            data,
            results_key='applications',
            total_count=paginator.page.paginator.count,
        )


class AdminApplicationDetailView(_AdminBase):
    def get(self, request, pk):
        # Read is role-scoped: reviewer only their assigned applicant; partner none.
        app, err = self._scoped_application(request, pk)
        if err:
            return err
        # Access audit (security item D): one structured line per applicant-record
        # open. A compromised/abusive admin scraping records produces a burst of
        # these, which a Cloud Logging alert trips (one admin reading > 30 records
        # in 10 min → email). app_id is a row pk, not PII — no name/NRIC is logged.
        admin = self.get_admin(request)
        logger.info(
            'AUDIT applicant_detail_read admin_id=%s app_id=%s',
            getattr(admin, 'id', '?'), pk,
        )
        # TD-282 — THE ONE PLACE A DOCUMENT SNAPSHOT IS OPENED. Building this payload used to
        # cost 315 database queries with no documents on file and 385 with three, because the
        # verdict, income, anomaly and blocker engines underneath each re-queried
        # `applicant_documents` every time they were asked a question. The snapshot reads them
        # once and every one of those helpers filters that list in Python instead; outside this
        # block they all behave exactly as before. It is safe here because this handler never
        # WRITES `applicant_documents`, so the list cannot go stale while it is open.
        # ⚠ THIS GET IS NOT READ-ONLY, and the first draft of this comment said it was. Building
        # the payload runs `sync_resolution_items`, which creates and resolves ResolutionItem rows
        # and can notify the student by email — driven by verdict facts that now read through
        # the snapshot. So a wrong row here would be PERSISTED AND EMAILED, not just drawn. The
        # rule is "no write to applicant_documents", and the stakes are why the ON==OFF matrix
        # in `test_document_snapshot.py` compares the FIRST open as well as the warmed one.
        with document_snapshot(app):
            return Response(AdminApplicationDetailSerializer(app).data)

    def patch(self, request, pk):
        """Admin-editable per-application flags: mentoring-candidate. Writes are
        assignment-based (super, or the admin/reviewer this application is assigned to).
        Reviewer assignment itself is the super-only audited endpoint (F7: .../assign/)."""
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        fields = []
        if 'mentoring_candidate' in request.data:
            app.mentoring_candidate = bool(request.data['mentoring_candidate'])
            fields.append('mentoring_candidate')
        # Payments D9: a super/org_admin may CORRECT the Vircle ID here (without asking the
        # student to redo the Action-Centre task). Digits-only; must pass the D9 rule (or blank
        # to clear). Restricted to super/org_admin even though _require_app_write is wider.
        if 'vircle_id' in request.data:
            if not (admin.is_super or admin.role == 'org_admin'):
                return self._deny_role()
            from .. import payments
            vid = ''.join(ch for ch in (request.data.get('vircle_id') or '') if ch.isdigit())
            if vid and not payments.valid_vircle_id(vid):
                return Response({'error': 'bad_vircle_id', 'code': 'bad_vircle_id',
                                 'reason': payments.vircle_id_error(vid)},
                                status=status.HTTP_400_BAD_REQUEST)
            # This field decides where money goes, and until 2026-07-30 a change here left NO
            # record of who made it — unlike its sibling `reporting_date_set`. Log BOTH values:
            # the correction only makes sense against what it replaced.
            if vid != (app.vircle_id or ''):
                logger.info('AUDIT vircle_id_set app_id=%s by=%s was=%s now=%s',
                            app.id, (getattr(admin, 'email', '') or '?'),
                            (app.vircle_id or '-'), (vid or '-'))
            app.vircle_id = vid
            fields.append('vircle_id')
        if fields:
            app.save(update_fields=fields)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminVerdictSummaryView(_AdminBase):
    """GET the Check-2 case summary — a short LLM briefing that narrates the (already-decided)
    verdict for the reviewer. Read-only; dark behind VERDICT_CASE_SUMMARY_ENABLED. The FE fetches
    it lazily so the detail GET is never blocked on the model call."""
    def get(self, request, pk):
        app, err = self._scoped_application(request, pk)
        if err:
            return err
        from ..verdict_narrative import verdict_case_summary
        return Response(verdict_case_summary(app))


class AdminVerifyAcceptView(_AdminBase):
    """
    POST .../<pk>/verify-accept/ — the human verification gate.

    The admin confirms a checklist (NRIC, name, results, document) against the
    uploaded MyKad. On accept we set ``profile.nric_verified`` (which LOCKS the
    NRIC — the student can no longer edit it), stamp who/when/what was confirmed,
    and advance the application ``shortlisted`` → ``accepted``.

    This is the single point where NRIC uniqueness is enforced (soft-NRIC): if
    another profile already has this NRIC *verified*, the clash is surfaced (409)
    for the admin to resolve rather than silently double-verifying. (Resolves TD-054.)
    """
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        # Must be a live pre-accept state (not already accepted/rejected/withdrawn).
        if app.status not in ('shortlisted', 'profile_complete', 'interviewing', 'interviewed'):
            return Response(
                {'error': 'Only a live shortlisted/in-review application can be accepted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # HARD completeness gate (no override): all compulsory parts must be present.
        completeness = application_completeness(app)
        if not completeness['complete']:
            return Response(
                {'error': 'This applicant has not completed every required step yet.',
                 'code': 'incomplete_profile', 'completeness': completeness},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # HARD audit gate (no override): the reviewer must have RECORDED their verdict
        # (audited the AI's four-fact verdict) before a case can be closed/accepted.
        # See the application-processing-pipeline plan, Check 3.
        if app.verdict_decided_at is None:
            return Response(
                {'error': 'Record your verdict (review the AI’s checks) before accepting.',
                 'code': 'verdict_not_recorded'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile = app.profile
        if profile is None:
            return Response({'error': 'Application has no linked profile.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Soft-NRIC uniqueness is enforced HERE (and only here). A duplicate that
        # was tolerated while unverified must be resolved before a second verify.
        from apps.courses.models import StudentProfile
        if profile.nric and StudentProfile.objects.filter(
            nric=profile.nric, nric_verified=True,
        ).exclude(pk=profile.pk).exists():
            return Response(
                {'error': 'This NRIC is already verified on another account. Resolve the duplicate first.',
                 'code': 'nric_conflict'},
                status=status.HTTP_409_CONFLICT,
            )

        # Verify-&-accept is the highest-stakes admin write: the profile flag and the
        # application status must move together (TD audit 2026-06-14). Wrap both in one
        # transaction so a failure can't strand nric_verified=True with an un-accepted app.
        with transaction.atomic():
            if not profile.nric_verified:
                profile.nric_verified = True
                profile.save(update_fields=['nric_verified'])
            # QC (2026-07): the reviewer's verify-accept ("submit verdict") lands the case in
            # 'interviewed' = AWAITING QC (was 'recommended'). QC then clears it to 'recommended'
            # (qc-decision accept) or reopens it (qc-decision reopen). The reviewer still owns
            # identity verification (nric_verified + checklist) here.
            app.status = 'interviewed'
            app.verified_at = timezone.now()
            app.verified_by = admin.email
            app.verify_checklist = request.data.get('checklist', {}) or {}
            app.save(update_fields=['status', 'verified_at', 'verified_by', 'verify_checklist'])
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminRejectView(_AdminBase):
    """POST .../<pk>/reject/ {category} — post-shortlist admin rejection (buckets 3 & 4).
    'interview'  = reviewed but not selected (allowed from shortlisted/profile_complete/
                   interviewing/interviewed) → extra-thankful email.
    'contractual' = failed post-award steps (allowed from 'recommended'/'sponsored') → generic email.
    Reviewer-gated. The engine buckets (merit/need/ineligible) are NOT settable here."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        category = request.data.get('category')
        try:
            admin_reject(app, admin, category)
        except ValueError as e:
            code = str(e)  # 'bad_status' | 'bad_category'
            msg = ('Only an accepted applicant can be declined for contractual reasons.'
                   if code == 'bad_status' and category == 'contractual'
                   else 'This applicant cannot be declined from their current status.'
                   if code == 'bad_status' else 'Unknown rejection category.')
            return Response({'error': msg, 'code': code}, status=status.HTTP_400_BAD_REQUEST)
        # Declining a REOPENED decision is a real correction (counting model B).
        reopen_service.close_reopen_with_change(app)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminOrgRejectView(_AdminBase):
    """POST .../<pk>/org-reject/ {comments} — the ORG ADMIN's drop of a stuck SHORTLISTED
    applicant (bucket 'incomplete'). Owner 2026-07-21: "rejection is a super feature; the org
    admin is the super of the organisation", so this is gated tighter than every other
    per-application write — `super` or `org_admin` ONLY. A `qc` or the assigned reviewer, both
    of whom `_require_app_write` would let through, are deliberately refused: this action is
    immediate and irreversible (no cool-off, no cancel window), and it belongs to whoever owns
    the programme, not to whoever is reviewing the case.

    `comments` is REQUIRED (400 comments_required) — a blank reason on an unrecoverable action
    would leave no record of why. Status must be 'shortlisted' (400 bad_status); the cockpit
    renders the card under the same rule (services.ORG_REJECT_FROM)."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        # Narrow _require_app_write's set (super/org_admin/qc/assignee) to the two org-super
        # roles. Mirrors the vircle_id correction guard in AdminApplicationFlagsView.
        if not (admin.is_super or admin.role == 'org_admin'):
            return self._deny_role()
        try:
            org_admin_reject(app, admin, request.data.get('comments'))
        except ValueError as e:
            code = str(e)   # 'bad_status' | 'comments_required'
            msg = ('Say why you are rejecting — the reason is recorded on the case.'
                   if code == 'comments_required'
                   else 'Only a shortlisted applicant can be rejected here.')
            return Response({'error': msg, 'code': code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminReportingDateView(_AdminBase):
    """POST .../<pk>/reporting-date/ {date: 'YYYY-MM-DD'} — record the date a student reports to
    their institution, when the offer letter carries no readable one (owner 2026-07-23).

    Exists because the date is NOT display-only: `award` sizes the bursary off the course-start
    year derived from it, `payments` gates eligibility on it, and `income_engine` asks a
    continuing student for their semester result off the same signal. A letter without a readable
    date used to leave all three silently defaulting; QC now refuses to accept such a case, and
    this is how the officer clears it.

    Gated by `_require_app_write` — super / org_admin / qc / the assigned reviewer, i.e. whoever
    can already act on the case. Narrower would recreate the deadlock the QC stop is meant to
    resolve: QC bounces the case back precisely so the REVIEWER can fill this in.

    No provenance is stored (owner: a rare one-off, not worth a column). The cockpit distinguishes
    a typed date from a documented one for free — its verified tick reads document corroboration,
    so a hand-typed date renders untick_ed — and WHO typed it is in the AUDIT log."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        try:
            set_reporting_date_by_officer(app, admin, request.data.get('date'))
        except ValueError:
            return Response({'error': 'Enter the date the student reports to their institution.',
                             'code': 'date_required'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminNudgeStudentView(_AdminBase):
    """POST .../<pk>/nudge/ — an org admin manually re-sends the "you haven't submitted yet"
    reminder to a SHORTLISTED student who has consented but not pressed the final Review &
    submit. The manual counterpart to the one-time auto nudge (send_application_nudges cron).

    Gated to super / org_admin ONLY — mirrors AdminOrgRejectView: this belongs to whoever owns
    the programme, not to a reviewer/qc whom `_require_app_write` would also admit. Refuses when
    the student isn't in the consented-but-unsubmitted state (400 not_applicable), or during the
    pre-auto window / cooldown (400 nudge_unavailable). Returns the refreshed detail so the
    cockpit re-reads `nudge` (new sent_at + cooldown)."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        if not (admin.is_super or admin.role == 'org_admin'):
            return self._deny_role()
        from ..nudge import is_applicable, nudge_state, send_nudge
        if not is_applicable(app):
            return Response(
                {'error': 'This reminder only applies to a shortlisted student who has given '
                          'consent but not yet submitted.', 'code': 'not_applicable'},
                status=status.HTTP_400_BAD_REQUEST)
        if not nudge_state(app)['available']:
            return Response(
                {'error': 'A reminder was sent recently — please wait before sending another.',
                 'code': 'nudge_unavailable'}, status=status.HTTP_400_BAD_REQUEST)
        if not send_nudge(app, manual=True):
            return Response(
                {'error': 'The reminder could not be sent — please try again.',
                 'code': 'send_failed'}, status=status.HTTP_502_BAD_GATEWAY)
        logger.info('AUDIT student_nudge app_id=%s by=%s', app.id, getattr(admin, 'email', ''))
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminCancelDeclineView(_AdminBase):
    """POST .../<pk>/cancel-decline/ — abort a scheduled-but-unrevealed decline within the
    decline cool-off (the student never saw it). Reviewer-gated. Idempotent."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        cancel_pending_decline(app)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminHoldAwardView(_AdminBase):
    """POST .../<pk>/hold-award/ — reverse an accepted-but-unconfirmed award within the award
    cool-off (the amount returns to the sponsor; the student never saw confirmation).
    Reviewer-gated. Idempotent."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        hold_pending_award(app)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminApplicationRefereeView(_AdminBase):
    """
    GET  .../<pk>/referees/  — list referees recorded for an application.
    POST .../<pk>/referees/  — coordinator records a referee at the verify-&-accept
    stage (the referee was moved out of the student flow in the Step-4 redesign).
    """
    def get(self, request, pk):
        if not self.get_admin(request):
            return self._deny()
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
        refs = Referee.objects.filter(application=app)
        return Response({'referees': RefereeSerializer(refs, many=True).data})

    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        serializer = RefereeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ref = Referee.objects.create(application=app, **serializer.validated_data)
        return Response(RefereeSerializer(ref).data, status=status.HTTP_201_CREATED)


class AdminRefereeDetailView(_AdminBase):
    """DELETE .../<pk>/referees/<ref_id>/ — remove a referee from the application."""
    def delete(self, request, pk, ref_id):
        _app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        ref = Referee.objects.filter(pk=ref_id, application_id=pk).first()
        if ref is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        ref.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
