"""
B40 Assistance Programme — data models.

Phase 1 (intake & profile engine). Sponsor and money models arrive in
Phases 2-3. See docs/scholarship/b40-assistance-prd.md and
docs/scholarship/b40-phase1-roadmap.md.
"""
from django.db import models


class ScholarshipCohort(models.Model):
    """
    A single application round. Holds the configurable shortlisting thresholds
    and funding parameters so they can be tuned without code changes (the
    shortlisting rules engine in Sprint 3 reads these).
    """
    code = models.CharField(
        max_length=50, unique=True,
        help_text="URL-safe slug, e.g. 'b40-2026'",
    )
    name = models.CharField(
        max_length=200,
        help_text="Display name, e.g. 'B40 Assistance Programme 2026'",
    )
    year = models.IntegerField()
    is_active = models.BooleanField(default=True)
    is_open = models.BooleanField(
        default=True, help_text="Currently accepting new applications",
    )

    # Shortlisting thresholds (consumed by the rules engine in Sprint 3)
    # Academic floor (S8 redesign): SPM needs >= min_spm_a_count grades at A-/A/A+ AND
    # >= min_spm_bplus_count grades at B+ or better; STPM needs PNGK >= min_stpm_pngk.
    min_spm_a_count = models.IntegerField(
        default=4, help_text="Minimum SPM grades at A- or better (A+/A/A- all count)",
    )
    min_spm_bplus_count = models.IntegerField(
        default=5,
        help_text="Minimum SPM grades at B+ or better (the '+1 B+' beyond the A's → 5 strong subjects)",
    )
    min_stpm_pngk = models.FloatField(
        default=2.9, help_text="Minimum STPM PNGK (academic floor)",
    )
    income_ceiling = models.IntegerField(
        null=True, blank=True,
        help_text="B40 monthly household income ceiling in RM (reference; the income gate uses per_capita_ceiling)",
    )
    per_capita_ceiling = models.IntegerField(
        default=1584,
        help_text="Per-capita monthly income ceiling in RM for non-STR applicants (household_income / "
                  "household_size). RM5,860 B40 ceiling / 3.7 avg household = RM1,584 (DOSM 2024).",
    )
    bucket_b_margin = models.IntegerField(
        default=1,
        help_text="DEPRECATED (pre-S8 marginal-miss logic); unused by the current engine",
    )

    # Funding + workflow parameters (consumed by later sprints)
    funding_envelope = models.IntegerField(
        null=True, blank=True, help_text="Per-student funding envelope in RM",
    )
    fail_email_delay_days = models.IntegerField(
        default=3,
        help_text="DEPRECATED (pre-S8); the scheduler now uses success/decline_delay_hours",
    )
    success_delay_hours = models.FloatField(
        default=48,
        help_text="Hours after submit before the shortlist (invitation) email + follow-up unlock (S8 delayed "
                  "reveal). Float so sub-hour delays are possible (e.g. 0.9167 = 55 minutes).",
    )
    decline_delay_hours = models.FloatField(
        default=48,
        help_text="Hours after submit before the warm decline email (S8 delayed reveal). Float (see above).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scholarship_cohorts'
        ordering = ['-year', 'code']

    def __str__(self):
        return f'{self.name} ({self.code})'


class ScholarshipApplication(models.Model):
    """
    One application by one student to one cohort.

    Captures the shortlisting-relevant intake fields explicitly (so the rules
    engine can score them) plus a free-form ``form_data`` blob for everything
    else the native form collects.
    """
    QUALIFICATION_CHOICES = [('spm', 'SPM'), ('stpm', 'STPM')]
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('shortlisted', 'Shortlisted'),
        # Phase C post-shortlist funnel (between shortlisted and accepted):
        ('profile_complete', 'Profile complete'),  # student confirmed a complete Step-4 profile
        ('interviewing', 'Interviewing'),           # an interview session has been started
        ('interviewed', 'Interviewed'),             # interview captured + submitted
        ('accepted', 'Accepted'),      # admin verified & accepted (S11a) — confirmed for award
        ('sponsored', 'Sponsored'),    # Phase E3: a sponsor's award was accepted — student leaves the pool
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
        # Auto-closed: shortlisted but never completed after the full reminder
        # sequence (R1–R4 + a 5-day final grace). The student may start a fresh
        # application — an 'expired' app never blocks a new one.
        ('expired', 'Expired (not completed in time)'),
    ]
    BUCKET_CHOICES = [('', 'Unassigned'), ('A', 'Bucket A'), ('B', 'Bucket B')]
    UPU_CHOICES = [
        ('applied', 'Applied through UPU'),
        ('public_other', 'Plan STPM / Matrikulasi / PISMP / TVET'),
        ('ipts', 'Plan to study at IPTS'),       # IPTS-only is a disqualifier (engine, S8)
        ('unknown', 'Unsure what UPU is'),
    ]
    HELP_CHOICES = [('yes', 'Yes'), ('no', 'No'), ('unsure', 'Not sure')]

    cohort = models.ForeignKey(
        ScholarshipCohort, on_delete=models.PROTECT,
        related_name='applications',
    )
    profile = models.ForeignKey(
        'courses.StudentProfile', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='scholarship_applications',
        help_text="Linked HalaTuju profile (always set in the apply-first flow)",
    )

    # Per-application fields only. Person-level data (grades, household_income,
    # household_size, receives_str/jkm, exam_type) lives on the linked
    # StudentProfile — the single source of truth. The shortlisting engine reads
    # those from the profile; this row never duplicates them.
    intended_pathway = models.CharField(
        max_length=50, blank=True, default='',
        help_text="e.g. asasi, matrik, stpm, pismp, diploma, degree",
    )
    intends_tertiary_2026 = models.BooleanField(default=True)
    consent_to_contact = models.BooleanField(
        default=False,
        help_text="Consent to be contacted about this application "
                  "(sponsor-sharing consent is collected later)",
    )
    # Phase E3: the admin-approved award amount a sponsor funds in full. Non-identifying;
    # shown on the anonymised pool card. Null until an admin sets it (gates fundability).
    award_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # ── Plans + Support intake (Sprint 7, apply-form rebuild) ──────────────────
    # Collected at apply; drive the sponsor profile + mentoring. Some feed the
    # decision engine in S8 (e.g. upu_status='ipts'-only disqualifies). All optional
    # so older clients/tests that don't send them keep working.
    field_of_study = models.CharField(
        max_length=50, blank=True, default='',
        help_text="Intended field of study (taxonomy key/label)")
    pathways_considered = models.JSONField(
        default=list, blank=True,
        help_text="Post-SPM pathways being considered (non-exclusive): "
                  "['matrik','asasi','stpm','poly','kkom',...]")
    top_choices = models.JSONField(
        default=list, blank=True,
        help_text="Ranked top-3 choices: [{rank, course_id, course_name, institution}]")
    upu_status = models.CharField(
        max_length=20, blank=True, default='', choices=UPU_CHOICES,
        help_text="UPU / destination intent; 'ipts'-only is a disqualifier (S8)")
    other_scholarships = models.JSONField(
        default=list, blank=True,
        help_text="Other scholarships applied/held (keys): ['jpa','petronas','mara',...]")
    other_scholarships_text = models.CharField(
        max_length=300, blank=True, default='',
        help_text="Other scholarships not in the list (free text)")
    help_university = models.CharField(
        max_length=10, blank=True, default='', choices=HELP_CHOICES,
        help_text="Wants help with university applications")
    help_scholarship = models.CharField(
        max_length=10, blank=True, default='', choices=HELP_CHOICES,
        help_text="Wants help with scholarship applications & interviews")
    anything_else = models.TextField(
        blank=True, default='',
        help_text="'Anything else you'd like us to know' — narrative context only")
    mentoring_candidate = models.BooleanField(
        default=False,
        help_text="Flagged for mentoring (lost/unfocused); coordinator-facing, NOT a reject signal")

    # ── Plans redesign (context-aware, progressive disclosure) ────────────────
    # Source of truth for the student's stated pathway plan, captured on the
    # apply-form "Your Plans" step. All optional/additive (older clients keep
    # working). The decision gate still reads intends_tertiary_2026 + upu_status
    # ('ipts'-only disqualifies); upu_status is derived from chosen_pathway in the
    # frontend, so these fields don't change the shortlisting engine.
    pathway_certainty = models.CharField(
        max_length=10, blank=True, default='',
        choices=[('sure', 'Knows pathway'), ('uncertain', 'Still deciding')],
        help_text="Top split: does the student already know their pathway?")
    chosen_pathway = models.CharField(
        max_length=20, blank=True, default='',
        help_text="When sure: the pathway_type (matric/stpm/asasi/university/poly/"
                  "kkom/pismp/iljtm/ilkbs), or 'ipts'/'none' (→ upu_status='ipts').")
    pre_u_track = models.CharField(
        max_length=30, blank=True, default='',
        help_text="STPM bidang (sains/sains_sosial/not_sure) or Matric track "
                  "(sains/kejuruteraan/sains_komputer/perakaunan).")
    pre_u_institution = models.CharField(
        max_length=255, blank=True, default='',
        help_text="Chosen STPM school or Matriculation college name.")
    chosen_programme = models.JSONField(
        default=dict, blank=True,
        help_text="Single chosen programme when sure: {course_id, course_name, institution, source}.")
    uncertainty_reasons = models.JSONField(
        default=list, blank=True,
        help_text="When uncertain: reason keys ['waiting','guidance','financial','family','appeal','other'].")
    uncertainty_note = models.TextField(
        blank=True, default='',
        help_text="When uncertain: 'where are you right now?' free text (Plans step).")

    # ── Income evidence — Check-1 wizard answers (income fact, item 3) ───────
    # Drive the dynamic document requirements (see income_engine.income_requirements).
    # All additive/optional — blank until the student walks the wizard.
    INCOME_ROUTE_CHOICES = [('', 'Not chosen'), ('str', 'STR'), ('salary', 'Salary')]
    INCOME_EARNER_CHOICES = [
        ('', 'Not chosen'), ('father', 'Father'), ('mother', 'Mother'),
        ('guardian', 'Legal guardian')]
    EARNER_WORK_CHOICES = [
        ('', 'Not chosen'), ('payslip', 'Working — has payslip'),
        ('informal', 'Working — no payslip'), ('not_working', 'Not working')]
    income_route = models.CharField(
        max_length=10, blank=True, default='', choices=INCOME_ROUTE_CHOICES,
        help_text="Wizard Q1 'have an STR document?': yes→'str' route, no→'salary' route.")
    income_earner = models.CharField(
        max_length=10, blank=True, default='', choices=INCOME_EARNER_CHOICES,
        help_text="STR route only — whose income/STR is shown (single earner). Drives the relationship "
                  "proof: father=student-IC patronymic, mother=birth_certificate, guardian=guardianship_letter. "
                  "The SALARY route uses income_working_members (multi-select) instead.")
    # Salary (non-STR) route: the household members who currently work. Replaces the
    # single income_earner + earner_work_status + household_other_earners for that route.
    # Each ticked member gets their own IC + salary slip + EPF (tagged via
    # ApplicantDocument.household_member). Relationship proof: father/brother/sister via the
    # student-IC patronymic (siblings carry the same father's name), mother via birth cert,
    # guardian via letter. List of {father,mother,guardian,brother,sister}; additive, 0-row-safe.
    income_working_members = models.JSONField(
        default=list, blank=True,
        help_text="Salary route: household members who work (subset of "
                  "father/mother/guardian/brother/sister). Drives per-member income docs.")
    # DEPRECATED (salary route): Q3 work-status + Q4 other-earner are superseded by
    # income_working_members (informal is now inferred from 'IC present, no payslip/EPF').
    # Kept for the STR route's legacy reads + to avoid a destructive migration; drop later (tech debt).
    earner_work_status = models.CharField(
        max_length=12, blank=True, default='', choices=EARNER_WORK_CHOICES,
        help_text="DEPRECATED (salary route) — informal is now inferred. STR route unaffected.")
    household_other_earners = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="DEPRECATED — superseded by income_working_members (siblings ticked explicitly).")

    # Workflow
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='submitted',
    )
    bucket = models.CharField(
        max_length=1, choices=BUCKET_CHOICES, blank=True, default='',
    )
    shortlist_reason = models.TextField(
        blank=True, default='',
        help_text="Set by the shortlisting engine (which criterion missed)",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    # Shortlisting outcome + decision-email tracking (Sprint 3)
    shortlisted_at = models.DateTimeField(null=True, blank=True)
    # Phase C: stamped when the student explicitly confirms a complete Step-4
    # profile (status shortlisted → profile_complete). Completion is NOT a
    # freeze — the student can still add documents afterwards.
    profile_completed_at = models.DateTimeField(null=True, blank=True)
    # Phase C: the admin's "please send more documentation" request. Surfaced
    # read-only on the student's Step 4; does not change status.
    info_request_note = models.TextField(blank=True, default='')
    info_requested_at = models.DateTimeField(null=True, blank=True)
    # Phase B: Gemini-suggested interview questions ("gaps") from the typed
    # narrative — admin-on-demand only (never auto). Each item carries its own
    # dynamic text: {code, question, why}. Stored (not recomputed) + shown beside
    # the deterministic anomaly flags; captured into InterviewSession.findings by
    # code. List, additive, 0-row-safe.
    interview_gaps = models.JSONField(default=list, blank=True)
    interview_gaps_run_at = models.DateTimeField(null=True, blank=True)
    decision_email_sent_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the pass/fail decision email was sent",
    )
    # S8 delayed reveal: the engine computes the verdict silently at submit; the
    # scheduler flips status + sends the email at decision_due_at (submit + delay).
    verdict = models.CharField(
        max_length=20, choices=STATUS_CHOICES, blank=True, default='',
        help_text="Engine's computed outcome ('shortlisted'/'rejected'), stored at submit; "
                  "status stays 'submitted' until the scheduler releases it",
    )
    decision_due_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the verdict is revealed (submit + success/decline delay)",
    )
    decision_released_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the scheduler flipped status + sent the verdict email",
    )

    # Post-shortlist completion reminders + auto-close (the daily reminder job).
    # The cadence counts from reminder_anchor_at — normally = shortlisted_at (set
    # when the invitation is released), but it is a separate knob so a one-time
    # launch backfill (or an admin grace extension) can re-anchor the clock without
    # touching the audit timestamp. NULL anchor = not on the reminder track.
    reminder_anchor_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the completion-reminder clock starts (usually = shortlisted_at)",
    )
    # 0 = none sent yet; 1–4 = the last reminder stage sent (R1 +2d, R2 +9d,
    # R3 +23d, R4/final +53d). Drives idempotency — a stage is never re-sent.
    reminder_stage = models.PositiveSmallIntegerField(default=0)
    last_reminder_at = models.DateTimeField(null=True, blank=True)
    # When the application was auto-closed for non-completion (status → 'expired').
    expired_at = models.DateTimeField(null=True, blank=True)

    # Admin verify-&-accept (S11a): a PartnerAdmin confirms NRIC/name/results against
    # the uploaded MyKad, which sets profile.nric_verified (locks the NRIC) and
    # advances status → 'accepted'. These capture who/when/what was confirmed.
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text="Email of the PartnerAdmin who verified & accepted",
    )
    verify_checklist = models.JSONField(
        default=dict, blank=True,
        help_text="What the admin confirmed at accept: {nric, name, results, document: bool}",
    )

    # Pathway Check-1: the student confirms (via an AI-raised Action-Centre query, no
    # human officer) that the offer letter they uploaded IS their final chosen pathway.
    # On confirm, the offer's programme+institution are written to chosen_programme and
    # this is stamped — the Pathway fact then reads 'verified'.
    pathway_confirmed_at = models.DateTimeField(null=True, blank=True)

    # Rejection bucket — WHY/WHEN an application ended at status='rejected'. Pre-shortlist
    # rejections (merit/need/ineligible) are set automatically by the engine at submit; the
    # post-shortlist ones (interview/contractual) are set by an admin action. Drives which
    # decline email is sent and whether the Review & actions panel stays visible (only the
    # pre-shortlist buckets hide it — those applicants were never reviewed).
    REJECTION_CATEGORIES = [
        ('merit', 'Did not meet the academic/merit floor'),       # engine: academic floor
        ('need', 'Did not meet the financial-need criteria'),     # engine: income test
        ('ineligible', 'Out of scope / ineligible'),              # engine: consent/intent/IPTS gate
        ('interview', 'Reviewed but not selected'),               # admin: post-shortlist decline
        ('contractual', 'Failed post-award contractual steps'),   # admin: post-accept decline
    ]
    rejection_category = models.CharField(
        max_length=20, choices=REJECTION_CATEGORIES, blank=True, default='',
        help_text="Why the application was rejected; blank unless status='rejected'",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text="Email of the PartnerAdmin who rejected (post-shortlist buckets only); blank for engine rejections",
    )

    # Phase C: which reviewer this application is assigned to (for the interview
    # stage). Null = unassigned. SET_NULL so deactivating an admin doesn't delete
    # applications.
    assigned_to = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_applications',
        help_text="Phase C: the reviewer assigned to interview this applicant",
    )
    locale = models.CharField(
        max_length=2, default='en',
        help_text="Applicant's language at apply time (en/ms/ta) for deferred emails",
    )
    notify_email = models.EmailField(
        blank=True, default='',
        help_text="Resolved contact email captured at submit (for the deferred fail email)",
    )

    # Deeper info (STEP 2 — collected after shortlisting)
    aspirations = models.TextField(blank=True, default='')
    plans = models.TextField(blank=True, default='')
    fears = models.TextField(blank=True, default='')
    justification = models.TextField(
        blank=True, default='', help_text="Why the student needs assistance",
    )

    # ── "Your story" guided narrative fields (S2 redesign) ──────────────────
    # Collected on the 5-tab /scholarship/application Story tab (Card A + Card B).
    # All additive and optional — older clients/applications keep working without them.
    # Card A — About your family
    first_in_family = models.BooleanField(
        default=False,
        help_text="I would be the first in my family to go to university.",
    )
    parents_occupation = models.CharField(
        max_length=255, blank=True, default='',
        help_text="What do your parents or guardians do for a living?",
    )
    # TD-061: legacy `siblings_studying` boolean dropped — superseded by the
    # count below (S15). (Column removed in scholarship/0022.)
    siblings_studying_count = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="How many of the applicant's siblings are currently studying. "
                  "A proxy for how much education-funding burden the family carries. "
                  "Kept for back-compat; the income wizard now splits this into "
                  "school + tertiary below (the sum = studying).",
    )
    # Family burden (income wizard) — dependents in education. Tertiary weighs more (fees).
    siblings_in_school = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Family burden: dependents (siblings) currently in school.")
    siblings_in_tertiary = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Family burden: dependents (siblings) in pre-U / college / university.")
    family_context = models.TextField(
        blank=True, default='',
        help_text="Anything about your family's situation we should know?",
    )
    # Card B — About you (aspirations/plans/fears already above; daily_life is new)
    daily_life = models.TextField(
        blank=True, default='',
        help_text="What is your daily life like? Any responsibilities such as work or caring for family?",
    )

    # Truthfulness declaration + typed-name "signature" (captured at submit). The
    # student types their full name (as in their IC) to sign the declaration that
    # everything they've provided is true. declared_at stamps when they signed.
    # This is an attestation record, not identity proof — we only hold the name
    # they typed in About Me to compare against, never the official JPN record.
    declaration_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Full name typed by the student as their signature on the truthfulness declaration",
    )
    declared_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the student signed the truthfulness declaration (at submit)",
    )

    form_data = models.JSONField(
        default=dict, blank=True,
        help_text="Raw/extra intake fields from the native form",
    )
    intake_snapshot = models.JSONField(
        default=dict, blank=True,
        help_text="Immutable record of what the applicant declared at submit time "
                  "(profile + application fields). Audit evidence, NOT the live source.",
    )

    # ── S5 verdict audit / override capture (Verification-verdict roadmap) ──────
    # When the officer records their verdict in the review cockpit, we snapshot the
    # AI's four-fact verdict (build_verdict) AS IT WAS at decision time and store the
    # officer's own per-fact decision + reason beside it. This is the override-rate
    # evidence ("how good is the AI"): a query over verdict_decided_at IS NOT NULL
    # compares ai_verdict_snapshot vs officer_verdict per fact (see audit.py). Kept on
    # the application (one snapshot = the final officer decision) — additive, NOT a new
    # table, so it deploys via the simpler migrate-first ALTER (no contenttypes step).
    # NOTE: distinct from the engine's shortlist `verdict` field above (different concept).
    ai_verdict_snapshot = models.JSONField(
        default=list, blank=True,
        help_text="The four-fact verification verdict (build_verdict) captured when the "
                  "officer recorded their decision. List of {fact,status,evidence,unresolved}.",
    )
    officer_verdict = models.JSONField(
        default=dict, blank=True,
        help_text="The officer's own four-fact decision at the cockpit: "
                  "{identity,academic,income,pathway: 'pass'|'fail', overall: 'accept'|'decline'|'hold'}.",
    )
    verdict_reason = models.TextField(
        blank=True, default='',
        help_text="The officer's free-text reason/notes recorded with the verdict.",
    )
    verdict_decided_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text="Email of the PartnerAdmin who recorded the verification verdict.",
    )
    verdict_decided_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the officer recorded their verification verdict (the audit anchor).",
    )

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scholarship_applications'
        ordering = ['-submitted_at']
        constraints = [
            # At most one LIVE application per (cohort, profile). Auto-closed
            # ('expired') rows are excluded so a student may restart after a
            # closure — the old expired row stays as history alongside the new one.
            models.UniqueConstraint(
                fields=['cohort', 'profile'],
                name='unique_application_per_cohort',
                condition=models.Q(profile__isnull=False) & ~models.Q(status='expired'),
            ),
        ]

    def __str__(self):
        who = self.profile_id or 'unlinked'
        return f'Application #{self.pk} ({who} -> {self.cohort.code})'


