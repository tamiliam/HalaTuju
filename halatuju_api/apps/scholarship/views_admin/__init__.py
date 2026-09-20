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
from django.db.models import ProtectedError
from django.db.models import Count, Exists, Max, OuterRef, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.pagination import FlexiblePageNumberPagination

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.courses.search import apply_people_search
# `from apps.courses.views_admin import PartnerAdminMixin` moved to `base.py` at H11 with
# `_AdminBase`, its only reader. Nothing here imports it now.

from .. import branding
from .. import money
from .. import pool
from .. import reopen as reopen_service
from .. import disbursement as disbursement_service
from .. import maintenance as maintenance_service
from .. import closure as closure_service
from ..anomaly_engine import detect_anomalies
from ..emails import send_request_info_email
from ..verdict_engine import build_verdict
from ..models import (
    ApplicantDocument, Disbursement, Donation, GraduationMessage, InterviewSession,
    InterviewSlot, OrgRequest, OrgRequestAttachment, Referee, ReviewerProfile,
    Programme, ScholarshipApplication, Sponsor, SponsorProfile, Sponsorship,
)
from .. import scheduling
from .. import sponsor_comms as sponsor_comms_mod
from .. import sponsor_terms as sponsor_terms_mod
from ..profile_engine import generate_anon_blurb, refine_sponsor_profile
from .. import in_programme as in_programme_service
from ..serializers import ApplicantDocumentSerializer, RefereeSerializer
from ..serializers_admin import (
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
from ..services import (
    AssignmentError, PauseError, admin_reject, application_completeness, assign_reviewer,
    cancel_pending_decline, org_admin_reject, review_writes_closed, set_paused,
    set_reporting_date_by_officer, submit_interview,
)
from .. import sponsorship as sponsorship_service
from ..sponsorship import hold_pending_award

# ── THE views_admin PACKAGE (code health H11, 2026-09-20) ────────────────────────
# Six domains moved out to the submodules below, verbatim. EVERY name they define is
# re-exported here, so `urls.py` is byte-identical and no importer changed — including
# the tests that reach for a private helper by name. `_AdminBase` lives in `base.py`:
# tenancy rule 3 puts the org scoping in the base gates, and every moved view still
# inherits it. The rest of this file is wave 2 (H12) and has not moved.
#
# ⚠ THE IMPORT BLOCK ABOVE WAS LEFT EXACTLY AS IT WAS, dead names and all. Nine of those
# names are now read only by a submodule, so nothing HERE uses them — but each is still an
# attribute of `apps.scholarship.views_admin`, which is what nineteen `patch(...)` strings
# and several lazy importers address. Deleting a name from this block is a change to the
# module's public surface, not tidying, so wave 2 removes them along with the code that
# needed them. (`Exists`, `OuterRef` and `OrgRequestAttachment` were dead BEFORE this move —
# TD-267.)
from .base import (
    _AdminBase, _MONTH_RE, _org_or_none,
)
from .contracts import (
    _CONTRACT_RULE_LABELS, _ContractsBase, _contract_clause_dict, _contract_schedule_dict,
    _contract_template_detail, _contract_template_summary, _contract_validation_dict,
    _contracts_err, AdminContractClausesView, AdminContractDeployView,
    AdminContractGenerateQuizView, AdminContractImportDocxView, AdminContractPreviewView,
    AdminContractQuizPreviewView, AdminContractRevertView, AdminContractScheduleView,
    AdminContractSubmitView, AdminContractTemplateDetailView, AdminContractTemplateListView,
    AdminContractValidateView, AdminContractVettingView,
)
from .gifts import (
    REQUIREMENT_FIELDS, _apply_copy_terms, _cohort_row, _programme_row, _window_from,
    programme_delete_blocker, programme_lifecycle, programme_student_queryset, round_state,
)
from .gift_programmes import (
    CODE_RE, _ProgrammeScopedBase, AdminApplyCopyDraftView, AdminProgrammeDetailView,
    AdminProgrammeListView,
)
from .intake_years import (
    _requirements_from, AdminIntakeYearDetailView, AdminIntakeYearFinishView,
    AdminIntakeYearListView,
)
from .invoices import (
    _InvoiceBase, _invoice_money, _invoice_payload, AdminInvoiceActionView, AdminInvoicePdfView,
    AdminInvoiceSettingsView, AdminInvoicesView, AdminOrgBuildHoursView,
)
from .payments import (
    _PAYMENTS_READ_ROLES, _PAYMENTS_WRITE_ROLES, _PaymentsBase, _payment_item_dict,
    _payment_run_detail, _payment_run_summary, _run_programme, _sig,
    AdminPaymentFundingSummaryView, AdminPaymentRunCancelView, AdminPaymentRunCsvView,
    AdminPaymentRunDetailView, AdminPaymentRunItemView, AdminPaymentRunListView,
    AdminPaymentRunSignView,
)
from .requests import (
    _OrgRequestsBase, _org_request_err, AdminOrgRequestAnswerView, AdminOrgRequestApproveView,
    AdminOrgRequestAskView, AdminOrgRequestCommentView, AdminOrgRequestCountView,
    AdminOrgRequestDeclineView, AdminOrgRequestDeferView, AdminOrgRequestDetailView,
    AdminOrgRequestListView, AdminOrgRequestModifyView,
)
from .requests_delivery import (
    AdminOrgRequestAiRerunView, AdminOrgRequestAnalysisApproveView, AdminOrgRequestAnalysisView,
    AdminOrgRequestAttachmentCreateView, AdminOrgRequestAttachmentDeleteView,
    AdminOrgRequestAttachmentSignUploadView, AdminOrgRequestDoneView, AdminOrgRequestQuoteView,
    AdminOrgRequestRequoteView, AdminOrgRequestScheduleView, AdminOrgRequestTriageView,
    AdminOrgRequestWithdrawAnalysisView,
)
from .sponsor_terms import (
    _SponsorTermsBase, _terms_detail_dict, _terms_err, _terms_section_dict, _terms_summary_dict,
    _terms_validation_dict, AdminSponsorTermsDetailView, AdminSponsorTermsGenerateQuizView,
    AdminSponsorTermsImportDocxView, AdminSponsorTermsListView, AdminSponsorTermsPreviewView,
    AdminSponsorTermsPublishView, AdminSponsorTermsSectionsView, AdminSponsorTermsValidateView,
)

logger = logging.getLogger(__name__)

# '' = an in-progress finding: the reviewer typed a one-line "what you found" but
# hasn't classified it (resolved/still_unclear/new_concern). The cockpit produces this
# for any gap whose verdict button wasn't clicked — rejecting it 400'd the whole
# Save-draft and lost the reviewer's notes. A draft finding may carry just a rationale.
_VALID_VERDICTS = {'', 'resolved', 'still_unclear', 'new_concern', 'deleted'}
_RATIONALE_MAX = 140


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
        from ..reextract import reextract_document
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
        from ..services import generate_ready_profile
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
        from ..gap_engine import generate_interview_gaps
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
    from ..submission_review import completeness_gaps as _submission_gaps
    from ..verdict_engine import build_verdict
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
        'given': sponsorship_service._amount_str(getattr(s, 'given_total', None)),
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
        from .. import sponsor_notify
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
    from .. import payments as payments_service

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
        # Every gift this ADMIN may accept the benefactor into — the choices behind the accept /
        # move panel. Deliberately NOT derived from `memberships` (which lists gifts they are
        # ALREADY in): the whole point of the panel is the gift they are not in yet.
        #
        # ⚠ `_programmes_for` INCLUDES INACTIVE gifts, and that is the case this exists for. A
        # second gift is created switched OFF and staffed before it opens, so a list of active
        # gifts would offer nothing at exactly the moment somebody needs to accept its first
        # benefactor — the defect the owner hit on their own first use of THE SHAPE.
        'assignable_programmes': [
            {'id': p.id, 'code': p.code, 'name': p.name_en or p.code,
             'is_active': p.is_active}
            for p in AdminProgrammeListView()._programmes_for(admin).order_by('code')
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
        from .. import award as award_rule
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
        # WHICH GIFT'S apply form lists this source (S-ASSIGN, 2026-09-04). NULL = every gift,
        # which is what all seven live referral organisations have and what needs no backfill.
        #
        # ⚠ IT NARROWS `show_in_apply`, and `show_in_apply` DOES NOT YET REACH THE STUDENT FORM.
        # The apply form's referring-organisation list is still the hard-coded
        # `REFERRING_ORG_OPTIONS` constant in `lib/scholarship.ts`; nothing reads this flag on
        # the student side yet. So setting a gift here records the organisation's intent and
        # changes NOTHING a visitor sees — do not read a value in this column as proof that the
        # form is narrowed. Wiring the form to the registry is its own change, and it is what
        # makes this field bite.
        #
        # ⚠ NOT ACCESS CONTROL. A referral organisation is an ATTRIBUTION relationship, never a
        # scope — the same warning `PartnerAdmin.org` and `referred_by_org` carry.
        'programme_id': org.programme_id,
        'programme_name': (org.programme.name_en or org.programme.code)
                          if org.programme_id else '',
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
    from .. import partner_comms
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
        orgs = PartnerOrganisation.objects.select_related('programme').order_by('name')
        return Response({
            'sources': [_source_dict(o, counts.get(o.id, 0)) for o in orgs],
            # The gift choices behind the per-source picker. ACTIVE only: this narrows which
            # apply form lists the source, and a form that is not open lists nothing.
            'programmes': [
                {'id': p.id, 'code': p.code, 'name': p.name_en or p.code}
                for p in AdminProgrammeListView()._programmes_for(admin)
                                                 .filter(is_active=True).order_by('code')
            ],
        })

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
        if 'programme_id' in request.data:
            # Blank/null CLEARS it, and clearing means EVERY gift — the permissive default all
            # seven live sources carry. A gift outside the caller's organisation is refused, so
            # a tenant cannot list a source on somebody else's form.
            asked = request.data.get('programme_id')
            if asked in (None, ''):
                org.programme = None
            else:
                programme = AdminProgrammeListView()._programmes_for(admin).filter(
                    pk=asked).first()
                if programme is None:
                    return Response({'error': 'not_found', 'code': 'not_found'},
                                    status=status.HTTP_404_NOT_FOUND)
                org.programme = programme
            fields.append('programme')
        if 'is_active' in request.data:
            org.is_active = bool(request.data.get('is_active'))
            fields.append('is_active')
        if fields:
            org.save(update_fields=fields)
        return Response(_source_dict(org, _source_application_counts().get(org.id, 0)))


def _partner_email_dict(tpl, last=None):
    """One partner-email template as the admin screen sees it: the wording, its switch, the
    placeholders it may use, and when it last went out."""
    from .. import partner_comms
    from ..models import PartnerEmailTemplate
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
        from .. import partner_comms
        from ..models import PartnerEmailLog, PartnerEmailTemplate

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
        from .. import partner_comms
        from ..models import PartnerEmailTemplate

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
        from ..models import SponsorEmailLog, SponsorEmailTemplate

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
        from ..models import SponsorEmailTemplate

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
            from .. import partner_notify
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
            from .. import partner_notify
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
                  .select_related('reviewer_profile', 'programme').order_by('name'))
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
        #
        # ⚠ A reviewer's GIFT travels the same way, and for the same reason (S-ASSIGN,
        # 2026-09-04). `programme_id` NULL means EVERY gift — the owner's ruling and the
        # permissive default every one of the 17 org-scoped staff on production still has — so a
        # client that ignores this field behaves exactly as before. It is a NARROWING of who is
        # offered work, never a fence: the org fence is `_org_scoped`, and a reviewer somehow
        # handed another gift's case still passes it. The screen greys the row and says which
        # gift they cover rather than hiding the name.
        return Response({'admins': [
            {'id': a.id, 'name': a.name, 'email': a.email,
             'role': 'super' if a.is_super else a.role, 'languages': langs(a),
             'paused': a.paused_at is not None,
             'programme_id': a.programme_id,
             'programme_name': (a.programme.name_en or a.programme.code) if a.programme_id else '',
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


def _reviewer_workloads(admins, *, organisation_id=None, programme=None, cohort=None):
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

    ⚠ **`programme` NARROWS ALONGSIDE THE ORGANISATION FILTER, NEVER INSTEAD OF IT** (2026-09-15,
    for the Programme Overview's `mine.pace`). The organisation stays the SECURITY fence and the
    gift is a restriction inside it; the Reviewers surface passes no gift and is byte-unchanged.
    The pair below is the Applications list's own (`views_admin.py:380`) so a reviewer's pace on
    a gift counts exactly the cases that gift's list shows — `ScholarshipApplication.programme` is
    set once at first save, so a cohort later moved between gifts would otherwise read as empty.
    """
    ids = [a.id for a in admins]
    if not ids:
        return {}
    rows = ScholarshipApplication.objects.filter(assigned_to_id__in=ids)
    if organisation_id is not None:
        # org-fence: the caller is a non-super, so only their own tenant's applications count.
        rows = rows.filter(owning_organisation_id=organisation_id)
    if programme is not None:
        rows = rows.filter(Q(programme=programme) | Q(cohort__programme=programme))
    if cohort is not None:
        # The intake round inside the gift (Overview phase 2) — narrows, never widens; the
        # Reviewers surface passes none and is byte-unchanged.
        rows = rows.filter(cohort=cohort)
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
        # ⚠ REVOKED IS NOT PAUSED, AND THE TABLE HAS TO SAY WHICH (2026-09-09). Paused means
        # stepped back from NEW work and still able to sign in; revoked means the account is
        # closed. The staff list served `is_active` and this one did not, so the two screens
        # showing the same people could disagree — the same drift that made one say Active while
        # the other said Paused until 2026-08-03.
        'is_active': admin.is_active,
        # ⚠ NULL IS "NOT RECORDED", NEVER "never signed in" — the backfill is best-effort and
        # everybody predating the column is empty. 20 of 21 staff carry a value on production; the
        # screen must say "not recorded" rather than accuse somebody of never turning up.
        'last_seen_at': admin.last_seen_at,
        # ⚠ THE GIFT COLUMN IS BACK, AND ITS OWN TRIGGER IS WHY (S-ASSIGN, 2026-09-04). This
        # used to be an explicit ABSENCE: "with one programme every reviewer serves it, so the
        # column could only ever say one thing… it returns when a second programme exists". The
        # owner created a second gift on 2026-09-03, so the condition that ruling named has
        # fired. The old note is rewritten rather than deleted so the reasoning survives.
        #
        # ⚠ NULL MEANS EVERY GIFT and is the permissive default — every one of the 17 org-scoped
        # staff on production still has it, and there is NO BACKFILL. A blank here is "as
        # before", never a missing value; the screen must not render it as one.
        'programme_id': admin.programme_id,
        'programme_name': (admin.programme.name_en or admin.programme.code)
                          if admin.programme_id else '',
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

    def _reviewers(self, org_id, include_revoked=False):
        """The organisation's reviewers. ACTIONABLE ones by default; the LIST and the DETAIL page
        pass ``include_revoked`` and get the closed accounts too.

        ⚠ **THE SPLIT IS NEW (2026-09-09) AND REVERSES A NARROWER RULING ON PURPOSE.** Until now a
        revoked reviewer was absent everywhere — *"revoking is an account kill-switch; they cannot
        act, so they are not staff to look at"*. That held while revoking happened on another
        screen. The owner has now asked for Revoke on this table, and a kill-switch you cannot see
        or undo from the only screen that lists people is a trap: revoke somebody and they vanish,
        with no way back. So they stay LISTED, marked revoked, with Restore beside them.
        **What did NOT change is what they may do:** pause and set-gift still take the default and
        404 on a revoked account, and assignment reads its own `is_active=True` queryset
        (`AdminAssignableView`), so a revoked reviewer can still never be handed a case.
        """
        from django.db.models import Q
        # org-fence: narrowed by owning_organisation for a non-super (org_id set by `_side`).
        qs = (PartnerAdmin.objects
              .filter(Q(is_super_admin=True) | Q(role__in=['reviewer', 'qc']))
              .select_related('reviewer_profile', 'programme').order_by('name'))
        if not include_revoked:
            qs = qs.filter(is_active=True)
        if org_id is not None:
            qs = qs.filter(owning_organisation_id=org_id, is_super_admin=False)
        return qs

    def _gift_choices(self, admin):
        """The gifts this admin may scope a reviewer to.

        INCLUDES inactive gifts, for the same reason the sponsor accept panel does: a gift is
        created switched off and STAFFED before it opens, so an active-only list would offer
        nothing at exactly the moment somebody needs to put a reviewer on the new gift.
        """
        return [
            {'id': p.id, 'code': p.code, 'name': p.name_en or p.code, 'is_active': p.is_active}
            for p in AdminProgrammeListView()._programmes_for(admin).order_by('code')
        ]


class AdminReviewerListView(_ReviewersBase):
    """GET admin/reviewers/ — the people who review this organisation's applications.

    Request #10. Staff (`/admin/organisation/staff`) invites and revokes; this is where you look at
    somebody: what they carry, how long cases sit with them, and how their cases ended.
    """

    def get(self, request):
        admin, org_id, err = self._side(request)
        if err:
            return err
        rows = list(self._reviewers(org_id, include_revoked=True))
        work = _reviewer_workloads(rows, organisation_id=org_id)
        return Response({
            'reviewers': [_reviewer_dict(r, work[r.id]) for r in rows],
            # The gift choices behind the per-reviewer picker. Sent with the LIST so the screen
            # can offer the change wherever a reviewer is shown, without a second round trip.
            'programmes': self._gift_choices(admin),
        })


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
        # ⚠ `include_revoked`: a closed account's record must still OPEN, or Restore on the list
        # would send somebody to a 404 (2026-09-09).
        target = self._reviewers(org_id, include_revoked=True).filter(pk=pk).first()
        if target is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        work = _reviewer_workloads([target], organisation_id=org_id)[target.id]
        rp = getattr(target, 'reviewer_profile', None)
        from .. import reopen as reopen_service
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
            'programmes': self._gift_choices(admin),
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
        # ⚠ NO `include_revoked` HERE, deliberately: pausing a closed account is meaningless, so a
        # revoked target 404s exactly as it did before.
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


class AdminReviewerProgrammeView(_ReviewersBase):
    """POST admin/reviewers/<pk>/programme/ {programme_id} — which gift this person covers.

    ⚠ **A NARROWING, NOT A FENCE, AND IT MUST NEVER BECOME ONE.** The organisation boundary is
    `_org_scoped`/`_org_allows`; this only decides who is OFFERED a case. A reviewer scoped to
    Sabah who is somehow handed a flagship case still passes the fence and can still work it —
    deliberately, because the alternative is stranding an in-flight review the day somebody
    tidies a dropdown.

    ⚠ **`programme_id` NULL / absent CLEARS IT, and clearing means EVERY GIFT** — the permissive
    default and what all 17 org-scoped staff on production have. So this endpoint can only ever
    narrow or widen the offer; it can never lock somebody out of work they already hold.

    ⚠ **NARROWER THAN READING THIS SURFACE**, exactly like `AdminReviewerPauseView`: `admin` and
    `finance` may look at the reviewers list, but deciding who gets which work is staff
    management, which the role matrix gives to super + org_admin. The list gate would admit all
    four, so this re-gates rather than inheriting.

    The gift is resolved through `_programmes_for`, so a gift outside the caller's organisation
    is **404, never 403** — a 403 would confirm the other tenant's gift exists.
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

        asked = request.data.get('programme_id')
        programme = None
        if asked not in (None, ''):
            programme = AdminProgrammeListView()._programmes_for(admin).filter(pk=asked).first()
            if programme is None:
                return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        old = target.programme.code if target.programme_id else ''
        target.programme = programme
        target.save(update_fields=['programme'])
        logger.info('AUDIT reviewer_programme_set admin=%s old=%s new=%s by=%s',
                    target.id, old or '(every gift)',
                    (programme.code if programme else '(every gift)'), admin.email or '')
        return Response({
            'id': target.id,
            'programme_id': target.programme_id,
            'programme_name': (programme.name_en or programme.code) if programme else '',
        })


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
        from .. import reviewer_system_emails
        return Response({'emails': reviewer_system_emails.rendered()})


class AdminInvitationsView(_ReviewersBase):
    """GET admin/invitations/[?kind=][&all=1] — who has been asked and **has not answered yet**.

    The Invitations page (owner's shape, 2026-08-03) is organised into FOUR kinds — admins,
    reviewers, source, sponsors — with one table on screen at a time, so this serves one kind plus
    the waiting counts for all four (the badge on each button; without it an invitation waiting
    under an unselected kind is invisible, which is what the page exists to prevent).

    ⚠ **IT LISTS THE WAITING ONES ONLY (2026-09-09).** `invitations.open_only` is the single
    definition of waiting, shared with `waiting_counts`, so the table and its own badge can never
    disagree. Everybody who has already accepted belongs to the People directory, not here.
    `?all=1` returns the full history for a caller that genuinely wants it; nothing in the console
    passes it today.

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
        from .. import invitations as inv_service
        from ..models import Invitation

        # org-fence: an invitation belongs to the organisation that sent it. A super sees all.
        qs = Invitation.objects.select_related('partner_admin', 'invited_by', 'programme').all()
        if org_id is not None:
            qs = qs.filter(organisation_id=org_id)

        counts = inv_service.waiting_counts(qs)
        totals = inv_service.kind_totals(qs)
        kind = (request.GET.get('kind') or inv_service.KIND_ADMINS).strip()
        if kind not in inv_service.KINDS:
            kind = inv_service.KIND_ADMINS

        # ⚠ WAITING-ONLY IS THE DEFAULT, AND THAT IS THE POINT OF THIS PAGE (2026-09-09).
        # It used to list every invitation ever sent, which on this tenant meant 18 accepted rows
        # and 2 waiting ones — a page named "Invitations" that was really a staff roster, and one
        # that would have got WORSE on its own as each waiting sponsor registered. Who is already
        # in is answered by the People directory; this endpoint answers who has not replied.
        # `?all=1` keeps the full history reachable for a caller that genuinely wants it.
        listed = inv_service.for_kind(qs, kind)
        if (request.GET.get('all') or '').strip() not in ('1', 'true'):
            listed = inv_service.open_only(listed)

        rows = []
        for i in listed.order_by('-created_at'):
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
                # Which gift this invitation was for (S-ASSIGN). NULL means EVERY gift — the
                # honest reading for every row written before the column existed, and for a
                # staff invitation, which carries none. Never render a blank as a gift name.
                'programme': i.programme.code if i.programme_id else '',
                'programme_name': (i.programme.name_en or i.programme.code)
                                  if i.programme_id else '',
            })

        return Response({
            'kind': kind,
            'invitations': rows,
            'waiting': counts,
            # Every invitation ever sent, per kind. The page needs it to tell an empty table
            # apart: nobody asked yet, or everybody asked has arrived. See `kind_totals`.
            'totals': totals,
            # What this caller may actually grant here. The FE renders the sub-selection from it
            # rather than keeping its own copy, so the two cannot drift.
            'invitable_roles': list(inv_service.KIND_INVITABLE_ROLES.get(kind, ())),
            # The gift choices for the sponsor invite form. ACTIVE only, matching exactly what
            # the POST accepts — an invitation is a prompt to register TODAY, so offering a gift
            # that is not open yet would invite somebody into a door that does not open. (The
            # accept panel on the sponsor detail page is the opposite case and takes inactive
            # ones, because a gift is staffed before it is switched on.)
            'programmes': [
                {'id': p.id, 'code': p.code, 'name': p.name_en or p.code}
                for p in AdminProgrammeListView()._programmes_for(admin)
                                                 .filter(is_active=True).order_by('code')
            ],
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

        from .. import invitations as inv_service
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

        from ..emails import send_sponsor_invitation_email
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
        from ..services import officer_queries_allowed
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
        from ..resolution import add_officer_item
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
        from ..models import ResolutionItem
        item = ResolutionItem.objects.filter(pk=item_id).select_related('application').first()
        if item is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # Assignment-based write: super, or the admin/reviewer assigned to the item's application.
        if not self._can_review_app(admin, item.application):
            return self._deny_role()
        from ..services import querying_locked
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
        _org = app.owning_organisation
        if any(s and not scheduling.meets_min_lead(s, _tz.now(), _org) for s in starts):
            return Response({'error': 'too_soon', 'code': 'too_soon'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Enforce the interview-slot rule (MYT, on the organisation's step, inside its booking
        # window) at the input boundary — the UI only offers valid chips, but reject anything
        # else too. Both checks read the SAME organisation the picker was served from.
        if any(s and not scheduling.slot_in_window(s, _org) for s in starts):
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
        from ..models import BursaryAgreement
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
        from .. import bursary
        from ..serializers import BursaryAgreementSerializer
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
        from .. import bursary
        from ..serializers import BursaryAgreementSerializer
        bursary.record_witness(
            agreement, org=org,
            by_name=getattr(admin, 'name', '') or '',
            witness_name=request.data.get('witness_name', '') or '')
        return Response(BursaryAgreementSerializer(agreement).data)


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

        from .. import usage
        if is_super:
            # super: every organisation + the platform (NULL-org) reconciliation row.
            payload = usage.monthly_usage(month, include_platform=True)
        else:
            # org_admin: its OWN organisation only — fenced by construction (no platform,
            # no other org can appear). A misconfigured org_admin with no org sees nothing.
            payload = usage.monthly_usage(month, restrict_org_id=admin.owning_organisation_id)

        # ⚠ **THE JOB → MODEL LIST IS SUPER-ONLY, and that is the same call as the platform row
        # above.** Which AI version a job is set to is a PLATFORM fact: every organisation runs
        # the same models, and a tenant cannot change one (owner, 2026-09-11 — see
        # `docs/decisions.md`). Showing a tenant a list they can only look at would be furniture.
        # What a tenant DOES get is the per-model split of their own usage, which is theirs.
        #
        # Read-only, and cheap: a few `getattr`s over Django settings plus three lazy imports.
        # It RESOLVES rather than remembers, so it cannot disagree with the engine.
        if is_super:
            from halatuju import ai_registry
            payload['ai_jobs'] = ai_registry.snapshot()
            payload['ai_models_in_use'] = ai_registry.models_in_use()
        return Response(payload)


class AdminPlatformCostsView(_AdminBase):
    """SUPER-ONLY: what the platform PAID this month, and what each tenant is charged.

    The gap the owner found on 2026-09-11: the ledger, the BigQuery sync, the reconciliation
    maths and the rates endpoint were all built in July 2026 and then starved. Nothing fed the
    ledger after June and **no endpoint ever read it**, so real invoices — GCP, Supabase,
    Workspace, Twilio — reached no screen at all.

    **Super-only, 403 not 404**, matching `AdminBillingRatesView`: what the platform pays and
    what margin sits on top is a commercial disclosure, but there is nothing to hide about the
    route existing. Unlike the usage screen there is no dark-ship flag — this never had one.

    ⚠ The payload carries `month_totals`' truthfulness flags verbatim — `entered_sources`,
    `is_complete`, `period_caveats` — and the screen renders them. **A total that mixes measured
    and hand-typed figures without saying so is not an audit** (the module's own words). That is
    the reason this calls `reconcile()` rather than re-summing rows in the view: a second summing
    would be a second place for those flags to be forgotten.
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()

        month = (request.query_params.get('month') or '').strip()
        if month and not _MONTH_RE.match(month):
            return Response({'error': 'bad_month', 'code': 'bad_month'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not month:
            # TD-209: localtime, never `timezone.now()`. See AdminBillingUsageView's note —
            # the same eight-hour window would open this page on the wrong month.
            month = timezone.localtime().strftime('%Y-%m')

        from apps.courses.models import PartnerOrganisation

        from .. import platform_cost
        from ..models import PlatformCost

        costs = platform_cost.reconcile(month)

        def _money(v):
            # ⚠ `None` SURVIVES, and nothing is quantised. This payload distinguishes "no figure
            # entered for that source yet" from "the figure is zero", and the only job here is to
            # stop DRF rendering a bare `Decimal` inside a nested dict as a float.
            return money.format_money(v, blank=None, blank_when=money.BLANK_NONE,
                                      quantize=False, coerce=False)

        payload = {
            'month': month,
            # Every month the ledger holds anything for, newest first — the picker's options.
            # Read from the LEDGER, not generated from a range: a month with no rows is a month
            # nobody has entered yet, and offering it would look like "we paid nothing".
            'months': list(PlatformCost.objects.order_by('-period_month')
                           .values_list('period_month', flat=True).distinct()),
            'costs': {
                'lines': costs['lines'],
                'total_myr': _money(costs['total_myr']),
                'attributable_myr': _money(costs['attributable_myr']),
                'platform_myr': _money(costs['platform_myr']),
                'development_myr': _money(costs['development_myr']),
                'tax_myr': _money(costs['tax_myr']),
                'by_source': {k: _money(v) for k, v in costs['by_source'].items()},
                'entered_sources': costs['entered_sources'],
                'extracted_sources': costs['extracted_sources'],
                'is_complete': costs['is_complete'],
                'unconverted': [{**u, 'amount_original': _money(u['amount_original'])}
                                for u in costs['unconverted']],
                'period_caveats': costs['period_caveats'],
                'metered_events': costs['metered_events'],
                'metered_org_null': costs['metered_org_null'],
                'metered_org_null_pct': costs['metered_org_null_pct'],
            },
            'charges': [],
            # ⚠ NOT filtered to the month being viewed. Outstanding work is outstanding whatever
            # month you happen to be looking at, and each row carries the month IT belongs to —
            # `worked_month` — so the reader sees everything unbilled and records each against
            # the month we actually worked.
            'unbilled_requests': [{**u,
                                   'hours': _money(u['hours']),
                                   'worked_on': u['worked_on'].isoformat()}
                                  for u in platform_cost.unbilled_request_hours()],
        }

        # ⚠ `.tenants()`, never `.filter(is_active=True)`. This table is dual-role: ten rows on
        # production, exactly one of them a tenant. The plain queryset would put a bill against
        # nine schools and NGOs that have never been customers.
        for org in PartnerOrganisation.objects.tenants().order_by('name'):
            c = platform_cost.charge_for(org, month)
            payload['charges'].append({
                'organisation_id': org.id,
                'organisation': org.name,
                'lines': [{**ln,
                           'hours': _money(ln.get('hours')),
                           'rate_myr': _money(ln.get('rate_myr')),
                           'margin_pct': _money(ln.get('margin_pct')),
                           'cost_myr': _money(ln.get('cost_myr')),
                           'tool_cost_myr': _money(ln.get('tool_cost_myr')),
                           'share_pct': _money(ln.get('share_pct')),
                           'amount_myr': _money(ln.get('amount_myr')),
                           'billed_rate_myr': _money(ln.get('billed_rate_myr')),
                           # ⚠ `amount_myr` is money inside a nested dict — DRF renders a bare
                           # Decimal there as a FLOAT (the sponsor-card lesson), so it is
                           # stringified here like every other figure on this payload.
                           'detail': [{**d, 'hours': _money(d['hours']),
                                       'amount_myr': _money(d.get('amount_myr'))}
                                      for d in ln.get('detail', [])]}
                          for ln in c['lines']],
                'subtotal_myr': _money(c['subtotal_myr']),
                'discount_pct': _money(c['discount_pct']),
                'discount_myr': _money(c['discount_myr']),
                'discount_reason': c['discount_reason'],
                'discount_set_by': c['discount_set_by'],
                'charged_myr': _money(c['charged_myr']),
                'blocked': c['blocked'],
            })
        return Response(payload)

    def post(self, request):
        """Record a discount for one organisation and one month.

        The owner's July instruction — *"we do not bill anything for July. 100% discount. But
        show the values."* A row here is what makes that a decision rather than a gap.

        `reason` is REQUIRED and refused when blank, exactly as `OrgBuildHours.basis` is: a
        waived month with no stated reason is indistinguishable from a bug, and this endpoint
        is the only place that can insist.
        """
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()

        from decimal import Decimal, InvalidOperation

        from ..models import OrgBillingAdjustment

        month = (request.data.get('period_month') or '').strip()
        if not _MONTH_RE.match(month):
            return Response({'error': 'bad_month', 'code': 'bad_month'},
                            status=status.HTTP_400_BAD_REQUEST)
        org = _org_or_none(request.data.get('organisation_id'))
        if org is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            pct = Decimal(str(request.data.get('discount_pct')))
        except (InvalidOperation, TypeError):
            return Response({'error': 'bad_value', 'code': 'bad_value'},
                            status=status.HTTP_400_BAD_REQUEST)
        if pct < 0 or pct > 100:
            return Response({'error': 'bad_value', 'code': 'bad_value'},
                            status=status.HTTP_400_BAD_REQUEST)
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'error': 'reason_required', 'code': 'reason_required'},
                            status=status.HTTP_400_BAD_REQUEST)

        row, _created = OrgBillingAdjustment.objects.update_or_create(
            organisation=org, period_month=month,
            defaults={'discount_pct': pct, 'reason': reason,
                      'set_by_email': (admin.email or '')})
        return Response({'id': row.id, 'organisation_id': org.id,
                         'period_month': row.period_month,
                         'discount_pct': str(row.discount_pct),
                         'reason': row.reason},
                        status=status.HTTP_201_CREATED)


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

        from ..models import BillingRate
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

        from ..models import BillingRate

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
        from .. import sponsorship as sponsorship_service
        from ..models import Programme
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
        from .. import sponsorship as sponsorship_service
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
        from .. import sponsorship as sponsorship_service
        try:
            sponsorship_service.cancel_admin_credit(credit, admin)
        except sponsorship_service.CreditError as e:
            return Response({'error': e.code, 'code': e.code},
                            status=status.HTTP_400_BAD_REQUEST)
        credit.refresh_from_db()
        return Response(_credit_dict(credit))


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


class AdminOrganisationConfigurationView(_AdminBase):
    """GET/PUT `admin/scholarship/organisation/configuration/` — the values an organisation tunes.

    Org Config Sprint A (2026-09-07). The second tab of Organisation → Settings, beside Colours.
    The tab shows a small registry of organisation-wide values (`courses.org_config.SETTINGS`);
    a blank field means "follow the platform default", and the stored row holds ONLY what the
    organisation changed. First (and so far only) setting: `pool_funded_grace_days` — how long a
    just-funded student's card stays on the sponsor browse page.

    ⚠ A SETTING APPEARS HERE ONLY WHEN CODE READS IT. The registry is the catalogue; the read
    sites are the feature. Adding a row without its consumer is the "UI asserts what nothing
    checks" defect — see `org_config`'s module docstring.

    ⚠ THE ORGANISATION IS DERIVED, NEVER SENT — same fence, same 404-not-403, same refusal to
    pick silently between two, mirroring `AdminOrganisationThemeView._organisation_for` next
    door. (Deliberately NOT a subclass of the theme view: inheriting would drag its GET/PUT/
    DELETE verbs onto this route, and a stray DELETE here must not discard a colour draft.)

    Who may write: `super` and `org_admin` only — these values change what every sponsor of the
    organisation sees, so they are the organisation's decision, held by its administrator.

    PUT is ALL-OR-NOTHING: everything validates before anything is stored, and each changed key
    writes an `AUDIT org_config_set` line carrying old → new ('default' = no stored value).
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
        """Mirrors `AdminOrganisationThemeView._organisation_for` — see its docstring."""
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
        from apps.courses import org_config
        rows = []
        for key, spec in org_config.SETTINGS.items():
            rows.append({
                'key': key,
                'group': spec['group'],
                'unit': spec['unit'],
                'min': spec['min'],
                'max': spec['max'],
                # None = "following the platform default" — the screen renders a blank box with
                # the default beside it, never the default AS the value (a copied default rots).
                'value': org_config.stored(org, key),
                'default': org_config.default(key),
                # Present only for a setting whose vocabulary is a short list rather than a
                # range (the slot step) — the tab renders a menu instead of a box.
                'allowed': list(spec['allowed']) if spec.get('allowed') else None,
            })
        return {
            'organisation': {'code': org.code, 'name': org.name},
            'settings': rows,
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
        from apps.courses import org_config
        from apps.courses.models import OrganisationConfiguration

        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err

        changes = request.data.get('values')
        if not isinstance(changes, dict):
            return Response({'error': 'bad_values', 'code': 'bad_values'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Validate EVERYTHING before writing ANYTHING (the programme-config rule): a half-applied
        # save is worse than a refused one. `None` means "clear back to the platform default" and
        # is valid for any known key; everything else goes through the registry's own fence.
        to_set = {k: v for k, v in changes.items() if v is not None}
        to_clear = [k for k, v in changes.items() if v is None]
        # The RESULT of the save, not the diff — a cross-field rule (Sprint D: the interview
        # window must open before it closes) is a statement about the two values that will be
        # STORED TOGETHER, and one of them may be arriving while the other is already on file
        # or is following the platform default. Validating the diff alone would let an inverted
        # window reach `row.save()`, where the model's own fence raises with the audit lines
        # already written — a 500 for what is an ordinary typo.
        # ⚠ Read the stored values by QUERY, never through `org.configuration`. Touching the
        # reverse OneToOne caches the row on this `org` instance, and `_payload` below would
        # then answer the save with the values as they were BEFORE it — a save that looks
        # ignored until the page is reloaded.
        existing = dict(OrganisationConfiguration.objects
                        .filter(organisation=org)
                        .values_list('values', flat=True).first() or {})
        merged = {k: v for k, v in existing.items() if k not in to_clear}
        merged.update(to_set)
        try:
            for key in to_clear:
                if key not in org_config.SETTINGS:
                    raise org_config.OrgConfigError('unknown_setting', key)
            # Per-key first, so the refusal names the key the person actually typed.
            org_config.validate_values(to_set, pairs=False)
            org_config.validate_values(merged)
        except org_config.OrgConfigError as exc:
            code = exc.code
            http = status.HTTP_404_NOT_FOUND if code == 'unknown_setting' else status.HTTP_400_BAD_REQUEST
            return Response({'error': code, 'code': code, 'key': exc.key}, status=http)

        row, _created = OrganisationConfiguration.objects.get_or_create(organisation=org)
        values = dict(row.values or {})
        for key in to_clear:
            was = values.pop(key, None)
            if was is not None:
                logger.info('AUDIT org_config_set org=%s key=%s was=%s now=default by=%s',
                            org.code, key, was, admin.email or '')
        for key, new in to_set.items():
            was = values.get(key)
            if was == new:
                continue
            values[key] = new
            logger.info('AUDIT org_config_set org=%s key=%s was=%s now=%s by=%s',
                        org.code, key, 'default' if was is None else was, new,
                        admin.email or '')
        row.values = values
        row.updated_by_email = admin.email or ''
        row.save()
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
        from .. import requirements
        from ..models import ApplicationItem
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

        from ..models import ITEM_STATE_CHOICES, ApplicationItem, ProgrammeApplicationItem
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

        from .. import requirements
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


# ── the officer's spending screen (sponsor spending S4) ──────────────────────
#
# ⚠ READ AND WRITE ARE BOTH admin / org_admin, AND `finance` IS DELIBERATELY ABSENT.
# `_b40_scope` states that a finance admin never sees an applicant file, document, income
# figure or verdict, and that its ONLY student data is the Payments funding summary allowlist.
# This screen carries student names beside what they bought, which is welfare oversight rather
# than disbursement — adding finance here would quietly widen a boundary another docstring
# promises is closed.
_SPENDING_ROLES = ('admin', 'org_admin')


class _SpendingBase(_AdminBase):
    """Shared gate for the spending endpoints: an active admin, the right role, and the SCOPE to
    read within.

    ⚠ The scope is returned rather than looked up again downstream, so there is exactly ONE place
    the fence can be forgotten. **This method is the only door to the platform-wide scope in the
    whole feature** — `spend_report.ALL_ORGS` appears nowhere else outside its own module.

    ⚠⚠ **A SUPER GETS `ALL_ORGS`; EVERYONE ELSE GETS THEIR OWN ORGANISATION OR NOTHING.** Until
    2026-09-11 a super was refused `no_org`, on the reasoning that "defaulting to unfenced is how a
    super with no org context sees the platform" — which is true of a DEFAULT and not of an
    explicit scope. The owner opened their own console as super, was refused, and asked for the
    platform view (`docs/decisions.md`, 2026-09-11, superseding the S4a ruling). It is spelled as
    a sentinel object precisely so that it can only ever be chosen, never fallen into.

    ⚠ A super's own `owning_organisation`, if they have one, is deliberately IGNORED here. A super
    who saw one tenant on this page and every tenant on the neighbouring Payments list would have
    to work out which screens narrow and which do not; `admin.is_super` means the same thing on
    both. An `org_admin` with no organisation is still `no_org` — that is a broken account, not a
    scope.
    """

    def _spending_admin(self, request):
        """`(admin, scope, programme, error)`.

        ⚠ The GIFT is resolved here too (TD-241) so this stays the ONE door: a screen that
        read the scope from here and the gift from somewhere else would have two answers to
        'what am I looking at', and only one of them fenced.
        """
        from .. import spend_report

        admin = self.get_admin(request)
        if not admin:
            return None, None, None, self._deny()
        if not (admin.is_super or admin.role in _SPENDING_ROLES):
            return None, None, None, self._deny_role()
        programme, err = self._gift_narrowing(request, admin)
        if err:
            return None, None, None, err
        if admin.is_super:
            return admin, spend_report.ALL_ORGS, programme, None
        org = admin.owning_organisation
        if org is None:
            return None, None, None, Response({'error': 'no_org', 'code': 'no_org'},
                                              status=status.HTTP_400_BAD_REQUEST)
        return admin, org, programme, None


def _spending_gaps(gaps):
    """`wallet_gaps` with its money stringified.

    ⚠ A bare `Decimal` in a plain dict is rendered by DRF's JSON renderer as a FLOAT — `30.00`
    reached a sponsor's screen as `30.0` in S5, and the unit test was green throughout because
    the values ARE Decimals until the boundary. Every money-bearing payload in this feature
    stringifies here, at the edge, for that reason.
    """
    return {
        **gaps,
        'unseen_students': [
            {'application_id': r['application_id'], 'name': r['name'],
             'paid': str(r['paid']), 'spent': str(r['spent'])}
            for r in gaps['unseen_students']
        ],
    }


class AdminSpendingView(_SpendingBase):
    """GET /api/v1/admin/scholarship/spending/ — the officer's view of what students spent.

    Four computed figures, the merchant table, the per-student table, what the model decided
    lately, and the two wallet gaps that are derivable. Everything comes from
    `spend_report`, which holds the organisation fence.

    ⚠ **THE PAYLOAD IS BUILT KEY BY KEY FROM PLAIN DICTS — there is no model passthrough**, so
    a field added to `ScholarshipApplication` or `StudentProfile` tomorrow cannot reach this
    response unless somebody writes a line for it. That is the same guarantee a hand-written
    allowlist serializer gives, and `test_spend_report.py` proves it the way the sponsor pool
    serializers are proved: a real NRIC, phone, address, email and school are planted on the
    fixture and asserted ABSENT from the rendered JSON. The student NAME is present on purpose
    — this is the officer's own organisation's students, on an admin-only surface.

    ⚠ Money is rendered as a STRING, never a float. It is summed, compared against a released
    total and shown to a person.

    tenancy: org-fenced on `application__owning_organisation` inside `spend_report._txns`, and
    the organisation is resolved once by `_spending_admin`. Classified in test_org_fence.py.
    """

    def get(self, request):
        admin, org, programme, err = self._spending_admin(request)
        if err:
            return err
        from .. import spend_report
        from ..models import SPEND_CATEGORY_CHOICES

        totals = spend_report.totals(org, programme)
        return Response({
            'totals': {
                'spent': str(totals['spent']),
                'placed': str(totals['placed']),
                'unplaced': str(totals['unplaced']),
                'placed_pct': totals['placed_pct'],
                'merchants_to_check': totals['merchants_to_check'],
            },
            'merchants': [{
                'merchant': r['merchant'],
                'category': r['category'],
                'decided_by': r['decided_by'],
                'visits': r['visits'],
                'total': str(r['total']),
                'last_seen': r['last_seen'].isoformat() if r['last_seen'] else None,
                'held_back': r['held_back'],
                # ⚠ WHEN THE VERDICT WAS REACHED, not when a student last shopped here. Added S7
                # when the separate "what the model decided recently" list was deleted: that list
                # held exactly one fact this table did not, and a fact is a column.
                'decided_at': r['decided_at'].isoformat() if r['decided_at'] else None,
            } for r in spend_report.merchant_rows(org, programme)],
            'students': [{
                'application_id': r['application_id'],
                'name': r['name'],
                # ⚠ TRANSACTIONS — things the student BOUGHT. It was called `payments`,
                # which beside the new `paid`/`balance` read as the number of
                # disbursements: two different money words on one row (owner, 2026-09-12).
                'transactions': r['transactions'],
                'spent': str(r['spent']),
                'unplaced': str(r['unplaced']),
                'paid': str(r['paid']),
                # ⚠ NOT floored at zero, unlike the sponsor card's. A negative is real —
                # the wallet is the student's own and a parent may top it up — and the
                # officer is exactly the person who should notice and ask.
                'balance': str(r['balance']),
            } for r in spend_report.student_rows(org, programme)],
            # ⚠ `model_decisions` WAS HERE AND IS DELETED (S7, 2026-09-11). It was this same data
            # filtered to `ai` within 14 days, rendered read-only beside a table that CAN be
            # corrected — so a reader found a wrong guess there and had to scroll up to fix it.
            # The owner asked what action it expected; the answer was none. Filter the shops table
            # by "how we decided" instead. Do not reintroduce it.
            'wallet_gaps': _spending_gaps(spend_report.wallet_gaps(org, programme)),
            'categories': [{'code': c, 'label': label} for c, label in SPEND_CATEGORY_CHOICES],
        })


class AdminSpendingCategoryView(_SpendingBase):
    """POST /api/v1/admin/scholarship/spending/category/ — correct one shop's category.

    Body: `{"merchant": "...", "category": "..."}`. Writes a `decided_by='owner'` verdict,
    which outranks every rung of the sorter and survives a full `--all` re-sort for ever.

    ⚠ The merchant must be one THIS organisation's students actually used. The verdict itself
    is global — a shop's category is a fact about the shop — so the fence has to be on who may
    SET it, or any tenant's admin could write a verdict for any shop by guessing a name.

    ⚠ An unknown category or an unused merchant is a 400 with a code, never a silent no-op: a
    correction screen that quietly does nothing is worse than one that refuses.

    tenancy: org-fenced inside `spend_report.set_owner_category` via the same `_txns` filter.
    Classified in test_org_fence.py.
    """

    def post(self, request):
        admin, org, programme, err = self._spending_admin(request)
        if err:
            return err
        from .. import spend_report

        merchant = request.data.get('merchant') or ''
        category = request.data.get('category') or ''
        changed, code = spend_report.set_owner_category(
            merchant, category, admin.email, org, programme)
        if code:
            return Response({'error': code, 'code': code},
                            status=status.HTTP_400_BAD_REQUEST)
        # ⚠ ON THE AUDIT LINE because it is the part nobody can reconstruct later: the stored
        # row says who decided and when, but "and it moved 42 payments" is the fact a reader
        # would otherwise have to guess at.
        logger.info('AUDIT spend_category_corrected merchant=%r category=%s rows=%s by=%s',
                    merchant, category, changed, admin.email or '')
        return Response({'merchant': merchant.strip().upper(), 'category': category,
                         'decided_by': 'owner', 'rows_changed': changed})


class AdminProgrammeOverviewView(_AdminBase):
    """GET /api/v1/admin/scholarship/programme-overview/ — "how is this gift doing?"

    The page a person lands on after clicking a gift card. **Open to every console role and
    SHAPED by role**: a reviewer lands on their own cases, a QC on their queue, a finance admin
    on the money, an org admin on all of it. Everything is computed by `programme_overview`,
    which holds the organisation fence.

    ⚠⚠ **THERE ARE TWO GATES HERE, AND THE SECOND IS NOT COSMETIC.** The first is the ORG FENCE
    (`programme_overview.application_scope`, re-asserted per query inside that module). The second
    is ROLE SHAPING: `SECTIONS_BY_ROLE` decides SERVER-SIDE which keys are built at all, so a
    reviewer's response has no money key to hide and a finance admin's has no funnel. The menu
    already withholds Payments and Spending from reviewer/qc; an Overview that served their
    figures anyway would have made that withholding decorative.

    ⚠ **FINANCE IS ADMITTED HERE THOUGH `_SPENDING_ROLES` EXCLUDES IT FROM THE SPENDING PAGE.**
    Deliberate widening, owner 2026-09-15, recorded in `docs/decisions.md` and the role matrix:
    finance gets TOTALS — committed, paid, remaining, spent, by month, by category — and never a
    name, a file or a verdict, because none of those is in a section it is given.

    ⚠ **A ROLE WITH NO SECTIONS IS REFUSED, NOT SERVED AN EMPTY PAGE.** `partner` is the one such
    role today (a referral organisation is attribution, never a scope). A future role added to
    `ROLE_CHOICES` without a decision in `SECTIONS_BY_ROLE` lands here too — a 403 is a question
    somebody answers, an empty page is a bug nobody notices.

    ⚠ A SUPER GETS `spend_report.ALL_ORGS`, the same platform scope the Spending and
    funding-summary screens hand them (2026-09-11/12) — `admin.is_super` must mean the same thing
    on every Programme page, or the console teaches people that some pages "just do not work for
    you". An `org_admin` with no organisation is still `no_org`: that is a broken account, not a
    scope.

    tenancy: org-fenced in `programme_overview.application_scope`; role-shaped by
    `SECTIONS_BY_ROLE`. Classified in test_org_fence.py.
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        from .. import programme_overview, spend_report
        if not programme_overview.sections_for(admin):
            return self._deny_role()
        programme, gift_err = self._gift_narrowing(request, admin)
        if gift_err:
            return gift_err
        cohort, intake_err = self._intake_narrowing(request, admin, programme)
        if intake_err:
            return intake_err
        if admin.is_super:
            org = spend_report.ALL_ORGS
        else:
            org = admin.owning_organisation
            if org is None:
                return Response({'error': 'no_org', 'code': 'no_org'},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response(programme_overview.build(admin, org, programme, cohort=cohort))


class AdminOverviewLayoutView(_AdminBase):
    """GET/PUT `admin/scholarship/organisation/overview-layout/` — which Overview widgets an
    organisation shows, and in what order (Programme Overview phase 2, 2026-09-18).

    Edited from the Overview's Customise mode by the org admin; read by
    `programme_overview.build` for every role in the organisation as a NARROWING of what the
    role may see (`overview_layout.apply` — never a widening; `mine`/`qc` are pages, not
    widgets, and are not in the list at all).

    ⚠ THE ORGANISATION IS DERIVED, NEVER SENT — the `AdminOrganisationConfigurationView` fence,
    mirrored (same 404-not-403, same refusal to pick silently between two, `?org=` for a super).
    A third copy of `_gate`/`_organisation_for`; extracting a verb-less base for the three is
    noted as debt rather than done inside a feature sprint.

    Who may write: `org_admin` and super — the layout changes what every colleague sees.

    PUT is ALL-OR-NOTHING: the body must be the FULL ordered list of the five widgets with a
    boolean each (`overview_layout.validate_sections`), refused with `{error, code, key}`; one
    `AUDIT overview_layout_set` line per save in the compact `funnel+,money-,…` form.

    tenancy: org-fenced on the derived organisation. Classified in test_org_fence.py.
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
        """Mirrors `AdminOrganisationConfigurationView._organisation_for` — see its docstring."""
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
        from .. import overview_layout
        from ..models import OrganisationOverviewLayout
        # org-fence: `org` is the derived organisation above.
        row = OrganisationOverviewLayout.objects.filter(organisation=org).first()
        return {
            'organisation': {'code': org.code, 'name': org.name},
            'sections': overview_layout.for_org(org),
            'updated_by_email': row.updated_by_email if row else '',
            'updated_at': row.updated_at.isoformat() if row else None,
        }

    def get(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        return Response(self._payload(org))

    @staticmethod
    def _compact(sections):
        return ','.join(f"{s['key']}{'+' if s['on'] else '-'}" for s in sections)

    def put(self, request):
        from .. import overview_layout
        from ..models import OrganisationOverviewLayout

        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        try:
            sections = overview_layout.normalised(request.data.get('sections'))
        except overview_layout.OverviewLayoutError as exc:
            return Response({'error': exc.code, 'code': exc.code, 'key': exc.key},
                            status=status.HTTP_400_BAD_REQUEST)
        was = overview_layout.for_org(org)
        # org-fence: as above. ⚠ `defaults=` carries the list INTO the create: the model's
        # `save()` validates, and a row created empty first would be refused before the update.
        row, created = OrganisationOverviewLayout.objects.get_or_create(
            organisation=org,
            defaults={'sections': sections, 'updated_by_email': admin.email or ''})
        if not created:
            row.sections = sections
            row.updated_by_email = admin.email or ''
            row.save()
        if was != sections:
            logger.info('AUDIT overview_layout_set org=%s was=%s now=%s by=%s',
                        org.code, self._compact(was), self._compact(sections), admin.email or '')
        return Response(self._payload(org))
