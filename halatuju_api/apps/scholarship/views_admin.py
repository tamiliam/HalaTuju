"""
MyNadi admin API for the B40 Assistance Programme (Sprint 6a).

Reuses the existing PartnerAdmin auth (super admin sees all). Routes live under
/api/v1/admin/scholarship/ — covered by the NRIC-gate /admin/ whitelist;
PartnerAdminMixin does the real authorisation.
"""
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.pagination import FlexiblePageNumberPagination

from apps.courses.models import PartnerAdmin
from apps.courses.search import apply_people_search
from apps.courses.views_admin import PartnerAdminMixin

from . import pool
from . import reopen as reopen_service
from . import disbursement as disbursement_service
from . import maintenance as maintenance_service
from . import closure as closure_service
from .anomaly_engine import detect_anomalies
from .emails import send_request_info_email
from .verdict_engine import build_verdict
from .models import (
    ApplicantDocument, Disbursement, GraduationMessage, InterviewSession, InterviewSlot,
    OrgRequest, Referee, ReviewerProfile, ScholarshipApplication, Sponsor, SponsorProfile,
    Sponsorship,
)
from . import scheduling
from .profile_engine import generate_anon_blurb, refine_sponsor_profile
from . import in_programme as in_programme_service
from .serializers import ApplicantDocumentSerializer, RefereeSerializer
from .serializers_admin import (
    AdminApplicationDetailSerializer,
    AdminApplicationListSerializer,
    AdminGraduationMessageSerializer,
    InterviewSessionSerializer,
    interview_schedule_payload,
    OrgRequestOrgSerializer,
    OrgRequestOwnerSerializer,
    ReviewerProfileSerializer,
    SponsorProfileSerializer,
)
from .services import (
    AssignmentError, admin_reject, application_completeness, assign_reviewer,
    cancel_pending_decline, org_admin_reject, set_reporting_date_by_officer,
    submit_interview,
)
from .sponsorship import hold_pending_award

logger = logging.getLogger(__name__)

# '' = an in-progress finding: the reviewer typed a one-line "what you found" but
# hasn't classified it (resolved/still_unclear/new_concern). The cockpit produces this
# for any gap whose verdict button wasn't clicked — rejecting it 400'd the whole
# Save-draft and lost the reviewer's notes. A draft finding may carry just a rationale.
_VALID_VERDICTS = {'', 'resolved', 'still_unclear', 'new_concern', 'deleted'}
_RATIONALE_MAX = 140


class _AdminBase(PartnerAdminMixin, APIView):
    """Shared 403-if-not-admin guard + own-application lookup."""

    def _deny(self):
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

    def _deny_role(self):
        return Response({'error': 'Your admin role cannot perform this action.'},
                        status=status.HTTP_403_FORBIDDEN)

    def _require_reviewer(self, request):
        """Auth prologue for reviewer-gated admin WRITES: returns ``(admin, None)`` when the
        caller is an active admin with the reviewer role, else ``(None, error_response)``.
        Centralises the get_admin + reviewer-role check (TD audit 2026-06-14) so a write
        endpoint can't silently forget the role gate and under-protect PII/consent actions
        (a plain 'admin' has full B40 scope but is read-only — the role check is the guard)."""
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not self.has_role(admin, 'reviewer'):
            return None, self._deny_role()
        return admin, None

    def _get_application(self, pk):
        # org-fence: the shared lookup; every caller re-gates via _org_allows /
        # _scoped_application / _require_app_write / _require_qc before use.
        return ScholarshipApplication.objects.select_related('profile', 'cohort').filter(pk=pk).first()

    def _b40_scope(self, admin):
        """B40 Applications access by role:
          'all'      — super + admin + qc + org_admin (see every application in scope, read)
          'assigned' — reviewer (only the applicants assigned to them)
          'none'     — partner / finance / anyone else (B40 is not their page)
        'all' is org-fenced downstream by _org_scoped/_org_allows (super global; the rest
        see only their own org). qc + org_admin are org-wide WRITERS via _can_review_app
        (review-all within their org); a plain 'admin' stays assigned-only for writes.

        `finance` is 'none' BY DECISION (role matrix 2026-07-23), not by omission: it never
        sees an applicant file, document, income figure or verdict. Its only student data is
        the award/paid/remaining/eWallet allowlist served by the Payments funding summary,
        which is a Payments endpoint and does not read this scope.
        """
        if admin is None or admin.role in ('partner', 'finance'):
            return 'none'
        if self.has_role(admin, 'admin') or admin.role in ('qc', 'org_admin'):  # super + admin + qc + org_admin
            return 'all'
        if admin.role == 'reviewer':
            return 'assigned'
        return 'none'

    # ── Organisation fence (platform Sprint 3a) ────────────────────────────────
    # The tenant wall on the B40 admin surface. Access control keys off
    # PartnerAdmin.owning_organisation (NOT the referral `org`). Invisible while
    # BrightPath is the only organisation (every staff/application pair is same-org),
    # and the real fence the moment a second organisation exists. NULL owning_org is
    # a safe degenerate bucket (=None → IS NULL) so bare test fixtures self-partition.
    def _org_scoped(self, qs, admin, field='owning_organisation_id'):
        """Fence an applications queryset (or any model reaching an application by
        ``field``, e.g. 'application__owning_organisation_id') to the caller's
        organisation. Super is global; everyone else is filtered to their own org."""
        if admin is not None and self.has_role(admin, 'super'):
            return qs
        org_id = admin.owning_organisation_id if admin is not None else None
        return qs.filter(**{field: org_id})

    def _org_allows(self, admin, app):
        """Row-level org fence: True if this admin's organisation owns ``app``.
        Super is global; everyone else must match owning_organisation. A cross-org
        answer must surface as 404 (never 403) so existence isn't leaked."""
        if admin is None or app is None:
            return False
        if self.has_role(admin, 'super'):
            return True
        return app.owning_organisation_id == admin.owning_organisation_id

    def _scoped_application(self, request, pk):
        """The application IFF this admin may access it (reviewer assignment-scoped;
        partner none). Returns (app, error_response|None)."""
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        scope = self._b40_scope(admin)
        if scope == 'none':
            return None, self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if not self._org_allows(admin, app):
            # Cross-org: 404, not 403 — don't leak that another org's app exists.
            return None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if scope == 'assigned' and app.assigned_to_id != admin.id:
            return None, self._deny_role()   # reviewer, not assigned to them
        return app, None

    def _can_review_app(self, admin, app):
        """True if this admin may WRITE (review-act) on this application:
          super              — acts on any application;
          org_admin / qc     — act on ANY application in their OWN org (org_admin = the
                               organisation superadmin; qc = the hybrid review-all role);
          admin / reviewer   — act ONLY on applications ASSIGNED to them;
          partner            — never.
        (Assignment-based review permission, 2026-07 — a plain 'admin' has full READ scope
        via _b40_scope='all' but assigned-only WRITE, so a view-all admin can be given a
        selective review remit. org_admin/qc write across the org is safe because the QC
        recorder guard in _require_qc stops anyone QC-ing a verdict they themselves recorded.
        `finance` never reaches here: its _b40_scope is 'none', so the first test refuses it.)"""
        if admin is None or app is None:
            return False
        if self._b40_scope(admin) == 'none':          # partner / non-B40
            return False
        if self.has_role(admin, 'super'):
            return True
        if not self._org_allows(admin, app):          # cross-org (Sprint 3a)
            return False
        if admin.role in ('org_admin', 'qc'):         # org-wide write (same-org guaranteed above)
            return True
        return app.assigned_to_id == admin.id

    def _require_app_write(self, request, pk):
        """Auth prologue for a per-application WRITE. Returns (app, admin, None) when the caller
        may act on this application (super, or the assigned admin/reviewer), else
        (None, None, error_response). Replaces the old _require_reviewer + _scoped_application
        pair for per-application mutations (the role-only _require_reviewer stays for the few
        non-application writes: sponsor review, graduation review, reviewer profile)."""
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        app = self._get_application(pk)
        if app is None:
            return None, None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if not self._org_allows(admin, app):
            # Cross-org: 404 (don't leak existence). Distinct from the 403 below, which
            # is a SAME-org app the caller simply isn't assigned to.
            return None, None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if not self._can_review_app(admin, app):
            return None, None, self._deny_role()
        return app, admin, None

    def _require_qc(self, request, pk):
        """Auth prologue for the QC gate. Returns (app, admin, None) when the caller may QC this
        application — a `super` or a `qc`-role admin, and the app is in the AWAITING-QC stage
        (`interviewed`) — else (None, None, error_response). QC is deliberately NOT assignment-
        scoped (it checks a reviewer's work across the queue) and is distinct from reviewer writes.

        Self-QC guard: the senior `qc`/`org_admin` roles can also REVIEW their assigned cases, so
        they must NOT QC a case they were the assigned reviewer of — that routes to another QC /
        super. (Super is the owner override and is exempt.)

        `finance` is refused by the role list below — it is a money checker, not a case checker,
        and has no B40 scope to QC with."""
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not (self.has_role(admin, 'super') or admin.role in ('qc', 'org_admin')):
            return None, None, self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return None, None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if not self._org_allows(admin, app):
            # Cross-org QC: 404, don't leak existence (super is exempt via _org_allows).
            return None, None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if app.status != 'interviewed':
            return None, None, Response(
                {'error': 'This case is not awaiting QC.', 'code': 'not_awaiting_qc'},
                status=status.HTTP_400_BAD_REQUEST)
        if not self.has_role(admin, 'super') and app.assigned_to_id == admin.id:
            return None, None, Response(
                {'error': 'You reviewed this case — it must be QC-checked by someone else.',
                 'code': 'self_qc_forbidden'}, status=status.HTTP_403_FORBIDDEN)
        # Recorder guard (2026-07-15): with org_admin/qc able to record a verdict on ANY
        # own-org case, assignment no longer proves who recorded it. Two-person control
        # (models.py:482) means the person who RECORDED the verdict must never QC it —
        # match on the recorder's email (the stable staff key). Super is the owner override.
        recorder = (app.verdict_decided_by or '').strip().lower()
        if not self.has_role(admin, 'super') and recorder and recorder == (getattr(admin, 'email', '') or '').strip().lower():
            return None, None, Response(
                {'error': 'You recorded this verdict — it must be QC-checked by someone else.',
                 'code': 'self_verdict_qc_forbidden'}, status=status.HTTP_403_FORBIDDEN)
        return app, admin, None


class AdminApplicationListView(_AdminBase):
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        scope = self._b40_scope(admin)
        if scope == 'none':
            return self._deny_role()   # partner has no B40 Applications access
        # org-fence: _org_scoped applied immediately below (tenant wall on the list).
        qs = ScholarshipApplication.objects.select_related(
            'profile', 'cohort', 'assigned_to').order_by('-submitted_at')
        qs = self._org_scoped(qs, admin)   # tenant fence (Sprint 3a) — super sees all
        if scope == 'assigned':
            qs = qs.filter(assigned_to=admin)   # reviewer sees only their assigned applicants
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
            from .serializers_admin import _application_merit_score
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
            from . import payments
            vid = ''.join(ch for ch in (request.data.get('vircle_id') or '') if ch.isdigit())
            if vid and not payments.valid_vircle_id(vid):
                return Response({'error': 'bad_vircle_id', 'code': 'bad_vircle_id'},
                                status=status.HTTP_400_BAD_REQUEST)
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
        from .verdict_narrative import verdict_case_summary
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
        from .nudge import is_applicable, nudge_state, send_nudge
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