class FundingNeed(models.Model):
    """
    "How you'd use the support" for one application — the S3 funding reframe
    (v2.4.2). Assistance is capped at RM3,000; instead of asking for an itemised
    total, the student ticks the categories the support would help with, may
    add an open note (incl. how they'd cope without), and gives a rough
    programme length. (The legacy per-line-item amount columns were dropped in
    TD-059 cleanup.)
    """
    application = models.OneToOneField(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='funding_need',
    )
    categories = models.JSONField(
        default=list, blank=True,
        help_text="Selected support categories: living/transport/accommodation/books/device/tuition/other",
    )
    funding_note = models.TextField(
        blank=True, default='',
        help_text="Open: how they'd use it / plan to fund studies / cope without",
    )
    programme_months = models.IntegerField(
        null=True, blank=True,
        help_text="Programme length in months",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'funding_needs'

    def __str__(self):
        return f'FundingNeed for application #{self.application_id}'


class ApplicantDocument(models.Model):
    """A supporting document for an application, stored in a private Supabase
    Storage bucket. Only the storage path + metadata live here; file bytes never
    pass through Django."""
    DOC_TYPES = [
        ('ic', 'Identity Card'),
        ('results_slip', 'Results Slip'),
        ('photo', 'Photo'),
        ('epf', 'EPF Statement'),
        ('str', 'STR Document'),
        ('statement_of_intent', 'Statement of Intent'),
        ('reference_letter', 'Reference Letter'),
        ('salary_slip', 'Salary Slip'),
        ('water_bill', 'Water Bill'),
        ('electricity_bill', 'Electricity Bill'),
        ('offer_letter', 'Offer Letter'),
        # S17 — minor consent flow. parent_ic is compulsory when the applicant
        # is under 18; guardianship_letter is compulsory when the consenting
        # adult is NOT the father or mother (e.g. legal guardian, grandparent,
        # older sibling, other relative).
        ('parent_ic', 'Parent/Guardian IC'),
        ('guardianship_letter', 'Guardianship Letter'),
        # Income Check-1: links the income earner to the student when the earner is the
        # MOTHER (the student-IC patronymic only names the father). OCR: child/mother/father.
        ('birth_certificate', 'Birth Certificate'),
    ]
    VERIFICATION_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    # Income Check-1 salary route: which household member this document belongs to,
    # so one application can hold father's AND mother's AND a sibling's IC/payslip/EPF
    # without them overwriting each other. '' for everything outside the multi-earner
    # flow (single-instance docs, STR-route parent_ic, IC/results slip/etc.). The
    # (doc_type, household_member) pair is the single-instance key for income docs.
    HOUSEHOLD_MEMBER_CHOICES = [
        ('', 'Not applicable'),
        ('father', 'Father'), ('mother', 'Mother'), ('guardian', 'Legal guardian'),
        ('brother', 'Elder brother'), ('sister', 'Elder sister'),
    ]
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='documents',
    )
    doc_type = models.CharField(max_length=30, choices=DOC_TYPES)
    household_member = models.CharField(
        max_length=10, blank=True, default='', choices=HOUSEHOLD_MEMBER_CHOICES,
        help_text="Salary-route income docs only — whose IC/salary slip/EPF this is. "
                  "Blank for all other documents.")
    storage_path = models.CharField(max_length=500)
    original_filename = models.CharField(max_length=255, blank=True, default='')
    content_type = models.CharField(max_length=100, blank=True, default='')
    size = models.IntegerField(default=0)
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_CHOICES, default='pending',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # ── S13: Vision OCR (soft signal, never a hard block) ──────────────────
    # Populated only for doc_type='ic'. The admin verify-&-accept stays the
    # real identity gate; these fields are hints (and a UX nudge for typos).
    vision_nric = models.CharField(max_length=20, blank=True, default='')
    vision_name = models.CharField(max_length=200, blank=True, default='')
    # S18 (post-S14): MyKad address from OCR. Surfaced to the admin verify-&-accept
    # card alongside profile.address — no automated matcher (admin/interviewer
    # eyeballs it). Useful when the registered IC address differs from where the
    # student currently lives (e.g. relocated since IC issue).
    vision_address = models.CharField(max_length=500, blank=True, default='')
    vision_run_at = models.DateTimeField(null=True, blank=True)
    vision_error = models.CharField(max_length=200, blank=True, default='')
    # Soft supporting-document checks: does the student's OR a parent/guardian's
    # name appear in the document text (results_slip / str / salary_slip / epf /
    # water_bill / electricity_bill / offer_letter), and — for utility bills — does
    # the home address appear? Computed at upload against names + address on file.
    # SOFT signal only (never blocks); surfaced to the student and the interviewer.
    # '' = not run / not applicable; else 'found' / 'not_found' / 'unreadable'.
    vision_name_match = models.CharField(max_length=12, blank=True, default='')
    vision_address_match = models.CharField(max_length=12, blank=True, default='')
    # Document-assist: Gemini-extracted structured fields (admin-on-... no — runs
    # automatically on upload for the weak-OCR supporting docs). Shape:
    # {fields: {...per doc_type}, warnings: [...], student_verdict: 'ok'|
    # 'name_mismatch'|'address_mismatch'|'wrong_doc'|'unreadable'|'review_manually',
    # error: ''}. Empty dict = not run. SOFT signal, never blocks. Surfaced to the
    # student (corrective nudge) + the admin (extracted values). Additive, 0-row-safe.
    vision_fields = models.JSONField(default=dict, blank=True)
    vision_fields_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'applicant_documents'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.doc_type} for application #{self.application_id}'


