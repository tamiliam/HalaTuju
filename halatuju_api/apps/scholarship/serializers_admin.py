"""Admin-facing serializers for the B40 Assistance Programme (Sprint 6a)."""
from rest_framework import serializers

from .models import (
    FundingNeed, GraduationMessage, InterviewSession, InterviewSlot, ReviewerProfile,
    ScholarshipApplication, SponsorProfile,
)
from . import pool
from .serializers import (
    ApplicantDocumentSerializer,
    ConsentSerializer,
    FundingNeedSerializer,
    RefereeSerializer,
)


def _admin_name_by_email(email):
    """Resolve a stored reviewer email → their full name (for the audit lines).
    Returns '' if no match (the cockpit then falls back to showing the email)."""
    email = (email or '').strip()
    if not email:
        return ''
    from apps.courses.models import PartnerAdmin
    return PartnerAdmin.objects.filter(email__iexact=email).values_list('name', flat=True).first() or ''


def _full_name(application):
    """The applicant's full legal name, UPPER-CASED for the admin views (students
    type their signature inconsistently — some lowercase). Prefer the declaration
    signature (typed at submit, e.g. 'SHARMILA A/P SANGGAR') over profile.name —
    the latter is often the Google display name / handle ('Sharmila 1204')."""
    declared = (getattr(application, 'declaration_name', '') or '').strip()
    name = declared or (getattr(application.profile, 'name', '') if application.profile else '')
    return name.upper()


def _verified_email(application):
    """The applicant's VERIFIED email, for admin display. A typed contact email
    is only trusted once the student clicks "Verify" (contact_email_verified);
    until then we show the Google/Supabase login email, which is always verified.
    Returns '' if neither is available (admin then sees a dash) — we never show an
    unverified address here. NOTE: `notify_email` is deliberately NOT a fallback —
    it captures the comms email at submit and CAN be a custom unverified one."""
    p = getattr(application, 'profile', None)
    if p is None:
        return ''
    if p.contact_email and p.contact_email_verified:
        return p.contact_email
    # Fall back to the verified login email from Supabase auth.users. The admin is
    # the caller here (not the student), so the login email isn't on the JWT — we
    # look it up by the profile's supabase_user_id. One query, detail view only.
    if getattr(p, 'supabase_user_id', None):
        try:
            from apps.courses.views_admin import _fetch_auth_data
            auth = _fetch_auth_data([p.supabase_user_id]).get(p.supabase_user_id, {})
            login_email = (auth.get('email') or '').strip()
            if login_email:
                return login_email
        except Exception:  # pragma: no cover - auth.users absent in unit-test DB
            pass
    return ''


class InterviewSessionSerializer(serializers.ModelSerializer):
    interviewer_name = serializers.CharField(source='interviewer.name', read_only=True, default=None)

    class Meta:
        model = InterviewSession
        fields = [
            'id', 'status', 'findings', 'rubric', 'overall_note',
            'interviewer_name', 'started_at', 'submitted_at', 'updated_at',
        ]


class InterviewSlotSerializer(serializers.ModelSerializer):
    """One proposed interview time. Times are ISO (UTC); the FE renders them in MYT."""
    class Meta:
        model = InterviewSlot
        fields = ['id', 'start', 'duration_min', 'is_active']


def interview_schedule_payload(application, *, include_reviewer_busy=False):
    """The interview-scheduling block shared by the admin + student responses:
    the booking state + the active proposed slots. Used by both serializers so the
    cockpit and the student portal read identical data.

    ``include_reviewer_busy`` (reviewer/admin context ONLY) adds the start times this
    reviewer already holds for OTHER applicants, so the propose grid can grey them out
    to avoid double-booking. Never sent to students (it would leak other interviews)."""
    from django.conf import settings
    active = [s for s in application.interview_slots.all() if s.is_active]
    active.sort(key=lambda s: s.start)
    payload = {
        'enabled': bool(getattr(settings, 'INTERVIEW_SCHEDULING_ENABLED', False)),
        'status': application.interview_status or '',
        'start': application.interview_start,
        'meeting_url': application.interview_meeting_url or '',
        'meeting_provider': application.interview_meeting_provider or '',
        'booked_slot_id': application.interview_slot_id,
        'slots': InterviewSlotSerializer(active, many=True).data,
        'reschedule_cutoff_hours': _reschedule_cutoff_hours(),
        # Student asked for different times (none of the proposed slots worked).
        'alternatives_requested': application.interview_alternatives_requested_at is not None,
        'alternatives_note': application.interview_alternatives_note or '',
        # Why the student cancelled their booked interview (if they gave a reason).
        'cancel_reason': application.interview_cancel_reason or '',
    }
    if include_reviewer_busy:
        reviewer = application.assigned_to
        busy = []
        if reviewer is not None:
            from .models import InterviewSlot
            busy = list(
                InterviewSlot.objects
                .filter(reviewer=reviewer, is_active=True)
                .exclude(application=application)
                .values_list('start', flat=True))
        payload['reviewer_busy'] = busy
    return payload


