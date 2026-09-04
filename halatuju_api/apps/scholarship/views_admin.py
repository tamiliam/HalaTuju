"""
MyNadi admin API for the B40 Assistance Programme (Sprint 6a).

Reuses the existing PartnerAdmin auth (super admin sees all). Routes live under
/api/v1/admin/scholarship/ — covered by the NRIC-gate /admin/ whitelist;
PartnerAdminMixin does the real authorisation.
"""
import logging
import re

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Exists, Max, OuterRef, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.pagination import FlexiblePageNumberPagination

from apps.courses.models import PartnerAdmin, PartnerOrganisation
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
    ApplicantDocument, Disbursement, Donation, GraduationMessage, InterviewSession,
    InterviewSlot, OrgRequest, OrgRequestAttachment, Referee, ReviewerProfile,
    Programme, ScholarshipApplication, Sponsor, SponsorProfile, Sponsorship,
)
from . import scheduling
from . import sponsor_comms as sponsor_comms_mod
from . import sponsor_terms as sponsor_terms_mod
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
    AssignmentError, PauseError, admin_reject, application_completeness, assign_reviewer,
    cancel_pending_decline, org_admin_reject, review_writes_closed, set_paused,
    set_reporting_date_by_officer, submit_interview,
)
from . import sponsorship as sponsorship_service
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

    def _require_open_case(self, request, pk):
        """Auth prologue for a REVIEW-track write (interview capture, gap suggestion, verdict).

        `_require_app_write` plus one thing it deliberately does not check: whether there is
        still a review to write into. It has no status gate at all, so on a case that expired
        or was rejected before anyone reviewed it, every one of these endpoints answered 200 —
        `record-verdict` would have stamped a verdict AND an award amount onto a rejected file
        (the same defect the 2026-07-30 sprint fixed, reached through a different door), and
        `suggest-gaps` would have spent a Gemini call on it.

        ⚠ ADD A NEW REVIEW-TRACK WRITE HERE, NOT TO `_require_app_write`. The two are separate
        because the majority of per-application writes are legitimate on a closed case
        (cancelling a decline, correcting a reporting date, re-running a document read); making
        the status gate universal would break them. See `services.review_writes_closed` for why
        a REOPENED case is open however terminal its status reads.
        """
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return None, None, err
        if review_writes_closed(app):
            return None, None, Response(
                {'error': 'This case is closed — there is no review left to record.',
                 'code': 'case_closed', 'status': app.status},
                status=status.HTTP_400_BAD_REQUEST)
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
        app, admin, err = self._require_open_case(request, pk)
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


def _is_authoring(old_findings, new_findings, old_note, new_note):
    """Did this save ADD INTERVIEW CONTENT, as opposed to housekeeping? (TD-216, owner 2026-08-13)

    This decides who the interview is credited to. Before it existed, the credit went to whoever
    caused the session row to exist — and clearing an AI agenda question causes that, because a
    delete is a decision and must survive a reload, so it writes the whole session. Three students
    ended up with an interview attributed to somebody who had only tidied their agenda; a reviewer
    typing findings into one of those afterwards would have had the work recorded under that other
    name, silently.

    ⚠ **CONTENT IS THE PER-ITEM FINDINGS *AND* THE MAIN NOTE, DELIBERATELY.** The owner's rule was
    "whoever writes or edits the findings", and the screen has one free-text box that carries both
    the findings and the conclusion (its own placeholder says so). Keying on the per-item lines
    alone would leave **31 of 83** submitted interviews with no interviewer at all — the reviewers
    who write everything in the main box. Owner chose this reading on 2026-08-13 knowing the
    trade: somebody who rewrites only the conclusion does take the credit, because nothing in the
    data can distinguish that from rewriting the findings. Splitting the box is the fix for that
    and was deferred.

    ⚠ **A DELETION IS NEVER AUTHORSHIP**, however much of the findings dict it changes. That is the
    whole origin of the bug and is checked explicitly — a plain "did the findings change?" test
    would still stamp the person who cleared a question.
    """
    if (new_note or '').strip() != (old_note or '').strip():
        return True
    old = old_findings if isinstance(old_findings, dict) else {}
    for code, value in (new_findings or {}).items():
        if not isinstance(value, dict):
            continue
        if value.get('verdict') == 'deleted':
            continue
        if old.get(code) != value:
            return True
    return False


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
        app, admin, err = self._require_open_case(request, pk)
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
        note = request.data.get('overall_note', '') or ''
        if session is None:
            # ⚠ NO interviewer here. The row must exist for a DELETE to persist, but causing a row
            # to exist is not conducting an interview — see `_is_authoring` and TD-216.
            session = InterviewSession(application=app, started_at=timezone.now())
        # Decided BEFORE the new values are written over the old ones.
        authored = _is_authoring(session.findings, findings, session.overall_note, note)
        session.findings = findings
        session.rubric = request.data.get('rubric', {}) or {}
        session.overall_note = note
        if authored:
            # ⚠ THE CREDIT MOVES TO WHOEVER WROTE THE CONTENT, EVERY TIME (owner, 2026-08-13).
            # One field, overwritten — an earlier contributor's name is expunged, which the owner
            # considered and accepted. Somebody who only re-saves, or only submits, keeps the
            # existing name: that is the case this exists to protect (A interviews, B submits →
            # the record must still read A).
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
        app, admin, err = self._require_open_case(request, pk)
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
        app, admin, err = self._require_open_case(request, pk)
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
        # Added 2026-07-27 so the list can be scanned rather than merely read: `last_seen_at`
        # answers "is this sponsor still with us" (nothing recorded it before), and `given`
        # is what an admin actually looks for. `given` + `students` are annotated THROUGH THE
        # SAME FENCE as the detail page — an org sees its own share, never another tenant's.
        'last_seen_at': s.last_seen_at,
        'given': sponsorship_service._money(getattr(s, 'given_total', None)),
        # Money given says what they have put in; students says what it is DOING. The pair is
        # the whole point of the row — a large balance with no students is the case an admin
        # most needs to spot. Counted the same way the detail page's per-wallet `students` is
        # (HOLDING allocations), so the list and the page can never disagree.
        'students': getattr(s, 'students_total', None) or 0,
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
        # `given` per row in ONE query (no N+1 over the list). CONFIRMED money only — the
        # same rule `visible_donations` applies — and org-fenced for a non-super caller, so
        # the account stays cross-org while the MONEY inside it does not.
        money = Q(donations__status=Donation.STATUS_CONFIRMED)
        if not self.has_role(admin, 'super'):
            money &= Q(donations__programme__organisation_id=admin.owning_organisation_id)
        qs = qs.annotate(given_total=Sum('donations__amount', filter=money))

        # Students is counted in its OWN query, deliberately NOT a second annotate() on the
        # line above: two multi-valued joins in one queryset multiply each other, and the
        # usual `distinct=True` cure is wrong for a Sum (it would collapse two credits of the
        # same amount into one). One extra aggregate query, no N+1, no inflated money.
        held = Q(status__in=Sponsorship.HOLDING)
        if not self.has_role(admin, 'super'):
            # Students fence on the APPLICATION's owner, not the programme's — a sponsorship
            # belongs to a student an organisation owns. Same split as the detail page.
            held &= Q(application__owning_organisation_id=admin.owning_organisation_id)
        rows = list(qs)
        # org-fence: `held` carries application__owning_organisation_id for a non-super
        # caller (built above), so this count never crosses a tenant boundary.
        counts = dict(
            Sponsorship.objects.filter(held, sponsor__in=rows)
            .values('sponsor_id')
            .annotate(n=Count('id'))
            .values_list('sponsor_id', 'n')
        )
        for s in rows:
            s.students_total = counts.get(s.id, 0)
        return Response({'sponsors': [_sponsor_dict(s) for s in rows]})


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


class AdminReleaseNricLockView(_AdminBase):
    """POST .../applications/<pk>/release-nric-lock/ {reason} — the break-glass. SUPER ONLY.

    An IC lock is one-way by design: once the uploaded MyKad confirms the typed number, the
    student can never change it and neither can an admin. That is right, and it has one failure
    mode with a victim who did nothing wrong.

    Somebody uploads a card that is not theirs — a sibling's, say — and types that card's name
    and number so the two agree. It locks. Their own results slip then carries a different name,
    fails the academic gate, and the account is unusable, so they abandon it. **But the abandoned
    account still holds a live claim on a real person's IC number.** When the true owner
    registers, uniqueness refuses them their own number, and without this endpoint nobody can
    free it — they cannot apply at all.

    So this is a housekeeping power over an ORPHANED CLAIM, not an appeal against a decision.
    It clears ``nric_verified`` so the number stops blocking; it does not blank the number, does
    not touch the application, and does not re-open anything else.

    SUPER ONLY (owner, 2026-07-29), deliberately narrower than the gate that TAKES the lock —
    verify-&-accept admits org_admin, qc and the assigned reviewer. Setting an identity is
    routine casework; unsetting one is not.

    The reason is mandatory and goes to the audit log. There is no audit TABLE in this system
    (``audit.py`` is verdict-override metrics), so the structured log is the record — which is
    also why this cannot be done with a direct database write.

    ⚠ **This reaches the lock THROUGH an application, while the lock itself lives on the
    PROFILE.** That is safe only because both routes to a lock require an application — reading
    an uploaded MyKad (the document hangs off one) and verify-&-accept (a bursary review). So a
    locked profile always has an application to address it by, and production agrees: 0 locked
    profiles without one, against 643 course-selector profiles that have no application at all.

    **If you ever add a route that locks a profile WITHOUT an application** — the obvious
    candidate is confirming a course-selector identity for Lentera's longitudinal tracking,
    which is what ``nric_verified`` was originally added for — then this endpoint can no longer
    reach it: there is no ``pk`` to put in the URL, and that student's lock becomes permanent
    with no escape. Re-address it by profile at that point, and note it widens the reachable set
    from 143 records to 786, which is why it is not built that way today.

    The note sits here rather than in a debt register on purpose: nothing is owed while the
    invariant holds, and this is where somebody would be standing when they broke it.
    """
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()
        # Unfenced BY CONSTRUCTION: the gate above admits super only, and a super's scope is
        # every organisation, so no tenant dimension is left to narrow. Widen this to org_admin
        # and it needs `self._org_scoped(...)` like every other application lookup.
        # org-fence: super-only endpoint — no org dimension
        app = ScholarshipApplication.objects.filter(pk=pk).select_related('profile').first()
        if app is None or app.profile is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'error': 'A reason is required to release an identity lock.',
                             'code': 'reason_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        profile = app.profile
        if not profile.nric_verified:
            return Response({'error': 'This IC is not locked.', 'code': 'not_locked'},
                            status=status.HTTP_400_BAD_REQUEST)
        profile.nric_verified = False
        profile.save(update_fields=['nric_verified'])
        # The record of who unset an identity, and why. Deliberately logged BEFORE anything can
        # fail afterwards, and with the application id rather than the NRIC — the log must not
        # become a place identity numbers accumulate.
        logger.info('AUDIT nric_lock_released admin_id=%s app_id=%s reason=%r',
                    admin.id, pk, reason[:200])
        return Response(AdminApplicationDetailSerializer(app).data)


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
        previous_status = sponsor.status
        sponsor.status = new_status
        sponsor.reviewed_at = timezone.now()
        sponsor.reviewed_by = admin.email
        sponsor.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'updated_at'])
        # Vetting the ACCOUNT settles their membership of the gift they registered into, which is
        # what migration 0123 did for every sponsor who predates the programme layer. Without it
        # an approved sponsor sees no students and can hold no wallet.
        #
        # ⚠ THE SAME GIFT THE REGISTRATION RESOLVED, AND ONLY THAT ONE. `signup_programme_for` is
        # stable across both moments because the invitation outlives the registration — so the
        # account's own row settles and a SECOND gift's membership, which is that organisation's
        # separate acceptance decision, is never flipped as a side-effect of account vetting.
        sponsorship_service.sync_account_membership(
            sponsor, sponsorship_service.signup_programme_for(sponsor), vetted_by=admin.email)
        # S3: until now this endpoint flipped a field and returned — eight people on production
        # were approved and never told. `previous_status` is read BEFORE the write because an
        # approval that lifts a suspension is a REINSTATEMENT, and the two read very differently
        # to the person receiving them. Dark until the template is switched on; best-effort.
        from . import sponsor_notify
        sponsor_notify.send_vetting_outcome(sponsor, new_status, previous_status=previous_status)
        return Response(_sponsor_dict(sponsor))


def _chain_organisations(programmes, credit_rows, membership_rows):
    """Every organisation whose finance setting governs a credit on this screen.

    Three sources, because a credit can exist before its wallet does: a wallet appears only
    once a credit is CONFIRMED (`visible_donations`), so a freshly-recorded credit awaiting
    its signatures — the one whose chain the screen must draw correctly — belongs to a
    programme with no wallet row. The approved memberships cover the step before that, when
    the maker is about to record a first credit into a gift.
    """
    orgs = {p.organisation for p in programmes if p is not None}
    orgs |= {c.programme.organisation for c in credit_rows if c.programme_id}
    orgs |= {m.programme.organisation for m in membership_rows
             if m.programme_id and m.status == 'approved'}
    return {o for o in orgs if o is not None}


def _sponsor_detail_dict(sponsor, admin, base):
    """The one sponsor, built field-by-field — NEVER a ModelSerializer.

    An exact-key-set test pins this payload, so a column added to `Sponsor` later cannot
    reach an admin screen (or a log, or a CSV) by accident. Same reasoning as the sponsor
    pool's allowlist, applied in the other direction.

    **The account is platform-level; the money and the students inside it are NOT.** A
    `Sponsor` deliberately has no organisation (`AdminSponsorListView` is classified
    cross-org-by-design), but a credit belongs to a programme owned by an org, and a
    sponsorship belongs to an application owned by an org. So identity is shown whole and
    everything with money or a student in it is fenced through ``base`` — the same split
    the credit endpoints already make. `fenced` tells the screen to say whose share it is.
    """
    from . import payments as payments_service

    programmes = base.programmes
    ledger = [
        {
            'programme_id': row['programme'].id if row['programme'] else None,
            'programme_name': getattr(row['programme'], 'name_en', '') or '',
            'given': row['given'],
            'committed': row['committed'],
            'available': row['available'],
            'credits': row['credits'],
            'students': row['students'],
        }
        for row in sponsorship_service.programme_ledger(sponsor)
        if base.covers(row['programme'])
    ]

    # The credits ledger shows EVERY state including draft/cancelled — an admin has to see
    # an unsigned credit in order to sign it. That is the opposite of the sponsor-facing
    # read, which narrows through `visible_donations`; the tiles above use that seam, this
    # list deliberately does not. Both are correct for their audience.
    #
    # REUSES `_credit_dict` (the credit endpoints' own allowlist) rather than spelling the
    # fields again — two copies of a money payload is two places for the next column to be
    # added to only one.
    # org-fence: fenced on programme→organisation via base.credits(), never all donations.
    credit_rows = list(base.credits())
    credits = [_credit_dict(d) for d in credit_rows]

    membership_rows = [
        m for m in sponsor.programme_memberships.select_related('programme__organisation')
        if base.covers(m.programme)
    ]

    sponsorships = [
        {
            'id': sp.id,
            'application_id': sp.application_id,
            'ref': pool.pool_ref(sp.application_id),
            'programme_name': getattr(sp.application.programme, 'name_en', '') or '',
            'amount': str(sp.amount),
            'status': sp.status,
            'offered_at': sp.offered_at,
            'decided_at': sp.decided_at,
        }
        for sp in base.sponsorships()
    ]

    return {
        'id': sponsor.id,
        'name': sponsor.name,
        'email': sponsor.email,
        'phone': sponsor.phone,
        'organisation': sponsor.organisation,
        'source': sponsor.source,
        'note': sponsor.note,
        'status': sponsor.status,
        'is_trusted': sponsor.is_trusted,
        'created_at': sponsor.created_at,
        'reviewed_at': sponsor.reviewed_at,
        'reviewed_by': sponsor.reviewed_by,
        'last_seen_at': sponsor.last_seen_at,
        'consent_at': sponsor.consent_at,
        'consent_version': sponsor.consent_version,
        'notify_frequency': sponsor.notify_frequency,
        'last_digest_sent_at': sponsor.last_digest_sent_at,
        'programmes': ledger,
        'credits': credits,
        'sponsorships': sponsorships,
        'referrals': [
            {
                'id': r.id,
                'invitee_name': r.invitee_name,
                'invitee_email': r.invitee_email,
                'status': r.status,
                'created_at': r.created_at,
                'joined_at': r.joined_at,
            }
            for r in sponsor.referrals_sent.all()
        ],
        'memberships': [
            {
                # `programme_id` is what the credit form posts (S2). It has to come from the
                # MEMBERSHIPS and not the wallet ledger above: `record_admin_credit` refuses
                # `sponsor_not_in_programme`, so the creditable set is "gifts they were
                # accepted into" — which includes a gift they hold no money in yet, and that
                # is exactly the case a FIRST credit is being recorded for.
                'programme_id': m.programme_id,
                'programme_name': getattr(m.programme, 'name_en', '') or '',
                'status': m.status,
                'vetted_by': m.vetted_by,
                'vetted_at': m.vetted_at,
            }
            for m in membership_rows
        ],
        # Live, never stored — appointing a finance admin arms the middle step of the credit
        # chain retroactively, so the screen must ask at read time, exactly as the sign
        # service does.
        #
        # Asked across the WALLETS, the CREDITS and the approved MEMBERSHIPS, not the wallets
        # alone. A wallet only exists once a credit is CONFIRMED (`visible_donations`), so a
        # first credit — recorded, then awaiting its signatures — belongs to a programme with
        # no wallet yet. Reading wallets only, the screen would draw a two-step chain and
        # offer an org_admin a countersign the service then refuses with
        # `finance_check_required`, which is exactly the mismatch this flag exists to prevent.
        'finance_check_required': any(
            payments_service.finance_check_required(org)
            for org in _chain_organisations(programmes, credit_rows, membership_rows)
        ),
        # True when this caller sees only their own organisation's share of the account, so
        # the screen can say so rather than implying it is the sponsor's whole giving record.
        'fenced': base.is_fenced,
    }