class Referee(models.Model):
    """A person who can vouch for the applicant (teacher, counsellor, referring
    org contact). The B40 analysis flagged the absence of a referee."""
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='referees',
    )
    name = models.CharField(max_length=200)
    role = models.CharField(
        max_length=200, blank=True, default='',
        help_text='e.g. teacher, school counsellor, referring org contact',
    )
    relationship = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'referees'

    def __str__(self):
        return f'Referee {self.name} for application #{self.application_id}'


class Consent(models.Model):
    """A versioned, withdrawable consent record. For a minor (<18), consent must
    be granted by a guardian. Replaces the verbal consent the B40 analysis
    flagged as insufficient for PDPA."""
    GRANTED_BY = [('self', 'Self'), ('guardian', 'Guardian')]
    # S19 — relationship list refined: older_sibling split into brother/sister
    # (no "older" qualifier — the existing parent_ic_underage rule already
    # blocks anyone <18 from acting as guardian, so age is enforced upstream);
    # other_relative shortened to relative. 'Other' remains intentionally
    # excluded — unusual cases route through legal_guardian + letter.
    GUARDIAN_RELATIONSHIPS = [
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('legal_guardian', 'Legal guardian (court-appointed)'),
        ('grandparent', 'Grandparent'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('relative', 'Relative'),
    ]
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='consents',
    )
    consent_type = models.CharField(max_length=50, default='share_with_sponsors')
    version = models.CharField(max_length=20)
    locale = models.CharField(max_length=2, default='en')
    granted_by = models.CharField(max_length=20, choices=GRANTED_BY, default='self')
    guardian_name = models.CharField(max_length=200, blank=True, default='')
    # S17: now a code from GUARDIAN_RELATIONSHIPS (no DB-level enum change — chars
    # work; the choices list is enforced at the serializer + admin level). Pre-S17
    # rows that hold free text are kept as-is; they just won't pass the new validator
    # if re-saved. Backfill ad-hoc as needed; no migration needed for that.
    guardian_relationship = models.CharField(max_length=100, blank=True, default='')
    # S19 — guardian's own NRIC (typed by them). Validated at consent submit
    # against the OCR'd NRIC from the uploaded parent_ic; mismatch is a hard
    # gate (not a soft anomaly flag). Stored in masked YYMMDD-PB-#### form
    # for legibility; comparisons strip non-digits.
    guardian_nric = models.CharField(max_length=20, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'consents'
        ordering = ['-granted_at']

    def __str__(self):
        return f'Consent {self.consent_type} v{self.version} for application #{self.application_id}'


class SponsorProfile(models.Model):
    """The AI-drafted, admin-reviewed sponsor-facing profile for an application.
    The draft is generated by Gemini; an admin may edit it, then publish."""
    STATUS = [('draft', 'Draft'), ('approved', 'Approved'), ('published', 'Published')]
    application = models.OneToOneField(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='sponsor_profile',
    )
    draft_markdown = models.TextField(blank=True, default='')
    edited_markdown = models.TextField(blank=True, default='')
    # Phase D: the "v2" profile — a second Gemini pass that refines the draft with
    # the submitted interview findings. Admin-facing for now (the sponsor consumer
    # is gated on Phase E). Kept separate from draft/edited so both stay visible.
    final_markdown = models.TextField(blank=True, default='')
    final_model_used = models.CharField(max_length=50, blank=True, default='')
    finalised_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='draft')
    model_used = models.CharField(max_length=50, blank=True, default='')
    generated_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    # ── Phase E2: the ANONYMOUS, sponsor-pool-facing profile ──────────────────
    # GENERATED (not scrubbed) from non-identifying inputs only — it must never
    # contain the student's name/school/town. Distinct from draft/edited/final
    # (which are the NAMED admin-facing write-ups). `anon_published` is the
    # sponsor-pool visibility gate: a profile appears in the pool only when it is
    # anon-published AND the application has an active share_with_sponsors consent.
    anon_markdown = models.TextField(blank=True, default='')
    anon_model_used = models.CharField(max_length=50, blank=True, default='')
    anon_generated_at = models.DateTimeField(null=True, blank=True)
    anon_published = models.BooleanField(default=False)
    anon_published_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sponsor_profiles'

    @property
    def current_markdown(self):
        """Edited text wins over the raw AI draft."""
        return self.edited_markdown or self.draft_markdown

    def __str__(self):
        return f'SponsorProfile #{self.application_id} ({self.status})'


