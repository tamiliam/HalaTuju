"""
MyNadi admin API for the B40 Assistance Programme (Sprint 6a).

Reuses the existing PartnerAdmin auth (super admin sees all). Routes live under
/api/v1/admin/scholarship/ — covered by the NRIC-gate /admin/ whitelist;
PartnerAdminMixin does the real authorisation.
"""
import logging

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
from .anomaly_engine import detect_anomalies
from .emails import send_request_info_email
from .models import (
    ApplicantDocument, GraduationMessage, InterviewSession, InterviewSlot, Referee,
    ReviewerProfile, ScholarshipApplication, Sponsor, SponsorProfile, Sponsorship,
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
    ReviewerProfileSerializer,
    SponsorProfileSerializer,
)
from .services import (
    AssignmentError, admin_reject, application_completeness, assign_reviewer,
    cancel_pending_decline, submit_interview,
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
        return ScholarshipApplication.objects.select_related('profile', 'cohort').filter(pk=pk).first()

    def _b40_scope(self, admin):
        """B40 Applications access by role:
          'all'      — super + admin (see every application)
          'assigned' — reviewer (only the applicants assigned to them)
          'none'     — partner / anyone else (B40 is not their page)
        """
        if admin is None or admin.role == 'partner':
            return 'none'
        if self.has_role(admin, 'admin'):   # super + admin
            return 'all'
        if admin.role == 'reviewer':
            return 'assigned'
        return 'none'

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
        if scope == 'assigned' and app.assigned_to_id != admin.id:
            return None, self._deny_role()   # reviewer, not assigned to them
        return app, None


class AdminApplicationListView(_AdminBase):
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        scope = self._b40_scope(admin)
        if scope == 'none':
            return self._deny_role()   # partner has no B40 Applications access
        qs = ScholarshipApplication.objects.select_related(
            'profile', 'cohort', 'assigned_to').order_by('-submitted_at')
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
        """Admin-editable per-application flags: mentoring-candidate. Writes require
        reviewer/super (admin is read-only). Reviewer assignment moved to the
        super-only audited endpoint (F7: .../assign/)."""
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, err = self._scoped_application(request, pk)
        if err:
            return err
        fields = []
        if 'mentoring_candidate' in request.data:
            app.mentoring_candidate = bool(request.data['mentoring_candidate'])
            fields.append('mentoring_candidate')
        if fields:
            app.save(update_fields=fields)
        return Response(AdminApplicationDetailSerializer(app).data)


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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
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
            app.status = 'accepted'
            app.verified_at = timezone.now()
            app.verified_by = admin.email
            app.verify_checklist = request.data.get('checklist', {}) or {}
            app.save(update_fields=['status', 'verified_at', 'verified_by', 'verify_checklist'])
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminRejectView(_AdminBase):
    """POST .../<pk>/reject/ {category} — post-shortlist admin rejection (buckets 3 & 4).
    'interview'  = reviewed but not selected (allowed from shortlisted/profile_complete/
                   interviewing/interviewed) → extra-thankful email.
    'contractual' = failed post-award steps (allowed only from 'accepted') → generic email.
    Reviewer-gated. The engine buckets (merit/need/ineligible) are NOT settable here."""
    def post(self, request, pk):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
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


class AdminCancelDeclineView(_AdminBase):
    """POST .../<pk>/cancel-decline/ — abort a scheduled-but-unrevealed decline within the
    decline cool-off (the student never saw it). Reviewer-gated. Idempotent."""
    def post(self, request, pk):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
        cancel_pending_decline(app)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminHoldAwardView(_AdminBase):
    """POST .../<pk>/hold-award/ — reverse an accepted-but-unconfirmed award within the award
    cool-off (the amount returns to the sponsor; the student never saw confirmation).
    Reviewer-gated. Idempotent."""
    def post(self, request, pk):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
        serializer = RefereeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ref = Referee.objects.create(application=app, **serializer.validated_data)
        return Response(RefereeSerializer(ref).data, status=status.HTTP_201_CREATED)


class AdminRefereeDetailView(_AdminBase):
    """DELETE .../<pk>/referees/<ref_id>/ — remove a referee from the application."""
    def delete(self, request, pk, ref_id):
        admin, err = self._require_reviewer(request)
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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)   # reviewer assignment-scoped; partner none
        if _err:
            return _err
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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
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
        admin, err = self._require_reviewer(request)
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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
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
        admin, err = self._require_reviewer(request)
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
        admin, err = self._require_reviewer(request)
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
    'Pre-interview flags' card shows)."""
    return [a['code'] for a in detect_anomalies(application)]


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
         note). Creating the first draft advances profile_complete → interviewing.
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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
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
        # First interview activity moves the funnel forward.
        if app.status == 'profile_complete':
            app.status = 'interviewing'
            app.save(update_fields=['status'])
        return Response(InterviewSessionSerializer(session).data)


class AdminInterviewSubmitView(_AdminBase):
    """POST .../<pk>/interview/submit/ — finalise the draft session and advance the
    application → interviewed. Reviewer/super only."""
    def post(self, request, pk):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
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
        if not self.get_admin(request):
            return self._deny()
        # Deterministic ordering (TD audit 2026-06-14) — without it the row order was
        # undefined. Full pagination is deferred: these are low-cardinality admin tables and
        # the sponsors table FE does not yet handle a paged envelope (would truncate to 25).
        qs = Sponsor.objects.all().order_by('-id')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response({'sponsors': [_sponsor_dict(s) for s in qs]})


class AdminSponsorReviewView(_AdminBase):
    """Phase E: POST .../admin/sponsors/<pk>/review/ {action: approve|reject|suspend}
    — vet a sponsor account. Reviewer-gated; stamps who/when."""
    _ACTION_STATUS = {'approve': 'approved', 'reject': 'rejected', 'suspend': 'suspended'}

    def post(self, request, pk):
        admin, err = self._require_reviewer(request)
        if err:
            return err
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
    """Phase E3: POST .../applications/<pk>/award-amount/ {amount} — set (or clear,
    with null/blank) the admin-approved award amount a sponsor funds in full.
    Reviewer-gated. Gates fundability + shows on the anonymised pool card."""
    def post(self, request, pk):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
        from decimal import Decimal, InvalidOperation
        raw = request.data.get('amount')
        try:
            amount = Decimal(str(raw)) if raw not in (None, '') else None
        except (InvalidOperation, TypeError):
            return Response({'error': 'invalid_amount'}, status=status.HTTP_400_BAD_REQUEST)
        if amount is not None and amount <= 0:
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
        if not self.get_admin(request):
            return self._deny()
        qs = (Sponsorship.objects.select_related('sponsor', 'application', 'application__profile')
              .order_by('-id'))  # deterministic ordering (TD audit 2026-06-14)
        st = request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        return Response({'sponsorships': [_sponsorship_dict(s) for s in qs]})


class AdminAssignableAdminsView(_AdminBase):
    """GET .../assignable-admins/ — active REVIEWERS (+ supers) for the assignment
    dropdown. Only roles that can actually be assigned an applicant appear (mirrors
    services._can_review): a plain 'admin' is read-only, and 'partner'/'viewer' have
    no review role, so none of them are listed."""
    def get(self, request):
        if not self.get_admin(request):
            return self._deny()
        from django.db.models import Q
        admins = (PartnerAdmin.objects.filter(is_active=True)
                  .filter(Q(is_super_admin=True) | Q(role__in=['reviewer', 'super']))
                  .select_related('reviewer_profile').order_by('name'))
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

        return Response({'admins': [
            {'id': a.id, 'name': a.name, 'email': a.email,
             'role': 'super' if a.is_super else a.role, 'languages': langs(a),
             'corrections': corrections.get(a.id, 0)}
            for a in admins
        ]})


class AdminRequestInfoView(_AdminBase):
    """POST .../<pk>/request-info/ — the admin asks the student for more
    documentation. Records a note on the application + emails the student. Does
    NOT change status (the student keeps editing). Reviewer/super only."""
    def post(self, request, pk):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
        from .services import querying_locked
        if querying_locked(app):
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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        if action not in ('waive', 'resolve', 'reopen'):
            return Response({'error': 'bad_action'}, status=status.HTTP_400_BAD_REQUEST)
        from .models import ResolutionItem
        item = ResolutionItem.objects.filter(pk=item_id).select_related('application').first()
        if item is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err

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
                        # Publish to the pool only on APPROVE (overall='accept') AND when the
                        # redaction backstop is clean — a declined/held student never appears.
                        leaks = pool.scan_profile_pii(
                            result['markdown'], getattr(app, 'profile', None))
                        published = (overall == 'accept' and not leaks)
                        if published:
                            sp.anon_published = True
                            sp.anon_published_at = timezone.now()
                            sp.realtime_notified_at = None
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
                        finalise_result = {'ok': True, 'published': published, 'leaks': leaks}

        with transaction.atomic():
            app.save(update_fields=verdict_fields)
            if sp_to_save is not None:
                sp_to_save.save()
            # If this re-records a REOPENED decision, that's a real correction
            # (counting model B) — close the audit row + clear the reopened flag.
            # The (re)publish on accept already happened via the finalise path above.
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
        qs = (ScholarshipApplication.objects
              .filter(verdict_decided_at__isnull=False)
              .only('ai_verdict_snapshot', 'officer_verdict', 'cohort_id'))
        cohort = request.query_params.get('cohort')
        if cohort:
            qs = qs.filter(cohort_id=cohort)
        pairs = ((a.ai_verdict_snapshot, a.officer_verdict) for a in qs)
        return Response(override_metrics(pairs))


class AdminAssignReviewerView(_AdminBase):
    """POST .../applications/<pk>/assign/ — (re)assign a reviewer (F7). SUPER-ONLY +
    audited. Body `{reviewer_id}` (null/''/0 = unassign). The first assignment of an
    unassigned app is gated on is_ready_for_assignment; reassign/unassign of an
    already-assigned app is allowed any time. Every change writes an AssignmentEvent.
    The target must be an active reviewer/super (never a viewer)."""

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, err = self._scoped_application(request, pk)
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
        admin, err = self._require_reviewer(request)
        if err:
            return err
        app, err = self._scoped_application(request, pk)
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
        qs = GraduationMessage.objects.select_related('application').all()
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
        message = GraduationMessage.objects.select_related('application__profile').filter(pk=pk).first()
        if message is None:
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