class _SponsorScope:
    """How much of one sponsor's money + students this caller may see.

    Super sees everything. Everyone else sees only what their organisation owns — the
    programmes it runs and the applications it owns. Built once per request so the three
    fenced reads cannot drift apart.
    """
    def __init__(self, sponsor, org_id, is_super):
        self.sponsor = sponsor
        self.org_id = org_id
        self.is_fenced = not is_super
        self.programmes = [
            p for p in sponsorship_service._wallet_programmes(sponsor)
            if self.covers(p)
        ]

    def covers(self, programme):
        if not self.is_fenced:
            return True
        # A NULL-programme wallet belongs to no organisation, so a fenced caller never sees
        # it. Bare test fixtures self-partition the same way the org fence does.
        return programme is not None and programme.organisation_id == self.org_id

    def credits(self):
        qs = self.sponsor.donations.select_related('programme').order_by('-created_at')
        if self.is_fenced:
            qs = qs.filter(programme__organisation_id=self.org_id)
        return qs

    def sponsorships(self):
        qs = (self.sponsor.sponsorships
              .select_related('application', 'application__programme')
              .order_by('-offered_at'))
        if self.is_fenced:
            qs = qs.filter(application__owning_organisation_id=self.org_id)
        return qs


class AdminSponsorDetailView(_AdminBase):
    """GET .../admin/sponsors/<pk>/ — everything an admin needs about ONE sponsor.

    Same role gate as the list (super / org_admin / admin / finance). The ACCOUNT is
    platform-level and shown whole; the money and the students are org-fenced — see
    `_sponsor_detail_dict`.
    """
    def get(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super or admin.role in ('org_admin', 'admin', 'finance')):
            return self._deny_role()
        sponsor = Sponsor.objects.filter(pk=pk).first()
        if sponsor is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        scope = _SponsorScope(sponsor, admin.owning_organisation_id,
                              self.has_role(admin, 'super'))
        return Response(_sponsor_detail_dict(sponsor, admin, scope))


class AdminSponsorMembershipView(_AdminBase):
    """POST .../admin/sponsors/<pk>/membership/ {programme_id, status} — accept a benefactor into
    one of THIS organisation's gifts, or take it back (S-ASSIGN, 2026-09-04).

    ⚠ THIS IS THE ENDPOINT THAT UNBLOCKS THE MONEY. `record_admin_credit` refuses
    `sponsor_not_in_programme` unless an approved membership exists, and until now the only writer
    was `sync_account_membership` with a hard-coded `'brightpath-flagship'`. A second gift's first
    benefactor could not be recorded without an engineer writing SQL — the one thing the owner's
    acceptance test forbids.

    ⚠ TWO GATES, AND THIS IS ONLY THE SECOND. `Sponsor.status` is the ACCOUNT gate ("is this a real,
    legitimate person"), settled once, platform-wide, by `AdminSponsorReviewView`. This is the
    per-gift acceptance, and the owner's rule is that a sponsor sees a gift's students only if
    *"specifically onboarded into both and accepted into both — and that is not a given"*. The
    service refuses `account_not_approved` rather than letting a row say yes while the account
    says no.

    ⚠ THE FENCE IS THE PROGRAMME'S ORGANISATION, resolved through `_ProgrammeScopedBase`'s own
    `_programmes_for`, so a cross-org gift is **404, never 403** — a 403 would confirm the tenant
    exists. The SPONSOR is deliberately unfenced: an account is platform-level by design (one
    login, one identity, one vetting), which is exactly why the money and the students hanging off
    it are fenced instead.

    Who may write: `super` and `org_admin`. Deciding who may fund your students is the
    organisation's own decision, held by its administrator — the same gate as sponsor vetting, one
    role narrower than the sponsor LIST (which `admin` and `finance` also read).
    """
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super or self.has_role(admin, 'org_admin')):
            return self._deny_role()

        sponsor = Sponsor.objects.filter(pk=pk).first()
        if sponsor is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        # Reuse the programme fence rather than re-deriving it — `_programmes_for` already answers
        # "which gifts may this admin touch", INCLUDING inactive ones, which matters here: a gift
        # is configured and staffed before it is switched on.
        programmes = AdminProgrammeListView()._programmes_for(admin)
        programme = programmes.filter(pk=request.data.get('programme_id')).first()
        if programme is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            m = sponsorship_service.set_programme_membership(
                sponsor, programme, (request.data.get('status') or '').strip(),
                vetted_by=admin.email or '')
        except sponsorship_service.MembershipError as e:
            code = str(e)
            return Response({'error': code, 'code': code}, status=status.HTTP_400_BAD_REQUEST)

        logger.info('AUDIT sponsor_membership_set sponsor=%s programme=%s status=%s by=%s',
                    sponsor.id, programme.code, m.status, admin.email or '')
        return Response({'programme_id': programme.id, 'programme': programme.code,
                         'status': m.status})


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
    from . import partner_comms
    # chip -> number of applications carrying it (NULL/'' collapse to ''). The tally comes from
    # `partner_comms.chip_tally()`, the SAME definition `partner_comms.partner_applications(org)`
    # filters on, so this screen and the partner weekly digest cannot report different numbers
    # (docs/lessons.md: give the rule ONE named predicate both sides call).
    # org-fence: intentionally GLOBAL — see `chip_tally`'s own note.
    tally = partner_comms.chip_tally()
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


def _partner_email_dict(tpl, last=None):
    """One partner-email template as the admin screen sees it: the wording, its switch, the
    placeholders it may use, and when it last went out."""
    from . import partner_comms
    from .models import PartnerEmailTemplate
    return {
        'kind': tpl.kind,
        'enabled': bool(tpl.enabled),
        # Who receives it. Every row on this screen but one goes to the partner ORGANISATION, and
        # the exception (request #3) goes to the STUDENT — a difference the screen must state
        # rather than leave a reader to infer from the wording. It also explains why the platform
        # partner-comms switch does not silence that row.
        'to_student': tpl.kind in PartnerEmailTemplate.STUDENT_KINDS,
        # Request #10: a third audience. Our own volunteers, edited on Organisation → Reviewers.
        # Like `to_student` this comes from the SERVER, never from the front end's kind list, so
        # the "who gets this" label cannot drift from the rule that decides who actually does.
        'to_reviewer': tpl.kind in PartnerEmailTemplate.REVIEWER_KINDS,
        'subject': tpl.subject,
        'body': tpl.body,
        'placeholders': sorted(partner_comms.PLACEHOLDERS.get(tpl.kind, set())),
        'updated_by_email': tpl.updated_by_email or '',
        'updated_at': tpl.updated_at.isoformat() if tpl.updated_at else None,
        'last_sent_at': last['sent_at'].isoformat() if last and last.get('sent_at') else None,
        'last_sent_orgs': (last or {}).get('orgs', 0),
    }


class AdminPartnerEmailsView(_SourcesBase):
    """GET .../admin/scholarship/partner-emails/ — the five partner-email templates plus who can
    currently receive one.

    `qualifying` is the honest answer to "if I switch this on, who hears about it?" — the screen
    states it rather than looking as though it works. Today, on prod, it is EMPTY: nine referral
    partners, none with a contact email on file.
    """
    def get(self, request):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from django.conf import settings as _settings
        from apps.courses.models import PartnerOrganisation
        from . import partner_comms
        from .models import PartnerEmailLog, PartnerEmailTemplate

        by_kind = {t.kind: t for t in PartnerEmailTemplate.objects.all()}
        last = {}
        for row in (PartnerEmailLog.objects.filter(ok=True)
                    .values('kind').annotate(sent_at=Max('sent_at'), orgs=Count('organisation',
                                                                                distinct=True))):
            last[row['kind']] = row
        # ⚠ `?family=reviewer` splits this list in two, and the Sources screen must pass NOTHING
        # (the default) so the five reviewer emails stay OFF it. A reviewer is not a referral
        # partner, and a template about our own volunteers sitting under "Partner emails" would be
        # filed where nobody looking for it would look. One endpoint, two audiences, one filter —
        # a second endpoint would be a second copy of the fence.
        # THREE families now, and the default is "everything that is not one of the others" —
        # so a NEW family cannot leak onto the Sources screen by forgetting to exclude it. That is
        # exactly what happened when the invitation kinds were added: the reviewer filter was a
        # two-way split, and the two new kinds silently landed in the partner list.
        family = (request.GET.get('family') or '').strip()
        families = {
            'reviewer': PartnerEmailTemplate.REVIEWER_KINDS,
            'invite': PartnerEmailTemplate.INVITE_KINDS,
        }
        named = set().union(*families.values())
        wanted = families.get(family)
        templates = [
            _partner_email_dict(by_kind[k], last.get(k))
            for k in partner_comms.KINDS
            if k in by_kind and (k in wanted if wanted is not None else k not in named)
        ]
        qualifying = {o.id for o in partner_comms.qualifying_partners()}
        counts = _source_application_counts()
        # Every organisation, each with WHY it does or doesn't qualify — the house org is excluded
        # by rule (it is us), the rest simply need an address.
        # org-fence: GLOBAL by design — this mirrors the Sources registry, which lists every org.
        orgs = [
            {
                'id': o.id, 'code': o.code, 'name': o.name,
                'students': counts.get(o.id, 0),
                'has_email': bool((o.contact_email or '').strip()),
                'is_house_org': o.code == partner_comms.HOUSE_ORG_CODE,
                'qualifies': o.id in qualifying,
            }
            for o in PartnerOrganisation.objects.order_by('name')
        ]
        return Response({
            'templates': templates,
            'organisations': orgs,
            'qualifying_count': len(qualifying),
            'partner_count': sum(1 for o in orgs if not o['is_house_org']),
            'comms_enabled': bool(getattr(_settings, 'PARTNER_COMMS_ENABLED', False)),
        })


class AdminPartnerEmailDetailView(_SourcesBase):
    """PATCH .../admin/scholarship/partner-emails/<kind>/ {enabled?, subject?, body?} — switch one
    partner email on/off, or edit its wording.

    Two refusals, both deliberate: an unknown `{placeholder}` would render literally into a
    partner's inbox, and the co-owned voice the owner specified (2026-07-26) is enforced rather
    than left to a reviewer's memory — a partner organisation runs this bursary alongside us, so
    conduit phrasing and "your students" are refused.
    """
    def patch(self, request, kind):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from . import partner_comms
        from .models import PartnerEmailTemplate

        tpl = PartnerEmailTemplate.objects.filter(kind=kind).first()
        if tpl is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)

        subject = tpl.subject if 'subject' not in request.data else (
            (request.data.get('subject') or '').strip()[:255])
        body = tpl.body if 'body' not in request.data else (request.data.get('body') or '').strip()
        if 'subject' in request.data or 'body' in request.data:
            if not subject or not body:
                return Response({'error': 'subject_and_body_required',
                                 'code': 'subject_and_body_required'},
                                status=status.HTTP_400_BAD_REQUEST)
            unknown = partner_comms.unknown_placeholders(kind, subject, body)
            if unknown:
                return Response({'error': 'unknown_placeholder', 'code': 'unknown_placeholder',
                                 'placeholders': list(unknown)},
                                status=status.HTTP_400_BAD_REQUEST)
            banned = partner_comms.banned_phrases(subject, body)
            if banned:
                return Response({'error': 'conduit_phrasing', 'code': 'conduit_phrasing',
                                 'phrases': list(banned)},
                                status=status.HTTP_400_BAD_REQUEST)
            # ⚠ THE OPPOSITE-DIRECTION CHECK, and nothing did it before. The guard above refuses a
            # token the kind does not SUPPLY; this refuses a body that has dropped one it REQUIRES.
            # Without it a staff invitation could be saved with `{access}` deleted, and everybody
            # invited afterwards would get a warm letter containing no way to sign in — with
            # nothing to report it, because the send succeeds and the account exists.
            missing = partner_comms.missing_required_placeholders(kind, subject, body)
            if missing:
                return Response({'error': 'missing_required_placeholder',
                                 'code': 'missing_required_placeholder',
                                 'placeholders': list(missing)},
                                status=status.HTTP_400_BAD_REQUEST)

        fields = []
        if 'enabled' in request.data:
            tpl.enabled = bool(request.data.get('enabled'))
            fields.append('enabled')
        if subject != tpl.subject:
            tpl.subject = subject
            fields.append('subject')
        if body != tpl.body:
            tpl.body = body
            fields.append('body')
        if fields:
            tpl.updated_by_email = (getattr(admin, 'email', '') or '')[:254]
            fields += ['updated_by_email', 'updated_at']
            tpl.save(update_fields=fields)
        return Response(_partner_email_dict(tpl))


def _sponsor_email_dict(tpl, last=None):
    """Allowlist view of one sponsor-email template. Explicit fields — never model passthrough."""
    return {
        'kind': tpl.kind,
        'label': tpl.get_kind_display(),
        'enabled': tpl.enabled,
        'subject': tpl.subject,
        'body': tpl.body,
        'placeholders': sorted(sponsor_comms_mod.PLACEHOLDERS.get(tpl.kind, set())),
        'updated_by_email': tpl.updated_by_email or '',
        'updated_at': tpl.updated_at.isoformat() if tpl.updated_at else None,
        'last_sent_at': last['sent_at'].isoformat() if last and last.get('sent_at') else None,
        'last_sent_count': (last or {}).get('sponsors', 0),
    }


class _SponsorEmailsBase(_AdminBase):
    """Gate for the sponsor-email panel.

    The SAME gate as the Sponsors list it lives on (super / org_admin / admin / finance) would be
    wrong: deciding what every donor hears is an editorial power, not a reading one. So this
    mirrors the Sources gate instead — super, org_admin, admin. Finance reads sponsors because
    money is its business; the wording of a welcome email is not.
    """
    def _emails_admin(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (self.has_role(admin, 'admin') or admin.role == 'org_admin'):
            return None, self._deny_role()
        return admin, None


class AdminSponsorEmailsView(_SponsorEmailsBase):
    """GET .../admin/scholarship/sponsor-emails/ — the nine templates + the honest state of play.

    `comms_enabled` is the PLATFORM gate, returned rather than assumed: the panel must be able to
    say "these switches do nothing yet" instead of implying a switched-on template will send.
    That is the lesson from the bursary panel, which rendered for everyone because its gate lived
    only in a comment (L380).
    """
    def get(self, request):
        admin, err = self._emails_admin(request)
        if err:
            return err
        from .models import SponsorEmailLog, SponsorEmailTemplate

        by_kind = {t.kind: t for t in SponsorEmailTemplate.objects.all()}
        last = {}
        # org-fence: sponsor comms is platform-level by design — a Sponsor has no organisation
        # (see AdminSponsorListView), and one switch per email serves every sponsor.
        for row in (SponsorEmailLog.objects.filter(ok=True).values('kind')
                    .annotate(sent_at=Max('sent_at'), sponsors=Count('sponsor', distinct=True))):
            last[row['kind']] = row
        templates = [
            _sponsor_email_dict(by_kind[k], last.get(k))
            for k in sponsor_comms_mod.KINDS if k in by_kind
        ]
        return Response({
            'templates': templates,
            'comms_enabled': sponsor_comms_mod.comms_enabled(),
            'seeded': len(templates),
            'expected': len(sponsor_comms_mod.KINDS),
            'sponsor_count': Sponsor.objects.count(),
        })


class AdminSponsorEmailDetailView(_SponsorEmailsBase):
    """PATCH .../admin/scholarship/sponsor-emails/<kind>/ {enabled?, subject?, body?}.

    Two refusals, both deliberate. An unknown `{placeholder}` would render literally into a
    donor's inbox — and, more seriously, the allowlist is a privacy control: no token resolves to
    a student's identity, so a template cannot become a new route around the anonymity the pool
    serializers enforce. The voice guard refuses a tax-relief claim (we hold no s44(6) approval),
    student-ownership phrasing, and urgency copy that would turn account mail into marketing.
    """
    def patch(self, request, kind):
        admin, err = self._emails_admin(request)
        if err:
            return err
        from .models import SponsorEmailTemplate

        tpl = SponsorEmailTemplate.objects.filter(kind=kind).first()
        if tpl is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)

        subject = tpl.subject if 'subject' not in request.data else (
            (request.data.get('subject') or '').strip()[:255])
        body = tpl.body if 'body' not in request.data else (request.data.get('body') or '').strip()
        if 'subject' in request.data or 'body' in request.data:
            if not subject or not body:
                return Response({'error': 'subject_and_body_required',
                                 'code': 'subject_and_body_required'},
                                status=status.HTTP_400_BAD_REQUEST)
            unknown = sponsor_comms_mod.unknown_placeholders(kind, subject, body)
            if unknown:
                return Response({'error': 'unknown_placeholder', 'code': 'unknown_placeholder',
                                 'placeholders': list(unknown)},
                                status=status.HTTP_400_BAD_REQUEST)
            banned = sponsor_comms_mod.banned_phrases(subject, body)
            if banned:
                return Response({'error': 'banned_phrasing', 'code': 'banned_phrasing',
                                 'phrases': list(banned)},
                                status=status.HTTP_400_BAD_REQUEST)

        fields = []
        if 'enabled' in request.data:
            tpl.enabled = bool(request.data.get('enabled'))
            fields.append('enabled')
        if subject != tpl.subject:
            tpl.subject = subject
            fields.append('subject')
        if body != tpl.body:
            tpl.body = body
            fields.append('body')
        if fields:
            tpl.updated_by_email = (getattr(admin, 'email', '') or '')[:254]
            fields += ['updated_by_email', 'updated_at']
            tpl.save(update_fields=fields)
        return Response(_sponsor_email_dict(tpl))


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
        previous_org_id = app.witness_org_id
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
        # Partner comms (2026-07-26): tell the organisation a student has joined its bursary
        # students. Inline — an explicit admin action with nothing to revert — and fully
        # best-effort, so an email problem can never fail the assignment. A CLEARED witness
        # (None) emails nobody; a reassignment emails the NEW organisation only.
        if app.witness_org is not None:
            from . import partner_notify
            partner_notify.notify_partner_assigned(app, app.witness_org)
        # Request #3 (2026-08-01): tell the STUDENT too. That organisation may witness their
        # bursary contract and can see details of their application in order to do it, and until
        # now only the organisation was told. Requester: "We DO NOT want the student's consent, but
        # a notification is a must." Same best-effort contract as the line above, and the same
        # stored template — the owner switches it and edits its wording on the Sources screen
        # beside the five organisation emails, with its recipient labelled there.
        #
        # Only on a CHANGE of organisation: re-saving the same one is an administrator tidying a
        # form, and the student has already been told that fact. (The organisation's own email
        # deliberately keeps its existing behaviour and fires on every save — narrowing it is a
        # change to partner comms nobody asked for.) A CLEARED assignment emails nobody: "your
        # organisation has been removed" is a different message, and one the requester has not
        # asked for — they do not intend to reassign at all.
        if app.witness_org is not None and app.witness_org_id != previous_org_id:
            from . import partner_notify
            partner_notify.notify_student_assigned(app, app.witness_org)
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