class InterviewSession(models.Model):
    """Phase C: the structured record of a post-shortlist interview.

    The interview agenda is generated from the deterministic anomaly engine
    (apps/scholarship/anomaly_engine.detect_anomalies) — the same flags the admin
    "Pre-interview flags" card shows. ``findings`` records a closed-ended verdict
    + short rationale against each flag (and any manually-added concerns), so two
    reviewers rating the same applicant converge (the standardisation north star
    in docs/scholarship/post-shortlist-vision.md).
    """
    STATUS = [('draft', 'Draft'), ('submitted', 'Submitted')]
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='interview_sessions',
    )
    interviewer = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='interviews_conducted',
    )
    status = models.CharField(max_length=20, choices=STATUS, default='draft')
    # findings: { "<anomaly_code>": {"verdict": "resolved|still_unclear|new_concern",
    #             "rationale": "<=140 chars"} }. Keys are the codes from
    # detect_anomalies(); manually-added concerns use synthetic "manual_<n>" codes.
    findings = models.JSONField(default=dict, blank=True)
    # rubric: fixed 1-5 dimensions, e.g. {"clarity_of_plan": 4, "financial_need": 5,
    # "resilience": 3}. The inter-rater-reliability mechanism.
    rubric = models.JSONField(default=dict, blank=True)
    overall_note = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'interview_sessions'
        ordering = ['-created_at']

    def __str__(self):
        return f'InterviewSession #{self.application_id} ({self.status})'