class AdminRunVisionView(_AdminBase):
    """
    POST .../<pk>/documents/<doc_id>/re-run-vision/ — re-run a document's automatic
    read. **IC / parent-IC** → MyKad OCR (identity soft signal). **Supporting docs**
    (results slip, income proofs, bills, offer letter) → the soft name/address match
    PLUS the doc-assist field extraction — i.e. the results-slip **GRADES** read (S2).
    This is an admin action and **FORCES** the (billable) extraction regardless of the
    cost knob / hourly throttle (the admin clicked it deliberately). The verify-&-accept
    stays the real identity gate. Returns the updated document.
    """
    def post(self, request, pk, doc_id):
        # Re-running a (billable) document read is a reviewer-gated WRITE action — it was
        # previously only scope-checked, letting a read-only admin trigger it (TD audit 2026-06-14).
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        # org-fence: parent application already fenced by _require_app_write above.
        doc = ApplicantDocument.objects.filter(pk=doc_id, application_id=pk).first()
        if doc is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # Shared with the bulk reextract command so the per-doc + batch reads can't drift.
        from .reextract import reextract_document
        if not reextract_document(doc):
            return Response({'error': 'This document type has no automatic check to re-run.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(ApplicantDocumentSerializer(doc).data)


class AdminGenerateProfileView(_AdminBase):
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        # Optional output language ('en'/'ms'); defaults to the applicant's locale.
        # Shared store path (Check 2 STEP 3): same as the auto-trigger, with claim-gating.
        from .services import generate_ready_profile
        sp, error = generate_ready_profile(app, language=request.data.get('language'))
        if error is not None:
            return Response({'error': error}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(SponsorProfileSerializer(sp).data)


class AdminFinaliseProfileView(_AdminBase):
    """Phase D: POST .../<pk>/finalise-profile/ — second Gemini pass that refines the
    existing draft profile with the SUBMITTED interview's findings → ``final_markdown``.
    Reviewer-gated, admin-on-demand. Requires both a draft and a submitted interview."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        sp = SponsorProfile.objects.filter(application=app).first()
        if sp is None or not sp.current_markdown.strip():
            return Response({'error': 'Draft a profile first.', 'code': 'no_draft'},
                            status=status.HTTP_400_BAD_REQUEST)
        session = app.interview_sessions.filter(status='submitted').order_by('-submitted_at').first()
        if session is None:
            return Response({'error': 'Submit an interview first.', 'code': 'no_interview'},
                            status=status.HTTP_400_BAD_REQUEST)
        result = refine_sponsor_profile(
            app, draft=sp.current_markdown, session=session,
            language=request.data.get('language'))
        if 'error' in result:
            return Response({'error': result['error']}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        sp.final_markdown = result['markdown']
        sp.final_model_used = result.get('model_used', '')
        sp.prompt_version = result.get('prompt_version', '')
        sp.finalised_at = timezone.now()
        sp.save()
        return Response(SponsorProfileSerializer(sp).data)


class AdminPublishAnonProfileView(_AdminBase):
    """Phase E2: POST .../<pk>/anon-profile/publish/ {publish: true|false} — the
    human gate that makes the anonymous profile visible in the sponsor pool (with
    an active share consent). Reviewer-gated. Requires a generated anon profile."""
    def post(self, request, pk):
        _app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        sp = SponsorProfile.objects.filter(application_id=pk).first()
        if sp is None or not sp.anon_markdown.strip():
            return Response({'error': 'Generate an anonymous profile first.', 'code': 'no_anon'},
                            status=status.HTTP_400_BAD_REQUEST)
        publish = request.data.get('publish', True)
        if publish:
            # Backstop: refuse to publish a profile that leaks the student's forbidden
            # PII (name/NRIC/phone/email — school + town are allowed by the 2026-06-15 policy).
            leaks = pool.scan_profile_pii(sp.anon_markdown, getattr(sp.application, 'profile', None))
            if leaks:
                return Response(
                    {'error': 'The anonymous profile may contain identifying details — regenerate before publishing.',
                     'code': 'anon_identifier_leak', 'fields': leaks},
                    status=status.HTTP_400_BAD_REQUEST)
        sp.anon_published = bool(publish)
        sp.anon_published_at = timezone.now() if publish else None
        # F3: mark this student for the next real-time sponsor alert. Resetting on
        # both publish AND unpublish means a re-published student is alerted again
        # (no synchronous fan-out here — the hourly job picks them up).
        sp.realtime_notified_at = None
        sp.save(update_fields=['anon_published', 'anon_published_at', 'realtime_notified_at', 'updated_at'])
        return Response(SponsorProfileSerializer(sp).data)


class AdminSuggestGapsView(_AdminBase):
    """Phase B: admin-on-demand Gemini interview gap-spotter. One Gemini call →
    up to 3 suggested interview questions stored on the application, shown beside the
    deterministic pre-interview flags. With ``append: true`` it generates 3 MORE
    (not repeating the existing ones) and appends; otherwise it replaces with a
    fresh set of 3. Reviewer-gated (billable)."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        from .gap_engine import generate_interview_gaps
        append = bool(request.data.get('append'))
        existing = app.interview_gaps or []
        result = generate_interview_gaps(
            app, language=request.data.get('language'),
            existing=existing if append else None)
        if 'error' in result:
            return Response({'error': result['error']}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        app.interview_gaps = (existing + result['gaps']) if append else result['gaps']
        app.interview_gaps_run_at = timezone.now()
        app.save(update_fields=['interview_gaps', 'interview_gaps_run_at'])
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminProfileEditView(_AdminBase):
    def put(self, request, pk):
        _app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        sp = SponsorProfile.objects.filter(application_id=pk).first()
        if sp is None:
            return Response({'error': 'No profile drafted yet'}, status=status.HTTP_404_NOT_FOUND)
        sp.edited_markdown = request.data.get('edited_markdown', '')
        new_status = request.data.get('status')
        if new_status in ('draft', 'approved'):
            sp.status = new_status
        sp.save()
        return Response(SponsorProfileSerializer(sp).data)


class AdminPublishProfileView(_AdminBase):
    def post(self, request, pk):
        _app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        sp = SponsorProfile.objects.filter(application_id=pk).first()
        if sp is None or not sp.current_markdown.strip():
            return Response({'error': 'Nothing to publish.'}, status=status.HTTP_400_BAD_REQUEST)
        sp.status = 'published'
        sp.published_at = timezone.now()
        sp.save()
        return Response(SponsorProfileSerializer(sp).data)


# ── Phase C: interview capture + request-more-documentation ──────────────────

def _interview_agenda(application):
    """The anomaly codes that form the interview agenda (same flags the admin
    'Pre-interview flags' card shows). Flat list — kept stable for the AdminInterviewView
    scaffold + its FE. V3 (#9) adds the richer folded agenda in ``interview_agenda_full``."""
    return [a['code'] for a in detect_anomalies(application)]


# V3 (#9): the verdict items that explicitly say "confirm at interview" — folded onto the agenda
# by ITEM CODE (not fact status) so they don't evaporate at Check 3. NB since V5, `income_above_
# b40_line` rides on a RED ('gap') income fact, not an amber one — the folding is code-keyed, so
# it's still picked up; the historical name is kept. Over-the-line income is phrased for the
# INTERVIEWER only (never a student message — owner decision 4).
_NEEDS_INTERVIEW_AMBERS = ('income_unverified_needs_interview', 'income_above_b40_line',
                           'academic_grade_uncertain', 'ic_service_down')


def interview_agenda_full(application):
    """The interviewer's talking-point agenda for Check 3. Returns ``[{code, kind, params}]`` where
    kind is one of:
      - ``anomaly``        — the deterministic pre-interview flags (as before);
      - ``needs_interview``— the verdict ambers that say "confirm at interview"
                             (``_NEEDS_INTERVIEW_AMBERS``); over-the-line income is interviewer-only;
      - ``motivation``     — a STANDING 'Motivation & grit' section, always present, ``seeded``
                             rich when the statement of intent / aspirations is thin
                             (``motivation_missing``). Motivation stays a human judgement
                             (owner decision 3) — no student query, structured for Check 3.
    Deduped across kinds by (kind, code). The FE resolves copy per (kind, code).

    NOTE (owner, 2026-07-06): open Check-2 queries / doc-requests are NO LONGER echoed here as
    "carried-over" items. They stay in Check-2 Outstanding (a pending upload isn't an interview
    talking point, and the generic echo was noise the reviewer deleted every time). V3 #9's "nothing
    evaporates" is served by Check-2 remaining open — not by duplicating it onto the agenda."""
    from .submission_review import completeness_gaps as _submission_gaps
    from .verdict_engine import build_verdict
    agenda = [{'code': a['code'], 'kind': 'anomaly', 'params': a.get('params', {})}
              for a in detect_anomalies(application)]
    seen = {(e['kind'], e['code']) for e in agenda}

    def _add(kind, code, params):
        if (kind, code) not in seen:
            agenda.append({'code': code, 'kind': kind, 'params': params or {}})
            seen.add((kind, code))

    # the "needs interview" verdict ambers.
    for fact in build_verdict(application):
        for item in fact.get('unresolved', []):
            if item['code'] in _NEEDS_INTERVIEW_AMBERS:
                _add('needs_interview', item['code'], item.get('params', {}))
    # (c) the standing Motivation & grit section (seeded rich when the statement of intent is thin).
    thin = any(g['code'] == 'motivation_missing' for g in _submission_gaps(application))
    _add('motivation', 'motivation_grit', {'seeded': thin})
    return agenda


def _validate_findings(findings):
    """Validate a findings dict: each value must have a valid verdict + a rationale
    within length. Returns an error string or None."""
    if not isinstance(findings, dict):
        return 'findings must be an object'
    for code, val in findings.items():
        if not isinstance(val, dict):
            return f'finding {code} must be an object'
        if val.get('verdict') not in _VALID_VERDICTS:
            return f'finding {code} has an invalid verdict'
        if len(val.get('rationale', '') or '') > _RATIONALE_MAX:
            return f'finding {code} rationale exceeds {_RATIONALE_MAX} chars'
    return None


class AdminInterviewView(_AdminBase):
    """
    GET  .../<pk>/interview/ — the latest interview session, or an empty scaffold
         (status null) carrying the agenda codes from the anomaly engine.
    POST .../<pk>/interview/ — create/update the DRAFT session (findings/rubric/
         note). Saving a draft does NOT change the application status — 'interviewing'
         is reached only by proposing times (the forward trigger) or, for an offline
         interview, by SUBMITTING the session; both require an assigned reviewer.
    Reviewer/super only.
    """
    def get(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
        session = app.interview_sessions.first()  # ordering = -created_at
        data = InterviewSessionSerializer(session).data if session else None
        return Response({'session': data, 'agenda': _interview_agenda(app)})

    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        findings = request.data.get('findings', {}) or {}
        err = _validate_findings(findings)
        if err:
            return Response({'error': err, 'code': 'bad_findings'},
                            status=status.HTTP_400_BAD_REQUEST)
        session = app.interview_sessions.filter(status='draft').first()
        if session is None and app.decision_reopened_at is not None:
            # Decision reopened → edit the SUBMITTED session IN PLACE (reopen it as a draft)
            # instead of spawning a second session (the duplicate-draft trap, app #15).
            session = app.interview_sessions.filter(status='submitted').order_by('-submitted_at').first()
            if session is not None:
                session.status = 'draft'
        if session is None:
            session = InterviewSession(application=app, interviewer=admin,
                                       started_at=timezone.now())
        session.findings = findings
        session.rubric = request.data.get('rubric', {}) or {}
        session.overall_note = request.data.get('overall_note', '') or ''
        if session.interviewer_id is None:
            session.interviewer = admin
        session.save()
        # A draft save does NOT advance the funnel. 'interviewing' means the interview
        # process is genuinely underway for an accountable reviewer — reached by proposing
        # times (scheduling.propose_slots) or submitting the session (offline fallback),
        # both assignment-gated. Advancing on ANY draft save (incl. an agenda-item delete)
        # was a Phase-C leftover that mis-fired once V3 folded the agenda into the draft
        # (four live apps flipped on early triage). See docs/decisions.md.
        return Response(InterviewSessionSerializer(session).data)


class AdminInterviewSubmitView(_AdminBase):
    """POST .../<pk>/interview/submit/ — finalise the draft session and advance the
    application → interviewed. Reviewer/super only."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        session = app.interview_sessions.filter(status='draft').first()
        if session is None:
            return Response({'error': 'No draft interview to submit.', 'code': 'no_draft'},
                            status=status.HTTP_400_BAD_REQUEST)
        err = _validate_findings(session.findings or {})
        if err:
            return Response({'error': err, 'code': 'bad_findings'},
                            status=status.HTTP_400_BAD_REQUEST)
        if session.interviewer_id is None:
            session.interviewer = admin
            session.save(update_fields=['interviewer'])
        submit_interview(session)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminInterviewReopenView(_AdminBase):
    """POST .../<pk>/interview/reopen/ — the assigned reviewer reopens a SUBMITTED
    interview to add/edit a forgotten finding. Un-submits the latest session (→ draft)
    and reverts status interviewed→interviewing, which reopens BOTH the Interview Stage
    AND Check 2, and switches Approve/Decline off until it's re-submitted. Reviewer/super.
    Only valid BEFORE a decision is recorded — once decided, use the Decision panel's
    Reopen (super-only, holds the profile from the pool)."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        if app.verdict_decided_at is not None:
            return Response(
                {'error': 'A decision is recorded — reopen the decision instead.',
                 'code': 'decision_recorded'}, status=status.HTTP_400_BAD_REQUEST)
        session = app.interview_sessions.filter(status='submitted').order_by('-submitted_at').first()
        if session is None:
            return Response({'error': 'No submitted interview to reopen.', 'code': 'no_submitted'},
                            status=status.HTTP_400_BAD_REQUEST)
        session.status = 'draft'
        session.save(update_fields=['status', 'updated_at'])
        if app.status == 'interviewed':   # back a step so Check 2 + the decision gate reopen
            app.status = 'interviewing'
            app.save(update_fields=['status'])
        return Response(AdminApplicationDetailSerializer(app).data)


def _sponsor_dict(s):
    return {
        'id': s.id, 'name': s.name, 'email': s.email, 'phone': s.phone,
        'source': s.source, 'organisation': s.organisation,
        'note': s.note, 'status': s.status, 'reviewed_at': s.reviewed_at,
        'reviewed_by': s.reviewed_by, 'created_at': s.created_at,
    }


class AdminSponsorListView(_AdminBase):
    """Phase E: GET .../admin/sponsors/[?status=pending] — self-registered sponsor
    ACCOUNTS for vetting (distinct from the old sponsor-interest leads)."""
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        # Matrix (2026-07-23): the Sponsors surface is visible to super / org_admin /
        # Admin-General / finance. qc + reviewer are refused (nav + endpoint). Finance sees
        # sponsors READ-ONLY — who funds the programme is finance's business; approving them
        # is not, so the review gate (AdminSponsorReviewView) stays super/org_admin.
        if not (admin.is_super or admin.role in ('org_admin', 'admin', 'finance')):
            return self._deny_role()
        # Deterministic ordering (TD audit 2026-06-14) — without it the row order was
        # undefined. Full pagination is deferred: these are low-cardinality admin tables and
        # the sponsors table FE does not yet handle a paged envelope (would truncate to 25).
        # tenancy: cross-org by design until Sprint 10 (D-1). A Sponsor is a platform-
        # level account (no owning_organisation; may fund across programmes), so the
        # vetting list is intentionally NOT org-fenced. Sponsor accounts carry no
        # student identity, so this is not an applicant-data leak.
        qs = Sponsor.objects.all().order_by('-id')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response({'sponsors': [_sponsor_dict(s) for s in qs]})


class AdminSponsorPendingCountView(_AdminBase):
    """GET .../admin/sponsors/pending-count/ — {count} of sponsor accounts awaiting vetting.
    A lean COUNT for the nav + Administration-hub badges (so an always-loaded nav needn't fetch the
    full sponsor list on every page). Same role-gate as the list (super / org_admin /
    Admin-General / finance) — kept deliberately in lockstep so a role that can open the list
    never 403s on its badge; cross-org by design (a sponsor is a platform-level account)."""
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super or admin.role in ('org_admin', 'admin', 'finance')):
            return self._deny_role()
        return Response({'count': Sponsor.objects.filter(status='pending').count()})


class AdminSponsorReviewView(_AdminBase):
    """Phase E: POST .../admin/sponsors/<pk>/review/ {action: approve|reject|suspend}
    — vet a sponsor account. Matrix (2026-07-15): sponsor vetting is a super or ORG_ADMIN
    power (migrated off the old reviewer gate); stamps who/when."""
    _ACTION_STATUS = {'approve': 'approved', 'reject': 'rejected', 'suspend': 'suspended'}

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super or admin.role == 'org_admin'):
            return self._deny_role()
        sponsor = Sponsor.objects.filter(pk=pk).first()
        if sponsor is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        new_status = self._ACTION_STATUS.get(request.data.get('action'))
        if not new_status:
            return Response({'error': 'bad_action'}, status=status.HTTP_400_BAD_REQUEST)
        sponsor.status = new_status
        sponsor.reviewed_at = timezone.now()
        sponsor.reviewed_by = admin.email
        sponsor.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'updated_at'])
        return Response(_sponsor_dict(sponsor))


class AdminSetAwardAmountView(_AdminBase):
    """POST .../applications/<pk>/award-amount/ {amount} — OVERRIDE the standardised
    assistance amount. SUPER-ONLY (owner decision 2026-06-29: reviewers no longer set the
    amount; it's fixed by pathway via the award rule and auto-applied on approve). A super
    may adjust it to one of the allowed slider stops (RM1,000–3,000 in RM500 steps), or
    clear it with null/blank. Gates fundability + shows on the anonymised pool card."""
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
        from decimal import Decimal, InvalidOperation
        from . import award as award_rule
        raw = request.data.get('amount')
        try:
            amount = Decimal(str(raw)) if raw not in (None, '') else None
        except (InvalidOperation, TypeError):
            return Response({'error': 'invalid_amount'}, status=status.HTTP_400_BAD_REQUEST)
        # A set value must be one of the permitted slider stops (clearing is allowed).
        if amount is not None and not award_rule.is_allowed_amount(amount):
            return Response({'error': 'invalid_amount'}, status=status.HTTP_400_BAD_REQUEST)
        app.award_amount = amount
        app.save(update_fields=['award_amount'])
        return Response(AdminApplicationDetailSerializer(app).data)


def _sponsorship_dict(s):
    profile = getattr(s.application, 'profile', None)
    return {
        'id': s.id, 'status': s.status, 'amount': str(s.amount),
        'offered_at': s.offered_at, 'accept_deadline': s.accept_deadline, 'decided_at': s.decided_at,
        # Admin oversight sees BOTH sides (not anonymised) — this is the back office.
        'sponsor': {'id': s.sponsor_id, 'name': s.sponsor.name, 'email': s.sponsor.email},
        'application': {
            'id': s.application_id,
            'name': (getattr(profile, 'name', '') or '') if profile else '',
            'ref': pool.pool_ref(s.application_id),
        },
    }


class AdminSponsorshipListView(_AdminBase):
    """Phase E3: GET .../admin/sponsorships/[?status] — oversight of all matches
    (sponsor ↔ student + amount + status)."""
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        # org-fence: _org_scoped on the application join, applied below.
        qs = (Sponsorship.objects.select_related('sponsor', 'application', 'application__profile')
              .order_by('-id'))  # deterministic ordering (TD audit 2026-06-14)
        qs = self._org_scoped(qs, admin, field='application__owning_organisation_id')
        st = request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        return Response({'sponsorships': [_sponsorship_dict(s) for s in qs]})


# ── Sources (referral organisations) + witness assignment (go-live transition) ────
# The Sources module is the first UI that edits organisation records as a registry (name,
# contact person/email/phone, active-in-apply, student count) — reusing the SAME
# PartnerOrganisation.phone/contact_* fields the existing AdminProfileView self-edit writes
# (no second contact_phone column, which would drift against that editor). Single-tenant
# today, so source rows are shared and NOT org-fenced (multi-tenant fencing of shared source
# rows is deliberately out of scope — see the plan's Out of scope / future).

def _source_dict(org, student_count=None):
    return {
        'id': org.id,
        'code': org.code,
        'name': org.name,
        'contact_person': org.contact_person or '',
        'contact_email': org.contact_email or '',
        'phone': org.phone or '',
        'show_in_apply': bool(org.show_in_apply),
        'is_active': bool(org.is_active),
        'student_count': student_count,
    }


# The platform's own bursary programme — the "house" organisation. Applicants who did
# not come through an external referral partner (self-referred via the apply form, or
# unattributed) count as the house org's own students. Kept as a code (not an id) so it
# survives reseeding; mirror of courses/views_admin.py owning-org default.
HOUSE_ORG_CODE = 'brightpath'


def _source_application_counts():
    """{org_id: bursary-APPLICATION count attributed to that organisation}.

    Counts scholarship *applications* (not the legacy course-selector referral
    registry, which holds hundreds of non-applicant profiles) and attributes each
    by the applicant's raw referral chip (`profile.referral_source`) — the SAME
    signal the Applications-list Source filter uses, so a source's count here
    equals its filtered applicant count. The stored `referred_by_org` FK is
    deliberately NOT used: it can drift (a self-referral chip left pointing at an
    old partner), which is what previously inflated CUMIG.

    Each external partner counts the applications whose chip == its `code`. The
    house org (`brightpath`) is the RESIDUAL: every application not claimed by an
    external partner (self-referral chips halatuju/other/social, blanks, or any
    unmapped chip). Single tenant today, so this is a global tally; revisit the
    residual split if applications ever span multiple house tenants.
    """
    from apps.courses.models import PartnerOrganisation
    from django.db.models import Count
    # chip -> number of applications carrying it (NULL/'' collapse to '')
    # org-fence: intentionally GLOBAL — the sources registry lists every organisation and
    # the house-org residual = (total apps − apps claimed by partners), so this tally must
    # span all tenants, not one. Single tenant today; revisit the split if that changes.
    tally = {
        (row['profile__referral_source'] or ''): row['n']
        # org-fence: GLOBAL by design (residual house-org tally spans all tenants; see above)
        for row in (ScholarshipApplication.objects
                    .values('profile__referral_source')
                    .annotate(n=Count('pk')))
    }
    total = sum(tally.values())
    orgs = list(PartnerOrganisation.objects.values('id', 'code'))
    partner_codes = {o['code'] for o in orgs if o['code'] != HOUSE_ORG_CODE}
    claimed = sum(tally.get(code, 0) for code in partner_codes)
    counts = {}
    for o in orgs:
        if o['code'] == HOUSE_ORG_CODE:
            counts[o['id']] = total - claimed          # residual → house org
        else:
            counts[o['id']] = tally.get(o['code'], 0)
    return counts


class _SourcesBase(_AdminBase):
    """Gate for the Sources + witness-assignment endpoints: super, admin, or org_admin
    (owner 2026-07-19 — the Admin role manages sources too). qc/reviewer/partner → 403.
    `has_role(admin, 'admin')` already passes super; org_admin is added explicitly."""
    def _sources_admin(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (self.has_role(admin, 'admin') or admin.role == 'org_admin'):
            return None, self._deny_role()
        return admin, None


class AdminSourcesView(_SourcesBase):
    """GET  .../admin/scholarship/sources/ — every referral organisation + its student count.
    POST .../admin/scholarship/sources/ {code, name, contact_person?, contact_email?, phone?,
         show_in_apply?} — create a new source organisation."""
    def get(self, request):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from apps.courses.models import PartnerOrganisation
        counts = _source_application_counts()
        orgs = PartnerOrganisation.objects.order_by('name')
        return Response({'sources': [_source_dict(o, counts.get(o.id, 0)) for o in orgs]})

    def post(self, request):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from apps.courses.models import PartnerOrganisation
        code = (request.data.get('code') or '').strip().lower()
        name = (request.data.get('name') or '').strip()
        if not code or not name:
            return Response({'error': 'code_and_name_required', 'code': 'code_and_name_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        if PartnerOrganisation.objects.filter(code=code).exists():
            return Response({'error': 'code_taken', 'code': 'code_taken'},
                            status=status.HTTP_400_BAD_REQUEST)
        org = PartnerOrganisation.objects.create(
            code=code, name=name,
            contact_person=(request.data.get('contact_person') or '').strip()[:200],
            contact_email=(request.data.get('contact_email') or '').strip()[:254],
            phone=(request.data.get('phone') or '').strip()[:30],
            show_in_apply=bool(request.data.get('show_in_apply', False)),
        )
        return Response(_source_dict(org, 0), status=status.HTTP_201_CREATED)


class AdminSourceDetailView(_SourcesBase):
    """PATCH .../admin/scholarship/sources/<pk>/ — edit a source's name, contact details,
    active-in-apply flag, or is_active. Whitelisted fields only; the code slug is immutable."""
    def patch(self, request, pk):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from apps.courses.models import PartnerOrganisation
        org = PartnerOrganisation.objects.filter(pk=pk).first()
        if org is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        fields = []
        if 'name' in request.data:
            org.name = (request.data.get('name') or '').strip()[:200]
            fields.append('name')
        if 'contact_person' in request.data:
            org.contact_person = (request.data.get('contact_person') or '').strip()[:200]
            fields.append('contact_person')
        if 'contact_email' in request.data:
            org.contact_email = (request.data.get('contact_email') or '').strip()[:254]
            fields.append('contact_email')
        if 'phone' in request.data:
            org.phone = (request.data.get('phone') or '').strip()[:30]
            fields.append('phone')
        if 'show_in_apply' in request.data:
            org.show_in_apply = bool(request.data.get('show_in_apply'))
            fields.append('show_in_apply')
        if 'is_active' in request.data:
            org.is_active = bool(request.data.get('is_active'))
            fields.append('is_active')
        if fields:
            org.save(update_fields=fields)
        return Response(_source_dict(org, _source_application_counts().get(org.id, 0)))


class AdminApplicationWitnessView(_SourcesBase):
    """PATCH .../admin/scholarship/applications/<pk>/witness/ {witness_org: <code|id|null>} —
    assign (or clear) the witness-organisation OVERRIDE for a (typically sourceless) application.
    NULL/'' clears the override (bursary witness resolution then falls back to the referring org,
    else straight to the Foundation countersignature)."""
    def patch(self, request, pk):
        admin, err = self._sources_admin(request)
        if err:
            return err
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        if 'witness_org' not in request.data:
            return Response({'error': 'witness_org_required', 'code': 'witness_org_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        raw = request.data.get('witness_org')
        if raw in (None, '', 'none'):
            app.witness_org = None
        else:
            from apps.courses.models import PartnerOrganisation
            key = str(raw).strip()
            org = PartnerOrganisation.objects.filter(code=key).first()
            if org is None and key.isdigit():
                org = PartnerOrganisation.objects.filter(pk=int(key)).first()
            if org is None:
                return Response({'error': 'unknown_organisation', 'code': 'unknown_organisation'},
                                status=status.HTTP_400_BAD_REQUEST)
            app.witness_org = org
        app.save(update_fields=['witness_org'])
        return Response({
            'id': app.id,
            'witness_org': app.witness_org.code if app.witness_org else None,
            'witness_org_name': app.witness_org.name if app.witness_org else None,
        })


class AdminDisbursementScheduleView(_AdminBase):
    """Post-award S4: POST .../applications/<pk>/disbursements/ {amount, sequence?, label?,
    scheduled_for?} — schedule one tranche against a funded application. Reviewer-gated.
    Returns the refreshed application detail (the cockpit re-renders its disbursement panel)."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        seq = request.data.get('sequence')
        try:
            seq = int(seq) if seq not in (None, '') else None
        except (TypeError, ValueError):
            return Response({'error': 'bad_sequence'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            disbursement_service.schedule_tranche(
                app,
                amount=request.data.get('amount'),
                sequence=seq,
                label=request.data.get('label', ''),
                scheduled_for=request.data.get('scheduled_for') or None,
            )
        except disbursement_service.DisbursementError as e:
            return Response({'error': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminDisbursementActionView(_AdminBase):
    """Post-award S4: POST .../disbursements/<pk>/<action>/ where action ∈
    release | withhold | return | mark_due. Reviewer-gated + access-scoped via the
    tranche's application. A 'release' (the first one) flips the app active → maintenance.
    Returns the refreshed application detail."""
    def post(self, request, pk, action):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        writer = disbursement_service.ACTIONS.get(action)
        if writer is None:
            return Response({'error': 'bad_action'}, status=status.HTTP_400_BAD_REQUEST)
        disb = (Disbursement.objects.select_related('application', 'application__profile',
                                                    'application__cohort')
                .filter(pk=pk).first())
        if disb is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # Assignment-based write: super, or the admin/reviewer assigned to the tranche's application.
        if not self._can_review_app(admin, disb.application):
            return self._deny_role()
        try:
            writer(disb, by_email=admin.email,
                   note=request.data.get('note', ''))
        except disbursement_service.DisbursementError as e:
            return Response({'error': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(disb.application).data)


class AdminCloseApplicationView(_AdminBase):
    """Post-award S6: POST .../applications/<pk>/close/ {closure_reason} — manually close a
    funded application (active/maintenance) with a reason (graduated/completed/withdrawn/
    lapsed/terminated). Reviewer-gated + access-scoped. Terminal. Returns the refreshed detail."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        try:
            closure_service.close_application(
                app, closure_reason=request.data.get('closure_reason'), by_email=admin.email)
        except closure_service.ClosureError as e:
            return Response({'error': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminMaintenanceSubstateView(_AdminBase):
    """Post-award S5: POST .../applications/<pk>/maintenance/ {substate} — set the
    operational maintenance sub-state (on_track | probation | on_hold | ready_to_close).
    Reviewer-gated + access-scoped. `on_hold` pauses tranche releases. Returns the
    refreshed application detail."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        try:
            maintenance_service.set_substate(app, request.data.get('substate'))
        except maintenance_service.MaintenanceError as e:
            return Response({'error': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminAssignableAdminsView(_AdminBase):
    """GET .../assignable-admins/ — active REVIEWERS, ADMINS (+ supers) for the assignment
    dropdown. Only roles that can be assigned an applicant appear (mirrors services._can_review):
    a view-all 'admin' and the senior 'qc' role can be assigned selective review work (assignment
    grants WRITE on the assigned application while their read stays all), so admins + qc are listed;
    'partner' and 'finance' have no review role and are excluded. (A qc's own reviewed case is QC'd
    by someone else — the self-QC guard in _require_qc.)"""
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        from django.db.models import Q
        # tenancy: list-fenced (2026-07-15). Super sees every assignable staff member; a
        # non-super (org_admin) sees only their OWN org's assignable staff — so a delegated
        # assignment can't reach across tenants. (A PartnerAdmin list, not applicant data.)
        admins = (PartnerAdmin.objects.filter(is_active=True)
                  .filter(Q(is_super_admin=True) | Q(role__in=['reviewer', 'super', 'admin', 'qc', 'org_admin']))
                  .select_related('reviewer_profile').order_by('name'))
        if not self.has_role(admin, 'super'):
            admins = admins.filter(owning_organisation_id=admin.owning_organisation_id,
                                   is_super_admin=False)
        # Internal-only "corrections" tally per reviewer (reopened decisions that led
        # to a real change). Never shown to sponsors/students — an internal quality
        # signal for whoever assigns reviewers.
        corrections = reopen_service.reviewer_correction_counts()

        def langs(a):
            # Languages the reviewer can conduct a review in (conversational or better),
            # for matching against the student's preferred call language. Codes: en/ms/ta.
            rp = getattr(a, 'reviewer_profile', None)
            if rp is None:
                return []
            ok = ('conversational', 'fluent')
            return [code for code, lvl in (('en', rp.english_fluency),
                                           ('ms', rp.bm_fluency),
                                           ('ta', rp.tamil_fluency)) if lvl in ok]

        # "Past reviewers" for the list-page assignee FILTER (owner 2026-07-16): anyone still on
        # record as an application's ASSIGNEE (any status incl. closed/rejected) — filtering by
        # them returns their old cases. Deliberately INDEPENDENT of is_active/role, so an inactive
        # or role-changed past reviewer stays filterable; and deliberately NOT AssignmentEvent
        # history (a fully-reassigned person filters to zero rows — a dead option).
        # org-fence: _org_scoped below — a non-super sees only their own org's past assignees.
        assigned_apps = self._org_scoped(
            ScholarshipApplication.objects.filter(assigned_to__isnull=False), admin)
        past = (PartnerAdmin.objects
                .filter(id__in=assigned_apps.values_list('assigned_to_id', flat=True).distinct())
                .order_by('name'))

        return Response({'admins': [
            {'id': a.id, 'name': a.name, 'email': a.email,
             'role': 'super' if a.is_super else a.role, 'languages': langs(a),
             'corrections': corrections.get(a.id, 0)}
            for a in admins
        ], 'past_assignees': [{'id': p.id, 'name': p.name} for p in past]})


class AdminRequestInfoView(_AdminBase):
    """POST .../<pk>/request-info/ — the admin asks the student for more
    documentation. Records a note on the application + emails the student. Does
    NOT change status (the student keeps editing). Reviewer/super only."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        note = (request.data.get('note', '') or '').strip()
        if not note:
            return Response({'error': 'A note is required.', 'code': 'note_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        app.info_request_note = note
        app.info_requested_at = timezone.now()
        app.save(update_fields=['info_request_note', 'info_requested_at'])
        name = getattr(app.profile, 'name', '') if app.profile else ''
        send_request_info_email(to_email=app.notify_email, applicant_name=name,
                                programme_name=app.cohort.name, note=note, lang=app.locale)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminResolutionItemView(_AdminBase):
    """POST .../<pk>/resolution-items/ — officer raises a manual resolution ticket
    (the structured successor to request-info). Body: {kind, prompt, doc_type?,
    fact?}. Reviewer/super only."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        # An officer may ask during Completed + Interviewing only (owner, 2026-07-13). Blocks
        # `shortlisted` — the Action Centre doesn't render until the student submits, so a ticket
        # raised there is invisible: a question nobody can see or answer. And blocks `interviewed`
        # onward — the interview is concluded, it's decision time. (Was gated on querying_locked,
        # which let an officer raise an unseeable ticket at `shortlisted`.)
        from .services import officer_queries_allowed
        if not officer_queries_allowed(app):
            return Response({'error': 'querying_closed'}, status=status.HTTP_400_BAD_REQUEST)
        kind = (request.data.get('kind') or '').strip()
        prompt = (request.data.get('prompt') or '').strip()
        if kind not in ('doc', 'confirm', 'explanation'):
            return Response({'error': 'bad_kind'}, status=status.HTTP_400_BAD_REQUEST)
        if not prompt:
            return Response({'error': 'prompt_required'}, status=status.HTTP_400_BAD_REQUEST)
        member = (request.data.get('household_member') or '').strip()
        if member and member not in ('father', 'mother', 'guardian', 'brother', 'sister'):
            return Response({'error': 'bad_member'}, status=status.HTTP_400_BAD_REQUEST)
        from .resolution import add_officer_item
        add_officer_item(app, kind=kind, prompt=prompt,
                         admin_email=getattr(admin, 'email', '') or '',
                         doc_type=(request.data.get('doc_type') or '').strip(),
                         fact=(request.data.get('fact') or 'other').strip(),
                         household_member=member)
        # Re-notify the student that there's something new for them — but DON'T email
        # per item (a reviewer raises several in one sitting → email spam + Brevo quota).
        # Instead reset the one-time notify stamp so the delayed, batched, idempotent
        # `send_due_query_emails` sweep sends ONE summary email on its next run (it now
        # counts officer items too). A re-request after the student cleared everything
        # thus re-notifies them once. Flag-gated to the student-query channel.
        from django.conf import settings as _settings
        if (getattr(_settings, 'CHECK2_STUDENT_QUERIES_ENABLED', False)
                and app.query_raised_notified_at is not None):
            app.query_raised_notified_at = None
            app.save(update_fields=['query_raised_notified_at'])
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminResolutionItemActionView(_AdminBase):
    """POST .../resolution-items/<item_id>/<action>/ — officer waives or resolves
    a ticket by hand. action ∈ {waive, resolve}. Reviewer/super only."""
    def post(self, request, item_id, action):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if action not in ('waive', 'resolve', 'reopen'):
            return Response({'error': 'bad_action'}, status=status.HTTP_400_BAD_REQUEST)
        from .models import ResolutionItem
        item = ResolutionItem.objects.filter(pk=item_id).select_related('application').first()
        if item is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # Assignment-based write: super, or the admin/reviewer assigned to the item's application.
        if not self._can_review_app(admin, item.application):
            return self._deny_role()
        from .services import querying_locked
        if querying_locked(item.application):
            return Response({'error': 'querying_closed'}, status=status.HTTP_400_BAD_REQUEST)
        if action == 'reopen':
            # "Ask again" — the officer wasn't satisfied with the student's answer; send
            # the query back to the student's to-do. The typed answer stays in
            # resolution_text for the audit trail; only the answered stamp is cleared.
            item.status = 'open'
            item.resolved_by = ''
            item.resolved_at = None
        else:
            item.status = 'waived' if action == 'waive' else 'resolved'
            item.resolved_by = getattr(admin, 'email', '') or 'officer'
            item.resolved_at = timezone.now()
        item.save(update_fields=['status', 'resolved_by', 'resolved_at'])
        return Response(AdminApplicationDetailSerializer(item.application).data)


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
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err

        raw = request.data.get('officer_verdict')
        if not isinstance(raw, dict):
            return Response({'error': 'officer_verdict object required', 'code': 'verdict_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        from .audit import FACTS
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

        from .verdict_engine import build_verdict
        app.ai_verdict_snapshot = build_verdict(app)
        app.officer_verdict = officer_verdict
        app.verdict_reason = (request.data.get('reason') or '').strip()
        app.verdict_decided_by = getattr(admin, 'email', '') or ''
        app.verdict_decided_at = timezone.now()
        verdict_fields = [
            'ai_verdict_snapshot', 'officer_verdict', 'verdict_reason',
            'verdict_decided_by', 'verdict_decided_at',
        ]

        # Standardised assistance (owner decision 2026-06-29): the amount is fixed by the
        # pathway, not chosen by the reviewer. On APPROVE, auto-apply the proposed amount —
        # but only when unset, so a SUPER's manual override (set-award endpoint) survives a
        # re-record. When the verdict confidently disqualifies (offer_not_official /
        # income_above_b40_line) the proposal is None, so award_amount STAYS unset — a super
        # may set a value if the system has erred. On DECLINE, clear it. See
        # apps.scholarship.award; reuse the verdict just snapshotted, don't recompute.
        from . import award as award_rule
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
                from .emails import send_qc_returned_email
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
                from .emails import send_qc_rejected_email
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
        from .audit import override_metrics
        # org-fence: _org_scoped applied below (fences the metrics roll-up).
        qs = (ScholarshipApplication.objects
              .filter(verdict_decided_at__isnull=False)
              .only('ai_verdict_snapshot', 'officer_verdict', 'cohort_id'))
        qs = self._org_scoped(qs, admin)   # super global
        cohort = request.query_params.get('cohort')
        if cohort:
            qs = qs.filter(cohort_id=cohort)
        pairs = ((a.ai_verdict_snapshot, a.officer_verdict) for a in qs)
        return Response(override_metrics(pairs))


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


def _parse_slot_starts(raw):
    """Parse the proposed-slot times from the request body into tz-aware datetimes.
    Accepts a list of ISO strings, or of objects with a 'start' key. A naive value
    (e.g. a browser datetime-local '2026-06-20T20:00') is read as Malaysia time."""
    from zoneinfo import ZoneInfo
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone as _tz
    out = []
    for item in (raw or []):
        s = item.get('start') if isinstance(item, dict) else item
        if not s:
            continue
        dt = parse_datetime(s)
        if dt is None:
            continue
        if _tz.is_naive(dt):
            dt = dt.replace(tzinfo=ZoneInfo('Asia/Kuala_Lumpur'))
        out.append(dt)
    return out


class AdminInterviewSlotsView(_AdminBase):
    """GET  .../applications/<pk>/interview-slots/ — booking state + proposed slots.
    POST .../applications/<pk>/interview-slots/ — the assigned reviewer (or super)
         proposes interview times. Body {slots: [<iso>, ...]} (or [{start}]). Dark
         behind INTERVIEW_SCHEDULING_ENABLED (404 when off)."""

    def get(self, request, pk):
        if not scheduling.scheduling_enabled():
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        app, err = self._scoped_application(request, pk)
        if err:
            return err
        return Response(interview_schedule_payload(app, include_reviewer_busy=True))

    def post(self, request, pk):
        if not scheduling.scheduling_enabled():
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        starts = _parse_slot_starts(request.data.get('slots'))
        # Minimum scheduling notice — reject any slot sooner than the lead window (checked
        # first so a too-soon time reads as 'too_soon', not 'invalid_slot_time').
        from django.utils import timezone as _tz
        if any(s and not scheduling.meets_min_lead(s, _tz.now()) for s in starts):
            return Response({'error': 'too_soon', 'code': 'too_soon'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Enforce the interview-slot rule (MYT, 30-min, 08:00–21:30) at the input
        # boundary — the UI only offers valid chips, but reject anything else too.
        if any(s and not scheduling.slot_in_window(s) for s in starts):
            return Response({'error': 'invalid_slot_time', 'code': 'invalid_slot_time'},
                            status=status.HTTP_400_BAD_REQUEST)
        # reschedule=True: the reviewer is MOVING an already-booked interview — release the
        # held booking, then offer the fresh menu (student is asked to re-pick).
        reschedule = bool(request.data.get('reschedule'))
        try:
            scheduling.propose_slots(app, reviewer=admin, starts=starts, release_booking=reschedule)
        except scheduling.SchedulingError as e:
            return Response({'error': str(e), 'code': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(interview_schedule_payload(app, include_reviewer_busy=True))


class AdminInterviewSlotDetailView(_AdminBase):
    """DELETE .../applications/<pk>/interview-slots/<slot_id>/ — withdraw a proposed
    (unbooked) slot. Reviewer/super, assignment-scoped."""

    def delete(self, request, pk, slot_id):
        if not scheduling.scheduling_enabled():
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        slot = InterviewSlot.objects.filter(application=app, pk=slot_id).first()
        if slot is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            scheduling.withdraw_slot(slot)
        except scheduling.SchedulingError as e:
            return Response({'error': str(e), 'code': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(interview_schedule_payload(app, include_reviewer_busy=True))


class ReviewerProfileView(_AdminBase):
    """GET/PATCH /api/v1/admin/reviewer-profile/ — a reviewer's OWN credentials +
    contact details (F6). Self-scoped: it only ever reads/writes the calling admin's
    own row (resolved from the JWT via get_admin), so one admin can never see or edit
    another's. Reviewer + super only — a viewer (read-only staff) gets 403. The
    sensitive PII (phone/address) lives in its own table and is exposed by no other
    serializer."""

    def get(self, request):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        profile, _ = ReviewerProfile.objects.get_or_create(partner_admin=admin)
        return Response(ReviewerProfileSerializer(profile).data)

    def patch(self, request):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        profile, _ = ReviewerProfile.objects.get_or_create(partner_admin=admin)
        serializer = ReviewerProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AdminGraduationMessageListView(_AdminBase):
    """GET /api/v1/admin/graduation-messages/ — the moderation queue (F9a). Reviewer +
    super (viewer is read-only staff and may also read). ``?status=pending`` (default)
    filters; ``?status=all`` returns everything. Staff see the full text + scan
    outcome — they are NOT the anonymity boundary."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        # org-fence: _org_scoped on the application join, applied below.
        qs = GraduationMessage.objects.select_related('application').all()
        qs = self._org_scoped(qs, admin, field='application__owning_organisation_id')
        status_f = request.GET.get('status', 'pending')
        if status_f != 'all':
            qs = qs.filter(status=status_f)
        paginator = FlexiblePageNumberPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = AdminGraduationMessageSerializer(page, many=True).data
        return paginator.envelope(
            data, results_key='messages', total_count=paginator.page.paginator.count,
        )


class AdminGraduationMessageReviewView(_AdminBase):
    """POST /api/v1/admin/graduation-messages/<id>/review/ — approve or reject a
    graduation thank-you (F9a). Reviewer + super only (viewer is read-only). Body:
    ``{action: 'approve'|'reject', scrubbed_text?, review_note?}``. On approve the
    ``scrubbed_text`` (defaults to the raw text) is RE-SCANNED so a staff edit can
    never reintroduce an identifier (400 `scrubbed_leak`). Only a `pending` message
    can be approved; `pending`/`blocked` can be rejected."""

    def post(self, request, pk):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        # org-fence: _org_allows(message.application) checked immediately below.
        message = GraduationMessage.objects.select_related(
            'application', 'application__profile').filter(pk=pk).first()
        if message is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if not self._org_allows(admin, message.application):
            # Cross-org write: 404, don't leak existence (Sprint 3a).
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        action = (request.data.get('action') or '').strip()
        by_email = getattr(admin, 'email', '') or ''
        try:
            if action == 'approve':
                in_programme_service.approve_graduation_message(
                    message, by_email=by_email,
                    scrubbed_text=request.data.get('scrubbed_text'),
                )
            elif action == 'reject':
                in_programme_service.reject_graduation_message(
                    message, by_email=by_email,
                    review_note=request.data.get('review_note', ''),
                )
            else:
                return Response({'error': 'action must be approve or reject',
                                 'code': 'bad_action'}, status=status.HTTP_400_BAD_REQUEST)
        except in_programme_service.InProgrammeError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminGraduationMessageSerializer(message).data)


class _BursaryAdminBase(_AdminBase):
    """Shared lookup for the bursary-agreement admin actions."""

    def _agreement(self, pk):
        from .models import BursaryAgreement
        return BursaryAgreement.objects.select_related(
            'application', 'application__profile', 'witness_org').filter(application_id=pk).first()


class AdminBursaryCountersignView(_BursaryAdminBase):
    """POST — the Foundation countersignature on a student's bursary agreement.
    SUPER-ONLY (the Foundation acts as counterparty). Stamps foundation_signed_by/_at
    with the acting super-admin's name and regenerates the PDF."""

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super_admin or self.has_role(admin, 'super')):
            return self._deny_role()
        agreement = self._agreement(pk)
        if agreement is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        from . import bursary
        from .serializers import BursaryAgreementSerializer
        bursary.countersign_foundation(agreement, by_name=getattr(admin, 'name', '') or '')
        return Response(BursaryAgreementSerializer(agreement).data)


class AdminBursaryWitnessView(_BursaryAdminBase):
    """POST — the partner organisation's (non-blocking) witness attestation. Allowed for
    a PartnerAdmin whose org == the application's referring org (else 403); a super may
    also witness. This NEVER blocks the award lifecycle — it is a record only."""

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        agreement = self._agreement(pk)
        if agreement is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        profile = agreement.application.profile
        # tenancy: GRANDFATHERED exception — witness authority is REFERRAL semantics
        # (the org that referred the student attests), which is orthogonal to the
        # ownership fence. This is the ONE place `admin.org`/`referred_by_org` is
        # intentionally used for authorisation. A non-blocking record only.
        org = getattr(profile, 'referred_by_org', None) if profile else None
        is_super = bool(admin.is_super_admin or self.has_role(admin, 'super'))
        is_referring_partner = bool(
            org is not None and admin.org_id is not None and admin.org_id == org.id)
        if not (is_super or is_referring_partner):
            return self._deny_role()
        from . import bursary
        from .serializers import BursaryAgreementSerializer
        bursary.record_witness(
            agreement, org=org,
            by_name=getattr(admin, 'name', '') or '',
            witness_name=request.data.get('witness_name', '') or '')
        return Response(BursaryAgreementSerializer(agreement).data)


# ── Payments module (Vircle payment runs) — admin + org_admin, org-fenced (P2) ────
# Access: an `admin` or `org_admin` (super passes), and the run is org-fenced (a
# cross-org run is 404, never 403). Reviewer/qc/partner -> 403. The service
# (apps.scholarship.payments) owns the state machine; these views are thin.
from decimal import Decimal as _Decimal


def _payment_item_dict(item):
    app = item.application
    profile = getattr(app, 'profile', None)
    return {
        'id': item.id, 'application_id': app.id,
        'name': getattr(profile, 'name', '') or '',
        'nric': getattr(profile, 'nric', '') or '',
        'vircle_id': item.vircle_id_snapshot or (app.vircle_id or ''),
        'award_amount': str(item.award_amount_snapshot),
        'paid_to_date': str(item.paid_to_date_snapshot),
        'amount': str(item.amount),
        'credit_applied': str(item.credit_applied),
        'included': item.included,
        'exclude_reason': item.exclude_reason,
    }


def _sig(name, email, at):
    return {'name': name, 'email': email, 'at': at} if at else None


def _payment_run_summary(run):
    included = [i for i in run.items.all() if i.included]
    total = sum((i.amount for i in included), _Decimal('0'))
    return {
        'id': run.id, 'reference': run.reference, 'payment_date': run.payment_date,
        'period_month': run.period_month,
        'status': run.status, 'students': len(included), 'total': str(total),
        'created_at': run.created_at,
    }


def _payment_run_detail(run):
    items = list(run.items.select_related('application', 'application__profile').all())
    included = [i for i in items if i.included]
    total = sum((i.amount for i in included), _Decimal('0'))
    # "Skipped this run" -- payable-status + started students who fail D4-4/5/6 (greyed,
    # shown not hidden). Computed live from the eligibility choke-point. A student who IS
    # an item of this run is never "skipped" by it -- without this, a COMPLETED run's own
    # students re-enter as already_paid (they now sit in a completed run for the period).
    from . import payments
    item_app_ids = {i.application_id for i in items}
    skipped = []
    for row in payments.eligible_rows(run.organisation, run.payment_date, period_month=run.period_month):
        if not row['eligible'] and row['application'].id not in item_app_ids:
            a = row['application']
            p = getattr(a, 'profile', None)
            skipped.append({'application_id': a.id, 'name': getattr(p, 'name', '') or '',
                            'nric': getattr(p, 'nric', '') or '', 'reasons': row['reasons']})
    from django.conf import settings as _settings
    return {
        'id': run.id, 'reference': run.reference, 'payment_date': run.payment_date,
        'period_month': run.period_month,
        'vircle_email': getattr(_settings, 'VIRCLE_PAYMENTS_EMAIL', ''),
        'status': run.status, 'note': run.note, 'drive_file_url': run.drive_file_url,
        'created_by': run.created_by, 'created_at': run.created_at,
        'admin_signed': _sig(run.admin_signed_name, run.admin_signed_email, run.admin_signed_at),
        'finance_signed': _sig(run.finance_signed_name, run.finance_signed_email, run.finance_signed_at),
        # Whether THIS org's chain includes the finance check, computed server-side and read
        # verbatim by the frontend. The activation rule lives in exactly one place
        # (payments.finance_check_required); mirroring it in TypeScript would make it the sixth
        # keep-in-sync pair this codebase has had to un-drift (see docs/lessons.md).
        'finance_check_required': payments.finance_check_required(run.organisation),
        'org_admin_signed': _sig(run.org_admin_signed_name, run.org_admin_signed_email, run.org_admin_signed_at),
        'items': [_payment_item_dict(i) for i in items],
        'skipped': skipped,
        'students': len(included), 'total': str(total),
    }


_PAYMENTS_READ_ROLES = ('admin', 'org_admin', 'finance')
_PAYMENTS_WRITE_ROLES = ('admin', 'org_admin')


class _PaymentsBase(_AdminBase):
    """Shared gate + org-fenced run lookup for the Payments endpoints."""
    def _payments_admin(self, request, roles=_PAYMENTS_READ_ROLES):
        """Gate a Payments endpoint. The default admits `finance` — correct for the READ
        endpoints (list, detail, CSV) and for Sign, whose per-step role logic lives in
        `payments.sign`. The MUTATING endpoints (create a run, edit an item, cancel) pass
        ``roles=_PAYMENTS_WRITE_ROLES`` explicitly: finance checks a run, it never authors one.
        `payments.sign`'s `wrong_role` remains the backstop on the signing step."""
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (admin.is_super or admin.role in roles):
            return None, self._deny_role()
        return admin, None

    def _run_for(self, admin, pk):
        """The run IFF this admin's organisation owns it (super global); else None -> 404."""
        from .models import PaymentRun
        run = PaymentRun.objects.filter(pk=pk).select_related('organisation').first()
        if run is None:
            return None
        if admin.is_super:
            return run
        if run.organisation_id != admin.owning_organisation_id:
            return None   # cross-org -> 404, no existence leak
        return run


class AdminPaymentRunListView(_PaymentsBase):
    """GET list (org-fenced, newest first) . POST {payment_date} create a draft run."""
    def get(self, request):
        admin, err = self._payments_admin(request)
        if err:
            return err
        from .models import PaymentRun
        qs = PaymentRun.objects.all().prefetch_related('items').order_by('-payment_date', '-id')
        if not admin.is_super:
            qs = qs.filter(organisation_id=admin.owning_organisation_id)
        return Response({'runs': [_payment_run_summary(r) for r in qs]})

    def post(self, request):
        admin, err = self._payments_admin(request, roles=_PAYMENTS_WRITE_ROLES)
        if err:
            return err
        org = admin.owning_organisation
        if org is None:
            # The payments module is org-scoped; a caller with no owning organisation
            # (e.g. a bare super) has no org context to create a run in.
            return Response({'error': 'no_org', 'code': 'no_org'}, status=status.HTTP_400_BAD_REQUEST)
        from django.utils.dateparse import parse_date
        pd = parse_date((request.data.get('payment_date') or '').strip())
        if pd is None:
            return Response({'error': 'bad_date', 'code': 'bad_date'}, status=status.HTTP_400_BAD_REQUEST)
        # The MONTH this run pays for (dedup key). Accepts 'YYYY-MM' or a full date; defaults to
        # the payment date's own month when omitted.
        pm_raw = (request.data.get('payment_month') or '').strip()
        if len(pm_raw) == 7:
            pm_raw += '-01'
        pm = parse_date(pm_raw) if pm_raw else pd
        if pm is None:
            return Response({'error': 'bad_month', 'code': 'bad_month'}, status=status.HTTP_400_BAD_REQUEST)
        from . import payments
        try:
            run = payments.create_run(org, pd, pm, by_email=getattr(admin, 'email', '') or '')
        except payments.PaymentsError as e:
            body = {'error': e.code, 'code': e.code}
            if e.code == 'too_early':
                # Return the earliest valid pay date so the UI can name it in the message. The
                # rule lives ONLY in payments.earliest_payment_date — deliberately not mirrored
                # in the frontend, which would make it a keep-in-sync pair that drifts.
                body['earliest'] = payments.earliest_payment_date(pm).isoformat()
            return Response(body, status=status.HTTP_400_BAD_REQUEST)
        return Response(_payment_run_detail(run), status=status.HTTP_201_CREATED)


class AdminPaymentRunDetailView(_PaymentsBase):
    """GET a run's detail: items + greyed skipped list + totals + signatures."""
    def get(self, request, pk):
        admin, err = self._payments_admin(request)
        if err:
            return err
        run = self._run_for(admin, pk)
        if run is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(_payment_run_detail(run))


class AdminPaymentRunItemView(_PaymentsBase):
    """PATCH a run item -- toggle include/exclude(+reason), edit amount (draft only)."""
    def patch(self, request, pk, item_id):
        admin, err = self._payments_admin(request, roles=_PAYMENTS_WRITE_ROLES)
        if err:
            return err
        run = self._run_for(admin, pk)
        if run is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from .models import PaymentRunItem
        item = (PaymentRunItem.objects.filter(pk=item_id, run=run)
                .select_related('application', 'run').first())
        if item is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        kwargs = {}
        if 'included' in request.data:
            kwargs['included'] = bool(request.data.get('included'))
        if 'exclude_reason' in request.data:
            kwargs['exclude_reason'] = request.data.get('exclude_reason')
        if 'amount' in request.data:
            kwargs['amount'] = request.data.get('amount')
        from . import payments
        try:
            payments.set_item(item, **kwargs)
        except payments.PaymentsError as e:
            return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        return Response(_payment_run_detail(run))


class AdminPaymentRunSignView(_PaymentsBase):
    """POST {typed_name} -- admin (maker) sign, finance (checker) sign when the org's chain
    includes that step, or org_admin (approver) countersign (which completes the run). The
    per-step role logic + name/pairwise-distinctness checks live in payments.sign; this view
    admits every payments role and lets the service refuse the wrong step."""
    def post(self, request, pk):
        admin, err = self._payments_admin(request)
        if err:
            return err
        run = self._run_for(admin, pk)
        if run is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from . import payments
        try:
            payments.sign(run, admin, request.data.get('typed_name') or '')
        except payments.PaymentsError as e:
            return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        return Response(_payment_run_detail(run))


class AdminPaymentRunCancelView(_PaymentsBase):
    """POST -- cancel a run at any pre-completion status. admin/org_admin only."""
    def post(self, request, pk):
        admin, err = self._payments_admin(request, roles=_PAYMENTS_WRITE_ROLES)
        if err:
            return err
        run = self._run_for(admin, pk)
        if run is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from . import payments
        try:
            payments.cancel(run, by=getattr(admin, 'email', '') or '')
        except payments.PaymentsError as e:
            return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        return Response(_payment_run_detail(run))


class AdminPaymentRunCsvView(_PaymentsBase):
    """GET the run's payment CSV (any status >= admin_signed) as a download."""
    def get(self, request, pk):
        admin, err = self._payments_admin(request)
        if err:
            return err
        run = self._run_for(admin, pk)
        if run is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # finance_checked included: the checker must be able to READ the payment file to check
        # it, and a run stays at that status while awaiting countersignature.
        if run.status not in ('admin_signed', 'finance_checked', 'completed'):
            return Response({'error': 'not_ready', 'code': 'not_ready'},
                            status=status.HTTP_400_BAD_REQUEST)
        from django.http import HttpResponse
        from . import sheets
        resp = HttpResponse(sheets.payment_csv_text(run), content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="{run.reference}.csv"'
        return resp


class AdminPaymentFundingSummaryView(_PaymentsBase):
    """GET /api/v1/admin/payments/funding-summary/ — the org's payable students with award /
    paid / remaining / eWallet, plus org totals for the footer (Sprint 14).

    Rides `_PaymentsBase` with the DEFAULT read gate, so it is visible to super / admin /
    org_admin / finance and refused to reviewer / qc / partner. It lives inside the Payments
    module by design: it is the funding-side view of the same cohort the runs pay, and it is the
    only student data a `finance` admin can reach (`_b40_scope` = 'none').

    Serialised by `FundingSummaryRowSerializer` — an explicit allowlist, NOT a model dump.

    tenancy: org-fenced on `owning_organisation`, the same fence `payments.eligible_rows` uses;
    a super with no org context gets `no_org` (there is no "every tenant's students" reading of
    this page). Classified in test_org_fence.py.
    """
    def get(self, request):
        admin, err = self._payments_admin(request)
        if err:
            return err
        org = admin.owning_organisation
        if org is None:
            return Response({'error': 'no_org', 'code': 'no_org'},
                            status=status.HTTP_400_BAD_REQUEST)
        from . import payments
        from .serializers_admin import FundingSummaryRowSerializer
        # A caller with no org context was refused with `no_org` above, so the filter below
        # can never be a no-op and this can never run unfenced.
        # org-fence: owning_organisation=org (the fence payments.eligible_rows uses).
        qs = (ScholarshipApplication.objects
              .filter(owning_organisation=org, status__in=payments.PAYABLE_STATUSES)
              .select_related('profile').order_by('id'))
        rows = FundingSummaryRowSerializer(qs, many=True).data
        totals = {
            'students': len(rows),
            'award_total': str(sum(_Decimal(r['award_amount']) for r in rows)),
            'paid_total': str(sum(_Decimal(r['paid_to_date']) for r in rows)),
            'remaining_total': str(sum(_Decimal(r['remaining']) for r in rows)),
        }
        return Response({'rows': rows, 'totals': totals})


# ── Contract module (org-owned versioned bursary templates) — S3 admin API ────────
# Access: super or org_admin ONLY, org-fenced (a cross-org template is 404, never
# 403). Deploy is SUPER-only (org_admin -> 403). The service (apps.scholarship.
# contracts) owns the lifecycle + validation; these views are thin. generate-quiz
# is draft-only and calls the mockable Gemini seam (never live in tests).

_CONTRACT_RULE_LABELS = {
    'T1': 'Version + counterparty complete',
    'T2': 'Lawyer vetting recorded',
    'C1': 'Clauses numbered 1..N (contiguous)',
    'C2': 'English complete on every clause',
    'Q1': 'At least one quiz question',
    'Q2': 'Each quiz question is structurally valid',
    'Q3': 'No quiz on a non-candidate clause',
    'Q4': 'Quiz languages agree (same correct answer)',
    'S1': 'A default schedule row exists',
    'S2': 'Schedule row shapes are valid',
    'S3': 'Each schedule total is an allowed amount',
    'S4': 'Schedule totals match the award amounts',
    'P1': 'Uses only v1-supported options',
    'W1': 'Guarantor wording vs co-signer config',
    'W2': 'Some translations are incomplete',
    'W3': 'A clause body contains an RM figure',
}


def _contract_clause_dict(c):
    return {
        'order': c.order,
        'level': c.level,
        'heading_en': c.heading_en, 'heading_ms': c.heading_ms, 'heading_ta': c.heading_ta,
        'body_en': c.body_en, 'body_ms': c.body_ms, 'body_ta': c.body_ta,
        'is_quiz_candidate': c.is_quiz_candidate,
        'quiz_en': c.quiz_en, 'quiz_ms': c.quiz_ms, 'quiz_ta': c.quiz_ta,
        'quiz_generated_model': c.quiz_generated_model,
    }


def _contract_schedule_dict(r):
    return {
        'pathway': r.pathway, 'variant': r.variant,
        'label_en': r.label_en, 'label_ms': r.label_ms, 'label_ta': r.label_ta,
        'monthly_amount': str(r.monthly_amount), 'start_month': r.start_month,
        'paid_offsets': list(r.paid_offsets or []), 'sort_order': r.sort_order,
        'months': len(r.paid_offsets or []), 'total': str(r.total),
    }


def _contract_template_summary(t):
    return {
        'id': t.id, 'organisation': t.organisation.code, 'version': t.version,
        'status': t.status, 'languages_available': t.languages_available,
        'vetted_by_name': t.vetted_by_name, 'vetted_on': t.vetted_on,
        'deployed_by_at': t.deployed_by_at, 'created_at': t.created_at,
        'updated_at': t.updated_at,
    }


def _contract_template_detail(t):
    d = _contract_template_summary(t)
    d.update({
        'title_en': t.title_en, 'title_ms': t.title_ms, 'title_ta': t.title_ta,
        'preamble_en': t.preamble_en, 'preamble_ms': t.preamble_ms, 'preamble_ta': t.preamble_ta,
        'progress_standard_en': t.progress_standard_en, 'progress_standard_ms': t.progress_standard_ms,
        'progress_standard_ta': t.progress_standard_ta,
        'counterparty_name': t.counterparty_name, 'counterparty_title': t.counterparty_title,
        'counterparty_nric': t.counterparty_nric, 'counterparty_address': t.counterparty_address,
        'counterparty_notify_emails': t.counterparty_notify_emails or [],
        'parent_role': t.parent_role, 'parent_pin_required': t.parent_pin_required,
        'witness_policy': t.witness_policy,
        'vetting_attested_by_email': t.vetting_attested_by_email,
        'vetting_attested_at': t.vetting_attested_at,
        'created_by_email': t.created_by_email, 'submitted_by_email': t.submitted_by_email,
        'submitted_by_at': t.submitted_by_at, 'deployed_by_email': t.deployed_by_email,
        'archived_at': t.archived_at,
        'clauses': [_contract_clause_dict(c) for c in t.clauses.all().order_by('order')],
        'schedule': [_contract_schedule_dict(r) for r in t.schedule_rows.all()],
    })
    return d


def _contract_validation_dict(result):
    return {
        'ok': result.ok,
        'errors': [{'code': c, 'label': _CONTRACT_RULE_LABELS.get(c, c)} for c in result.errors],
        'warnings': [{'code': c, 'label': _CONTRACT_RULE_LABELS.get(c, c)} for c in result.warnings],
    }


def _contracts_err(e):
    body = {'error': e.code, 'code': e.code}
    if getattr(e, 'errors', None):
        body['errors'] = e.errors
    http = status.HTTP_403_FORBIDDEN if e.code == 'deploy_forbidden' else status.HTTP_400_BAD_REQUEST
    return Response(body, status=http)


class _ContractsBase(_AdminBase):
    """Gate + org-fenced template lookup for the Contract admin endpoints.
    super or org_admin only; deploy is super-only; cross-org -> 404."""

    def _not_found(self):
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    def _contract_admin(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (self.has_role(admin, 'super') or admin.role == 'org_admin'):
            return None, self._deny_role()
        return admin, None

    def _template_for(self, request, pk):
        """(template, admin, None) if the caller may access it; else (None, None, err).
        Cross-org -> 404 (no existence leak). Super global; org_admin own-org only."""
        admin, err = self._contract_admin(request)
        if err:
            return None, None, err
        from .models import ContractTemplate
        template = (ContractTemplate.objects.filter(pk=pk)
                    .select_related('organisation')
                    .prefetch_related('clauses', 'schedule_rows').first())
        if template is None:
            return None, None, self._not_found()
        if not self.has_role(admin, 'super') and template.organisation_id != admin.owning_organisation_id:
            return None, None, self._not_found()   # cross-org 404
        return template, admin, None

    def _target_org(self, request, admin):
        """The org a new template belongs to: super -> the request 'organisation' code
        (required); org_admin -> own owning org."""
        from apps.courses.models import PartnerOrganisation
        if self.has_role(admin, 'super'):
            code = (request.data.get('organisation') or '').strip()
            if not code:
                return None, Response({'error': 'organisation_required', 'code': 'organisation_required'},
                                      status=status.HTTP_400_BAD_REQUEST)
            org = PartnerOrganisation.objects.filter(code=code).first()
            if org is None:
                return None, Response({'error': 'unknown_organisation', 'code': 'unknown_organisation'},
                                      status=status.HTTP_400_BAD_REQUEST)
            return org, None
        org = admin.owning_organisation
        if org is None:
            return None, self._deny_role()
        return org, None


class AdminContractTemplateListView(_ContractsBase):
    """GET list (org-fenced; super may ?organisation=<code>). POST create a DRAFT
    ({version, organisation? (super), copy_from?})."""
    def get(self, request):
        admin, err = self._contract_admin(request)
        if err:
            return err
        from .models import ContractTemplate
        qs = (ContractTemplate.objects.select_related('organisation')
              .prefetch_related('clauses', 'schedule_rows')
              .order_by('organisation_id', '-created_at'))
        if not self.has_role(admin, 'super'):
            qs = qs.filter(organisation_id=admin.owning_organisation_id)
        else:
            org_f = (request.query_params.get('organisation') or '').strip()
            if org_f:
                qs = qs.filter(organisation__code=org_f)
        return Response({'templates': [_contract_template_summary(t) for t in qs]})

    def post(self, request):
        admin, err = self._contract_admin(request)
        if err:
            return err
        org, oerr = self._target_org(request, admin)
        if oerr:
            return oerr
        from . import contracts
        from .models import ContractTemplate
        copy_from = None
        cf = request.data.get('copy_from')
        if cf:
            copy_from = ContractTemplate.objects.filter(pk=cf, organisation=org).first()
            if copy_from is None:
                return Response({'error': 'copy_from_not_found', 'code': 'copy_from_not_found'},
                                status=status.HTTP_400_BAD_REQUEST)
        try:
            template = contracts.create_template(
                org, (request.data.get('version') or '').strip(),
                created_by_email=getattr(admin, 'email', '') or '', copy_from=copy_from)
        except contracts.ContractsError as e:
            return _contracts_err(e)
        return Response(_contract_template_detail(template), status=status.HTTP_201_CREATED)


class AdminContractTemplateDetailView(_ContractsBase):
    """GET the full template. PATCH updates whitelisted config fields (draft only)."""
    def get(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        return Response(_contract_template_detail(template))

    def patch(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from . import contracts
        fields = {k: v for k, v in request.data.items() if k in contracts._CONFIG_FIELDS}
        try:
            contracts.update_config(template, **fields)
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractClausesView(_ContractsBase):
    """PUT the full ordered clause list (draft only)."""
    def put(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        clauses = request.data.get('clauses')
        if not isinstance(clauses, list):
            return Response({'error': 'clauses must be a list', 'code': 'bad_body'},
                            status=status.HTTP_400_BAD_REQUEST)
        from . import contracts
        try:
            contracts.replace_clauses(template, clauses)
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractScheduleView(_ContractsBase):
    """PUT the full payment schedule (draft only)."""
    def put(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        rows = request.data.get('rows')
        if not isinstance(rows, list):
            return Response({'error': 'rows must be a list', 'code': 'bad_body'},
                            status=status.HTTP_400_BAD_REQUEST)
        from . import contracts
        try:
            contracts.replace_schedule(template, rows)
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractGenerateQuizView(_ContractsBase):
    """POST — generate a clause's quiz via Gemini (draft only; billable, on-demand).
    The Gemini call is the mockable seam contracts._gemini_generate (never live in tests)."""
    def post(self, request, pk, order):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        clause = template.clauses.filter(order=order).first()
        if clause is None:
            return self._not_found()
        from . import contracts
        try:
            contracts.generate_quiz(clause, model=request.data.get('model') or None)
        except contracts.ContractsError as e:
            return _contracts_err(e)
        return Response(_contract_clause_dict(clause))


class AdminContractVettingView(_ContractsBase):
    """POST — record the lawyer-vetting attestation ({vetted_by_name, vetted_on}).
    The attesting admin's own email is stamped as the attester."""
    def post(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from django.utils.dateparse import parse_date
        from . import contracts
        try:
            contracts.record_vetting(
                template,
                vetted_by_name=(request.data.get('vetted_by_name') or '').strip(),
                vetted_on=parse_date((request.data.get('vetted_on') or '').strip()),
                attested_by_email=(getattr(admin, 'email', '') or '').strip())
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractValidateView(_ContractsBase):
    """GET — the deploy-validation result (errors + warnings), mirroring the service."""
    def get(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from . import contracts
        return Response(_contract_validation_dict(contracts.validate_for_deployment(template)))


class AdminContractSubmitView(_ContractsBase):
    """POST — draft -> pending_deployment (refuses when validation fails)."""
    def post(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from . import contracts
        try:
            contracts.submit_for_deployment(
                template, submitted_by_email=getattr(admin, 'email', '') or '')
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractRevertView(_ContractsBase):
    """POST — pending_deployment -> draft (to edit further)."""
    def post(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from . import contracts
        try:
            contracts.revert_to_draft(template)
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractDeployView(_ContractsBase):
    """POST — pending_deployment -> active (SUPER only; org_admin -> 403). Atomically
    archives the org's previous active version."""
    def post(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        if not self.has_role(admin, 'super'):
            return self._deny_role()   # deploy is super-only
        from . import contracts
        try:
            contracts.deploy(template, is_super=True,
                             deployed_by_email=getattr(admin, 'email', '') or '')
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractPreviewView(_ContractsBase):
    """GET — a rendered preview (HTML, or ?output=pdf). Sample particulars only.

    NOTE: the PDF selector is ``?output=pdf``, NOT ``?format=pdf`` — ``format`` is DRF's
    RESERVED content-negotiation query param, and ``?format=pdf`` makes DRF raise Http404
    (no 'pdf' renderer) during content negotiation, BEFORE this view runs (TD-163)."""
    def get(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from django.http import HttpResponse
        from . import contracts
        html = contracts.render_preview_html(template, request.query_params.get('locale', 'en'))
        if request.query_params.get('output') == 'pdf':
            from . import bursary
            try:
                pdf = bursary.generate_pdf(html)
            except bursary.BursaryError as e:
                return Response({'error': e.code, 'code': e.code},
                                status=status.HTTP_400_BAD_REQUEST)
            resp = HttpResponse(pdf, content_type='application/pdf')
            resp['Content-Disposition'] = f'inline; filename="contract_{template.version}.pdf"'
            return resp
        return HttpResponse(html, content_type='text/html')


class AdminContractQuizPreviewView(_ContractsBase):
    """GET — the comprehension checkpoints served for a locale (author preview)."""
    def get(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from . import contracts
        loc = contracts.resolve_locale(request.query_params.get('locale', 'en'), template)
        return Response({'template_version': template.version, 'locale_used': loc,
                         'checkpoints': contracts.quiz_checkpoints(template, loc)})


class AdminContractImportDocxView(_ContractsBase):
    """POST a .docx — parse it (deterministically from the doc's own heading/list
    numbering; Gemini only as a fallback for unstyled docs) into a PROPOSED clause list
    plus a detected title/preamble, for the author to review (draft-only). Nothing is
    saved and the uploaded file is NOT retained — on confirm the FE PUTs the reviewed
    clauses and fills a blank title/preamble. Failures return a code the FE degrades on."""
    from rest_framework.parsers import MultiPartParser
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        if template.status != 'draft':
            return Response({'error': 'not_draft', 'code': 'not_draft'},
                            status=status.HTTP_400_BAD_REQUEST)
        upload = request.FILES.get('file')
        if upload is None:
            return Response({'error': 'no_file', 'code': 'no_file'},
                            status=status.HTTP_400_BAD_REQUEST)
        from . import contracts
        try:
            proposal = contracts.segment_docx(upload.read())   # bytes only; never stored
        except contracts.ContractsError as e:
            return _contracts_err(e)
        # PROPOSED — the FE reviews, then PUTs clauses (+ fills blank title/preamble/party fields).
        return Response({
            'clauses': proposal['clauses'],
            'title': proposal.get('title', ''),
            'preamble': proposal.get('preamble', ''),
            'counterparty': proposal.get('counterparty', {}),
        })


# ── Requests space (Sprint 15) ─────────────────────────────────────────────────────
# The org-section "Requests" area: bug/feature forms → AI reviewer → owner-gated hours
# quotes. Ships DARK behind REQUESTS_ENABLED — every route 404s while the flag is off
# (the FE hub card is hidden by the same 404-probe, so there is no client flag). Service =
# apps.scholarship.org_requests; org-fenced via _org_request_for (cross-org 404), role-gated
# per the endpoint table (org-side vs super-only). All classes classified in
# test_org_fence.py FENCED_OR_EXEMPT and the OrgRequest model is WATCHED (its raw admin
# queries below all carry an # org-fence pragma).

def _org_request_err(e):
    """Map an OrgRequestError code to a 4xx. bad_transition/bug_is_free/... are 4xx; the two
    AI-availability codes are 503 (the model is unconfigured/unavailable, not the caller's fault)."""
    if e.code in ('triage_ai_unconfigured', 'triage_ai_unavailable'):
        return Response({'error': e.code, 'code': e.code},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)


class _OrgRequestsBase(_AdminBase):
    """Shared flag/role/org gate for the Requests-space endpoints.

    404-FIRST dark ship: with ``REQUESTS_ENABLED`` off, ``_flag`` short-circuits every handler to
    404 BEFORE any auth/role work — the same shape as the sponsor-pool flag gate — so the feature
    leaks no existence signal while dark. When the flag is on, role denials are REAL 403s and a
    cross-org id is 404 (no existence leak)."""

    def _flag(self):
        """Returns an error Response (404) when the feature is dark, else None."""
        if not getattr(settings, 'REQUESTS_ENABLED', False):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        return None

    def _not_found(self):
        return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

    def _org_request_for(self, admin, pk):
        # org-fence: fetch then re-gate to the caller's organisation (super global); a cross-org
        # id returns None -> 404 (no existence leak). This is the ONLY OrgRequest.objects read.
        req = (OrgRequest.objects
               .select_related('organisation', 'submitted_by').filter(pk=pk).first())
        if req is None:
            return None
        if self.has_role(admin, 'super'):
            return req
        if req.organisation_id != admin.owning_organisation_id:
            return None
        return req

    # ── role prologues (flag already assumed checked by the caller) ──────────────
    def _org_side(self, request):
        """Caller must be an org_admin or super (the roles that OPEN the Requests area)."""
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (admin.is_super or admin.role == 'org_admin'):
            return None, self._deny_role()
        return admin, None

    def _requestee(self, request, pk, *, allow_super=False):
        """A requestee WRITE (answer/defer/modify → org_admin only; approve/decline → +super).
        Returns (admin, req, None) or (None, None, err)."""
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not ((admin.role == 'org_admin') or (allow_super and admin.is_super)):
            return None, None, self._deny_role()
        req = self._org_request_for(admin, pk)
        if req is None:
            return None, None, self._not_found()
        return admin, req, None

    def _super_side(self, request, pk):
        """A super-only WRITE (triage/quote/requote/schedule/done/ai-rerun)."""
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not admin.is_super:
            return None, None, self._deny_role()
        req = self._org_request_for(admin, pk)
        if req is None:
            return None, None, self._not_found()
        return admin, req, None

    def _serialize(self, admin, req):
        """Super sees the OWNER payload (incl. the AI draft + triage); everyone else the
        allowlist ORG payload (no ai_* / triage ever)."""
        if self.has_role(admin, 'super'):
            return OrgRequestOwnerSerializer(req).data
        return OrgRequestOrgSerializer(req).data


class AdminOrgRequestListView(_OrgRequestsBase):
    """GET list (org-fenced) . POST create a request. org_admin + super."""

    def get(self, request):
        gate = self._flag()
        if gate:
            return gate
        admin, err = self._org_side(request)
        if err:
            return err
        # org-fence: list scoped to the caller's organisation (super global) via _org_scoped.
        qs = self._org_scoped(
            OrgRequest.objects.select_related('organisation', 'submitted_by'),
            admin, field='organisation_id')
        return Response({'requests': [self._serialize(admin, r) for r in qs]})

    def post(self, request):
        gate = self._flag()
        if gate:
            return gate
        admin, err = self._org_side(request)
        if err:
            return err
        from . import org_requests
        # Whose org the request belongs to: the org_admin's own; a super must name organisation_id.
        if admin.is_super:
            org_id = request.data.get('organisation_id')
            from apps.courses.models import PartnerOrganisation
            org = PartnerOrganisation.objects.filter(pk=org_id).first() if org_id else None
            if org is None:
                return Response({'error': 'org_required', 'code': 'org_required'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            org = admin.owning_organisation
            if org is None:
                return Response({'error': 'no_org', 'code': 'no_org'},
                                status=status.HTTP_400_BAD_REQUEST)
        try:
            req = org_requests.create_request(
                org, admin, kind=(request.data.get('kind') or '').strip(),
                title=request.data.get('title') or '',
                description=request.data.get('description') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        # Best-effort post-commit: notify the owner + auto-run the AI reviewer (never fails create).
        try:
            from . import emails
            emails.send_org_request_submitted_email(req)
        except Exception:
            logger.warning('Requests: submit-notify failed for OrgRequest %s', req.pk, exc_info=True)
        org_requests.auto_run_ai_review(req)
        req.refresh_from_db()
        return Response(self._serialize(admin, req), status=status.HTTP_201_CREATED)


class AdminOrgRequestCountView(_OrgRequestsBase):
    """GET {count} for the nav / Administration-hub badge. Super: global count of SUBMITTED
    (awaiting triage). org_admin: own org's requests that need THEIR attention — quoted (awaiting
    accept) OR carrying an unanswered clarifying question. org_admin + super."""

    def get(self, request):
        gate = self._flag()
        if gate:
            return gate
        admin, err = self._org_side(request)
        if err:
            return err
        if self.has_role(admin, 'super'):
            # org-fence: super is global by design for the triage badge.
            return Response({'count': OrgRequest.objects.filter(status='submitted').count()})
        # org-fence: own org only (org_admin).
        qs = OrgRequest.objects.filter(
            organisation_id=admin.owning_organisation_id,
        ).exclude(status__in=('done', 'declined')).only('status', 'clarifications')
        count = 0
        for r in qs:
            if r.status == 'quoted' or any(
                    not c.get('answer') and c.get('question') for c in (r.clarifications or [])):
                count += 1
        return Response({'count': count})


class AdminOrgRequestDetailView(_OrgRequestsBase):
    """GET one request (org_admin own else 404; super). org_admin + super."""

    def get(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, err = self._org_side(request)
        if err:
            return err
        req = self._org_request_for(admin, pk)
        if req is None:
            return self._not_found()
        return Response(self._serialize(admin, req))


class AdminOrgRequestAnswerView(_OrgRequestsBase):
    """POST answer a clarifying question (org_admin own org). No status transition."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk)
        if err:
            return err
        from . import org_requests
        try:
            req = org_requests.answer_clarification(
                req, request.data.get('answer') or '',
                index=request.data.get('index'))
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        # Best-effort: notify the owner + re-run the AI reviewer on the new answer.
        try:
            from . import emails
            emails.send_org_request_answered_email(req)
        except Exception:
            logger.warning('Requests: answer-notify failed for OrgRequest %s', req.pk, exc_info=True)
        org_requests.auto_run_ai_review(req)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


class AdminOrgRequestApproveView(_OrgRequestsBase):
    """POST accept a quote (quoted/deferred → approved). org_admin own org, or super."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk, allow_super=True)
        if err:
            return err
        from . import org_requests
        by_role = 'super' if admin.is_super else 'org_admin'
        try:
            req = org_requests.approve(req, admin, by_role=by_role)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        try:
            from . import emails
            emails.send_org_request_accepted_email(req)
        except Exception:
            logger.warning('Requests: accept-notify failed for OrgRequest %s', req.pk, exc_info=True)
        return Response(self._serialize(admin, req))


class AdminOrgRequestDeferView(_OrgRequestsBase):
    """POST defer a quote (quoted → deferred). org_admin own org."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk)
        if err:
            return err
        from . import org_requests
        try:
            req = org_requests.defer(req, admin)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        return Response(self._serialize(admin, req))


class AdminOrgRequestModifyView(_OrgRequestsBase):
    """POST modify (amend the description; quoted/deferred → submitted). org_admin own org."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk)
        if err:
            return err
        from . import org_requests
        try:
            req = org_requests.modify(req, admin, description=request.data.get('description') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        org_requests.auto_run_ai_review(req)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


class AdminOrgRequestDeclineView(_OrgRequestsBase):
    """POST decline/withdraw (→ declined, terminal). org_admin own org (withdraw, reason
    optional), or super (decline, reason required)."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk, allow_super=True)
        if err:
            return err
        from . import org_requests
        by_role = 'super' if admin.is_super else 'org_admin'
        try:
            req = org_requests.decline(req, admin, by_role=by_role,
                                       reason=request.data.get('reason') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        return Response(self._serialize(admin, req))


class AdminOrgRequestTriageView(_OrgRequestsBase):
    """POST triage (submitted → triaged). Super only."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from . import org_requests
        try:
            req = org_requests.triage(
                req, admin, triaged_kind=(request.data.get('triaged_kind') or '').strip(),
                lane=(request.data.get('lane') or '').strip(),
                note=request.data.get('note') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        return Response(self._serialize(admin, req))


class AdminOrgRequestQuoteView(_OrgRequestsBase):
    """POST send a quote (triaged → quoted; feature only). Super only. Emails the submitter."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from . import org_requests
        try:
            req = org_requests.quote(
                req, admin, hours=request.data.get('hours'),
                margin_pct=request.data.get('margin_pct'),
                note=request.data.get('note') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        try:
            from . import emails
            emails.send_org_request_quote_email(req)
        except Exception:
            logger.warning('Requests: quote email failed for OrgRequest %s', req.pk, exc_info=True)
        return Response(self._serialize(admin, req))


class AdminOrgRequestRequoteView(_OrgRequestsBase):
    """POST re-quote a deferred request (deferred → quoted). Super only. Emails the submitter."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from . import org_requests
        try:
            req = org_requests.requote(
                req, admin, hours=request.data.get('hours'),
                margin_pct=request.data.get('margin_pct'),
                note=request.data.get('note') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        try:
            from . import emails
            emails.send_org_request_quote_email(req)
        except Exception:
            logger.warning('Requests: re-quote email failed for OrgRequest %s', req.pk, exc_info=True)
        return Response(self._serialize(admin, req))


class AdminOrgRequestScheduleView(_OrgRequestsBase):
    """POST schedule (triaged-bug or approved → scheduled). Super only. Optional date."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from django.utils.dateparse import parse_date
        from . import org_requests
        raw = (request.data.get('scheduled_for') or '').strip()
        sched = parse_date(raw) if raw else None
        try:
            req = org_requests.schedule(req, admin, scheduled_for=sched)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        return Response(self._serialize(admin, req))


class AdminOrgRequestDoneView(_OrgRequestsBase):
    """POST mark done (scheduled → done, terminal). Super only."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from . import org_requests
        try:
            req = org_requests.done(req, admin)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        return Response(self._serialize(admin, req))


class AdminOrgRequestAiRerunView(_OrgRequestsBase):
    """POST re-run the AI reviewer manually (no transition; submitted/triaged). Super only.
    Unlike the auto-run this surfaces the ContractsError as a 503 so the owner sees WHY."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from . import org_requests
        try:
            result = org_requests.run_ai_review(req)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        if result['new_questions']:
            try:
                from . import emails
                emails.send_org_request_questions_email(req, result['new_questions'])
            except Exception:
                logger.warning('Requests: questions email failed for OrgRequest %s', req.pk,
                               exc_info=True)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))
