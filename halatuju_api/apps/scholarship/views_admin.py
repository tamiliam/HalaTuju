"""
MyNadi admin API for the B40 Assistance Programme (Sprint 6a).

Reuses the existing PartnerAdmin auth (super admin sees all). Routes live under
/api/v1/admin/scholarship/ — covered by the NRIC-gate /admin/ whitelist;
PartnerAdminMixin does the real authorisation.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import PartnerAdmin
from apps.courses.views_admin import PartnerAdminMixin

from . import pool
from .anomaly_engine import detect_anomalies
from .emails import send_request_info_email
from .models import (
    ApplicantDocument, InterviewSession, Referee, ScholarshipApplication,
    Sponsor, SponsorInterest, SponsorProfile, Sponsorship,
)
from .profile_engine import (
    generate_anonymous_profile, generate_sponsor_profile, refine_sponsor_profile,
)
from .serializers import ApplicantDocumentSerializer, RefereeSerializer
from .serializers_admin import (
    AdminApplicationDetailSerializer,
    AdminApplicationListSerializer,
    InterviewSessionSerializer,
    SponsorProfileSerializer,
)
from .services import admin_reject, application_completeness, submit_interview

_VALID_VERDICTS = {'resolved', 'still_unclear', 'new_concern'}
_RATIONALE_MAX = 140


class _AdminBase(PartnerAdminMixin, APIView):
    """Shared 403-if-not-admin guard + own-application lookup."""

    def _deny(self):
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

    def _deny_role(self):
        return Response({'error': 'Your admin role cannot perform this action.'},
                        status=status.HTTP_403_FORBIDDEN)

    def _get_application(self, pk):
        return ScholarshipApplication.objects.select_related('profile', 'cohort').filter(pk=pk).first()


class AdminApplicationListView(_AdminBase):
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        qs = ScholarshipApplication.objects.select_related(
            'profile', 'cohort', 'assigned_to').order_by('-submitted_at')
        status_f = request.GET.get('status')
        bucket_f = request.GET.get('bucket')
        assigned_f = request.GET.get('assigned')
        if status_f:
            qs = qs.filter(status=status_f)
        if bucket_f:
            qs = qs.filter(bucket=bucket_f)
        # Phase C: ?assigned=me|none|<admin_id>
        if assigned_f == 'me':
            qs = qs.filter(assigned_to=admin)
        elif assigned_f == 'none':
            qs = qs.filter(assigned_to__isnull=True)
        elif assigned_f and assigned_f.isdigit():
            qs = qs.filter(assigned_to_id=int(assigned_f))
        data = AdminApplicationListSerializer(qs, many=True).data
        return Response({'applications': data, 'total_count': len(data)})


class AdminApplicationDetailView(_AdminBase):
    def get(self, request, pk):
        if not self.get_admin(request):
            return self._deny()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminApplicationDetailSerializer(app).data)

    def patch(self, request, pk):
        """Admin-editable per-application flags: mentoring-candidate, and (Phase C)
        the assigned reviewer. Writes require reviewer/super (viewer is read-only)."""
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        fields = []
        if 'mentoring_candidate' in request.data:
            app.mentoring_candidate = bool(request.data['mentoring_candidate'])
            fields.append('mentoring_candidate')
        if 'assigned_to' in request.data:
            target_id = request.data['assigned_to']
            if target_id in (None, '', 0):
                app.assigned_to = None
            else:
                target = PartnerAdmin.objects.filter(pk=target_id, is_active=True).first()
                if target is None:
                    return Response({'error': 'No such active admin.', 'code': 'bad_assignee'},
                                    status=status.HTTP_400_BAD_REQUEST)
                app.assigned_to = target
            fields.append('assigned_to')
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
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
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
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
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
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        refs = Referee.objects.filter(application=app)
        return Response({'referees': RefereeSerializer(refs, many=True).data})

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = RefereeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ref = Referee.objects.create(application=app, **serializer.validated_data)
        return Response(RefereeSerializer(ref).data, status=status.HTTP_201_CREATED)


class AdminRefereeDetailView(_AdminBase):
    """DELETE .../<pk>/referees/<ref_id>/ — remove a referee from the application."""
    def delete(self, request, pk, ref_id):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        ref = Referee.objects.filter(pk=ref_id, application_id=pk).first()
        if ref is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        ref.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminRunVisionView(_AdminBase):
    """
    POST .../<pk>/documents/<doc_id>/re-run-vision/ — re-run Vision OCR on an
    existing IC document. Soft signal only; the admin verify-&-accept stays
    the real identity gate. Returns the updated document.
    """
    def post(self, request, pk, doc_id):
        if not self.get_admin(request):
            return self._deny()
        doc = ApplicantDocument.objects.filter(pk=doc_id, application_id=pk).first()
        if doc is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if doc.doc_type != 'ic':
            return Response(
                {'error': 'Vision OCR only runs on IC documents.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .vision import run_vision_for_document
        run_vision_for_document(doc)
        return Response(ApplicantDocumentSerializer(doc).data)


class AdminGenerateProfileView(_AdminBase):
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # Optional output language ('en'/'ms'); defaults to the applicant's locale.
        result = generate_sponsor_profile(app, language=request.data.get('language'))
        if 'error' in result:
            return Response({'error': result['error']}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        sp, _ = SponsorProfile.objects.get_or_create(application=app)
        sp.draft_markdown = result['markdown']
        sp.model_used = result.get('model_used', '')
        sp.generated_at = timezone.now()
        if sp.status == 'published':
            sp.status = 'draft'  # regenerating a published profile reverts it to draft
        sp.save()
        return Response(SponsorProfileSerializer(sp).data)


class AdminFinaliseProfileView(_AdminBase):
    """Phase D: POST .../<pk>/finalise-profile/ — second Gemini pass that refines the
    existing draft profile with the SUBMITTED interview's findings → ``final_markdown``.
    Reviewer-gated, admin-on-demand. Requires both a draft and a submitted interview."""
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
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
        sp.finalised_at = timezone.now()
        sp.save()
        return Response(SponsorProfileSerializer(sp).data)


class AdminGenerateAnonProfileView(_AdminBase):
    """Phase E2: POST .../<pk>/anon-profile/generate/ — generate the ANONYMOUS,
    sponsor-pool-facing profile (fed only non-identifying inputs). Reviewer-gated,
    billable. Regenerating reverts it to unpublished (an admin must re-publish)."""
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        result = generate_anonymous_profile(app, language=request.data.get('language'))
        if 'error' in result:
            return Response({'error': result['error']}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        sp, _ = SponsorProfile.objects.get_or_create(application=app)
        sp.anon_markdown = result['markdown']
        sp.anon_model_used = result.get('model_used', '')
        sp.anon_generated_at = timezone.now()
        # A fresh generation must be re-reviewed before sponsors see it.
        sp.anon_published = False
        sp.anon_published_at = None
        sp.save()
        return Response(SponsorProfileSerializer(sp).data)


class AdminPublishAnonProfileView(_AdminBase):
    """Phase E2: POST .../<pk>/anon-profile/publish/ {publish: true|false} — the
    human gate that makes the anonymous profile visible in the sponsor pool (with
    an active share consent). Reviewer-gated. Requires a generated anon profile."""
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        sp = SponsorProfile.objects.filter(application_id=pk).first()
        if sp is None or not sp.anon_markdown.strip():
            return Response({'error': 'Generate an anonymous profile first.', 'code': 'no_anon'},
                            status=status.HTTP_400_BAD_REQUEST)
        publish = request.data.get('publish', True)
        if publish:
            # TD-074b: structural backstop — refuse to publish a blurb that contains
            # the student's own identifying tokens (name/school/city/NRIC/phone/email).
            leaks = pool.scan_anon_for_identifiers(sp.anon_markdown, getattr(sp.application, 'profile', None))
            if leaks:
                return Response(
                    {'error': 'The anonymous profile may contain identifying details — regenerate before publishing.',
                     'code': 'anon_identifier_leak', 'fields': leaks},
                    status=status.HTTP_400_BAD_REQUEST)
        sp.anon_published = bool(publish)
        sp.anon_published_at = timezone.now() if publish else None
        sp.save(update_fields=['anon_published', 'anon_published_at', 'updated_at'])
        return Response(SponsorProfileSerializer(sp).data)


class AdminSuggestGapsView(_AdminBase):
    """Phase B: admin-on-demand Gemini interview gap-spotter. One Gemini call →
    3-6 suggested interview questions stored on the application, shown beside the
    deterministic pre-interview flags. Reviewer-gated (billable)."""
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from .gap_engine import generate_interview_gaps
        result = generate_interview_gaps(app, language=request.data.get('language'))
        if 'error' in result:
            return Response({'error': result['error']}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        app.interview_gaps = result['gaps']
        app.interview_gaps_run_at = timezone.now()
        app.save(update_fields=['interview_gaps', 'interview_gaps_run_at'])
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminProfileEditView(_AdminBase):
    def put(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
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
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
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
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        session = app.interview_sessions.first()  # ordering = -created_at
        data = InterviewSessionSerializer(session).data if session else None
        return Response({'session': data, 'agenda': _interview_agenda(app)})

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        findings = request.data.get('findings', {}) or {}
        err = _validate_findings(findings)
        if err:
            return Response({'error': err, 'code': 'bad_findings'},
                            status=status.HTTP_400_BAD_REQUEST)
        session = app.interview_sessions.filter(status='draft').first()
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
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
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


class AdminSponsorInterestView(_AdminBase):
    """GET .../admin/sponsor-interest/ — registered sponsor leads for follow-up."""
    def get(self, request):
        if not self.get_admin(request):
            return self._deny()
        rows = SponsorInterest.objects.all()
        return Response({'interests': [
            {'id': r.id, 'name': r.name, 'email': r.email, 'organisation': r.organisation,
             'message': r.message, 'status': r.status, 'created_at': r.created_at}
            for r in rows
        ]})


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
        qs = Sponsor.objects.all()
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response({'sponsors': [_sponsor_dict(s) for s in qs]})


class AdminSponsorReviewView(_AdminBase):
    """Phase E: POST .../admin/sponsors/<pk>/review/ {action: approve|reject|suspend}
    — vet a sponsor account. Reviewer-gated; stamps who/when."""
    _ACTION_STATUS = {'approve': 'approved', 'reject': 'rejected', 'suspend': 'suspended'}

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
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
    """Phase E3: POST .../applications/<pk>/award-amount/ {amount} — set (or clear,
    with null/blank) the admin-approved award amount a sponsor funds in full.
    Reviewer-gated. Gates fundability + shows on the anonymised pool card."""
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
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
        qs = Sponsorship.objects.select_related('sponsor', 'application', 'application__profile')
        st = request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        return Response({'sponsorships': [_sponsorship_dict(s) for s in qs]})


class AdminAssignableAdminsView(_AdminBase):
    """GET .../assignable-admins/ — active admins for the assignment dropdown."""
    def get(self, request):
        if not self.get_admin(request):
            return self._deny()
        admins = PartnerAdmin.objects.filter(is_active=True).order_by('name')
        return Response({'admins': [
            {'id': a.id, 'name': a.name, 'email': a.email,
             'role': 'super' if a.is_super else a.role}
            for a in admins
        ]})


class AdminRequestInfoView(_AdminBase):
    """POST .../<pk>/request-info/ — the admin asks the student for more
    documentation. Records a note on the application + emails the student. Does
    NOT change status (the student keeps editing). Reviewer/super only."""
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'reviewer'):
            return self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
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