class AdminScopeListView(_AdminBase):
    """GET .../scopes/ — the organisations and programmes this admin may LOOK AT (nav/IA N3a).

    Feeds the console's breadcrumb switchers. Until now the breadcrumb was static text and the
    programme crumb was hardcoded `undefined`, so it never rendered at all — the approved design
    had two switchers and the build had neither.

    ⚠ THIS IS NOT THE FENCE, and the switcher built on it must never become one.
    The org fence is `_org_scoped` / `_org_allows`, unchanged. This endpoint answers "what may I
    look at", and its answer is DERIVED from the same `owning_organisation` the fence uses — so it
    cannot widen anything. A client that ignores it entirely reaches exactly the same data.

    Specifically forbidden, and the reason the roadmap called it out: the selected scope must not
    travel as a global header, a cookie, or a middleware rewrite. That would relocate the fence
    into the client, which is the 2026-07-15 surface-partition incident in a new costume. For a
    super it is a DISPLAY preference and nothing more.

    Who sees what:
      super      — every active organisation and programme (they genuinely work across tenants)
      everyone   — exactly their own `owning_organisation`, and that org's active programmes
      partner    — nothing. A referral organisation is an attribution relationship, NEVER an
                   access scope (`PartnerAdmin.org` / `referred_by_org`); handing a school a
                   scope switcher would say otherwise.
      no org     — empty lists, not a 500. A reviewer with `owning_organisation` NULL is a real
                   row in production and must get a usable console.

    Programme codes are `Programme.code`, which is what PF-1 settled a programme is identified by
    (`/scholarship/apply?p=<code>`) — one vocabulary for "which programme", not two.

    Names come from the trilingual `name_*` columns with the en-fallback convention used across
    branding: a blank `ms`/`ta` falls back to `en` rather than rendering empty.
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()

        lang = (request.query_params.get('lang') or 'en').lower()
        if lang not in ('en', 'ms', 'ta'):
            lang = 'en'

        # A referral-org rep has no scope to switch between, and saying so with empty lists is
        # the honest answer — not an error, because nothing has gone wrong.
        if admin.role == 'partner':
            return Response({'organisations': [], 'programmes': []})

        # ⚠ TENANTS ONLY — `partner_organisations` also holds REFERRAL organisations
        # (schools, NGOs that send us students) with no flag between them. The rule and the
        # reason it is BOTH conditions live on the manager, so nobody has to know it here.
        orgs = PartnerOrganisation.objects.tenants().filter(is_active=True).order_by('name')
        # ⚠ INACTIVE PROGRAMMES ARE INCLUDED, AND THE PRODUCT RULE IS WHY (2026-09-03).
        # A gift is CREATED INACTIVE by design (Sabah S2: an active second programme changes live
        # behaviour the instant it exists) and must then be configured — its rules, what it asks
        # for, its first intake year — BEFORE it is switched on. So "not switched on yet" is
        # precisely the state an org_admin spends the most time standing inside, and a switcher
        # that could not reach it made the gift they had just created unreachable: the crumb
        # discarded the selection and fell back to the only ACTIVE gift, silently showing them
        # somebody else's settings. Reported by the owner on the first real use.
        # The ORGANISATION list keeps its `is_active` filter — an inactive tenant is a different
        # question, and nobody configures one.
        programmes = (Programme.objects.all()
                      .select_related('organisation').order_by('organisation__name', 'code'))
        if not self.has_role(admin, 'super'):
            # Derived from the SAME column the fence uses — so this can never widen access.
            # NULL owning_organisation narrows to nothing, which is correct and not an error.
            org_id = admin.owning_organisation_id
            orgs = orgs.filter(id=org_id) if org_id else orgs.none()
            programmes = programmes.filter(organisation_id=org_id) if org_id else programmes.none()

        def _name(p):
            return getattr(p, f'name_{lang}', '') or p.name_en

        return Response({
            'organisations': [
                {'id': o.id, 'code': o.code, 'name': o.name} for o in orgs
            ],
            'programmes': [
                {'id': p.id, 'code': p.code, 'name': _name(p),
                 # So a switcher can SAY a gift is not switched on yet, rather than the reader
                 # discovering it from the screen underneath.
                 'is_active': p.is_active,
                 'organisation_id': p.organisation_id} for p in programmes
            ],
        })


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

        # ⚠ A PAUSED reviewer is FLAGGED, never filtered out (request #10, 2026-08-02). The cockpit
        # unions the current assignee in from this very list, so dropping anybody reproduces bug
        # #66 — the case reads as "Unassigned" when it is nothing of the sort. The dropdown renders
        # them disabled with "Paused" as the reason, which also answers the reader's next question
        # instead of leaving a name mysteriously absent.
        return Response({'admins': [
            {'id': a.id, 'name': a.name, 'email': a.email,
             'role': 'super' if a.is_super else a.role, 'languages': langs(a),
             'paused': a.paused_at is not None,
             'corrections': corrections.get(a.id, 0)}
            for a in admins
        ], 'past_assignees': [{'id': p.id, 'name': p.name} for p in past]})


#: Which languages count as "can review in this" — conversational or better. Mirrors
#: `AdminAssignableAdminsView.langs`; both read `ReviewerProfile`, so keep them in step.
_REVIEW_FLUENCY = ('conversational', 'fluent')

#: An application still waiting for this reviewer's verdict. Narrower than "not decided":
#: `ASSIGNABLE_STATUSES` is where a review is actually outstanding.
_REVIEWER_OPEN_STATUSES = ('profile_complete', 'interviewing')

#: A decided case that went FORWARD. `recommended` is the reviewer's own verdict; the rest are the
#: stages a recommended student passes through afterwards, and a case that reached them was
#: recommended on the way.
_REVIEWER_PROGRESSED_STATUSES = ('recommended', 'awarded', 'active', 'maintenance', 'closed')


def _reviewer_languages(admin):
    rp = getattr(admin, 'reviewer_profile', None)
    if rp is None:
        return []
    return [code for code, lvl in (('en', rp.english_fluency),
                                   ('ms', rp.bm_fluency),
                                   ('ta', rp.tamil_fluency)) if lvl in _REVIEW_FLUENCY]


def _median_days(values):
    """Median, not mean — with 13 reviewers and single-digit caseloads one slow case drags a mean
    somewhere no real turnaround sits. Returns None for an empty list rather than 0, because
    "no reviews yet" and "instant" must not render the same."""
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 1)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 1)


def _reviewer_workloads(admins, *, organisation_id=None):
    """`{admin_id: {...figures}}` for every reviewer, in ONE query, grouped in Python.

    ⚠ NOT `annotate()`. Two counts over two multi-valued relations multiply each other, and
    `Sum(distinct=True)` — the reflex cure — is wrong for a sum (see `AdminSponsorListView` and
    `test_sponsor_detail.test_money_and_students_do_not_inflate_each_other`). Grouping a few hundred
    rows in Python cannot fan out at all, so the class of bug is absent rather than guarded against.

    ⚠ **EVERY DECIDED CASE ASSIGNED TO THEM COUNTS — including one somebody else recorded the
    verdict on** (owner, 2026-08-02). The first cut excluded those, reasoning that another person's
    judgement should not land on a volunteer's record. That was wrong, and production said so:
    application #13 was assigned to Balan, HE interviewed the student and submitted his findings,
    and only the final verdict click was the owner's. Excluding it erased a case he genuinely
    reviewed and left a footnote nobody could act on. Who pressed the button is an attribution
    detail for the audit trail; the OUTCOME belongs on the record of whoever did the review — which
    is exactly why `rejected_after_review` is a band of its own and not folded into `declined`.

    ⚠ The four outcome bands **partition** the decided cases, so they always sum to `completed`.
    Before `awaiting_qc` existed the bar quietly fell short of the figure printed above it. If a new
    status ever escapes all four, `test_the_bands_account_for_every_decided_case` fails rather than
    the screen silently under-reporting.
    """
    ids = [a.id for a in admins]
    if not ids:
        return {}
    rows = ScholarshipApplication.objects.filter(assigned_to_id__in=ids)
    if organisation_id is not None:
        # org-fence: the caller is a non-super, so only their own tenant's applications count.
        rows = rows.filter(owning_organisation_id=organisation_id)
    by_email = {a.id: (a.email or '').strip().lower() for a in admins}
    out = {i: {'open_now': 0, 'completed': 0, 'recommended': 0, 'declined': 0,
               'rejected_after_review': 0, 'awaiting_qc': 0, 'unaccounted': 0, '_days': []}
           for i in ids}
    for aid, status, assigned_at, decided_at, verdict in rows.values_list(
            'assigned_to_id', 'status', 'assigned_at', 'verdict_decided_at', 'officer_verdict'):
        slot = out[aid]
        if decided_at is None:
            if status in _REVIEWER_OPEN_STATUSES:
                slot['open_now'] += 1
            continue
        slot['completed'] += 1
        if status in _REVIEWER_PROGRESSED_STATUSES:
            slot['recommended'] += 1
        elif status == 'rejected':
            # ⚠ THE SPLIT READS THE RECORDED VERDICT, NOT `rejected_by`. Keying on who stamped the
            # rejection is WRONG and shipped wrong on 2026-08-02: a reviewer's decline always routes
            # through QC, and QC ACCEPTING that decline stamps `rejected_by` with the QC's name. So
            # "the rejector is not the reviewer" is the ORDINARY path for a decline, not the rare
            # one — it mislabelled 6 of BrightPath's 13 rejections, telling five volunteers they had
            # been overruled when they had simply declined a student and been agreed with.
            #
            # An overturn is the case where the reviewer said ACCEPT and the student was rejected
            # anyway. That claim needs positive evidence, so anything else — a decline, a blank
            # verdict, a draft — counts as their own decline rather than an accusation.
            # (`officerCockpit.rejectionTrail` already read it this way; this now agrees with it.)
            if (verdict or {}).get('overall') == 'accept':
                slot['rejected_after_review'] += 1
            else:
                slot['declined'] += 1
        elif status == 'interviewed':
            slot['awaiting_qc'] += 1
        else:
            # A decided case in none of the bands above. Counted so the arithmetic still closes and
            # a test can see it; today this is always 0.
            slot['unaccounted'] += 1
        if assigned_at:
            slot['_days'].append((decided_at - assigned_at).total_seconds() / 86400.0)
    for slot in out.values():
        slot['turnaround_days'] = _median_days(slot.pop('_days'))
    return out


def _reviewer_dict(admin, work):
    """One row of the reviewers table. Allowlist — an exact-key-set test pins it.

    ⚠ NO corrections figure here, by decision (2026-08-02). See `reopen.reviewer_reopens`.
    """
    return {
        'id': admin.id,
        'name': admin.name,
        'email': admin.email,
        'role': 'super' if admin.is_super else admin.role,
        'languages': _reviewer_languages(admin),
        'open_now': work['open_now'],
        'completed': work['completed'],
        'turnaround_days': work['turnaround_days'],
        'paused': admin.paused_at is not None,
        'paused_at': admin.paused_at,
        # ⚠ NO `programmes` KEY, and that is a decision (owner, 2026-08-02): with one programme
        # every reviewer serves it, so the column could only ever say one thing. It returns when a
        # second programme exists — until then everyone is on the BrightPath Bursary by default.
        # Do not add it back "for completeness"; a column with one possible value is furniture.
    }


class _ReviewersBase(_AdminBase):
    """Shared gate + fence for the reviewers surface (Organisation → Reviewers).

    Same role set as the organisation's other staff-facing screens. **List-fenced**: a `PartnerAdmin`
    carries `owning_organisation`, so a non-super sees only their own organisation's people.
    """

    def _side(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not (admin.is_super or admin.role in ('org_admin', 'admin', 'finance')):
            return None, None, self._deny_role()
        org_id = None if self.has_role(admin, 'super') else admin.owning_organisation_id
        return admin, org_id, None

    def _reviewers(self, org_id):
        from django.db.models import Q
        # org-fence: narrowed by owning_organisation for a non-super (org_id set by `_side`).
        qs = (PartnerAdmin.objects.filter(is_active=True)
              .filter(Q(is_super_admin=True) | Q(role__in=['reviewer', 'qc']))
              .select_related('reviewer_profile').order_by('name'))
        if org_id is not None:
            qs = qs.filter(owning_organisation_id=org_id, is_super_admin=False)
        return qs


class AdminReviewerListView(_ReviewersBase):
    """GET admin/reviewers/ — the people who review this organisation's applications.

    Request #10. Staff (`/admin/organisation/staff`) invites and revokes; this is where you look at
    somebody: what they carry, how long cases sit with them, and how their cases ended.
    """

    def get(self, request):
        admin, org_id, err = self._side(request)
        if err:
            return err
        rows = list(self._reviewers(org_id))
        work = _reviewer_workloads(rows, organisation_id=org_id)
        return Response({'reviewers': [_reviewer_dict(r, work[r.id]) for r in rows]})


class AdminReviewerDetailView(_ReviewersBase):
    """GET admin/reviewers/<pk>/ — one reviewer, whole.

    ⚠ The contact block is a deliberate PII WIDENING and is deliberately PARTIAL. `ReviewerProfile`
    also holds a home address; an org_admin assigning work has no reason to read it, so it is not
    serialised here. Recorded in `docs/scholarship/role-matrix.md`.
    """

    def get(self, request, pk):
        admin, org_id, err = self._side(request)
        if err:
            return err
        # org-fence: `_reviewers` is already narrowed, so a cross-org id 404s rather than resolving.
        # ⚠ 404, never 403 — a 403 would confirm that another tenant's staff member exists.
        target = self._reviewers(org_id).filter(pk=pk).first()
        if target is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        work = _reviewer_workloads([target], organisation_id=org_id)[target.id]
        rp = getattr(target, 'reviewer_profile', None)
        from . import reopen as reopen_service
        payload = _reviewer_dict(target, work)
        payload.update({
            # The four outcome bands. They partition the decided cases, so they sum to `completed`
            # — the bar and the figure above it can never disagree.
            'recommended': work['recommended'],
            'declined': work['declined'],
            'rejected_after_review': work['rejected_after_review'],
            'awaiting_qc': work['awaiting_qc'],
            'created_at': target.created_at,
            'qualification': getattr(rp, 'highest_qualification', '') or '',
            'university': getattr(rp, 'university', '') or '',
            'graduation_year': getattr(rp, 'graduation_year', None),
            'field_of_study': getattr(rp, 'field_of_study', '') or '',
            'phone': getattr(rp, 'phone', '') or '',
            'share_phone_with_students': bool(getattr(rp, 'share_phone_with_students', False)),
            'reopens': [
                {'id': r.id,
                 'application_id': r.application_id,
                 'reason': r.reason,
                 'reopened_by': r.reopened_by,
                 'at': r.closed_at or r.created_at}
                for r in reopen_service.reviewer_reopens(target, organisation_id=org_id)
            ],
        })
        return Response(payload)


class AdminReviewerPauseView(_ReviewersBase):
    """POST admin/reviewers/<pk>/pause/ {paused: bool} — step somebody back, or bring them back.

    The complement of the reviewer's own switch on their profile. It exists because a volunteer who
    has gone quiet cannot always press it themselves, and because a control with no way back is a
    one-way conversation — un-pause is the same endpoint with `false`.

    ⚠ **NARROWER than reading this surface.** `admin` and `finance` may look at the reviewers list;
    changing who gets work is staff management, which the role matrix gives to super + org_admin
    only. The list gate would have admitted all four, so this re-gates rather than inheriting.
    """

    def post(self, request, pk):
        admin, org_id, err = self._side(request)
        if err:
            return err
        if not (admin.is_super or self.has_role(admin, 'org_admin')):
            return self._deny_role()
        # org-fence: `_reviewers` is already narrowed, so a cross-org id 404s rather than resolving.
        target = self._reviewers(org_id).filter(pk=pk).first()
        if target is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            set_paused(target, request.data.get('paused'))
        except PauseError as e:
            return Response({'error': e.code, 'code': e.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'id': target.id,
                         'paused': target.paused_at is not None,
                         'paused_at': target.paused_at})


class AdminReviewerSystemEmailsView(_ReviewersBase):
    """GET admin/reviewers/system-emails/ — the reviewer emails nobody can edit, rendered in full.

    Owner ruling, 2026-08-02: *"their existence and content are known to the org_admin. If not
    specified, they'll exist in the background without anyone paying attention to them until
    something breaks."* So the Emails tab shows the editable five AND these seven, and the
    difference between the two lists is stated rather than left to be discovered.

    ⚠ **THE BODIES COME FROM THE SENDERS' OWN BUILDERS**, not from a copy of the prose kept here or
    on the front end — see `reviewer_system_emails`. Read-only by construction: there is no PATCH,
    no switch and no template row behind any of it.

    Carries NO organisation data — the same seven strings for every tenant — so the fence has
    nothing to narrow. It is gated to the reviewers-surface audience anyway, because a screen about
    our own volunteers belongs to the people who run them.
    """

    def get(self, request):
        admin, org_id, err = self._side(request)
        if err:
            return err
        from . import reviewer_system_emails
        return Response({'emails': reviewer_system_emails.rendered()})


class AdminInvitationsView(_ReviewersBase):
    """GET admin/invitations/[?kind=] — who has been asked to join this organisation.

    The Invitations page (owner's shape, 2026-08-03) is organised into FOUR kinds — admins,
    reviewers, source, sponsors — with one table on screen at a time, so this serves one kind plus
    the waiting counts for all four (the badge on each button; without it an invitation waiting
    under an unselected kind is invisible, which is what the page exists to prevent).

    ⚠ **FENCED ON `Invitation.organisation`, NOT through `PartnerAdmin`.** A sponsor invitation has
    no staff row to fence through — that is the whole point of a sponsor invitation, which creates
    no account — so fencing through the invitee would silently drop the sponsor kind entirely.

    ⚠ **`org_admin` IS LISTED AND NOT INVITABLE.** See `invitations.KIND_ROLES` vs
    `KIND_INVITABLE_ROLES`: an organisation admin is an admin and belongs in the table, but
    appointing one is a platform act a super performs, never something an org_admin does here.
    """

    def get(self, request):
        admin, org_id, err = self._side(request)
        if err:
            return err
        from . import invitations as inv_service
        from .models import Invitation

        # org-fence: an invitation belongs to the organisation that sent it. A super sees all.
        qs = Invitation.objects.select_related('partner_admin', 'invited_by').all()
        if org_id is not None:
            qs = qs.filter(organisation_id=org_id)

        counts = inv_service.waiting_counts(qs)
        kind = (request.GET.get('kind') or inv_service.KIND_ADMINS).strip()
        if kind not in inv_service.KINDS:
            kind = inv_service.KIND_ADMINS

        rows = []
        for i in inv_service.for_kind(qs, kind).order_by('-created_at'):
            pa = i.partner_admin
            rows.append({
                'id': i.id,
                'name': i.name or (pa.name if pa else ''),
                'email': i.email,
                'role': i.role,
                'status': inv_service.status_of(i),
                'sent_at': i.last_sent_at.isoformat() if i.last_sent_at else None,
                'send_count': i.send_count,
                'last_send_ok': i.last_send_ok,
                'last_send_error': i.last_send_error,
                'accepted_at': i.accepted_at.isoformat() if i.accepted_at else None,
                # The staff row behind a staff invitation, so the Action column can offer the right
                # verb — Resend while waiting, Revoke once somebody is actually in. Absent for a
                # sponsor invitation, which has no account by design.
                'admin_id': pa.id if pa else None,
                'is_active': pa.is_active if pa else None,
                'paused': (pa.paused_at is not None) if pa else None,
            })

        return Response({
            'kind': kind,
            'invitations': rows,
            'waiting': counts,
            # What this caller may actually grant here. The FE renders the sub-selection from it
            # rather than keeping its own copy, so the two cannot drift.
            'invitable_roles': list(inv_service.KIND_INVITABLE_ROLES.get(kind, ())),
        })

    def post(self, request):
        """Invite a SPONSOR. The other kinds go through `AdminInviteView`, which provisions an
        account; this one deliberately provisions nothing.

        ⚠ **AN INVITATION IS A PROMPT, NEVER A WAY ROUND THE FRONT DOOR.** Owner's constraint:
        *"invite, but nothing is skipped."* No `Sponsor` row is created, no account, no vetting
        shortcut — the email carries a link to the ordinary public registration, where they give
        consent, sign the terms and are vetted like anybody else. The invitation closes itself when
        a sponsor account appears for that address (`views_sponsor._attribute_referral`).

        ⚠ Staff invitations are NOT accepted here. They create Supabase accounts and carry
        passwords, and that logic already has one home; a second door into it would be a second
        place for the role rules to drift.
        """
        admin, org_id, err = self._side(request)
        if err:
            return err
        if not (admin.is_super or self.has_role(admin, 'org_admin')):
            return self._deny_role()

        from . import invitations as inv_service
        audience = (request.data.get('audience') or '').strip()
        if audience != 'sponsor':
            return Response({'error': 'unsupported_audience', 'code': 'unsupported_audience'},
                            status=status.HTTP_400_BAD_REQUEST)

        email = (request.data.get('email') or '').strip().lower()
        if '@' not in email or '.' not in email.rsplit('@', 1)[-1]:
            return Response({'error': 'bad_email', 'code': 'bad_email'},
                            status=status.HTTP_400_BAD_REQUEST)

        from apps.scholarship.models import Sponsor
        if Sponsor.objects.filter(email__iexact=email).exists():
            # Not an error worth a stack trace — they are already here. Say so plainly.
            return Response({'error': 'already_a_sponsor', 'code': 'already_a_sponsor'},
                            status=status.HTTP_400_BAD_REQUEST)

        org = admin.owning_organisation

        # ⚠ WHICH GIFT ARE YOU INVITING THEM INTO? (S-ASSIGN, 2026-09-04.) Until now this form
        # asked for an email, a name and a note, derived the organisation, and never asked — so a
        # benefactor invited for Sabah would have registered straight into the flagship, silently,
        # and their credit would then have been refused `sponsor_not_in_programme`.
        #
        # ⚠ ONE GIFT ASKS NOTHING. Omitted + the organisation runs exactly one → that one, so the
        # existing form is unchanged for BrightPath and nothing is sent. More than one and none
        # named → 400 `programme_required` carrying the choices, never a silent pick (the P2b /
        # PF-1 rule). A gift outside the caller's organisation is 404, never 403.
        #
        # It GRANTS nothing either way: a sponsor invitation creates no account and is a prompt to
        # the ordinary public registration, where they still consent, sign the terms and are
        # vetted. This only records which gift the organisation meant.
        programmes = AdminProgrammeListView()._programmes_for(admin).filter(is_active=True)
        asked = request.data.get('programme_id')
        if asked:
            programme = programmes.filter(pk=asked).first()
            if programme is None:
                return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            live = list(programmes.order_by('code')[:2])
            if len(live) > 1:
                return Response(
                    {'error': 'programme_required', 'code': 'programme_required',
                     'programmes': [{'id': p.id, 'code': p.code, 'name': p.name_en}
                                    for p in programmes.order_by('code')]},
                    status=status.HTTP_400_BAD_REQUEST)
            programme = live[0] if live else None

        inv = inv_service.create_or_refresh(
            audience='sponsor', email=email, name=(request.data.get('name') or '').strip(),
            organisation=org, invited_by=admin, programme=programme,
            ttl_days=inv_service.PII_RETENTION_DAYS)

        from .emails import send_sponsor_invitation_email
        ok, error = send_sponsor_invitation_email(
            email, org_name=(org.name if org else ''), note=(request.data.get('note') or ''),
            code=inv.code, invited_by=admin.name)
        inv_service.record_send(inv, ok, error)
        return Response({'id': inv.id, 'emailed': ok},
                        status=status.HTTP_201_CREATED if ok else status.HTTP_502_BAD_GATEWAY)


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
        app, admin, err = self._require_open_case(request, pk)
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

    def _payload(self, profile, admin):
        """The profile, plus the pause state — which lives on `PartnerAdmin`, not here.

        ⚠ `paused` is deliberately NOT a `ReviewerProfile` column. Pause governs assignment, and
        assignment reads `PartnerAdmin`; a second copy on the profile row would be a second truth
        to drift. It rides along on this payload because ONE screen owns "how I take part", and
        splitting it across two calls would be an implementation detail leaking into the UI.
        """
        data = dict(ReviewerProfileSerializer(profile).data)
        data['paused'] = admin.paused_at is not None
        data['paused_at'] = admin.paused_at
        return data

    def get(self, request):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        profile, _ = ReviewerProfile.objects.get_or_create(partner_admin=admin)
        return Response(self._payload(profile, admin))

    def patch(self, request):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        profile, _ = ReviewerProfile.objects.get_or_create(partner_admin=admin)
        # Split off `paused` before the serializer sees it — it belongs to a different model, and
        # an unknown key would otherwise be silently ignored, leaving the reviewer pressing a
        # switch that does nothing.
        body = {k: v for k, v in request.data.items() if k not in ('paused', 'paused_at')}
        serializer = ReviewerProfileSerializer(profile, data=body, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if 'paused' in request.data:
            try:
                set_paused(admin, request.data.get('paused'))
            except PauseError as e:
                return Response({'error': e.code, 'code': e.code},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response(self._payload(profile, admin))


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
        # Advisory: has Vircle activated this eWallet? (mirrored from the relay sheet). Shown as a
        # "not yet activated" chip on the run; never blocks — a run item stays payable regardless.
        'activated': app.vircle_activated_at is not None,
        'award_amount': str(item.award_amount_snapshot),
        'paid_to_date': str(item.paid_to_date_snapshot),
        'amount': str(item.amount),
        'credit_applied': str(item.credit_applied),
        'included': item.included,
        'exclude_reason': item.exclude_reason,
    }


def _sig(name, email, at):
    return {'name': name, 'email': email, 'at': at} if at else None


def _run_programme(run):
    """The gift a run pays from — ``{id, name}`` or None for a pre-P2b run. Shown beside the
    reference so an operator can tell two same-dated runs apart (references disambiguate with a
    `-02` suffix, which says there are two but not which is which)."""
    p = getattr(run, 'programme', None)
    if p is None:
        return None
    return {'id': p.id, 'name': (p.name_en or '').strip()}


def _payment_run_summary(run):
    included = [i for i in run.items.all() if i.included]
    total = sum((i.amount for i in included), _Decimal('0'))
    return {
        'id': run.id, 'reference': run.reference, 'payment_date': run.payment_date,
        'period_month': run.period_month, 'programme': _run_programme(run),
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
    # Narrowed to the run's own programme (P2b) — a run pays ONE gift, so a student of another
    # gift was never a candidate and must not read as "skipped by this run". A legacy run with
    # no programme passes None and keeps the pre-P2b whole-org behaviour.
    for row in payments.eligible_rows(run.organisation, run.payment_date,
                                      period_month=run.period_month,
                                      programme=run.programme):
        if not row['eligible'] and row['application'].id not in item_app_ids:
            a = row['application']
            p = getattr(a, 'profile', None)
            skipped.append({'application_id': a.id, 'name': getattr(p, 'name', '') or '',
                            'nric': getattr(p, 'nric', '') or '', 'reasons': row['reasons']})
    from django.conf import settings as _settings
    return {
        'id': run.id, 'reference': run.reference, 'payment_date': run.payment_date,
        'period_month': run.period_month, 'programme': _run_programme(run),
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
        # The GIFT this run pays from (P2b). Re-fenced on the caller's own organisation, so an
        # admin cannot create a run against another tenant's programme even by id. Omitted +
        # the org runs exactly one programme → that one is used; omitted + more than one → the
        # operator must say which (`programme_required`), never a silent pick.
        from .models import Programme
        org_programmes = Programme.objects.filter(organisation=org, is_active=True)
        programme_id = request.data.get('programme_id')
        if programme_id:
            programme = org_programmes.filter(pk=programme_id).first()
            if programme is None:
                return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            candidates = list(org_programmes[:2])
            if len(candidates) != 1:
                return Response({'error': 'programme_required', 'code': 'programme_required'},
                                status=status.HTTP_400_BAD_REQUEST)
            programme = candidates[0]
        from . import payments
        try:
            run = payments.create_run(org, programme, pd, pm,
                                      by_email=getattr(admin, 'email', '') or '')
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


# ── Billing & usage v1 (Sprint 13a) — the super/org_admin usage screen ────────────
# GET /api/v1/admin/scholarship/billing/usage/?month=YYYY-MM. Dual audience:
#   * org_admin — its OWN organisation's metered usage + document-storage snapshot,
#     org-fenced BY CONSTRUCTION (usage.monthly_usage(restrict_org_id=own org) can build
#     no other org and no platform/NULL row);
#   * super — every organisation PLUS the platform (NULL-org) reconciliation row.
# The platform section is SUPER-ONLY (never in an org_admin payload). Ships DARK behind
# BILLING_USAGE_ENABLED — 404-FIRST while the flag is off (no existence leak, same shape
# as the Requests dark ship). Reads through the plain allowlist dict in
# apps.scholarship.usage (no model passthrough); units/tokens ONLY, NO prices in v1.
# The aggregate is deliberately super-global (no tenant scope for a super) — the metering
# UsageEvent.objects query lives in usage.py, not in a raw views_admin query, so the
# org-fence static guard has nothing to police here. Classified in test_org_fence.py.
_MONTH_RE = re.compile(r'^\d{4}-\d{2}$')


class AdminBillingUsageView(_AdminBase):
    """Super + org_admin usage readout. The flag darkens the ORG-FACING screen only.

    `BILLING_USAGE_ENABLED` gates what the TENANT sees, not what the platform operator sees
    (owner, 2026-07-26). A super is the person who runs the meter: they need to read the numbers
    before an organisation is shown them, which is precisely the check a dark-until-a-date rollout
    is supposed to allow. So super passes whatever the flag says; org_admin keeps 404-ing until
    the 1 Aug flip, and their experience is byte-identical to before.

    Ordering matters: the flag check sits BEFORE the role check so every non-super role keeps
    getting the same **404** it got while dark (no new existence signal), and only becomes a 403
    once the feature is live for everyone. Unauthenticated callers never reach here — DRF's auth
    layer 401s first.
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        is_super = self.has_role(admin, 'super')
        if not is_super and not getattr(settings, 'BILLING_USAGE_ENABLED', False):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        if not (is_super or admin.role == 'org_admin'):
            return self._deny_role()

        month = (request.query_params.get('month') or '').strip()
        if month and not _MONTH_RE.match(month):
            return Response({'error': 'bad_month', 'code': 'bad_month'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not month:
            # TD-209: LOCALTIME, not now(). `timezone.now()` is an aware UTC instant and
            # `strftime` prints it WITHOUT converting, so this defaulted to the UTC month while
            # every other month computation on this screen is Malaysian — `available_months()`
            # groups with `.dates()` and `monthly_usage` filters on `__year`/`__month`, both of
            # which Postgres evaluates under TIME_ZONE='Asia/Kuala_Lumpur'. The two therefore
            # disagreed for the eight hours between Malaysian midnight and 08:00 on the 1st, and
            # the page opened on a month the data had already left. No figure was ever wrong; the
            # default was. A test pins the two computations to the same clock.
            month = timezone.localtime().strftime('%Y-%m')

        from . import usage
        if is_super:
            # super: every organisation + the platform (NULL-org) reconciliation row.
            payload = usage.monthly_usage(month, include_platform=True)
        else:
            # org_admin: its OWN organisation only — fenced by construction (no platform,
            # no other org can appear). A misconfigured org_admin with no org sees nothing.
            payload = usage.monthly_usage(month, restrict_org_id=admin.owning_organisation_id)
        return Response(payload)


class AdminBillingRatesView(_AdminBase):
    """SUPER-ONLY: read + set the conversion rate and per-category margins.

    Owner design 2026-07-27: the rate and margins are PLATFORM-side editable values, while
    hours sit on the org side. This is the platform side.

    **Super-only, with no flag and no org_admin path — on purpose.** These numbers decide what
    every tenant is charged. A tenant being able to read (let alone set) the margin applied to
    them is a commercial disclosure, not a feature; org_admin gets a **403**, not a 404, because
    unlike the dark usage screen there is nothing to hide about this route's existence — only
    about its contents.

    POST never updates in place. It writes a NEW effective-dated row, so changing a rate cannot
    retroactively re-price a month that has already been billed. The history IS the audit trail.
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()

        from .models import BillingRate
        rows = BillingRate.objects.all()   # org-fence: platform-level config, no tenant data
        return Response({'rates': [{
            'id': r.id,
            'category': r.category,
            'kind': r.kind,
            'value': str(r.value),
            'effective_from': r.effective_from.isoformat(),
            'updated_by_email': r.updated_by_email,
            'note': r.note,
        } for r in rows]})

    def post(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()

        from datetime import date
        from decimal import Decimal, InvalidOperation

        from .models import BillingRate

        category = (request.data.get('category') or '').strip()
        kind = (request.data.get('kind') or '').strip()
        if category not in dict(BillingRate.CATEGORY_CHOICES):
            return Response({'error': 'bad_category', 'code': 'bad_category'},
                            status=status.HTTP_400_BAD_REQUEST)
        if kind not in dict(BillingRate.KIND_CHOICES):
            return Response({'error': 'bad_kind', 'code': 'bad_kind'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            value = Decimal(str(request.data.get('value')))
        except (InvalidOperation, TypeError):
            return Response({'error': 'bad_value', 'code': 'bad_value'},
                            status=status.HTTP_400_BAD_REQUEST)
        if value < 0:
            # A negative margin or rate is almost certainly a typo, and it would silently
            # produce a credit note rather than an invoice.
            return Response({'error': 'negative_value', 'code': 'negative_value'},
                            status=status.HTTP_400_BAD_REQUEST)

        raw_from = (request.data.get('effective_from') or '').strip()
        try:
            effective_from = (date.fromisoformat(raw_from) if raw_from
                              else timezone.now().date().replace(day=1))
        except ValueError:
            return Response({'error': 'bad_effective_from', 'code': 'bad_effective_from'},
                            status=status.HTTP_400_BAD_REQUEST)

        row, _created = BillingRate.objects.update_or_create(
            category=category, kind=kind, effective_from=effective_from,
            defaults={'value': value,
                      'updated_by_email': (admin.email or ''),
                      'note': (request.data.get('note') or '')})
        return Response({'id': row.id, 'category': row.category, 'kind': row.kind,
                         'value': str(row.value),
                         'effective_from': row.effective_from.isoformat()},
                        status=status.HTTP_201_CREATED)


class AdminOrgBuildHoursView(_AdminBase):
    """Build hours for ONE organisation's modules. Super writes; org_admin reads its own.

    The org side of the owner's 2026-07-27 design. Fenced on `organisation_id` like every other
    org-scoped surface: an org_admin sees only its own hours, and a cross-org id is a **404**,
    never a 403 — consistent with the rest of the admin API, so the route leaks no existence.

    Only a super may RECORD hours: it is a charge against a tenant, and a tenant recording what
    it will be billed for is not a control anyone would accept.
    """

    def get(self, request, org_id):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        is_super = self.has_role(admin, 'super')
        if not (is_super or admin.role == 'org_admin'):
            return self._deny_role()
        if not is_super and admin.owning_organisation_id != int(org_id):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        month = (request.query_params.get('month') or '').strip()
        if month and not _MONTH_RE.match(month):
            return Response({'error': 'bad_month', 'code': 'bad_month'},
                            status=status.HTTP_400_BAD_REQUEST)

        from .models import OrgBuildHours
        qs = OrgBuildHours.objects.filter(organisation_id=org_id)  # org-fence: explicit filter
        if month:
            qs = qs.filter(period_month=month)
        payload = {'organisation_id': int(org_id), 'lines': [{
            'id': r.id, 'period_month': r.period_month, 'module': r.module,
            'hours': str(r.hours), 'basis': r.basis,
        } for r in qs]}

        # The charge is only computed when a month is asked for AND its rates are set. A
        # missing rate is reported as such, never silently rendered as RM0.00.
        if month:
            from . import platform_cost
            try:
                charge = platform_cost.development_charge(
                    admin.owning_organisation if not is_super else _org_or_none(org_id), month)
                payload['charge'] = {k: (str(v) if v is not None else None)
                                     for k, v in charge.items() if k != 'lines'}
            except platform_cost.RateMissing as exc:
                payload['charge'] = None
                payload['charge_blocked'] = str(exc)
        return Response(payload)

    def post(self, request, org_id):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()

        from decimal import Decimal, InvalidOperation

        from .models import OrgBuildHours

        month = (request.data.get('period_month') or '').strip()
        if not _MONTH_RE.match(month):
            return Response({'error': 'bad_month', 'code': 'bad_month'},
                            status=status.HTTP_400_BAD_REQUEST)
        module = (request.data.get('module') or '').strip()
        basis = (request.data.get('basis') or '').strip()
        if not module:
            return Response({'error': 'module_required', 'code': 'module_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not basis:
            # The whole point of the model: an hours figure with no stated reconstruction is
            # not auditable, and this is the only place that can insist on one.
            return Response({'error': 'basis_required', 'code': 'basis_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            hours = Decimal(str(request.data.get('hours')))
        except (InvalidOperation, TypeError):
            return Response({'error': 'bad_hours', 'code': 'bad_hours'},
                            status=status.HTTP_400_BAD_REQUEST)
        if hours <= 0:
            return Response({'error': 'bad_hours', 'code': 'bad_hours'},
                            status=status.HTTP_400_BAD_REQUEST)

        org = _org_or_none(org_id)
        if org is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        row = OrgBuildHours.objects.create(
            organisation=org, period_month=month, module=module, hours=hours,
            basis=basis, recorded_by_email=(admin.email or ''))
        return Response({'id': row.id, 'period_month': row.period_month,
                         'module': row.module, 'hours': str(row.hours)},
                        status=status.HTTP_201_CREATED)


def _org_or_none(org_id):
    from apps.courses.models import PartnerOrganisation
    # org-fence: super-only callers reach this; the org id is validated, not trusted.
    return PartnerOrganisation.objects.filter(pk=org_id).first()


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
                description=request.data.get('description') or '',
                component=request.data.get('component') or '',
                urgency=request.data.get('urgency') or '',
                steps_to_reproduce=request.data.get('steps_to_reproduce') or '')
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
    """GET {count} for the nav badge. Super: requests waiting on US — SUBMITTED (awaiting triage)
    OR a triaged FEATURE with no approved analysis (TD-205). org_admin: own org's requests that
    need THEIR attention — quoted (awaiting accept) OR carrying an unanswered clarifying question.
    org_admin + super."""

    def get(self, request):
        gate = self._flag()
        if gate:
            return gate
        admin, err = self._org_side(request)
        if err:
            return err
        from django.db.models import Count, Q
        if self.has_role(admin, 'super'):
            # TD-205: "waiting on us" is BOTH ends of the engineer's involvement. Untriaged is the
            # obvious half. The other is a triaged FEATURE with no approved analysis — it cannot be
            # quoted at all (`analysis_required` refuses), so it is stuck BY CONSTRUCTION and
            # nothing else says so. A triaged BUG is deliberately NOT counted: a bug is free and
            # schedulable straight from triage, so it waits on a decision, not on an analysis.
            #
            # A filtered Count, and one annotate only (two multi-valued annotates multiply each
            # other — this project has been bitten by that).
            #
            # A single `.exclude(analyses__approved_at__isnull=False, analyses__superseded_at__
            # isnull=True)` is EQUIVALENT here and was measured to be, not assumed: Django compiles
            # one multi-condition exclude into a single NOT EXISTS with both conditions on the same
            # joined row, which is exactly "has no approved, live analysis". The multi-valued
            # negation trap is real but belongs to CHAINED `.exclude(a).exclude(b)`, which asks two
            # independent questions of two different rows. Count is kept for being explicit about
            # the zero and for not needing `.distinct()`, NOT because exclude is broken — an
            # earlier version of this comment claimed it was, and a bite-check disproved it.
            #
            # An approved analysis always carries ≥1 cited file because `approve_analysis` refuses
            # otherwise, so this agrees with `org_requests.approved_analysis` without re-testing it.
            # org-fence: super is global by design for the triage badge.
            waiting = OrgRequest.objects.annotate(
                live_analyses=Count('analyses', filter=Q(analyses__approved_at__isnull=False,
                                                         analyses__superseded_at__isnull=True)),
            ).filter(
                Q(status='submitted')
                | Q(status='triaged', triaged_kind='feature', live_analyses=0)
            )
            return Response({'count': waiting.count()})
        # TD-201: "needs you" is a quote awaiting a decision, or a question awaiting a reply —
        # the latter is now a comment row, so it is one subquery instead of walking a JSON list
        # per request.
        # org-fence: own org only (org_admin). Kept ADJACENT to the query — the static guard reads
        # a 200-char window, so an explanation wedged in between silently un-fences it.
        qs = OrgRequest.objects.filter(
            organisation_id=admin.owning_organisation_id,
        ).exclude(status__in=('done', 'declined'))
        return Response({'count': qs.filter(
            Q(status='quoted') | Q(comments__awaiting_reply=True)
        ).distinct().count()})


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
            # ⚠ `comment_id` AND `admin`, and both were missing. This call still passed `index=`
            # — the parameter the service dropped on 2026-07-31 when clarifications became
            # comments — so EVERY answer raised TypeError before the service was reached, and the
            # `except OrgRequestError` below could not see it. Answering was 500-ing for every
            # organisation on every request for eighteen days (BrightPath request #15).
            req = org_requests.answer_clarification(
                req, request.data.get('answer') or '',
                comment_id=request.data.get('comment_id'),
                admin=admin)
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


class AdminOrgRequestAskView(_OrgRequestsBase):
    """POST <pk>/ask/ {question} — the OWNER asks the requester something. Super only.

    Until now the clarification thread ran one way: the AI asked, the requester answered, and the
    owner watched by email. So a judgement about the SHAPE of a request — "adding a sponsor
    directly would bypass the terms and consent; would an invite do?" — had nowhere to go, because
    `triage_note` is private to the owner and the org never sees it.

    Same window as `/answer/` and the AI's own questions (submitted/triaged): a quoted request
    must not grow new questions, because the quote was priced against what was known when it
    was sent.

    Emails the requester through the SAME helper the AI's questions use, so a question reads the
    same to them however it was authored — only the on-screen attribution differs.
    """

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from . import org_requests
        try:
            question = org_requests.ask_question(req, admin, request.data.get('question') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        try:
            from . import emails
            emails.send_org_request_questions_email(req, [question])
        except Exception:
            logger.warning('Requests: owner-question notify failed for OrgRequest %s',
                           req.pk, exc_info=True)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


class AdminOrgRequestCommentView(_OrgRequestsBase):
    """POST <pk>/comments/ {body, visibility?} — post to the DISCUSSION (TD-201).

    The verb the module never had. Until now exactly ONE action reached the requester: `ask` a
    question. So a conclusion — "here is what we would build, and why" — had to travel as a quote
    note or not at all, and the owner's judgement about the shape of a request left the system.

    ACTOR: super OR any org_admin of the owning organisation (owner ruling, 2026-07-31). They can
    already READ the request — requests are org-fenced, and a cross-org pk is a 404 — so this adds
    no visibility, it lets the people already in the room speak. `_requestee(allow_super=True)` is
    exactly that rule; the org fence is the request lookup, not a check here.

    ⚠ `visibility='internal'` is SUPER-ONLY and the service refuses it for an org author. Two
    layers on purpose: a serializer allowlist cannot save you here, because the leak would be a
    ROW the org may not read rather than a field — see `org_requests.comments_for`.

    WINDOW: until the request is TERMINAL, wider than `OPEN_FOR_SHAPING`. Discussion continues
    after assignment (the owner's Bugzilla framing); it is asking a NEW QUESTION that still stops
    at the quote, because a question can re-price and a remark cannot.
    """

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk, allow_super=True)
        if err:
            return err
        from . import org_requests
        visibility = (request.data.get('visibility') or org_requests.VISIBILITY_SHARED).strip()
        # An org_admin may not post an internal note. Refused HERE as well as in the service so
        # the endpoint's contract is readable without following the call.
        if visibility == org_requests.VISIBILITY_INTERNAL and not admin.is_super:
            return Response({'error': 'forbidden', 'code': 'forbidden'},
                            status=status.HTTP_403_FORBIDDEN)
        author_kind = (org_requests.AUTHOR_OWNER if admin.is_super
                       else org_requests.AUTHOR_ORG)

        # ⚠ THE ENGINEER MAY SPEAK DIRECTLY, BUT ONLY WHERE THE ORGANISATION CANNOT HEAR IT
        # (2026-08-01). Authorship is otherwise derived from the caller, which meant a note the
        # ENGINEER wrote — a triage recommendation, say — arrived stamped as the OWNER, because it
        # is the owner's token making the call. TD-204 already refused that trade for approved
        # analyses ("attributing it to the approver is a lie about who wrote it"); the same
        # objection applies to a note the owner did not write.
        #
        # ⚠ INTERNAL ONLY, and the pairing is the whole control. Engineer prose that REACHES the
        # requester still has exactly one route — stage an analysis, the owner approves — so this
        # cannot become a side door around that gate. An internal note is owner-visible by
        # construction (`org_requests.comments_for` filters the ROW), so there is nothing for an
        # approval step to protect.
        #
        # ⚠ THE RULE LIVES HERE, NOT IN `post_comment`, and that is deliberate rather than lazy:
        # `approve_analysis` legitimately posts engineer + SHARED through the same service, so a
        # service-level "engineer implies internal" would break the one path this exists to
        # protect. What is enforced here is the HTTP contract — who may claim to be whom — while
        # the domain rule (engineer + shared happens only on approval) stays in the service.
        claimed = (request.data.get('author') or '').strip()
        if claimed:
            if not admin.is_super or claimed != org_requests.AUTHOR_ENGINEER:
                return Response({'error': 'forbidden', 'code': 'forbidden'},
                                status=status.HTTP_403_FORBIDDEN)
            if visibility != org_requests.VISIBILITY_INTERNAL:
                return Response({'error': 'engineer_must_be_internal',
                                 'code': 'engineer_must_be_internal'},
                                status=status.HTTP_400_BAD_REQUEST)
            author_kind = org_requests.AUTHOR_ENGINEER
        try:
            org_requests.post_comment(
                # ⚠ `author_admin=None` for the engineer, exactly as `approve_analysis` does.
                # `_comment_dicts` exposes `author_name`, so passing the calling admin would print
                # the OWNER'S NAME beside an "Engineer" badge — the same lie in a second field,
                # and the one a reader would actually see.
                req, None if author_kind == org_requests.AUTHOR_ENGINEER else admin,
                request.data.get('body') or '',
                author_kind=author_kind, visibility=visibility)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


class AdminOrgRequestAnalysisView(_OrgRequestsBase):
    """POST <pk>/analysis/ {body, estimated_hours?, cited_files[], authored_by?, repo_sha?} —
    stage the ENGINEER'S ANALYSIS as a DRAFT (TD-204). Super only.

    Posts NOTHING. The draft is invisible to the requesting organisation by construction — no
    org-facing serializer names `org_request_analyses` — and reaches them only when the owner
    approves it below. Owner ruling, 2026-07-31: *"you have to do the proper analysis and estimate
    the workload, and I want you to post as well, with my approval."*

    ⚠ `cited_files` is REQUIRED and non-empty. The estimate must cite its files; that is the only
    thing separating the engineer's number from the model's, and an analysis citing nothing is
    exactly what this record exists to prevent.
    """

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from . import org_requests
        try:
            org_requests.record_analysis(
                req, admin,
                body=request.data.get('body') or '',
                estimated_hours=request.data.get('estimated_hours'),
                cited_files=request.data.get('cited_files') or [],
                authored_by=request.data.get('authored_by') or '',
                repo_sha=request.data.get('repo_sha') or '',
                # A PROPOSED triage — prefills the owner's form and applies nothing. The request's
                # own kind/lane still change only when the owner presses Run.
                proposed_kind=request.data.get('proposed_kind') or '',
                proposed_lane=request.data.get('proposed_lane') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


class AdminOrgRequestAnalysisApproveView(_OrgRequestsBase):
    """POST <pk>/analysis/<aid>/approve/ — the owner approves; it enters the thread (TD-204).

    This is the control the whole record hangs on: the engineer stages, the owner approves, and
    only approval reaches the requester. Same split as `pool.publish_profile_to_pool` — preparing
    is free, publishing is gated. Super only.

    ⚠ The analysis is reached through `req.analyses`, never the model's top-level manager — the org
    fence IS the request lookup, so a cross-org id must 404 rather than resolve. (Naming that
    manager even in prose trips the static fence guard, which scans source text: see
    test_org_fence.TestOrgFenceStaticGuard.)

    Only the PROSE crosses to the requester. The cited files and the hours stay owner-side; see the
    model docstring for why neither is secrecy.
    """

    def post(self, request, pk, aid):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        analysis = req.analyses.filter(pk=aid).first()   # org-fence: scoped to this request
        if analysis is None:
            return self._not_found()
        from . import org_requests
        try:
            org_requests.approve_analysis(analysis, admin)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


class AdminOrgRequestWithdrawAnalysisView(_OrgRequestsBase):
    """POST <pk>/analysis/<aid>/withdraw/ — retire a DRAFT the engineer got wrong. Super only.

    Staging is POST-only and a draft could not be corrected or retracted, so fixing one meant
    staging a second and leaving the first in the approve list. Two near-identical drafts render
    with the same badge, the same hours and the same cited files, and `approve_analysis` does not
    refuse a second approval — so the stale one could reach the requester as a duplicate comment.

    ⚠ Same org fence as approve: reached through `req.analyses`, never the model's top-level
    manager, so a cross-org id 404s rather than resolving.
    """

    def post(self, request, pk, aid):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        analysis = req.analyses.filter(pk=aid).first()   # org-fence: scoped to this request
        if analysis is None:
            return self._not_found()
        from . import org_requests
        try:
            org_requests.withdraw_analysis(analysis, admin)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        req.refresh_from_db()
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


# ── Screenshot attachments (Sprint 15.1, TD-172) ────────────────────────────────────
# Images ONLY, ≤5 per request, org-fenced. Every read/write reaches an attachment ONLY through the
# org-fenced request lookup (_requestee → _org_request_for → cross-org 404), and the storage key is
# requests/<org_id>/<request_id>/<uuid> so the download-URL org assertion (serializers_admin +
# storage.resolve_org_for_path) refuses a foreign blob. Attachments are queried via the request's
# related manager (req.attachments) — never a raw OrgRequestAttachment.objects query — so the fence
# rides on the already-fenced request (no separate pragma needed).


class AdminOrgRequestAttachmentSignUploadView(_OrgRequestsBase):
    """POST <pk>/attachments/sign-upload/ — a signed URL to PUT a screenshot. org_admin (own org) +
    super. The request must be non-terminal, and the count cap is enforced BEFORE we mint a URL."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk, allow_super=True)
        if err:
            return err
        from . import org_requests
        # Evidence closes when the quote is ACCEPTED, not merely at a terminal status — changing
        # a screenshot under an accepted quote changes what was priced. See org_requests.can_attach.
        if not org_requests.can_attach(req):
            return Response({'error': 'request_closed', 'code': 'request_closed'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Count cap BEFORE signing (≤5 recorded attachments).
        if req.attachments.count() >= org_requests.MAX_ATTACHMENTS:
            return Response({'error': 'attachment_limit', 'code': 'attachment_limit',
                             'max': org_requests.MAX_ATTACHMENTS},
                            status=status.HTTP_400_BAD_REQUEST)
        import uuid
        from .storage import create_signed_upload_url, build_request_attachment_key
        path = build_request_attachment_key(req.organisation_id, req.id, uuid.uuid4().hex)
        url = create_signed_upload_url(path)
        if not url:
            return Response({'error': 'storage_unavailable', 'code': 'storage_unavailable'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'upload_url': url, 'storage_path': path})


class AdminOrgRequestAttachmentCreateView(_OrgRequestsBase):
    """POST <pk>/attachments/ — record an attachment row after the PUT. org_admin (own org) + super.
    Validates: non-terminal request, IMAGE allowlist (no pdf), size ≤ MAX_DOC_SIZE_BYTES, count cap,
    and the storage_path prefix must match THIS request (a foreign path is rejected)."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk, allow_super=True)
        if err:
            return err
        from . import org_requests
        # Evidence closes when the quote is ACCEPTED, not merely at a terminal status — changing
        # a screenshot under an accepted quote changes what was priced. See org_requests.can_attach.
        if not org_requests.can_attach(req):
            return Response({'error': 'request_closed', 'code': 'request_closed'},
                            status=status.HTTP_400_BAD_REQUEST)
        storage_path = (request.data.get('storage_path') or '').strip()
        content_type = (request.data.get('content_type') or '').strip()
        original_filename = (request.data.get('original_filename') or '').strip()
        try:
            size = int(request.data.get('size') or 0)
        except (TypeError, ValueError):
            size = 0
        # Path prefix must belong to THIS request (foreign-path rejection).
        from .storage import build_request_attachment_key
        expected_prefix = build_request_attachment_key(req.organisation_id, req.id, '')
        if not storage_path.startswith(expected_prefix) or storage_path == expected_prefix:
            return Response({'error': 'bad_path', 'code': 'bad_path'},
                            status=status.HTTP_400_BAD_REQUEST)
        # IMAGE allowlist only (no pdf).
        if not org_requests.is_allowed_attachment(content_type, original_filename):
            return Response({'error': 'unsupported_format', 'code': 'unsupported_format'},
                            status=status.HTTP_400_BAD_REQUEST)
        if size > settings.MAX_DOC_SIZE_BYTES:
            return Response({'error': 'file_too_large', 'code': 'file_too_large',
                             'max_mb': settings.MAX_DOC_SIZE_BYTES // (1024 * 1024)},
                            status=status.HTTP_400_BAD_REQUEST)
        # Count cap at record too (another attachment may have landed since sign).
        if req.attachments.count() >= org_requests.MAX_ATTACHMENTS:
            return Response({'error': 'attachment_limit', 'code': 'attachment_limit',
                             'max': org_requests.MAX_ATTACHMENTS},
                            status=status.HTTP_400_BAD_REQUEST)
        req.attachments.create(
            storage_path=storage_path, original_filename=original_filename[:255],
            content_type=content_type[:100], size=size, uploaded_by=admin)
        req.refresh_from_db()
        return Response(self._serialize(admin, req), status=status.HTTP_201_CREATED)


class AdminOrgRequestAttachmentDeleteView(_OrgRequestsBase):
    """DELETE <pk>/attachments/<att_id>/ — remove an attachment while the request is non-terminal.
    org_admin (own org) + super; the attachment is reached through the org-fenced request, so
    another org's attachment is 404. Deletes the row + best-effort blob sweep."""

    def delete(self, request, pk, att_id):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk, allow_super=True)
        if err:
            return err
        from . import org_requests
        # Evidence closes when the quote is ACCEPTED, not merely at a terminal status — changing
        # a screenshot under an accepted quote changes what was priced. See org_requests.can_attach.
        if not org_requests.can_attach(req):
            return Response({'error': 'request_closed', 'code': 'request_closed'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Scoped to THIS (already org-fenced) request — a foreign attachment id is 404.
        att = req.attachments.filter(pk=att_id).first()
        if att is None:
            return self._not_found()
        path = att.storage_path
        att.delete()
        try:
            from .storage import delete_objects
            delete_objects([path])
        except Exception:
            logger.warning('Requests: attachment blob sweep failed for %s', path, exc_info=True)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


# ── Wallet credits (P4b) ─────────────────────────────────────────────────────────
# The admin surface that DRIVES the P4a credit chain. Until this existed, every wallet
# credit on the platform — including the RM172,000 already recorded — was written by a
# developer touching the database, which made the sign-off chain a control on paper: the
# people it names (an `admin` maker, an `org_admin` approver) had no way to execute their
# own steps. These endpoints remove the developer from the money path.
#
# ORG FENCE: a Sponsor is a platform-level account and is deliberately NOT org-fenced (see
# AdminSponsorListView), but a CREDIT is not — it belongs to a Programme, which belongs to
# an Organisation. Every read and write below is fenced on `programme__organisation_id`, so
# one tenant can never see or sign another tenant's money.

class _CreditsBase(_AdminBase):
    """Shared gate + org-fenced credit lookup for the wallet-credit endpoints."""

    # Who may OPEN a credit screen. Mirrors the payments read gate: finance is admitted
    # because checking is its job; the per-step role logic lives in the service, so this
    # gate is deliberately broad and `sponsorship.sign_admin_credit` refuses the wrong step.
    _READ_ROLES = ('org_admin', 'admin', 'finance')

    def _credits_admin(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (admin.is_super or admin.role in self._READ_ROLES):
            return None, self._deny_role()
        return admin, None

    def _credit_qs(self, admin):
        """Every credit visible to this admin — fenced by the programme's organisation."""
        return self._org_scoped(
            Donation.objects.select_related('sponsor', 'programme'),
            admin, field='programme__organisation_id')

    def _credit_for(self, admin, pk):
        return self._credit_qs(admin).filter(pk=pk).first()


def _credit_dict(credit):
    """Allowlist view of one credit. Explicit fields only — never model passthrough — so a
    later column cannot leak onto an admin surface by accident."""
    return {
        'id': credit.id,
        'sponsor_id': credit.sponsor_id,
        'sponsor_name': getattr(credit.sponsor, 'name', '') or '',
        'programme_id': credit.programme_id,
        'programme_name': getattr(credit.programme, 'name_en', '') or '',
        'amount': str(credit.amount),
        'source': credit.source,
        'external_reference': credit.external_reference,
        'status': credit.status,
        'is_spendable': credit.is_spendable,
        'recorded_by': credit.recorded_by,
        'recorded_at': credit.recorded_at,
        'finance_checked_by': credit.finance_checked_by,
        'finance_checked_at': credit.finance_checked_at,
        'confirmed_by': credit.confirmed_by,
        'confirmed_at': credit.confirmed_at,
        'created_at': credit.created_at,
    }


class AdminWalletCreditListCreateView(_CreditsBase):
    """GET  .../admin/scholarship/credits/[?sponsor=<id>&status=<s>] — the credit ledger.
    POST .../admin/scholarship/credits/ {sponsor_id, programme_id, amount,
    external_reference} — RECORD an off-platform gift as a `draft`.

    Recording stamps no signature: it opens the chain, and the maker signs separately with
    a typed name (the same separation payments keeps between create_run and sign)."""

    def get(self, request):
        admin, err = self._credits_admin(request)
        if err:
            return err
        qs = self._credit_qs(admin)
        sponsor_id = request.query_params.get('sponsor')
        if sponsor_id:
            qs = qs.filter(sponsor_id=sponsor_id)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response({'credits': [_credit_dict(c) for c in qs.order_by('-id')]})

    def post(self, request):
        admin, err = self._credits_admin(request)
        if err:
            return err
        from decimal import Decimal, InvalidOperation
        from . import sponsorship as sponsorship_service
        from .models import Programme
        sponsor = Sponsor.objects.filter(pk=request.data.get('sponsor_id')).first()
        if sponsor is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # The programme must be one this admin's organisation runs — otherwise an admin
        # could credit a wallet inside another tenant's gift.
        programme = self._org_scoped(
            Programme.objects.all(), admin, field='organisation_id'
        ).filter(pk=request.data.get('programme_id')).first()
        if programme is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            amount = Decimal(str(request.data.get('amount')))
        except (InvalidOperation, TypeError, ValueError):
            return Response({'error': 'invalid_amount', 'code': 'invalid_amount'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            credit = sponsorship_service.record_admin_credit(
                sponsor=sponsor, programme=programme, amount=amount,
                external_reference=request.data.get('external_reference') or '',
                admin=admin)
        except sponsorship_service.CreditError as e:
            return Response({'error': e.code, 'code': e.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(_credit_dict(credit), status=status.HTTP_201_CREATED)


class AdminWalletCreditSignView(_CreditsBase):
    """POST .../admin/scholarship/credits/<pk>/sign/ {typed_name} — maker sign, finance
    check (when the org's chain includes that step), or approver countersign, whichever is
    this credit's next step. The per-step role logic + typed-name match + pairwise
    distinctness live in `sponsorship.sign_admin_credit`; this view admits every credit role
    and lets the service refuse the wrong step (exactly as AdminPaymentRunSignView does)."""

    def post(self, request, pk):
        admin, err = self._credits_admin(request)
        if err:
            return err
        credit = self._credit_for(admin, pk)
        if credit is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from . import sponsorship as sponsorship_service
        try:
            sponsorship_service.sign_admin_credit(
                credit, admin, request.data.get('typed_name') or '')
        except sponsorship_service.CreditError as e:
            return Response({'error': e.code, 'code': e.code},
                            status=status.HTTP_400_BAD_REQUEST)
        credit.refresh_from_db()
        return Response(_credit_dict(credit))


class AdminWalletCreditCancelView(_CreditsBase):
    """POST .../admin/scholarship/credits/<pk>/cancel/ — void a credit that has not been
    confirmed (a mis-keyed amount or bank reference). The row is never deleted; a confirmed
    credit is reversed by a compensating entry, never by editing history."""

    def post(self, request, pk):
        admin, err = self._credits_admin(request)
        if err:
            return err
        credit = self._credit_for(admin, pk)
        if credit is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from . import sponsorship as sponsorship_service
        try:
            sponsorship_service.cancel_admin_credit(credit, admin)
        except sponsorship_service.CreditError as e:
            return Response({'error': e.code, 'code': e.code},
                            status=status.HTTP_400_BAD_REQUEST)
        credit.refresh_from_db()
        return Response(_credit_dict(credit))

# ── Sponsor terms (T2) ───────────────────────────────────────────────────────
# The versioned document a sponsor reads and accepts. Authoring only — nothing here is
# sponsor-facing; the wizard and the gate are T3.

def _terms_section_dict(sec):
    """Allowlist view of one section. Explicit fields — never model passthrough."""
    return {
        'order': sec.order,
        'heading_en': sec.heading_en, 'heading_ms': sec.heading_ms, 'heading_ta': sec.heading_ta,
        'body_en': sec.body_en, 'body_ms': sec.body_ms, 'body_ta': sec.body_ta,
        'is_quiz_candidate': sec.is_quiz_candidate,
        'quiz_en': sec.quiz_en, 'quiz_ms': sec.quiz_ms, 'quiz_ta': sec.quiz_ta,
        'quiz_generated_model': sec.quiz_generated_model,
    }


def _terms_summary_dict(terms):
    return {
        'id': terms.id,
        'version': terms.version,
        'status': terms.status,
        'title_en': terms.title_en,
        # The list table shows these two, so they belong on the summary. `languages_available`
        # walks the sections, which is why the list view prefetches them.
        'languages_available': terms.languages_available,
        'section_count': terms.sections.count(),
        'created_by_email': terms.created_by_email,
        'published_by_email': terms.published_by_email,
        'published_at': terms.published_at,
        'archived_at': terms.archived_at,
        'created_at': terms.created_at,
        'updated_at': terms.updated_at,
    }


def _terms_detail_dict(terms):
    d = _terms_summary_dict(terms)
    d.update({
        'title_ms': terms.title_ms, 'title_ta': terms.title_ta,
        'intro_en': terms.intro_en, 'intro_ms': terms.intro_ms, 'intro_ta': terms.intro_ta,
        'languages_available': terms.languages_available,
        'sections': [_terms_section_dict(x) for x in terms.sections.all()],
        'acceptance_count': terms.acceptances.count(),
    })
    return d


def _terms_validation_dict(result):
    return {
        'ok': result.ok,
        'errors': [{'code': c, 'label': sponsor_terms_mod.RULE_LABELS.get(c, c)}
                   for c in result.errors],
        'warnings': [{'code': c, 'label': sponsor_terms_mod.RULE_LABELS.get(c, c)}
                     for c in result.warnings],
    }


def _terms_err(exc):
    """A publish refusal is a 403 (you are not allowed); everything else is a 400 (fix it)."""
    payload = {'error': exc.code}
    if getattr(exc, 'detail', ''):
        payload['detail'] = exc.detail
    if getattr(exc, 'errors', None):
        payload['errors'] = [{'code': c, 'label': sponsor_terms_mod.RULE_LABELS.get(c, c)}
                             for c in exc.errors]
    status_code = 403 if exc.code == 'publish_forbidden' else 400
    return Response(payload, status=status_code)


class _SponsorTermsBase(_AdminBase):
    """Gate for the sponsor-terms panel — identical to the sponsor-emails gate, and for the same
    reason: authoring what every donor is bound by is an editorial power, not a reading one.
    Finance reads the sponsor list because money is its business; it does not write the terms.
    """
    def _terms_admin(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (self.has_role(admin, 'admin') or admin.role == 'org_admin'):
            return None, self._deny_role()
        return admin, None

    def _version_or_404(self, pk):
        from .models import SponsorTermsVersion
        return (SponsorTermsVersion.objects
                .prefetch_related('sections')
                .filter(pk=pk)
                .first())


class AdminSponsorTermsListView(_SponsorTermsBase):
    """GET  .../admin/scholarship/sponsor-terms/  — every version, newest first.
    POST .../admin/scholarship/sponsor-terms/  {version, copy_from?} — a new draft.
    """
    def get(self, request):
        admin, err = self._terms_admin(request)
        if err:
            return err
        from .models import SponsorTermsVersion
        rows = SponsorTermsVersion.objects.prefetch_related('sections').all()
        active = sponsor_terms_mod.active_version()
        return Response({
            'versions': [_terms_summary_dict(t) for t in rows],
            'active_version': active.version if active else '',
            'sponsor_count': Sponsor.objects.count(),
        })

    def post(self, request):
        admin, err = self._terms_admin(request)
        if err:
            return err
        copy_from = None
        if request.data.get('copy_from'):
            copy_from = self._version_or_404(request.data.get('copy_from'))
            if not copy_from:
                return Response({'error': 'not_found'}, status=404)
        try:
            terms = sponsor_terms_mod.create_version(
                version=request.data.get('version') or '',
                copy_from=copy_from,
                by_email=admin.email or '',
            )
        except sponsor_terms_mod.SponsorTermsError as exc:
            return _terms_err(exc)
        return Response(_terms_detail_dict(terms), status=201)


class AdminSponsorTermsDetailView(_SponsorTermsBase):
    """GET / PATCH one version. PATCH edits the title and intro only; sections have their own
    endpoint because they are replaced wholesale rather than patched field by field."""
    def get(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        return Response(_terms_detail_dict(terms))

    def patch(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        fields = {k: v for k, v in request.data.items()
                  if k in sponsor_terms_mod._CONFIG_FIELDS}
        if not fields:
            return Response({'error': 'nothing_to_update'}, status=400)
        try:
            sponsor_terms_mod.update_intro(terms, fields, by_email=admin.email or '')
        except sponsor_terms_mod.SponsorTermsError as exc:
            return _terms_err(exc)
        return Response(_terms_detail_dict(terms))


class AdminSponsorTermsSectionsView(_SponsorTermsBase):
    """PUT .../sponsor-terms/<pk>/sections/ {sections: [...]} — replace them all.

    Orders are assigned server-side by position, so a client cannot produce a gap or a duplicate.
    """
    def put(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        try:
            sponsor_terms_mod.replace_sections(terms, request.data.get('sections'))
        except sponsor_terms_mod.SponsorTermsError as exc:
            return _terms_err(exc)
        terms.refresh_from_db()
        return Response(_terms_detail_dict(terms))


class AdminSponsorTermsGenerateQuizView(_SponsorTermsBase):
    """POST .../sponsor-terms/<pk>/sections/<order>/generate-quiz/ — a Gemini draft. Billable."""
    def post(self, request, pk, order):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        section = terms.sections.filter(order=order).first()
        if not section:
            return Response({'error': 'not_found'}, status=404)
        try:
            sponsor_terms_mod.generate_quiz(section)
        except sponsor_terms_mod.SponsorTermsError as exc:
            return _terms_err(exc)
        terms.refresh_from_db()
        return Response(_terms_detail_dict(terms))


class AdminSponsorTermsValidateView(_SponsorTermsBase):
    """GET .../sponsor-terms/<pk>/validate/ — the publish checklist, labels included."""
    def get(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        return Response(_terms_validation_dict(sponsor_terms_mod.validate_for_publish(terms)))


class AdminSponsorTermsPublishView(_SponsorTermsBase):
    """POST .../sponsor-terms/<pk>/publish/ — super or org_admin.

    Opened from super-only on 2026-07-28 at the owner's direction, so the programme lead can
    publish without going through the platform owner. A plain `admin` is still refused: authoring
    is staff work, but making a document binding on a donor is not.
    """
    def post(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        try:
            # super OR org_admin. A plain `admin` may AUTHOR but not make it binding: they are
            # staff doing the work, not the people answerable for what a donor is bound by.
            may_publish = bool(admin.is_super_admin) or admin.role == 'org_admin'
            sponsor_terms_mod.publish(terms, by_email=admin.email or '', allowed=may_publish)
        except sponsor_terms_mod.SponsorTermsError as exc:
            return _terms_err(exc)
        terms.refresh_from_db()
        return Response(_terms_detail_dict(terms))


class AdminSponsorTermsImportDocxView(_SponsorTermsBase):
    """POST a .docx — parse it into a PROPOSED flat section list for the author to review.

    Nothing is saved and the upload is NOT retained. On confirm the frontend PUTs the reviewed
    sections, exactly as the contract importer works. Draft-only.
    """
    from rest_framework.parsers import MultiPartParser
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        if terms.status != 'draft':
            return Response({'error': 'not_draft'}, status=400)
        upload = request.FILES.get('file')
        if upload is None:
            return Response({'error': 'no_file'}, status=400)
        try:
            proposal = sponsor_terms_mod.import_docx(upload.read())   # bytes only; never stored
        except sponsor_terms_mod.SponsorTermsError as exc:
            return _terms_err(exc)
        except Exception:
            # contracts.* raises ContractsError for an unreadable/empty document. Map anything
            # that escapes to one code rather than leaking a stack trace into the panel.
            return Response({'error': 'docx_unreadable'}, status=400)
        return Response(proposal)


class AdminSponsorTermsPreviewView(_SponsorTermsBase):
    """GET .../sponsor-terms/<pk>/preview/?locale=en — exactly what a sponsor will read.

    Serves `sponsor_terms.document()`, the SAME function the sponsor-facing page will call in T3,
    so the preview cannot drift from the real thing.
    """
    def get(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        locale = request.query_params.get('locale') or 'en'
        return Response({
            'document': sponsor_terms_mod.document(terms, locale),
            'checkpoints': sponsor_terms_mod.quiz_checkpoints(terms, locale),
        })


def _checks_both_modes(tokens):
    """Every contrast result for a token set, in both modes, each row carrying its own `mode`.

    ONE helper rather than a call per site: the payload builder and the refusal path both report
    these numbers, and two independently-written list comprehensions is how they start disagreeing
    about which modes were measured.
    """
    from apps.courses import contrast, theme_tokens
    return [dict(r._asdict(), mode=mode)
            for mode in theme_tokens.MODES
            for r in contrast.check_tokens(tokens, mode)]


class AdminOrganisationThemeView(_AdminBase):
    """GET/PUT/DELETE `admin/scholarship/organisation/theme/` — an organisation's colour.

    Layer 1 A2. The second tab of the Programme screen, over the storage A1 built. An `org_admin`
    picks ONE colour; the server derives the ten shades, checks a person can read them, and freezes
    the result. What is stored is the approved SET, never the hex — `courses.theme_tokens` carries
    the argument for why that is the load-bearing decision of this arc.

    ⚠ THE CONTRAST GATE REFUSES; IT DOES NOT WARN. A tenant will pick a colour that renders at 4:1
    against white, and a warning is dismissed by the person who chose it while a student is the one
    who cannot read the page. So an unreadable colour is a `400 unreadable` carrying the failing
    pairs, and the screen turns them into sentences. The browser checks too — that is a courtesy,
    never the gate. This is the gate.

    ⚠ THE ORGANISATION IS DERIVED, NEVER SENT. It comes from `admin.owning_organisation`, the same
    field the org fence uses, so this cannot widen access by construction. A super names one with
    `?org=<code>`; more than one tenant and no code is `organisation_required`, never a silent pick
    (the PF-1 rule). A code outside the caller's organisation is **404, never 403** — a 403 would
    confirm the tenant exists.

    ⚠ `tenants()`, NOT `filter(is_active=True)`. `partner_organisations` is dual-role and holds nine
    referral organisations that are not tenants; the queryset that reads like "the organisations" is
    a trap the console has already fallen into once, in July.

    Who may write: `super` and `org_admin` only. A colour is the organisation's identity, held by
    its administrator — a reviewer or a plain admin gets 403.

    ⚠ THIS DOES NOT REFUSE THE PLATFORM ORGANISATION, AND `set_organisation_theme` DOES. That is
    deliberate, not drift. The command is the MECHANICAL path, where a casual backfill would give
    BrightPath a derived row and shift its own colours by a channel against the seeded ramp in
    `globals.css`. This is the DELIBERATE path: the person sees the ten shades and the six checks
    before they commit, and DELETE puts the stylesheet back exactly. A screen that showed its only
    live tenant a permanently disabled control would be a worse answer than either.

    Every write is audited (`AUDIT organisation_theme_set` / `organisation_theme_cleared`).
    """

    ROLES = ('org_admin',)

    def _gate(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not self.has_role(admin, *self.ROLES):
            return None, self._deny_role()
        return admin, None

    def _organisation_for(self, admin, code):
        """The one organisation this request is about, or an error response.

        Mirrors `AdminProgrammeConfigurationView._programme_for` deliberately — same fence, same
        404-not-403, same refusal to pick silently between two.
        """
        from apps.courses.models import PartnerOrganisation
        qs = PartnerOrganisation.objects.filter(is_active=True).tenants()
        if not self.has_role(admin, 'super'):
            org_id = admin.owning_organisation_id
            qs = qs.filter(id=org_id) if org_id else qs.none()
        if code:
            org = qs.filter(code=code).first()
            if org is None:
                return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
            return org, None
        orgs = list(qs.order_by('code')[:2])
        if not orgs:
            return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        if len(orgs) > 1:
            return None, Response(
                {'error': 'organisation_required', 'code': 'organisation_required',
                 'organisations': [o.code for o in qs.order_by('code')]},
                status=status.HTTP_400_BAD_REQUEST)
        return orgs[0], None

    def _payload(self, org):
        """What the screen needs to tell the two states apart.

        ⚠ `live` AND `draft` ARE SEPARATE KEYS, never one "colour" that means whichever exists.
        The entire point of A3 is that those are different things, and a payload that folds them
        together would invite a screen that cannot say which one a visitor is seeing.
        """
        from apps.courses import contrast, theme_tokens
        from apps.courses import theme_versions

        live = theme_versions.active_for(org)
        draft = theme_versions.draft_for(org)
        previous = theme_versions.previous_for(org)
        live_tokens = theme_tokens.applied_tokens(live.tokens) if live else None
        draft_tokens = theme_tokens.applied_tokens(draft.tokens) if draft else None

        def block(row, tokens):
            if row is None:
                return None
            return {
                'colour': row.source_colour or '',
                # Checks travel with whichever set they describe, so the screen never has to guess
                # which colour a number belongs to.
                # ⚠ BOTH MODES since F7a. A colour is stored once and rendered in light AND dark,
                # so a screen showing only the light numbers would report a colour as fine while
                # the gate that saves it disagrees.
                'checks': _checks_both_modes(tokens) if tokens else [],
            }

        return {
            'organisation': {'code': org.code, 'name': org.name},
            'live': block(live, live_tokens),
            'draft': block(draft, draft_tokens),
            # What Revert would put back. '' means "the platform colours" — a real answer, because
            # reverting the first colour an organisation ever published lands them there.
            'previous_colour': (previous.source_colour if previous else '') or '',
            'can_revert': live is not None,
            'published_at': live.published_at.isoformat() if live and live.published_at else '',
            'published_by': (live.published_by_email if live else '') or '',
            # The LIVE tokens — what a visitor is seeing right now, never the draft.
            'tokens': live_tokens,
        }

    def get(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        return Response(self._payload(org))

    def put(self, request):
        """Save the DRAFT. **What visitors see is untouched** — that is the whole sprint."""
        from apps.courses import contrast, theme_tokens
        from apps.courses import theme_versions

        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err

        colour = (request.data.get('colour') or '').strip()
        try:
            tokens = theme_tokens.tokens_from_colour(colour)
        except theme_tokens.ThemeTokenError:
            return Response({'error': 'bad_colour', 'code': 'bad_colour'},
                            status=status.HTTP_400_BAD_REQUEST)

        # ⚠ THE GATE RUNS AT DRAFT TIME, NOT ONLY AT PUBLISH. An unreadable colour should be
        # refused at the moment somebody types it, not saved and refused later — a draft that
        # cannot ever be published is a trap you walk into twice.
        # ⚠ AND IT RUNS IN BOTH MODES since F7a. A2 could honestly gate light alone because dark was
        # unreachable; it is reachable now, and a tenant refused only after somebody flips the
        # switch has been let down by the gate rather than protected by it.
        fails = contrast.failures_all_modes(tokens)
        if fails:
            return Response(
                {'error': 'unreadable', 'code': 'unreadable',
                 'checks': _checks_both_modes(tokens),
                 'failing': [f'{mode}:{r.key}' for mode, r in fails]},
                status=status.HTTP_400_BAD_REQUEST)

        theme_versions.save_draft(org, colour, tokens)
        logger.info('AUDIT organisation_theme_draft_saved org=%s colour=%s by=%s',
                    org.code, colour, admin.email or '')
        return Response(self._payload(org))

    def delete(self, request):
        """Discard the DRAFT. What is live stays live — a draft you throw away costs nobody."""
        from apps.courses import theme_versions

        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        if theme_versions.discard_draft(org):
            logger.info('AUDIT organisation_theme_draft_discarded org=%s by=%s',
                        org.code, admin.email or '')
        return Response(self._payload(org))


class AdminOrganisationThemePublishView(AdminOrganisationThemeView):
    """POST `admin/scholarship/organisation/theme/publish/` — the draft becomes what visitors see.

    Inherits the gate, the org fence and the payload from the view above deliberately: three
    endpoints acting on one resource should not each grow their own copy of "which organisation is
    this, and may you touch it".

    An `org_admin` may publish a draft they wrote themselves — the owner's 2026-07-28 ruling for
    sponsor terms, where a same-author check is deliberately absent and a test pins its absence. A
    colour is a smaller decision than a binding document, so the same answer holds.
    """

    def post(self, request):
        from apps.courses import theme_versions

        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        try:
            # `allowed=True` asserts the ROLE GATE ABOVE HAS PASSED. The service defaults it False
            # so a shell caller fails closed — mirroring `sponsor_terms.publish`.
            theme_versions.publish(org, by_email=admin.email or '', allowed=True)
        except theme_versions.ThemeVersionError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self._payload(org))


class AdminOrganisationThemeRevertView(AdminOrganisationThemeView):
    """POST `admin/scholarship/organisation/theme/revert/` — put back the colour that was live before.

    ⚠ REVERTING THE FIRST COLOUR EVER PUBLISHED LEAVES THE ORGANISATION ON THE PLATFORM STYLESHEET,
    and that is a correct outcome rather than an error: it is genuinely what they had before, and it
    is how a tenant gets all the way back to the default. The payload says so with an empty
    `live`; the screen renders it as "using the default colours".
    """

    def post(self, request):
        from apps.courses import theme_versions

        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        try:
            theme_versions.revert(org, by_email=admin.email or '', allowed=True)
        except theme_versions.ThemeVersionError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self._payload(org))


class AdminProgrammeConfigurationView(_AdminBase):
    """GET/PUT `admin/scholarship/programme/configuration/` — what ONE programme asks for.

    Layer 0 Sprint 5 (2026-08-30): the screen an `org_admin` uses to set, per catalogue item
    (documents AND questions), one of Off / Optional / Required. It writes
    `ProgrammeApplicationItem` rows — the same rows `requirements.programme_states` reads — so the
    gate, the payload, the verdict facts and Check-2 all follow the change with no edits of their
    own. That single seam is the design; do not teach this view a second copy of the rule.

    ⚠ THE CATALOGUE IS NOT A FENCE. Which items a programme asks for is configuration, never access
    control. The organisation fence is `_org_scoped` / `_org_allows` (cross-org ⇒ 404), and this
    view fences the PROGRAMME on `organisation_id` the same way: an org_admin may only ever load
    or write their own organisation's programme; a super passes `?programme=<code>`. A programme
    outside the caller's organisation is **404, never 403** — a 403 would confirm the tenant exists
    (the same reasoning that keeps the org fence on 404).

    Who may write: `super` and `org_admin` only — a plain `admin`/`qc`/`reviewer`/`finance` gets
    403 `_deny_role`. Configuration decides what every applicant to the programme is asked for;
    that is the organisation's decision, held by its administrator.

    Refuses to switch a CORE item off (`core_item`, 400) — the owner's 2026-07-28 policy floor.
    `programme_states` floors a stray row anyway, so this refusal is what the SCREEN reads; the
    floor underneath is what the data reads. Both are deliberate.

    Every change writes an `AUDIT programme_item_set` line (who, which programme, which item,
    old → new). Rows already at the requested state are not rewritten and not audited.

    `live_applicants` is COUNTED at request time (never typed in): applications on this programme
    still inside the submission gate (`shortlisted`). Those are the students a change reaches —
    a submitted student carries their frozen `requirements_snapshot` and is untouched.
    """

    ROLES = ('org_admin',)

    def _gate(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not self.has_role(admin, *self.ROLES):
            return None, self._deny_role()
        return admin, None

    def _programme_for(self, admin, code):
        """The one programme this request is about, or an error response.

        Fenced on `organisation_id` — derived from the same `owning_organisation` the org fence
        uses, so it cannot widen anything. Missing or cross-org → 404 (never 403).

        ⚠ NOT FILTERED ON `is_active`, AND THAT IS THE PRODUCT RULE (2026-09-03). A gift is created
        INACTIVE and is configured before it is switched on, so refusing to load the configuration
        of an unswitched gift refused the only screen that makes switching it on safe. It was
        `is_active=True` until the owner created a second gift and found they could not open it.
        Configuring an inactive programme reaches nobody: no cohort is open beneath it, so no
        application resolves through it. The FENCE is the organisation, and it is untouched.
        """
        qs = Programme.objects.all().select_related('organisation')
        if not self.has_role(admin, 'super'):
            org_id = admin.owning_organisation_id
            qs = qs.filter(organisation_id=org_id) if org_id else qs.none()
        if code:
            programme = qs.filter(code=code).first()
            if programme is None:
                return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
            return programme, None
        programmes = list(qs.order_by('code')[:2])
        if not programmes:
            return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        if len(programmes) > 1:
            # Never pick silently — the P2b/PF-1 rule. Name the choices so the client can ask.
            return None, Response(
                {'error': 'programme_required', 'code': 'programme_required',
                 'programmes': [p.code for p in qs.order_by('code')]},
                status=status.HTTP_400_BAD_REQUEST)
        return programmes[0], None

    def _payload(self, programme):
        from . import requirements
        from .models import ApplicationItem
        states = {
            'document': requirements.programme_states(programme, 'document'),
            'question': requirements.programme_states(programme, 'question'),
        }
        items = []
        for item in ApplicationItem.objects.filter(is_active=True).order_by('kind', 'code'):
            items.append({
                'kind': item.kind,
                'code': item.code,
                'label_key': item.label_key,
                'is_core': item.is_core,
                'default_state': item.default_state,
                'state': states[item.kind].get(item.code, item.default_state),
            })
        # org-fence: `programme` was fenced to the caller's organisation in _programme_for.
        live = ScholarshipApplication.objects.filter(
            programme=programme, status='shortlisted').count()
        return {
            'programme': {'code': programme.code, 'name': programme.name_en,
                          'organisation': programme.organisation.name},
            'live_applicants': live,
            'items': items,
        }

    def get(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        programme, err = self._programme_for(
            admin, (request.query_params.get('programme') or '').strip())
        if err:
            return err
        return Response(self._payload(programme))

    def put(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        programme, err = self._programme_for(
            admin, (request.query_params.get('programme') or '').strip())
        if err:
            return err

        from .models import ITEM_STATE_CHOICES, ApplicationItem, ProgrammeApplicationItem
        valid_states = {s for s, _ in ITEM_STATE_CHOICES}
        changes = request.data.get('items')
        if not isinstance(changes, list):
            return Response({'error': 'bad_items', 'code': 'bad_items'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Validate EVERYTHING before writing ANYTHING — a half-applied save is worse than a
        # refused one, and the screen renders one refusal, not a list of partial outcomes.
        resolved = []
        for entry in changes:
            kind = (entry or {}).get('kind')
            code = (entry or {}).get('code')
            state = (entry or {}).get('state')
            item = ApplicationItem.objects.filter(kind=kind, code=code, is_active=True).first()
            if item is None:
                return Response({'error': 'unknown_item', 'code': 'unknown_item',
                                 'item': f'{kind}:{code}'}, status=status.HTTP_404_NOT_FOUND)
            if state not in valid_states:
                return Response({'error': 'bad_state', 'code': 'bad_state',
                                 'item': f'{kind}:{code}'}, status=status.HTTP_400_BAD_REQUEST)
            if item.is_core and state == 'off':
                return Response({'error': 'core_item', 'code': 'core_item',
                                 'item': f'{kind}:{code}'}, status=status.HTTP_400_BAD_REQUEST)
            resolved.append((item, state))

        from . import requirements
        before = {
            'document': requirements.programme_states(programme, 'document'),
            'question': requirements.programme_states(programme, 'question'),
        }
        for item, state in resolved:
            was = before[item.kind].get(item.code, item.default_state)
            if was == state:
                continue
            ProgrammeApplicationItem.objects.update_or_create(
                programme=programme, item=item,
                defaults={'state': state, 'updated_by_email': admin.email or ''})
            logger.info('AUDIT programme_item_set programme=%s item=%s:%s was=%s now=%s by=%s',
                        programme.code, item.kind, item.code, was, state, admin.email or '')
        return Response(self._payload(programme))


# ── Gift programmes and their intake years (Sabah S2b, 2026-09-02) ───────────────────────────────
#
# Until now neither a Programme nor a ScholarshipCohort could be created anywhere: no endpoint, no
# screen, and `scholarship` registers no models in Django admin either. Standing up a second gift
# meant an engineer writing SQL. That is the whole reason this exists — the owner's acceptance test
# is "Suresh, as org admin, can do everything on his own without any work from me".
#
# ⚠ THE FENCE IS THE ORGANISATION, EXACTLY AS `AdminProgrammeConfigurationView` DOES IT:
# `organisation_id` derived from the caller's own `owning_organisation`, and anything outside it is
# **404, never 403** — a 403 would confirm the tenant exists. A super sees every tenant, because
# they genuinely work across them.
#
# ⚠ THESE SCREENS ARE NOT A SECOND SECURITY BOUNDARY. A programme narrows INSIDE the org wall; it
# never replaces it (`Programme` docstring). Nothing here authorises anything.

def _programme_row(p):
    """One gift, with the two counts the list screen shows. Deliberately not a serializer: the
    shape is three joins wide and exists only here."""
    from .models import ScholarshipCohort, ScholarshipApplication
    cohorts = ScholarshipCohort.objects.filter(programme=p)
    open_year = cohorts.filter(is_open=True, is_active=True).values_list('year', flat=True).first()
    return {
        'id': p.id, 'code': p.code,
        'name_en': p.name_en, 'name_ms': p.name_ms, 'name_ta': p.name_ta,
        'is_active': p.is_active,
        'intake_years': cohorts.count(),
        # Counted on a programme ALREADY narrowed to the caller's own `owning_organisation`, so it
        # cannot be handed another tenant's programme in the first place.
        # org-fence: programme pre-fenced by `_ProgrammeScopedBase._programmes_for`
        'applications': ScholarshipApplication.objects.filter(programme=p).count(),
        # The year currently taking applications, or None. Named `open_year` rather than `is_open`
        # because a PROGRAMME is never open — one of its years is.
        'open_year': open_year,
    }


# The requirement columns the screens tick and fill. NULL means "not applied" (S2a) — the value IS
# the switch, so unticking is writing null and there is no companion boolean to disagree with it.
REQUIREMENT_FIELDS = (
    'min_spm_a_count', 'min_spm_bplus_count', 'min_stpm_pngk', 'min_merit_score',
    'income_ceiling', 'per_capita_ceiling',
)


def _cohort_row(c):
    from .models import ScholarshipApplication
    return {
        'id': c.id, 'code': c.code, 'name': c.name, 'year': c.year,
        'is_open': c.is_open, 'is_active': c.is_active,
        # org-fence: same reasoning — the cohort reached here was selected through
        # `programme__in=self._programmes_for(admin)`, so it is already inside the caller's org.
        'applications': ScholarshipApplication.objects.filter(cohort=c).count(),
        'requirements': {f: getattr(c, f) for f in REQUIREMENT_FIELDS},
    }


class _ProgrammeScopedBase(_AdminBase):
    """Shared gate + org fence for the two screens. `org_admin` and `super` only — deciding what a
    programme is and who it asks for is the organisation's own decision, held by its administrator
    (the same rule and the same roles as the Layer 0 configuration screen)."""

    ROLES = ('org_admin',)

    def _gate(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not self.has_role(admin, *self.ROLES):
            return None, self._deny_role()
        return admin, None

    def _programmes_for(self, admin):
        """Every gift this caller may touch. ⚠ INCLUDES INACTIVE ONES, unlike the configuration
        screen's `_programme_for` — you cannot switch a programme on if you cannot see it."""
        from .models import Programme
        qs = Programme.objects.select_related('organisation')
        if not self.has_role(admin, 'super'):
            org_id = admin.owning_organisation_id
            qs = qs.filter(organisation_id=org_id) if org_id else qs.none()
        return qs

    def _programme_or_404(self, admin, pk):
        p = self._programmes_for(admin).filter(pk=pk).first()
        if p is None:
            return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        return p, None


# A URL-safe slug, because this is what an apply link carries (`?p=<code>`), and lower-case only
# so two codes cannot differ by case alone in a place people retype by hand.
CODE_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,49}$')


class AdminProgrammeListView(_ProgrammeScopedBase):
    """GET the organisation's gift programmes · POST create one."""

    def get(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        rows = [_programme_row(p) for p in self._programmes_for(admin).order_by('code')]
        return Response({'programmes': rows})

    def post(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        org = admin.owning_organisation
        if org is None:
            return Response({'error': 'no_org', 'code': 'no_org'}, status=status.HTTP_400_BAD_REQUEST)

        from .models import Programme
        code = (request.data.get('code') or '').strip().lower()
        name_en = (request.data.get('name_en') or '').strip()
        if not CODE_RE.match(code):
            return Response({'error': 'bad_code', 'code': 'bad_code'}, status=status.HTTP_400_BAD_REQUEST)
        if not name_en:
            return Response({'error': 'name_required', 'code': 'name_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        # `Programme.code` is unique PLATFORM-WIDE, not per organisation, because it is what an
        # apply link carries (`/scholarship/apply?p=<code>`) — PF-1. So the clash a tenant hits may
        # be with another tenant's code, and the message must not say whose.
        if Programme.objects.filter(code=code).exists():
            return Response({'error': 'code_taken', 'code': 'code_taken'},
                            status=status.HTTP_400_BAD_REQUEST)

        # ⚠ CREATED INACTIVE, ALWAYS, whatever the client sends. An active second programme changes
        # live behaviour the moment it exists: the payment-run picker appears (Sabah S1) and the
        # configuration screen starts asking which programme. Switching it on is a separate,
        # deliberate press once its first intake year is set up.
        p = Programme.objects.create(
            organisation=org, code=code, name_en=name_en,
            name_ms=(request.data.get('name_ms') or '').strip(),
            name_ta=(request.data.get('name_ta') or '').strip(),
            is_active=False,
        )
        logger.info('AUDIT programme_created code=%s org=%s by=%s', p.code, org.id, admin.email or '')
        return Response(_programme_row(p), status=status.HTTP_201_CREATED)


class AdminProgrammeDetailView(_ProgrammeScopedBase):
    """PATCH one gift — its three names and whether it is active. The CODE is never editable."""

    def patch(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        p, err = self._programme_or_404(admin, pk)
        if err:
            return err

        changed = []
        for f in ('name_en', 'name_ms', 'name_ta'):
            if f in request.data:
                v = (request.data.get(f) or '').strip()
                if f == 'name_en' and not v:
                    return Response({'error': 'name_required', 'code': 'name_required'},
                                    status=status.HTTP_400_BAD_REQUEST)
                setattr(p, f, v); changed.append(f)

        if 'is_active' in request.data:
            want = bool(request.data.get('is_active'))
            # ⚠ SWITCHING OFF A GIFT THAT IS TAKING APPLICATIONS WOULD STRAND THEM MID-FLIGHT: the
            # apply link would stop resolving (`resolve_open_cohort` filters `programme__is_active`)
            # while a half-finished application still points at it. Close the year first.
            if not want:
                from .models import ScholarshipCohort
                if ScholarshipCohort.objects.filter(programme=p, is_open=True, is_active=True).exists():
                    return Response({'error': 'has_open_year', 'code': 'has_open_year'},
                                    status=status.HTTP_400_BAD_REQUEST)
            p.is_active = want; changed.append('is_active')

        if changed:
            p.save(update_fields=changed)
            logger.info('AUDIT programme_updated code=%s fields=%s by=%s',
                        p.code, ','.join(changed), admin.email or '')
        return Response(_programme_row(p))


def _requirements_from(data):
    """Read the tick boxes. A key that is ABSENT is left alone; a key that is present and null
    UNTICKS that requirement. Both matter: a PATCH sends only what changed, and clearing a value is
    how a test is switched off (S2a — the value IS the switch)."""
    out, bad = {}, None
    for f in REQUIREMENT_FIELDS:
        if f not in data:
            continue
        v = data.get(f)
        if v in (None, ''):
            out[f] = None
            continue
        try:
            out[f] = float(v) if f in ('min_stpm_pngk', 'min_merit_score') else int(v)
        except (TypeError, ValueError):
            bad = f
            break
        if out[f] < 0:
            bad = f
            break
    return out, bad


class AdminIntakeYearListView(_ProgrammeScopedBase):
    """GET one gift's intake years · POST open a new one."""

    def get(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        p, err = self._programme_or_404(admin, pk)
        if err:
            return err
        from .models import ScholarshipCohort
        years = ScholarshipCohort.objects.filter(programme=p).order_by('-year', 'code')
        return Response({
            'programme': {'id': p.id, 'code': p.code, 'name_en': p.name_en,
                          'is_active': p.is_active},
            'years': [_cohort_row(c) for c in years],
        })

    def post(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        p, err = self._programme_or_404(admin, pk)
        if err:
            return err

        from .models import ScholarshipCohort
        code = (request.data.get('code') or '').strip().lower()
        name = (request.data.get('name') or '').strip()
        year = request.data.get('year')
        if not CODE_RE.match(code):
            return Response({'error': 'bad_code', 'code': 'bad_code'}, status=status.HTTP_400_BAD_REQUEST)
        if not name:
            return Response({'error': 'name_required', 'code': 'name_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            year = int(year)
        except (TypeError, ValueError):
            return Response({'error': 'bad_year', 'code': 'bad_year'}, status=status.HTTP_400_BAD_REQUEST)
        if ScholarshipCohort.objects.filter(code=code).exists():
            return Response({'error': 'code_taken', 'code': 'code_taken'},
                            status=status.HTTP_400_BAD_REQUEST)

        reqs, bad = _requirements_from(request.data)
        if bad:
            return Response({'error': 'bad_requirement', 'code': 'bad_requirement', 'field': bad},
                            status=status.HTTP_400_BAD_REQUEST)

        # ⚠ BOTH THE PROGRAMME AND THE ORGANISATION ARE SET, and they must agree. The application
        # denormalises `owning_organisation` from its cohort, so a cohort carrying one and not the
        # other files students under the wrong fence (TD-177 is exactly this, in a test fixture).
        # It is DERIVED, never asked for.
        #
        # ⚠ CREATED CLOSED, ALWAYS. `is_open` defaults to True on the model, which would mean
        # creating a year opens applications in the same press. Opening is what lets real students
        # in; it gets its own deliberate action below.
        c = ScholarshipCohort.objects.create(
            programme=p, owning_organisation=p.organisation,
            code=code, name=name, year=year, is_active=True, is_open=False, **reqs,
        )
        logger.info('AUDIT intake_year_created cohort=%s programme=%s by=%s',
                    c.code, p.code, admin.email or '')
        return Response(_cohort_row(c), status=status.HTTP_201_CREATED)


class AdminIntakeYearDetailView(_ProgrammeScopedBase):
    """PATCH one intake year — its name, its requirements, and whether it is taking applications."""

    def _cohort_or_404(self, admin, pk):
        from .models import ScholarshipCohort
        c = (ScholarshipCohort.objects
             .select_related('programme', 'programme__organisation')
             .filter(pk=pk, programme__in=self._programmes_for(admin)).first())
        if c is None:
            return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        return c, None

    def patch(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        c, err = self._cohort_or_404(admin, pk)
        if err:
            return err

        changed = []
        if 'name' in request.data:
            name = (request.data.get('name') or '').strip()
            if not name:
                return Response({'error': 'name_required', 'code': 'name_required'},
                                status=status.HTTP_400_BAD_REQUEST)
            c.name = name; changed.append('name')

        reqs, bad = _requirements_from(request.data)
        if bad:
            return Response({'error': 'bad_requirement', 'code': 'bad_requirement', 'field': bad},
                            status=status.HTTP_400_BAD_REQUEST)
        # ⚠ CAPTURE THE OLD VALUE BEFORE WRITING. A threshold decides who is shortlisted, and
        # `shortlisting.evaluate()` reads these columns LIVE — unlike the documents and questions,
        # which are frozen per application at submit (`requirements_snapshot`). So a change here
        # moves the bar for everybody still to be judged, and "which fields changed" does not
        # answer the only question anybody will ask afterwards: FROM WHAT, TO WHAT.
        #
        # This is TD-203's lesson applied before it bites twice: `award_amount` had no audit line
        # either, and when three production rows had to be corrected on 2026-07-30 there was no
        # system record of who set them or to what — it came down to the owner's memory.
        moved = {f: (getattr(c, f), v) for f, v in reqs.items() if getattr(c, f) != v}
        for f, v in reqs.items():
            setattr(c, f, v); changed.append(f)

        if 'is_open' in request.data:
            want = bool(request.data.get('is_open'))
            if want:
                # ⚠ ONE OPEN ROUND PER ORGANISATION, REFUSED HERE RATHER THAN DISCOVERED LATER.
                # `services.resolve_open_cohort` RAISES when two rounds are open, because picking
                # one would file a student under the wrong fence (PF-1). That refusal protects the
                # student, but it arrives at the moment they press Apply. This one arrives at the
                # moment the admin creates the ambiguity, which is where it can still be undone.
                from .models import ScholarshipCohort
                clash = (ScholarshipCohort.objects
                         .filter(owning_organisation=c.programme.organisation,
                                 is_open=True, is_active=True)
                         .exclude(pk=c.pk).values_list('code', flat=True).first())
                if clash:
                    return Response({'error': 'another_year_open', 'code': 'another_year_open',
                                     'open_code': clash}, status=status.HTTP_400_BAD_REQUEST)
                if not c.programme.is_active:
                    return Response({'error': 'programme_not_active', 'code': 'programme_not_active'},
                                    status=status.HTTP_400_BAD_REQUEST)
            c.is_open = want; changed.append('is_open')

        if changed:
            c.save(update_fields=changed)
            logger.info('AUDIT intake_year_updated cohort=%s fields=%s by=%s',
                        c.code, ','.join(changed), admin.email or '')
            # A SECOND line, only when a threshold actually moved, carrying old -> new. Kept
            # separate from the line above rather than widening it: that one records that an
            # intake year was edited, this one records that the bar changed, and the two are read
            # by different people asking different questions.
            if moved:
                logger.info(
                    'AUDIT intake_year_requirements_set cohort=%s changes=%s by=%s',
                    c.code,
                    ';'.join('%s:%s->%s' % (f, old, new) for f, (old, new) in sorted(moved.items())),
                    admin.email or '')
        return Response(_cohort_row(c))
