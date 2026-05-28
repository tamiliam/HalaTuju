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
    success_delay_hours = models.IntegerField(
        default=2,
        help_text="Hours after submit before the shortlist (invitation) email + follow-up unlock (S8 delayed reveal)",
    )
    decline_delay_hours = models.IntegerField(
        default=48,
        help_text="Hours after submit before the warm decline email (S8 delayed reveal)",
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
        ('accepted', 'Accepted'),      # admin verified & accepted (S11a) — confirmed for award
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
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
    siblings_studying = models.BooleanField(
        default=False,
        help_text="One or more of my siblings are also studying.",
    )
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

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scholarship_applications'
        ordering = ['-submitted_at']
        constraints = [
            models.UniqueConstraint(
                fields=['cohort', 'profile'],
                name='unique_application_per_cohort',
                condition=models.Q(profile__isnull=False),
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
    ]
    VERIFICATION_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='documents',
    )
    doc_type = models.CharField(max_length=30, choices=DOC_TYPES)
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
    vision_run_at = models.DateTimeField(null=True, blank=True)
    vision_error = models.CharField(max_length=200, blank=True, default='')

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
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='consents',
    )
    consent_type = models.CharField(max_length=50, default='share_with_sponsors')
    version = models.CharField(max_length=20)
    locale = models.CharField(max_length=2, default='en')
    granted_by = models.CharField(max_length=20, choices=GRANTED_BY, default='self')
    guardian_name = models.CharField(max_length=200, blank=True, default='')
    guardian_relationship = models.CharField(max_length=100, blank=True, default='')
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
    status = models.CharField(max_length=20, choices=STATUS, default='draft')
    model_used = models.CharField(max_length=50, blank=True, default='')
    generated_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sponsor_profiles'

    @property
    def current_markdown(self):
        """Edited text wins over the raw AI draft."""
        return self.edited_markdown or self.draft_markdown

    def __str__(self):
        return f'SponsorProfile #{self.application_id} ({self.status})'
