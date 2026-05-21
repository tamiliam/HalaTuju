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
