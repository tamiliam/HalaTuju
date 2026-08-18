"""Admin-facing serializers for the B40 Assistance Programme (Sprint 6a)."""
from rest_framework import serializers

from apps.courses.utils import tidy_parentage_marker

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
    the latter is often the Google display name / handle ('Sharmila 1204').

    ⚠ THIS READS THE SIGNATURE, SO NORMALISING `profile.name` DOES NOT REACH THIS SURFACE.
    Application #20 typed 'SHARVANI A/ P KANAGEVELLU'; her canonical name was corrected to the
    MyKad spelling on 2026-07-30 and the cockpit header still showed the stray space, because
    the signature wins here by design. The signature is a dated legal record and stays verbatim
    in the database — so the marker is tidied at DISPLAY time instead, alongside the upper-casing
    this function already does for the same reason (students type it inconsistently).
    Marker-only: it cannot alter a letter or the spacing between name words."""
    declared = (getattr(application, 'declaration_name', '') or '').strip()
    name = declared or (getattr(application.profile, 'name', '') if application.profile else '')
    return tidy_parentage_marker(name.upper())


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

    from . import scheduling
    active = [s for s in application.interview_slots.all() if s.is_active]
    active.sort(key=lambda s: s.start)
    # A BOOKED application's unpicked siblings are RELEASED (scheduling.held_starts):
    # the reviewer may re-offer those times to other students, first to book wins. So
    # the re-pick menu must drop any released time the reviewer has since re-offered
    # or re-booked elsewhere — otherwise the student books into a conflict.
    if application.interview_status == 'booked' and application.assigned_to_id:
        taken = scheduling.held_starts(application.assigned_to,
                                       exclude_application=application)
        active = [s for s in active
                  if s.id == application.interview_slot_id or s.start not in taken]
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
        # The student's messages to their reviewer (always-open channel) — newest last,
        # bounded so a chatty thread can't bloat the payload.
        'messages': [
            {'text': m.text, 'created_at': m.created_at}
            for m in application.interview_messages.order_by('-created_at')[:20][::-1]
        ],
    }
    if include_reviewer_busy:
        # Only the times the reviewer genuinely HOLDS (a booked application's released
        # siblings no longer block) — see scheduling.held_starts for the semantics.
        payload['reviewer_busy'] = sorted(
            scheduling.held_starts(application.assigned_to,
                                   exclude_application=application))
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


def _has_stpm_results(p):
    """⚠ TRUSTWORTHY IN ONE DIRECTION ONLY — read `held_qualification` before using it elsewhere.

    FALSE is conclusive: with no STPM grades and no CGPA on file there is nothing to hold.
    TRUE is not. This profile is SHARED with the HalaTuju course guide, where anyone may type
    STPM grades to explore STPM programmes, so the data can describe a hypothetical rather than a
    result. Application #15 carries a 4.0 CGPA and five STPM subjects and sat none of them — she
    took SPM in 2025 and is on a matriculation course (owner, 2026-08-18).
    """
    return bool(p.stpm_grades or {}) or p.stpm_cgpa is not None


def held_qualification(p):
    """Which qualification we hold RESULTS for — NOT which pathway the student is entering by
    (BrightPath request #14).

    ``profile.exam_type`` answers two different questions in this codebase: *"which results do I
    hold?"* (onboarding, the dashboard) and *"which exam am I heading for?"* (sign-up, the bursary
    application). For a Form Six student sitting STPM now, those genuinely disagree — she holds SPM
    results and no STPM ones — and the single field can only carry one answer. The declared one
    wins, which is how application #106 came to be labelled STPM with no STPM results behind it,
    and (worse) ranked on an STPM CGPA that does not exist, so she carried no merit figure at all.

    ⚠ IT RELIES ON ABSENCE, NEVER ON PRESENCE, and that asymmetry is the whole safety of it.
    Absent STPM data is conclusive — there is nothing to hold. PRESENT STPM data proves nothing,
    because this profile is shared with the course guide and anyone may type STPM grades there to
    explore programmes. Application #15 carries a 4.0 CGPA and five STPM subjects and sat none of
    them: she took SPM in 2025 and is on a MATRICULATION course (owner, 2026-08-18). So the
    tempting 'latest results we hold' rule would have re-labelled a matriculation student as STPM
    and re-based her merit onto a CGPA she never sat — on an AWARDED record. Measured before
    writing this: the wide rule moves 3 live records, the narrow one moves exactly 1.

    ⚠ NOT A GATE, AND MUST NOT BECOME ONE. `shortlisting` (who is shortlisted), `pool` (the
    sponsor-facing band), `income_engine` (the semester-result gap) and `vision` (which slip parser
    runs) all read `exam_type` for their own reasons and are correct to. This answers a display
    question for the admin surface only. Widening it re-bands live applicants.

    Self-correcting: the day her STPM results land, this returns 'stpm' again with nobody
    remembering to change anything.
    """
    if not p:
        return ''
    declared = (getattr(p, 'exam_type', '') or '').strip().lower()
    if declared == 'stpm' and not _has_stpm_results(p) and (p.grades or {}):
        return 'spm'
    return declared


def _application_merit_score(obj):
    """The course-guide merit (0-100) used for ranking — a single number rolling up grades
    + co-curriculum. SPM: computed academic+CoQ merit. STPM: the PNGK (CGPA) is the merit
    indicator. None if there's nothing to score. Derived LIVE from the persisted
    grades/CoQ/stream — there is no stored merit column (the inputs are the source of truth).

    ⚠ Keyed on `held_qualification`, NOT the declared `exam_type`. Ranking a student by results
    she does not have produces None, and a blank merit is not a low score — it is absence from the
    ordering altogether, which is how #106 became unsortable and uncomparable while looking fine.
    """
    p = obj.profile
    if not p:
        return None
    if held_qualification(p) == 'stpm':
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
    # The qualification we hold RESULTS for, not the one declared at sign-up — see
    # `held_qualification`. A Form Six student holds SPM results and reads SPM.
    qualification = serializers.SerializerMethodField()
    stpm_pngk = serializers.FloatField(source='profile.stpm_cgpa', read_only=True)
    spm_a_count = serializers.SerializerMethodField()
    # Source (the referring org, chosen at apply) + the course-guide merit, for the list table.
    referral_source = serializers.CharField(source='profile.referral_source', read_only=True, allow_null=True)
    merit_score = serializers.SerializerMethodField()
    # The student's preferred call language (en/ms/ta/mixed) — drives reviewer language matching.
    call_language = serializers.CharField(source='profile.preferred_call_language', read_only=True, allow_blank=True)
    assigned_to_id = serializers.IntegerField(source='assigned_to.id', read_only=True, default=None)
    assigned_to_name = serializers.CharField(source='assigned_to.name', read_only=True, default=None)
    # May this case change hands at all right now (Completed / interviewing only)? Computed here
    # so the list UI disables the dropdown rather than re-deriving the rule — an action the server
    # will refuse should not look available. See services.ASSIGNABLE_STATUSES.
    assignable = serializers.SerializerMethodField()
    # First-assignment readiness (mirrors the detail cockpit): all student tasks done OR the 5-day
    # submit-clock lapsed. The list dropdown disables a FIRST assignment while false, so it never
    # offers an assign the server would refuse with 'not_ready' (= services.is_ready_for_assignment,
    # the same value the detail serializer ships inside query_sla).
    ready_for_assignment = serializers.SerializerMethodField()

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'name', 'profile_id', 'cohort_code', 'qualification',
            'spm_a_count', 'stpm_pngk', 'referral_source', 'merit_score', 'call_language',
            'status', 'bucket', 'shortlist_reason',
            'submitted_at', 'profile_completed_at',
            'assigned_to_id', 'assigned_to_name', 'assignable', 'ready_for_assignment',
            # When set, the list pill shows "Reopened" (overriding accepted/rejected).
            'decision_reopened_at',
        ]

    def get_assignable(self, obj):
        from .services import is_assignable
        return is_assignable(obj)

    def get_ready_for_assignment(self, obj):
        from .services import is_ready_for_assignment
        return is_ready_for_assignment(obj)

    def get_name(self, obj):
        return _full_name(obj)

    def get_qualification(self, obj):
        return held_qualification(obj.profile)

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
    # The qualification we hold RESULTS for, not the one declared at sign-up — see
    # `held_qualification`. A Form Six student holds SPM results and reads SPM.
    qualification = serializers.SerializerMethodField()
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
    interview_agenda = serializers.SerializerMethodField()   # V3 (#9): folded Check-3 agenda
    verdict = serializers.SerializerMethodField()
    submission_review = serializers.SerializerMethodField()
    query_sla = serializers.SerializerMethodField()
    funding_estimate = serializers.SerializerMethodField()
    resolution_items = serializers.SerializerMethodField()
    completeness = serializers.SerializerMethodField()
    consent_blockers = serializers.SerializerMethodField()
    # The "you haven't submitted yet" nudge state (drives the Blockers-box reminder button):
    # applicable / sent_at / available / available_at. Server-computed — the FE only renders it.
    nudge = serializers.SerializerMethodField()
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
    recommended_by_name = serializers.SerializerMethodField()
    # The QC floor override. Written since the V5 gate shipped and, until now, exposed NOWHERE —
    # not on this payload, not in the web app. The endpoint's own comment says "the override
    # leaves a trail", and it left one in the table rather than on any trail a person walks.
    # A reason nobody can read provides no accountability, which is the entire point of
    # demanding one before a red fact can be accepted.
    qc_override_by_name = serializers.SerializerMethodField()
    rejected_by_name = serializers.SerializerMethodField()
    assigned_to_id = serializers.IntegerField(source='assigned_to.id', read_only=True, default=None)
    assigned_to_name = serializers.CharField(source='assigned_to.name', read_only=True, default=None)
    # Internal-only correction tally for the assigned reviewer (reopened decisions that
    # led to a real change). Shown in the assign panel; never on a sponsor/student surface.
    assigned_to_corrections = serializers.SerializerMethodField()
    # Decision-reopen state: when set, the decision panel is editable + the reviewer
    # dropdown unlocks + a "held from sponsors" banner shows. The open reason drives the banner.
    decision_reopen_reason = serializers.SerializerMethodField()
    # The most recent reopen (open OR closed) as a compact record for the decision-history
    # trail on a decided case: who reopened, the reviewer it's attributed to (the original
    # recommender), the reason, and when. None when the case was never reopened. This is what
    # lets a rejected card read "recommended by X → reopened by Y (reason) → declined by Z"
    # instead of hiding the reviewer's recommendation behind a lone "Declined by …" line.
    last_decision_reopen = serializers.SerializerMethodField()
    # Whether the (dark-by-default) Conditional Bursary Agreement feature is live — the cockpit
    # only renders the agreement panel when this is on (otherwise its signing flow doesn't exist).
    bursary_agreement_enabled = serializers.SerializerMethodField()
    # TD-144: the real loaded agreement (signature timestamps + derived status + signed PDF
    # URL) so the cockpit panel shows ACCURATE four-party ticks instead of an optimistic
    # default. None when the flag is off or no agreement exists yet. No donor field.
    bursary_agreement = serializers.SerializerMethodField()
    # Post-award S4: the money-out tranche ledger (admin-facing; no sponsor identity).
    disbursements = serializers.SerializerMethodField()
    # Payments module (P2): the Vircle account ID (display; edited via the detail PATCH,
    # gated to super/org_admin), the paid-to-date (SUM of released disbursements), and the
    # paid-ahead credit — all read-only here.
    vircle_id = serializers.CharField(read_only=True)
    payment_credit = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    paid_to_date = serializers.SerializerMethodField()
    # Standardised bursary (2026-06-29; by-type-only 2026-07-04): the pathway-derived amount the
    # cockpit shows + auto-applies on approve — always the STANDARD figure for the pathway type
    # (RM2k/3k/1k), never null now. award_amount is the persisted value. award_disqualifier still
    # names any confident marker (offer_not_official / income_above_b40_line) so the cockpit can
    # show it as a red fact — it no longer zeroes the amount (see award.py).
    proposed_award_amount = serializers.SerializerMethodField()
    award_disqualifier = serializers.SerializerMethodField()
    # Cockpit "verified value" reconciliation (2026-07-15) for the field-level ticks: does the
    # DOCUMENT-derived household income / itemised roster corroborate the student's stated income
    # and size? Non-mutating — a mismatch is flagged for the reviewer, never auto-applied.
    household_check = serializers.SerializerMethodField()
    # Read-time institution fill for a multi-campus POLY diploma (see get_chosen_programme).
    chosen_programme = serializers.SerializerMethodField()
    # The display split {title, stream}: a degree+specialisation pathway (PISMP) shows the CONSTANT
    # degree as the programme + the bidang on its own Stream/Bidang row; STPM/Matric carry the track;
    # else stream is ''. One backend home (card_display.programme_split) so the cockpit just renders.
    chosen_programme_display = serializers.SerializerMethodField()
    documents = ApplicantDocumentSerializer(many=True, read_only=True)
    referees = RefereeSerializer(many=True, read_only=True)
    consents = ConsentSerializer(many=True, read_only=True)
    # Go-live transition (T2): the student's referring organisation (the source) and the
    # witness-org OVERRIDE. The cockpit shows the witness dropdown for a SOURCELESS student
    # (referred_by_org is null) so an org_admin can assign one; witness_org is the current
    # override. Each is {id, code, name} or null.
    referred_by_org = serializers.SerializerMethodField()
    witness_org = serializers.SerializerMethodField()

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'name', 'school', 'nric', 'nric_verified', 'profile_id', 'qualification',
            'spm_a_count', 'merit_score', 'stpm_pngk', 'household_income', 'household_size',
            'receives_str', 'receives_jkm', 'intended_pathway', 'intends_tertiary_2026',
            'aspirations', 'plans', 'fears', 'justification',
            'address', 'postal_code', 'city', 'preferred_state',
            'contact_phone', 'contact_email', 'notify_email', 'verified_email', 'preferred_call_language', 'referral_source', 'guardians',
            'referred_by_org', 'witness_org',
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
            # Standardised assistance (2026-06-29): pathway-derived proposed amount + the
            # confident-disqualifier code (null = none; drives the cockpit "no amount" reason).
            'proposed_award_amount', 'award_disqualifier',
            # Rejection bucket (merit/need/ineligible/interview/contractual/incomplete) + stamps.
            # rejection_comments = the org-admin's verbatim reason ('incomplete' only). ADMIN
            # SERIALIZER ONLY — it must never reach the student-facing ApplicationReadSerializer.
            'rejection_category', 'rejected_at', 'rejected_by', 'rejected_by_name',
            'rejection_comments',
            # Closure bucket (post-award lifecycle): graduated/completed/withdrawn/lapsed/terminated
            'closure_reason', 'closed_at', 'closed_by',
            # Lifecycle transition stamps — the DATE first reached each milestone; drive the
            # cockpit header timeline (Submitted·Recommended·Awarded → Awarded·Active·Maintenance).
            'recommended_at', 'recommended_by', 'recommended_by_name',
            'awarded_at', 'active_at', 'maintenance_at',
            # The QC floor override — who accepted a case over a RED fact, when, and why.
            'qc_override_by', 'qc_override_by_name', 'qc_override_at', 'qc_override_reason',
            # The QC floor override — who accepted a case over a RED fact, when, and why.
            # S5: operational maintenance sub-state (on_track/probation/on_hold/ready_to_close)
            'maintenance_substate',
            # Cool-off (#13/#14): a scheduled-but-unrevealed decline / award confirmation +
            # its reveal date — drives the cockpit "scheduled — cancel/hold" banners.
            'pending_rejection_category', 'decline_due_at', 'award_due_at',
            # Phase C handoff + interview funnel
            'profile_completed_at', 'completeness', 'consent_blockers', 'nudge', 'interview_session',
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
            'chosen_programme', 'chosen_programme_display', 'uncertainty_reasons', 'uncertainty_note',
            # NB chosen_programme is a SerializerMethodField (get_chosen_programme) — fills a
            # blank POLY-diploma institution live from the offer (see the method).
            # S3: normalised (sortable) offer reporting date.
            'reporting_date',
            # Income wizard answers — drive the cockpit's route-aware income document panel.
            'income_route', 'income_earner', 'income_working_members',
            'household_check',
            'funding_need', 'documents', 'referees', 'consents', 'sponsor_profile',
            'anomalies',
            'interview_agenda',
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
            'decision_reopened_at', 'decision_reopen_reason', 'last_decision_reopen',
            'assigned_to_corrections', 'bursary_agreement_enabled', 'bursary_agreement',
            # Post-award S4: the disbursement/tranche ledger (cockpit money-out panel).
            'disbursements',
            # Payments module (P2): Vircle account ID + paid-to-date + paid-ahead credit.
            'vircle_id', 'payment_credit', 'paid_to_date',
        ]

    def get_disbursements(self, obj):
        from .disbursement import disbursement_dict
        return [disbursement_dict(d) for d in obj.disbursements.all()]

    def get_paid_to_date(self, obj):
        from . import payments
        return str(payments.paid_to_date(obj))

    def _verdict(self, obj):
        """Compute the four-fact verdict ONCE per serialised application — get_verdict,
        get_proposed_award_amount and get_award_disqualifier all share it."""
        cached = getattr(obj, '_cached_verdict', None)
        if cached is None:
            from .verdict_engine import build_verdict
            cached = build_verdict(obj)
            obj._cached_verdict = cached
        return cached

    def get_proposed_award_amount(self, obj):
        from .award import proposed_award_amount
        amount = proposed_award_amount(obj, verdict=self._verdict(obj))
        return None if amount is None else str(amount)

    def get_award_disqualifier(self, obj):
        from .award import verdict_disqualifier
        return verdict_disqualifier(self._verdict(obj)) or None

    def get_assigned_to_corrections(self, obj):
        from .reopen import reviewer_correction_count
        return reviewer_correction_count(obj.assigned_to)

    def get_bursary_agreement_enabled(self, obj):
        from django.conf import settings
        return bool(getattr(settings, 'BURSARY_AGREEMENT_ENABLED', False))

    def get_bursary_agreement(self, obj):
        from django.conf import settings
        if not getattr(settings, 'BURSARY_AGREEMENT_ENABLED', False):
            return None
        agreement = getattr(obj, 'bursary_agreement', None)
        if agreement is None:
            return None
        from .serializers import BursaryAgreementSerializer
        return BursaryAgreementSerializer(agreement).data

    def get_decision_reopen_reason(self, obj):
        if obj.decision_reopened_at is None:
            return ''
        from .reopen import open_reopen
        row = open_reopen(obj)
        return row.reason if row else ''

    def get_last_decision_reopen(self, obj):
        from .reopen import latest_reopen
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

    def get_name(self, obj):
        return _full_name(obj)

    def get_verified_by_name(self, obj):
        return _admin_name_by_email(obj.verified_by)

    def get_verdict_decided_by_name(self, obj):
        return _admin_name_by_email(obj.verdict_decided_by)

    def get_recommended_by_name(self, obj):
        return _admin_name_by_email(obj.recommended_by)

    def get_qc_override_by_name(self, obj):
        return _admin_name_by_email(obj.qc_override_by)

    def get_rejected_by_name(self, obj):
        return _admin_name_by_email(obj.rejected_by)

    def get_school(self, obj):
        return getattr(obj.profile, 'school', '') if obj.profile else ''

    @staticmethod
    def _org_dict(org):
        return {'id': org.id, 'code': org.code, 'name': org.name} if org else None

    def get_referred_by_org(self, obj):
        return self._org_dict(getattr(getattr(obj, 'profile', None), 'referred_by_org', None))

    def get_witness_org(self, obj):
        return self._org_dict(obj.witness_org)

    def get_spm_a_count(self, obj):
        from .shortlisting import count_spm_a_grades
        return count_spm_a_grades(getattr(obj.profile, 'grades', None)) if obj.profile else 0

    def get_qualification(self, obj):
        return held_qualification(obj.profile)

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

    def get_household_check(self, obj):
        """Document-vs-stated reconciliation for the cockpit income/size verified ticks
        (2026-07-15). Non-mutating: reports what the documents/roster say and whether they
        corroborate the student's stated figures — the reviewer reconciles a mismatch."""
        from . import income_engine
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

    def get_chosen_programme(self, obj):
        """Serve the stored chosen_programme, but fill a BLANK institution for a multi-campus
        POLY diploma from the student's live offer (the selection tree offers only a programme, so
        the offer is the sole campus source — owner 2026-07-17). Read-time so it can't go stale
        waiting for a re-run/backfill; catalogue-validated + poly-only in the helper, and it never
        overwrites a non-blank institution. The write-side merge still fills the STORED value on
        offer upload; this guarantees the cockpit is right even when that hasn't fired yet."""
        from . import offer_pathway as op
        cp = obj.chosen_programme if isinstance(obj.chosen_programme, dict) else {}
        if (cp.get('course_id') or '').startswith('POLY-') and not (cp.get('institution') or '').strip():
            inst = op.poly_institution_from_live_offer(obj)
            if inst:
                return {**cp, 'institution': inst}
        return cp

    def get_chosen_programme_display(self, obj):
        """The {title, stream} display split (card_display.programme_split): PISMP shows the constant
        degree as the title + the bidang as the stream; STPM/Matric carry the track; else stream=''."""
        from . import card_display
        return card_display.programme_split(obj)

    def get_interview_agenda(self, obj):
        """The interviewer's folded Check-3 agenda — anomalies + the 'needs interview' verdict
        ambers + a standing Motivation & grit section. Open Check-2 queries / doc-requests are NOT
        echoed here (owner 2026-07-06); they stay in Check-2 Outstanding. ``[{code, kind, params}]``."""
        from .views_admin import interview_agenda_full
        return interview_agenda_full(obj)

    def get_verdict(self, obj):
        """S1 verification verdict: the four-fact rollup the coordinator audits
        (identity / academic / income / pathway). Pure deterministic engine, no
        LLM calls — mirrors get_anomalies."""
        return self._verdict(obj)

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
        from .check2_queries import clarify_overflow_count
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

    def get_consent_blockers(self, obj):
        """The exact gate that must clear before a shortlisted student can submit — the SAME
        list the consent POST enforces (missing/mismatched docs, offer-not-official, an
        incomplete section, an IC identity issue). Lets the cockpit answer "why can't this
        student submit yet?" instead of the owner guessing. Empty = ready to submit."""
        from .services import consent_blockers
        return consent_blockers(obj)

    def get_nudge(self, obj):
        """The "you haven't submitted yet" reminder state for the cockpit button — applicable /
        sent_at / available / available_at (see nudge.nudge_state). Server is the single source
        of truth; the FE only renders it."""
        from .nudge import nudge_state
        return nudge_state(obj)

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
    (student/sponsor) serializer.

    ⚠ **One inward widening, and it is PARTIAL** (owner, 2026-08-02, request #10). The reviewers
    surface (`AdminReviewerDetailView`) shows an org_admin the credentials, the languages and the
    PHONE of their own organisation's reviewers — the person handing out cases needs to reach
    them. It does **not** serialise the ADDRESS fields, and must not start to: assigning a case
    is no reason to read where somebody lives. `share_phone_with_students` travels with the phone
    so the screen can say which number a student may be given; showing a withheld number without
    that caveat would defeat the consent this organisation asked the reviewer for.

    Recorded in `docs/scholarship/role-matrix.md`; a test in `test_reviewers_surface.py` asserts
    the address cannot appear in that payload. Widen it only by owner decision, doc first."""

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


class FundingSummaryRowSerializer(serializers.Serializer):
    """Sprint 14 — one student's line in the Payments FUNDING SUMMARY.

    **Allowlist by construction** (the `SponsorPoolCardSerializer` pattern): a plain
    ``Serializer`` where every field is explicit and derived, with ZERO model passthrough — so
    a new column on `ScholarshipApplication` can never reach this payload by accident. Input is
    a `ScholarshipApplication`.

    This is the ONLY student data the `finance` role ever sees, so the boundary is drawn at
    "what do you need to reconcile a payment run": who, how much was awarded, how much has been
    paid, what is left, which eWallet it goes to, and when they were last paid. Deliberately
    EXCLUDED and not to be added without a role-matrix change: NRIC, contact details, address,
    documents, income figures, verdicts, academic results, narrative — none of it is needed to
    check a payment, and finance has no B40 scope to see it through. A snapshot test pins the
    exact key set so a well-meant addition fails loudly.

    ``name`` is included on purpose: a payment file is made of named people, and finance must be
    able to match a line to the Vircle CSV. It is NOT a link — the frontend renders it as plain
    text, because finance has no applicant route to link to.
    """
    application_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    ref = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    pathway = serializers.SerializerMethodField()
    award_amount = serializers.SerializerMethodField()
    paid_to_date = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    vircle_id = serializers.SerializerMethodField()
    last_run = serializers.SerializerMethodField()
    # P2b — WHICH GIFT funds this student. Finance reconciles per programme once an org runs
    # more than one, and a payment file is drawn from one gift's money. A column, deliberately
    # not a grouping: grouping is a layout change to a live finance screen and owes a design
    # pass; the fact itself is useful now and costs no redesign.
    programme = serializers.SerializerMethodField()

    # Coarse funding status — the three payable states, nothing finer. A finance admin needs to
    # know a student is in the paying loop, not where they sit in the review funnel.
    _STATUS = {'awarded': 'awarded', 'active': 'active', 'maintenance': 'maintenance'}

    def get_application_id(self, obj):
        return obj.id

    def get_name(self, obj):
        return (getattr(getattr(obj, 'profile', None), 'name', '') or '').strip()

    def get_ref(self, obj):
        return pool.pool_ref(obj.id) or ''

    def get_status(self, obj):
        return self._STATUS.get(obj.status, '')

    def get_pathway(self, obj):
        return (obj.chosen_pathway or '').strip()

    def get_award_amount(self, obj):
        return str(obj.award_amount or 0)

    def get_paid_to_date(self, obj):
        from . import payments
        return str(payments.paid_to_date(obj))

    def get_remaining(self, obj):
        from . import payments
        award = obj.award_amount or 0
        rem = award - payments.paid_to_date(obj)
        return str(rem if rem > 0 else 0)

    def get_vircle_id(self, obj):
        return (obj.vircle_id or '').strip()

    def get_programme(self, obj):
        """The gift funding this student — ``{id, name}`` or None. Name only (no code, no
        organisation): finance needs to tell two gifts apart, not to navigate the tenancy."""
        p = getattr(obj, 'programme', None)
        if p is None:
            return None
        return {'id': p.id, 'name': (p.name_en or '').strip()}

    def get_last_run(self, obj):
        """The newest COMPLETED run this student was paid in — {reference, payment_date}, or
        None. Answers "when did we last pay them?" without exposing the run's other students."""
        item = (obj.payment_run_items
                .filter(included=True, run__status='completed')
                .select_related('run').order_by('-run__payment_date', '-run_id').first())
        if item is None:
            return None
        return {'reference': item.run.reference, 'payment_date': item.run.payment_date}


# ── Requests space (Sprint 15) ────────────────────────────────────────────────────

def _serialize_org_request_attachments(org_request):
    """The attachment list carried by BOTH request serializers (Sprint 15.1). Each entry is a
    minimal allowlist — {id, original_filename, content_type, size, created_at, download_url}. The
    ``download_url`` is a signed URL with the SAME org assertion as ``ApplicantDocumentSerializer``:
    a blob whose key-org disagrees with the request's org signs to None (belt-and-braces cross-org
    guard on top of the org-fenced endpoint reads)."""
    from .storage import create_signed_download_url, resolve_org_for_path
    org_id = getattr(org_request, 'organisation_id', None)
    out = []
    for att in org_request.attachments.all():
        path_org = resolve_org_for_path(att.storage_path)
        download_url = (None if (path_org is not None and org_id is not None and path_org != org_id)
                        else create_signed_download_url(att.storage_path))
        out.append({
            'id': att.id,
            'original_filename': att.original_filename,
            'content_type': att.content_type,
            'size': att.size,
            'created_at': att.created_at,
            'download_url': download_url,
        })
    return out


def _comment_dicts(req, *, viewer_is_org):
    """The discussion as this viewer may see it (TD-201).

    ⚠ The visibility filter is a ROW filter, and that is why it cannot live in the serializer's
    field list. An allowlist protects against a FIELD reaching the wrong audience; it does nothing
    about a row the audience may not read — a serializer naming `body` renders an internal comment
    just as happily as a shared one. So both serializers call this, and the org one passes
    ``viewer_is_org=True``.

    `author_name` is the person, resolved for display; the AI has none.
    """
    from . import org_requests
    out = []
    for c in org_requests.comments_for(req, viewer_is_org=viewer_is_org):
        out.append({
            'id': c.id,
            'author_kind': c.author_kind,
            'author_name': getattr(c.author_admin, 'name', '') or '',
            'body': c.body,
            'visibility': c.visibility,
            'awaiting_reply': c.awaiting_reply,
            'created_at': c.created_at,
        })
    return out


class OrgRequestOrgSerializer(serializers.Serializer):
    """The ORG-FACING view of an OrgRequest (what a submitting org_admin sees).

    **Allowlist by construction** — a plain ``Serializer`` with every field explicit and ZERO model
    passthrough, so nothing reaches the org that is not named here. An exact-key snapshot test pins
    the set, so a new field cannot slip in and a deliberate change has to be made twice.

    **The AI split (owner ruling, TD-202, 2026-07-30). The three ``ai_draft_*`` fields do NOT
    deserve the same answer:**

    * ``ai_draft_note`` + ``ai_draft_model`` — **SENT.** This is the reasoning that justifies the
      quote, and withholding it made a price look arbitrary. The owner found the gap by filing
      request #4 as an org_admin and seeing silence: the reviewer had in fact answered in 21
      seconds with an accurate reading of the bug, into a room the requester was not in.
    * ``ai_draft_hours`` — **WITHHELD**, and NOT for commercial reasons (the margin is already
      absent and ``quote_hours`` is sent when the owner quotes). The estimate is *demonstrably
      unreliable*: the model has no codebase context, so it quoted 24h for work that was largely
      already built and 8h for a change whose mailer already existed. Publishing an untrustworthy
      number as the justification for a price makes it the figure the real quote must argue against.
    * ``triaged_kind`` / ``lane`` / ``triage_note`` — **WITHHELD.** The owner's private judgement.
      They already have two channels that DO reach the org (the ``ask`` thread and the quote note)
      and used the quote note for exactly this on #3; opening the private note would cost the
      ability to be blunt and buy nothing.

    ⚠ **``ai_draft_note`` is free-form model prose, so it MAY state an hours figure even though
    ``ai_draft_hours`` is withheld.** Accepted knowingly: the owner sets the final quote regardless,
    so this is negotiation optics, not correctness. If it becomes a nuisance, the cheap fix is an
    instruction in the review prompt telling the reviewer not to state hours in its rationale —
    not a filter here.

    The org also sees: the QUOTE (hours + note — **the MARGIN is not sent**, owner 2026-07-30), the
    schedule/approval stamps, and the clarification thread.

    Input is an ``OrgRequest``.
    """
    id = serializers.IntegerField()
    kind = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    # Optional Bugzilla-style scoping (Sprint 15 increment) — org-SUBMITTED, so org-visible.
    component = serializers.CharField()
    urgency = serializers.CharField()
    steps_to_reproduce = serializers.CharField()
    status = serializers.CharField()
    # TD-201: the discussion, filtered to SHARED. `clarifications` is retired — nothing reads it
    # after 2026-07-31 (the column survives one sprint so the migrated copy can be verified against
    # the original on production; its drop is logged as its own follow-up).
    comments = serializers.SerializerMethodField()
    # The reviewer's REASONING and which model produced it — sent, per TD-202. `ai_draft_hours`
    # stays absent: see the class docstring for why the three fields split three ways.
    ai_draft_note = serializers.CharField()
    ai_draft_model = serializers.CharField()
    ai_draft_at = serializers.DateTimeField()
    quote_hours = serializers.SerializerMethodField()
    # `analyses` is DELIBERATELY ABSENT (TD-204, owner 2026-07-31). The engineer's analysis reaches
    # this organisation as PROSE, through `comments` — that is the reasoning, and TD-202 settled
    # that reasoning is shared. What stays behind is the CITED FILES (internal shape of a
    # multi-tenant platform, and unopenable by the requester anyway) and the ENGINEER'S HOURS (a
    # second figure in front of them recreates exactly what removing the AI's estimate fixed).
    # Read OrgRequestAnalysis's docstring before adding a counterpart here; the omission is a
    # decision, not an oversight.
    # quote_margin_pct is DELIBERATELY ABSENT (owner, 2026-07-30): "do not mention the margin".
    # Removed from the PAYLOAD, not merely hidden in the UI — a field the org must not see is a
    # field we must not send, which is the whole point of this allowlist. `quote_hours` is the
    # figure they accept and the only one anything bills on; nothing multiplies by the margin.
    # It remains on OrgRequestOwnerSerializer for the quote form.
    quote_note = serializers.CharField()
    quoted_at = serializers.DateTimeField()
    approved_at = serializers.DateTimeField()
    scheduled_for = serializers.DateField()
    decline_reason = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    submitted_by_name = serializers.SerializerMethodField()
    # Screenshot attachments (Sprint 15.1) — org-SUBMITTED evidence, so org-visible. Adds ONE key
    # to the exact-key snapshot (19 → 20); still no ai_* / triage key.
    attachments = serializers.SerializerMethodField()

    def get_comments(self, obj):
        # viewer_is_org=True — the ROW filter. An internal comment must never appear here.
        return _comment_dicts(obj, viewer_is_org=True)

    def get_quote_hours(self, obj):
        return str(obj.quote_hours) if obj.quote_hours is not None else None

    def get_submitted_by_name(self, obj):
        return (getattr(obj.submitted_by, 'name', '') or '').strip()

    def get_attachments(self, obj):
        return _serialize_org_request_attachments(obj)


class OrgRequestOwnerSerializer(serializers.Serializer):
    """The OWNER-FACING view (super) — every field incl. the AI draft + triage, plus the org
    id/name. Deliberately a SEPARATE serializer from the org one (never a shared serializer with a
    role-conditional field): the two payloads share no code, so a change to the owner view can't
    accidentally widen the org view. Input is an ``OrgRequest``."""
    id = serializers.IntegerField()
    organisation_id = serializers.IntegerField()
    organisation_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    kind = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    component = serializers.CharField()
    urgency = serializers.CharField()
    steps_to_reproduce = serializers.CharField()
    status = serializers.CharField()
    comments = serializers.SerializerMethodField()   # TD-201: the FULL thread, internal included
    analyses = serializers.SerializerMethodField()   # TD-204: OWNER-ONLY — files + hours live here
    ai_run_count = serializers.IntegerField()
    ai_draft_kind = serializers.CharField()
    ai_draft_lane = serializers.CharField()
    ai_draft_hours = serializers.SerializerMethodField()
    ai_draft_note = serializers.CharField()
    ai_draft_model = serializers.CharField()
    ai_draft_at = serializers.DateTimeField()
    triaged_kind = serializers.CharField()
    lane = serializers.CharField()
    triage_note = serializers.CharField()
    triaged_at = serializers.DateTimeField()
    quote_hours = serializers.SerializerMethodField()
    quote_margin_pct = serializers.IntegerField()
    quote_note = serializers.CharField()
    quoted_at = serializers.DateTimeField()
    approved_at = serializers.DateTimeField()
    scheduled_for = serializers.DateField()
    decline_reason = serializers.CharField()
    declined_by_role = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    attachments = serializers.SerializerMethodField()

    def get_attachments(self, obj):
        return _serialize_org_request_attachments(obj)

    def get_organisation_name(self, obj):
        return (getattr(obj.organisation, 'name', '') or '').strip()

    def get_submitted_by_name(self, obj):
        return (getattr(obj.submitted_by, 'name', '') or '').strip()

    def get_ai_draft_hours(self, obj):
        return str(obj.ai_draft_hours) if obj.ai_draft_hours is not None else None

    def get_comments(self, obj):
        # The owner sees the whole thread, internal notes included.
        return _comment_dicts(obj, viewer_is_org=False)

    def get_analyses(self, obj):
        """The engineer's working papers (TD-204) — OWNER-ONLY, newest first.

        ⚠ This is the ONE place `cited_files` and `estimated_hours` are serialised anywhere. The
        org-facing serializer deliberately has no counterpart: see OrgRequestAnalysis's docstring
        for why neither is secrecy (a citation the requester cannot open buys them nothing, and a
        second hours figure recreates the problem TD-202 removed from the AI). If you are adding a
        matching field to the org payload, read that docstring first — the omission is a decision.
        """
        from . import org_requests
        current = org_requests.approved_analysis(obj)
        out = []
        for a in obj.analyses.all().select_related('approved_by').order_by('-id'):
            out.append({
                'id': a.id,
                'body': a.body,
                'estimated_hours': str(a.estimated_hours) if a.estimated_hours is not None else None,
                'cited_files': list(a.cited_files or []),
                'authored_by': a.authored_by,
                'repo_sha': a.repo_sha,
                # The engineer's PROPOSED triage — prefills the owner's form, applies nothing.
                # OWNER-ONLY like everything else here: what the organisation is told is the prose,
                # and "we think this one is chargeable" is not a conclusion to hand them before the
                # owner has ruled on it.
                'proposed_kind': a.proposed_kind,
                'proposed_lane': a.proposed_lane,
                'created_at': a.created_at,
                'approved_at': a.approved_at,
                'approved_by_name': (getattr(a.approved_by, 'name', '') or '').strip(),
                'superseded_at': a.superseded_at,
                # The one the quote gate reads — so the screen and the gate cannot disagree about
                # which analysis is standing.
                'is_current': bool(current and a.id == current.id),
            })
        return out

    def get_quote_hours(self, obj):
        return str(obj.quote_hours) if obj.quote_hours is not None else None