class Sponsor(models.Model):
    """Phase E: a self-registered sponsor ACCOUNT. A sponsor signs in via Supabase Auth — like a
    student — then registers here; an admin VETS them before they get any access
    to the anonymised student pool ("open to apply, approved to browse").

    Safety: a Sponsor never sees identifying student data (name/NRIC/address/phone/
    email/photo) anywhere — the marketplace is permanently anonymous (P2P model).
    This model only governs the sponsor's own account + vetting state.
    """
    STATUS = [
        ('pending', 'Pending review'),   # self-registered, awaiting admin vetting
        ('approved', 'Approved'),         # vetted — may browse the anonymised pool
        ('rejected', 'Rejected'),         # vetting declined
        ('suspended', 'Suspended'),       # access revoked after approval
    ]
    supabase_user_id = models.CharField(
        max_length=100, unique=True,
        help_text='Supabase Auth UID, set when the sponsor self-registers',
    )
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True, default='')
    # "How did you find us?" — self-reported acquisition channel (free dropdown).
    source = models.CharField(max_length=50, blank=True, default='')
    organisation = models.CharField(max_length=200, blank=True, default='')
    # Light KYC context for the admin vetting decision (who they are / why they
    # want to sponsor). Never shown to students.
    note = models.TextField(blank=True, default='')
    # PDPA consent captured at registration (Personal Data Protection Act 2010).
    consent_at = models.DateTimeField(null=True, blank=True)
    consent_version = models.CharField(max_length=30, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text='Email of the PartnerAdmin who vetted this sponsor',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sponsors'
        ordering = ['-created_at']

    @property
    def is_approved(self):
        return self.status == 'approved'

    def __str__(self):
        return f'Sponsor {self.email} ({self.status})'


class Donation(models.Model):
    """Phase E3: money a sponsor donates into myNADI (via toyyibPay; mocked until
    the gateway is wired). A donation is FINAL — it is myNADI's money. It credits
    the sponsor's internal **directed-giving balance** (donations − active
    allocations); the sponsor can only redirect that balance within the platform,
    never withdraw it to a bank. Outbound disbursement is a later, gated phase."""
    sponsor = models.ForeignKey(
        Sponsor, on_delete=models.CASCADE, related_name='donations',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # toyyibPay billCode/ref once real; 'mock' for dev/dummy donations.
    reference = models.CharField(max_length=100, blank=True, default='mock')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sponsor_donations'
        ordering = ['-created_at']

    def __str__(self):
        return f'Donation {self.amount} by sponsor={self.sponsor_id}'


class Sponsorship(models.Model):
    """Phase E3: a sponsor's ALLOCATION of their donated balance to one (anonymous)
    student, for that student's admin-set award amount.

    Flow (1:1, full-or-nothing for now; many-sponsor plumbing underneath):
    sponsor funds in full → 'offered' (award letter issued) → student/guardian
    accepts within the deadline → 'active' (app → 'sponsored', leaves the pool);
    if not accepted in time → 'lapsed' and the amount returns to the sponsor's
    balance (a lapsed/cancelled allocation simply stops being subtracted — no
    bank refund). **Anonymity holds both ways:** the sponsor never sees the
    student's identity (allowlist card/blurb), and the student never sees the
    sponsor's identity (decided with the user). No tranches/disbursement this
    slice — that is E3b."""
    STATUS = [
        ('offered', 'Offered'),     # funded in full; award letter issued; awaiting acceptance
        ('active', 'Active'),        # student/guardian accepted; the match is live
        ('lapsed', 'Lapsed'),        # not accepted in time → amount returned to balance
        ('cancelled', 'Cancelled'),  # sponsor withdrew the offer before acceptance
    ]
    # Allocations that still hold the sponsor's balance (subtracted from donations).
    HOLDING = ('offered', 'active')

    sponsor = models.ForeignKey(
        Sponsor, on_delete=models.CASCADE, related_name='sponsorships',
    )
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='sponsorships',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS, default='offered')
    # The consent recorded when the student/guardian accepted. Null until accepted —
    # a Sponsorship is never 'active' without one.
    consent = models.ForeignKey(
        Consent, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    accept_deadline = models.DateTimeField(null=True, blank=True)
    offered_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sponsorships'
        ordering = ['-offered_at']
        constraints = [
            # 1 sponsor per student (for now): at most one HOLDING (offered/active)
            # sponsorship per application.
            models.UniqueConstraint(
                fields=['application'], condition=models.Q(status__in=['offered', 'active']),
                name='uniq_holding_sponsorship_per_app'),
        ]

    @property
    def is_active(self):
        return self.status == 'active'

    def __str__(self):
        return f'Sponsorship #{self.id} sponsor={self.sponsor_id} app={self.application_id} {self.amount} ({self.status})'


class ResolutionItem(models.Model):
    """A discrete, independently-resolvable action raised against an application
    (the IBKR model — see docs/scholarship/verification-verdict-plan.md, S3).

    Most items are GENERATED from the verification verdict's ``unresolved`` list
    (``verdict_engine.build_verdict``) by ``resolution.sync_resolution_items`` —
    one ``source='system'`` item per (application, code), created once and
    auto-resolved when the underlying gap clears. An officer may also raise a
    ``source='officer'`` item by hand (the structured successor to the freeform
    ``info_request_note``). Each item closes by a **document**, a typed
    **explanation**, or a one-tap **confirm** — so the student clears the queue
    self-service and a phone call stays the exception.
    """
    KIND = [
        ('doc', 'Upload a document'),
        ('confirm', 'Confirm / correct a value'),
        ('explanation', 'Explain in your own words'),
    ]
    STATUS = [
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('waived', 'Waived'),     # officer decided it isn't needed
    ]
    SOURCE = [('system', 'System'), ('officer', 'Officer')]

    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='resolution_items',
    )
    # The verdict fact this item belongs to (identity/academic/income/pathway),
    # or 'other' for an officer-raised item that isn't tied to a fact.
    fact = models.CharField(max_length=20, default='other')
    # The verdict item code (e.g. 'str_claimed_no_doc') or, for officer items,
    # a synthetic 'officer_<n>'. Drives the i18n copy + the resolution UI (S4).
    code = models.CharField(max_length=60)
    # The verdict item's params, frozen for display (so the queue reads the same
    # even if the underlying data later changes).
    params = models.JSONField(default=dict, blank=True)
    prompt = models.TextField(
        blank=True, default='',
        help_text='Officer-written ask (officer items); system items resolve copy from code via i18n.',
    )
    kind = models.CharField(max_length=20, choices=KIND, default='doc')
    # For kind='doc': which ApplicantDocument.doc_type the student should upload.
    doc_type = models.CharField(max_length=30, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS, default='open')
    source = models.CharField(max_length=20, choices=SOURCE, default='system')
    # The student's response: a typed explanation/confirmation, and/or the
    # document they uploaded to satisfy a 'doc' item.
    resolution_text = models.TextField(blank=True, default='')
    resolution_doc = models.ForeignKey(
        ApplicantDocument, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolves_items',
    )
    created_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text="Email of the PartnerAdmin for officer items; '' for system items.",
    )
    resolved_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text="'student' / 'system' / a PartnerAdmin email.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'resolution_items'
        ordering = ['-created_at']
        constraints = [
            # One SYSTEM item per (application, code), ever — generation is
            # idempotent and never re-nags. Officer items aren't constrained.
            models.UniqueConstraint(
                fields=['application', 'code'], condition=models.Q(source='system'),
                name='uniq_system_resolution_per_code'),
        ]

    def __str__(self):
        return f'ResolutionItem #{self.id} app={self.application_id} {self.code} ({self.status})'
