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
    min_spm_a_count = models.IntegerField(
        default=5, help_text="Minimum SPM A's (A+/A/A- all count) for Bucket A",
    )
    min_stpm_pngk = models.FloatField(
        default=3.0, help_text="Minimum STPM PNGK for Bucket A",
    )
    income_ceiling = models.IntegerField(
        null=True, blank=True,
        help_text="B40 monthly household income ceiling in RM",
    )
    bucket_b_margin = models.IntegerField(
        default=1,
        help_text="How many A's short of min_spm_a_count still qualifies for Bucket B",
    )

    # Funding + workflow parameters (consumed by later sprints)
    funding_envelope = models.IntegerField(
        null=True, blank=True, help_text="Per-student funding envelope in RM",
    )
    fail_email_delay_days = models.IntegerField(
        default=3,
        help_text="Days to wait before the 'not this round' email (Sprint 3)",
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
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]
    BUCKET_CHOICES = [('', 'Unassigned'), ('A', 'Bucket A'), ('B', 'Bucket B')]

    cohort = models.ForeignKey(
        ScholarshipCohort, on_delete=models.PROTECT,
        related_name='applications',
    )
    profile = models.ForeignKey(
        'courses.StudentProfile', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='scholarship_applications',
        help_text="Linked HalaTuju profile (always set in the apply-first flow)",
    )

    # Shortlisting inputs
    qualification = models.CharField(
        max_length=10, choices=QUALIFICATION_CHOICES, default='spm',
    )
    spm_a_count = models.IntegerField(
        null=True, blank=True,
        help_text="Snapshot of SPM A's at apply time (A+/A/A- all count)",
    )
    stpm_pngk = models.FloatField(null=True, blank=True)
    household_income = models.IntegerField(
        null=True, blank=True,
        help_text="Combined monthly household income in RM",
    )
    household_size = models.IntegerField(null=True, blank=True)
    receives_str = models.BooleanField(
        default=False,
        help_text="Active Sumbangan Tunai Rahmah recipient (B40 anchor)",
    )
    receives_jkm = models.BooleanField(
        default=False, help_text="Receives JKM assistance",
    )
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

    form_data = models.JSONField(
        default=dict, blank=True,
        help_text="Raw/extra intake fields from the native form",
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
    Structured funding-need breakdown for one application — the "quantified ask"
    a sponsor needs (the B40 analysis flagged its absence). Line items in RM.
    """
    application = models.OneToOneField(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='funding_need',
    )
    tuition_gap = models.IntegerField(default=0, help_text="Tuition not covered by subsidy (RM)")
    laptop = models.IntegerField(default=0)
    hostel = models.IntegerField(default=0)
    transport = models.IntegerField(default=0)
    books = models.IntegerField(default=0)
    monthly_allowance = models.IntegerField(default=0, help_text="Living allowance per month (RM)")
    allowance_months = models.IntegerField(default=0, help_text="Number of months of allowance")
    other = models.IntegerField(default=0)
    other_desc = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'funding_needs'

    @property
    def total(self):
        return (
            self.tuition_gap + self.laptop + self.hostel + self.transport
            + self.books + self.monthly_allowance * self.allowance_months + self.other
        )

    def __str__(self):
        return f'FundingNeed for application #{self.application_id} (RM{self.total})'


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