def _reschedule_cutoff_hours():
    from django.conf import settings
    return getattr(settings, 'INTERVIEW_RESCHEDULE_CUTOFF_HOURS', 12)


class SponsorProfileSerializer(serializers.ModelSerializer):
    current_markdown = serializers.CharField(read_only=True)

    class Meta:
        model = SponsorProfile
        fields = [
            'draft_markdown', 'edited_markdown', 'current_markdown', 'status',
            'model_used', 'generated_at', 'published_at', 'updated_at',
            'final_markdown', 'final_model_used', 'finalised_at',
            # Phase E2 anonymous (sponsor-pool) profile — admin-facing here.
            'anon_markdown', 'anon_model_used', 'anon_generated_at',
            'anon_published', 'anon_published_at',
        ]


def _application_merit_score(obj):
    """The course-guide merit (0-100) used for ranking — a single number rolling up grades
    + co-curriculum. SPM: computed academic+CoQ merit. STPM: the PNGK (CGPA) is the merit
    indicator. None if there's nothing to score. Derived LIVE from the persisted
    grades/CoQ/stream — there is no stored merit column (the inputs are the source of truth)."""
    p = obj.profile
    if not p:
        return None
    if p.exam_type == 'stpm':
        return p.stpm_cgpa
    grades = dict(p.grades or {})
    if not grades:
        return None
    # The engine's core uses 'history'; profiles store it as 'hist'. The eligibility flow
    # renames it before scoring, so mirror that — else History reads as a fail (G) and the
    # merit is understated.
    if 'hist' in grades:
        grades['history'] = grades.pop('hist')
    from apps.courses.engine import prepare_merit_inputs, calculate_merit_score
    s1, s2, s3 = prepare_merit_inputs(grades, getattr(p, 'stream_subjects', None) or None)
    coq = p.coq_score if p.coq_score is not None else 0
    result = calculate_merit_score(s1, s2, s3, coq)
    return round(result['final_merit'], 1)


class AdminApplicationListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    cohort_code = serializers.CharField(source='cohort.code', read_only=True)
    # Academic data is read live from the canonical profile, not the application.
    qualification = serializers.CharField(source='profile.exam_type', read_only=True)
    stpm_pngk = serializers.FloatField(source='profile.stpm_cgpa', read_only=True)
    spm_a_count = serializers.SerializerMethodField()
    # Source (the referring org, chosen at apply) + the course-guide merit, for the list table.
    referral_source = serializers.CharField(source='profile.referral_source', read_only=True, allow_null=True)
    merit_score = serializers.SerializerMethodField()
    # The student's preferred call language (en/ms/ta/mixed) — drives reviewer language matching.
    call_language = serializers.CharField(source='profile.preferred_call_language', read_only=True, allow_blank=True)
    assigned_to_id = serializers.IntegerField(source='assigned_to.id', read_only=True, default=None)
    assigned_to_name = serializers.CharField(source='assigned_to.name', read_only=True, default=None)

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'name', 'profile_id', 'cohort_code', 'qualification',
            'spm_a_count', 'stpm_pngk', 'referral_source', 'merit_score', 'call_language',
            'status', 'bucket', 'shortlist_reason',
            'submitted_at', 'profile_completed_at',
            'assigned_to_id', 'assigned_to_name',
            # When set, the list pill shows "Reopened" (overriding accepted/rejected).
            'decision_reopened_at',
        ]

    def get_name(self, obj):
        return _full_name(obj)

    def get_merit_score(self, obj):
        return _application_merit_score(obj)

    def get_spm_a_count(self, obj):
        from .shortlisting import count_spm_a_grades
        return count_spm_a_grades(getattr(obj.profile, 'grades', None)) if obj.profile else 0


class AdminApplicationDetailSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    school = serializers.SerializerMethodField()
    # NRIC shown in full so the admin can compare it to the uploaded MyKad at verify time.
    nric = serializers.CharField(source='profile.nric', read_only=True)
    nric_verified = serializers.BooleanField(source='profile.nric_verified', read_only=True)
    # Academic + financial data is read live from the canonical profile.
    qualification = serializers.CharField(source='profile.exam_type', read_only=True)
    stpm_pngk = serializers.FloatField(source='profile.stpm_cgpa', read_only=True)
    household_income = serializers.IntegerField(source='profile.household_income', read_only=True)
    household_size = serializers.IntegerField(source='profile.household_size', read_only=True)
    receives_str = serializers.BooleanField(source='profile.receives_str', read_only=True)
    receives_jkm = serializers.BooleanField(source='profile.receives_jkm', read_only=True)
    # Profile-stored address (S14) — surfaced so the admin Vision card can show
    # it alongside `vision_address` (the MyKad-read address) for eyeball compare.
    address = serializers.CharField(source='profile.address', read_only=True, allow_blank=True)
    # Complete-profile view — the remaining profile-sourced fields the student
    # entered at /apply (contact, family, academic detail). All read-only mirrors.
    postal_code = serializers.CharField(source='profile.postal_code', read_only=True, allow_blank=True)
    city = serializers.CharField(source='profile.city', read_only=True, allow_blank=True)
    preferred_state = serializers.CharField(source='profile.preferred_state', read_only=True, allow_blank=True)
    contact_phone = serializers.CharField(source='profile.contact_phone', read_only=True, allow_blank=True)
    contact_email = serializers.CharField(source='profile.contact_email', read_only=True, allow_blank=True)
    preferred_call_language = serializers.CharField(source='profile.preferred_call_language', read_only=True, allow_blank=True)
    referral_source = serializers.CharField(source='profile.referral_source', read_only=True, allow_null=True)
    guardians = serializers.JSONField(source='profile.guardians', read_only=True)
    # Academic detail (rendered SPM/STPM-aware on the admin page).
    muet_band = serializers.IntegerField(source='profile.muet_band', read_only=True)
    coq_score = serializers.FloatField(source='profile.coq_score', read_only=True)
    grades = serializers.JSONField(source='profile.grades', read_only=True)
    stpm_grades = serializers.JSONField(source='profile.stpm_grades', read_only=True)
    spm_prereq_grades = serializers.JSONField(source='profile.spm_prereq_grades', read_only=True)
    spm_a_count = serializers.SerializerMethodField()
    merit_score = serializers.SerializerMethodField()
    verified_email = serializers.SerializerMethodField()
    funding_need = serializers.SerializerMethodField()
    sponsor_profile = serializers.SerializerMethodField()
    # Pre-interview deterministic flag list (S16 Phase A). Each entry is
    # {code, params}; the frontend resolves human copy from its i18n bundle.
    anomalies = serializers.SerializerMethodField()
    verdict = serializers.SerializerMethodField()
    submission_review = serializers.SerializerMethodField()
    query_sla = serializers.SerializerMethodField()
    funding_estimate = serializers.SerializerMethodField()
    resolution_items = serializers.SerializerMethodField()
    completeness = serializers.SerializerMethodField()
    interview_session = serializers.SerializerMethodField()
    # Phase B: Gemini interview gaps — a PLAIN read-only field (the GET never calls
    # Gemini; gaps are produced + stored by the admin-on-demand suggest-gaps endpoint).
    interview_gaps = serializers.JSONField(read_only=True)
    interview_gaps_run_at = serializers.DateTimeField(read_only=True)
    # Interview scheduling: booking state + proposed slots (dark behind the flag).
    interview_schedule = serializers.SerializerMethodField()
    # The reviewer's full NAME for the audit lines (verified_by / verdict_decided_by /
    # rejected_by store an email; the cockpit shows the name, falling back to email).
    verified_by_name = serializers.SerializerMethodField()
    verdict_decided_by_name = serializers.SerializerMethodField()
    rejected_by_name = serializers.SerializerMethodField()
    assigned_to_id = serializers.IntegerField(source='assigned_to.id', read_only=True, default=None)
    assigned_to_name = serializers.CharField(source='assigned_to.name', read_only=True, default=None)
    # Internal-only correction tally for the assigned reviewer (reopened decisions that
    # led to a real change). Shown in the assign panel; never on a sponsor/student surface.
    assigned_to_corrections = serializers.SerializerMethodField()
    # Decision-reopen state: when set, the decision panel is editable + the reviewer
    # dropdown unlocks + a "held from sponsors" banner shows. The open reason drives the banner.
    decision_reopen_reason = serializers.SerializerMethodField()
    # Whether the (dark-by-default) Conditional Bursary Agreement feature is live — the cockpit
    # only renders the agreement panel when this is on (otherwise its signing flow doesn't exist).
    bursary_agreement_enabled = serializers.SerializerMethodField()
    # Post-award S4: the money-out tranche ledger (admin-facing; no sponsor identity).
    disbursements = serializers.SerializerMethodField()
    # Standardised assistance (2026-06-29): the pathway-derived proposed amount the cockpit
    # shows + auto-applies on approve. award_amount is the persisted value (super-overridable).
    proposed_award_amount = serializers.SerializerMethodField()
    documents = ApplicantDocumentSerializer(many=True, read_only=True)
    referees = RefereeSerializer(many=True, read_only=True)
    consents = ConsentSerializer(many=True, read_only=True)

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'name', 'school', 'nric', 'nric_verified', 'profile_id', 'qualification',
            'spm_a_count', 'merit_score', 'stpm_pngk', 'household_income', 'household_size',
            'receives_str', 'receives_jkm', 'intended_pathway', 'intends_tertiary_2026',
            'aspirations', 'plans', 'fears', 'justification',
            'address', 'postal_code', 'city', 'preferred_state',
            'contact_phone', 'contact_email', 'notify_email', 'verified_email', 'preferred_call_language', 'referral_source', 'guardians',
            # Academic detail (FE renders SPM vs STPM by qualification)
            'muet_band', 'coq_score', 'grades', 'stpm_grades', 'spm_prereq_grades',
            # "Your story" narrative (S2) + support + declaration
            'first_in_family', 'parents_occupation', 'siblings_studying_count',
            # P2 (Check 2): the school/tertiary split (cockpit shows the burden breakdown)
            'siblings_in_school', 'siblings_in_tertiary',
            # Structured family roster (redesign 2026-06) — the cockpit Family card
            # shows father/mother name + profession + the member pool.
            'father_name', 'father_occupation', 'father_occupation_other',
            'mother_name', 'mother_occupation', 'mother_occupation_other',
            'other_family_members',
            'family_context', 'daily_life', 'consent_to_contact',
            'declaration_name', 'declared_at',
            'status', 'bucket', 'shortlist_reason', 'submitted_at',
            # Phase E3: admin-set award amount (gates fundability; shown on the pool card)
            'award_amount',
            # Standardised assistance (2026-06-29): pathway-derived proposed amount.
            'proposed_award_amount',
            # Rejection bucket (merit/need/ineligible/interview/contractual) + stamps
            'rejection_category', 'rejected_at', 'rejected_by', 'rejected_by_name',
            # Closure bucket (post-award lifecycle): graduated/completed/withdrawn/lapsed/terminated
            'closure_reason', 'closed_at', 'closed_by',
            # S5: operational maintenance sub-state (on_track/probation/on_hold/ready_to_close)
            'maintenance_substate',
            # Cool-off (#13/#14): a scheduled-but-unrevealed decline / award confirmation +
            # its reveal date — drives the cockpit "scheduled — cancel/hold" banners.
            'pending_rejection_category', 'decline_due_at', 'award_due_at',
            # Phase C handoff + interview funnel
            'profile_completed_at', 'completeness', 'interview_session',
            'interview_gaps', 'interview_gaps_run_at', 'interview_schedule',
            'assigned_to_id', 'assigned_to_name', 'assigned_at',
            'info_request_note', 'info_requested_at',
            # S11a verify-&-accept + mentoring
            'mentoring_candidate', 'verified_at', 'verified_by', 'verified_by_name', 'verify_checklist',
            # S10 plans/support intake (surface for the admin review)
            'pathways_considered', 'top_choices', 'upu_status', 'field_of_study',
            'other_scholarships', 'other_scholarships_text', 'help_university',
            'help_scholarship', 'anything_else',
            # Plans redesign — surface the structured pathway plan for admin/coordinator
            'pathway_certainty', 'chosen_pathway', 'pre_u_track', 'pre_u_institution',
            'chosen_programme', 'uncertainty_reasons', 'uncertainty_note',
            # S3: normalised (sortable) offer reporting date.
            'reporting_date',
            # Income wizard answers — drive the cockpit's route-aware income document panel.
            'income_route', 'income_earner', 'income_working_members',
            'funding_need', 'documents', 'referees', 'consents', 'sponsor_profile',
            'anomalies',
            'verdict',
            'submission_review',
            'query_sla',
            'funding_estimate',
            'resolution_items',
            'intake_snapshot',
            # S5 verdict audit / override capture (read-only; written via record-verdict).
            'ai_verdict_snapshot', 'officer_verdict', 'verdict_reason',
            'verdict_decided_by', 'verdict_decided_at', 'verdict_decided_by_name',
            # Decision-reopen (reverse a recorded decision) state + assigned-reviewer corrections.
            'decision_reopened_at', 'decision_reopen_reason',
            'assigned_to_corrections', 'bursary_agreement_enabled',
            # Post-award S4: the disbursement/tranche ledger (cockpit money-out panel).
            'disbursements',
        ]

    def get_disbursements(self, obj):
        from .disbursement import disbursement_dict
        return [disbursement_dict(d) for d in obj.disbursements.all()]

    def get_proposed_award_amount(self, obj):
        from .award import proposed_award_amount
        return str(proposed_award_amount(obj))

    def get_assigned_to_corrections(self, obj):
        from .reopen import reviewer_correction_count
        return reviewer_correction_count(obj.assigned_to)

    def get_bursary_agreement_enabled(self, obj):
        from django.conf import settings
        return bool(getattr(settings, 'BURSARY_AGREEMENT_ENABLED', False))

    def get_decision_reopen_reason(self, obj):
        if obj.decision_reopened_at is None:
            return ''
        from .reopen import open_reopen
        row = open_reopen(obj)
        return row.reason if row else ''

    def get_name(self, obj):
        return _full_name(obj)

    def get_verified_by_name(self, obj):
        return _admin_name_by_email(obj.verified_by)

    def get_verdict_decided_by_name(self, obj):
        return _admin_name_by_email(obj.verdict_decided_by)

    def get_rejected_by_name(self, obj):
        return _admin_name_by_email(obj.rejected_by)

    def get_school(self, obj):
        return getattr(obj.profile, 'school', '') if obj.profile else ''

    def get_spm_a_count(self, obj):
        from .shortlisting import count_spm_a_grades
        return count_spm_a_grades(getattr(obj.profile, 'grades', None)) if obj.profile else 0

    def get_merit_score(self, obj):
        return _application_merit_score(obj)

    def get_verified_email(self, obj):
        """The verified email to display on the admin card (see _verified_email)."""
        return _verified_email(obj)

    def get_funding_need(self, obj):
        try:
            return FundingNeedSerializer(obj.funding_need).data
        except FundingNeed.DoesNotExist:
            return None

    def get_sponsor_profile(self, obj):
        try:
            return SponsorProfileSerializer(obj.sponsor_profile).data
        except SponsorProfile.DoesNotExist:
            return None

    #: Cockpit consolidation: anomalies that already have an authoritative home
    #: elsewhere (the verdict tile + the identity caveat) are NOT also surfaced as
    #: pre-interview flags, so the merged "Outstanding" panel never double-asks.
    _DEDUPED_ANOMALIES = frozenset({'vision_nric_mismatch', 'vision_name_mismatch'})

    def get_anomalies(self, obj):
        """S16 Phase A: deterministic pre-interview flag list. Pure rules,
        no LLM calls. Returns ``[]`` when nothing flags. Identity NRIC/name
        mismatches are deduped out (the verdict + caveat own them)."""
        from .anomaly_engine import detect_anomalies
        return [a for a in detect_anomalies(obj)
                if a['code'] not in self._DEDUPED_ANOMALIES]

    def get_verdict(self, obj):
        """S1 verification verdict: the four-fact rollup the coordinator audits
        (identity / academic / income / pathway). Pure deterministic engine, no
        LLM calls — mirrors get_anomalies."""
        from .verdict_engine import build_verdict
        return build_verdict(obj)

    def get_submission_review(self, obj):
        """Check 2 STEP 1: the deterministic facts ledger + completeness gaps +
        consistency flags. Pure rules, no LLM — mirrors get_verdict / get_anomalies."""
        from .submission_review import submission_review
        return submission_review(obj)

    def get_query_sla(self, obj):
        """Check 2 STEP 2/3: the query SLA clock for the cockpit — deadline, whether it
        lapsed, open clarify-query count, days left, whether the app is ready for
        assignment, and whether it's proceeding WITH queries still open (the
        'ready-with-open-queries' reviewer flag, design §5)."""
        from .services import is_ready_for_assignment, query_sla
        sla = query_sla(obj)
        ready = is_ready_for_assignment(obj)
        return {
            'deadline': sla['deadline'],
            'lapsed': sla['lapsed'],
            'open_count': sla['open_count'],
            'days_left': sla['days_left'],
            'ready_for_assignment': ready,
            'proceeding_with_open_queries': ready and sla['open_count'] > 0,
        }

    def get_funding_estimate(self, obj):
        """Check 2: the deterministic per-pathway funding-need estimate (the gap after
        government coverage) for award sizing. Pure rules, no LLM."""
        from .funding_estimate import estimate_funding
        return estimate_funding(obj)

    def get_resolution_items(self, obj):
        """S3 resolution queue: sync the system tickets against the live verdict AND
        the Check-2 AI clarify queries, then return the OPEN items (system + officer +
        check2) so the officer sees exactly what the student still owes. Idempotent."""
        from django.db.models import Q
        from .resolution import sync_resolution_items
        from .check2_queries import sync_check2_queries
        from .serializers import ResolutionItemSerializer
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
        from .services import application_completeness
        return application_completeness(obj)

    def get_interview_session(self, obj):
        """Phase C: the latest interview session (draft or submitted), or None."""
        session = obj.interview_sessions.first()  # ordering = -created_at
        return InterviewSessionSerializer(session).data if session else None

    def get_interview_schedule(self, obj):
        """Interview booking state + proposed slots (reviewer view → includes the
        reviewer's other-student busy times so the propose grid greys them out)."""
        return interview_schedule_payload(obj, include_reviewer_busy=True)


class ReviewerProfileSerializer(serializers.ModelSerializer):
    """A reviewer's own credentials + contact details (F6). Narrow + self-scoped:
    only the six editable fields are writable; the FK is never exposed or accepted.
    Sensitive staff PII (phone/address) lives only here, never in any outward
    (student/sponsor) serializer."""

    class Meta:
        model = ReviewerProfile
        fields = [
            'highest_qualification', 'university', 'graduation_year',
            'field_of_study', 'phone', 'address',
            'street_address', 'postcode', 'city', 'state',
            'english_fluency', 'bm_fluency', 'tamil_fluency',
            'share_phone_with_students',
        ]

    def validate_graduation_year(self, value):
        # A plausible graduation year (or None). PositiveSmallIntegerField already
        # bars negatives; keep the upper bound generous and the lower bound sane.
        if value is not None and not (1950 <= value <= 2100):
            raise serializers.ValidationError('Enter a valid graduation year.')
        return value


class AdminGraduationMessageSerializer(serializers.ModelSerializer):
    """F9a — staff (myNADI) view of a graduation thank-you awaiting moderation. Staff
    are NOT the anonymity boundary (they can see the student), so the full text +
    scan outcome is shown. ``ref`` is included so the reviewer sees the same anon
    alias the sponsor will, and ``application`` links to the cockpit."""
    ref = serializers.SerializerMethodField()

    class Meta:
        model = GraduationMessage
        fields = ['id', 'application', 'ref', 'status', 'raw_text', 'scrubbed_text',
                  'scan_result', 'approved_by', 'review_note', 'created_at', 'reviewed_at']
        read_only_fields = fields

    def get_ref(self, obj):
        return pool.pool_ref(obj.application_id)
