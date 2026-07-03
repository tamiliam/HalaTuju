"""
BrightPath Bursary Programme — data models.

Phase 1 (intake & profile engine). Sponsor and money models arrive in
Phases 2-3. See docs/scholarship/b40-assistance-prd.md and
docs/scholarship/b40-phase1-roadmap.md.
"""
from django.db import models

from .family import PROFESSION_CHOICES


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
        help_text="Display name, e.g. 'BrightPath Bursary Programme 2026'",
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
        help_text="B40 monthly household GROSS income ceiling in RM (DOSM B40 line, RM5,860 in 2024). "
                  "PRIMARY income gate: a non-STR applicant at or below this passes regardless of household size.",
    )
    per_capita_ceiling = models.IntegerField(
        default=1584,
        help_text="Per-capita monthly income ceiling in RM (household_income / household_size). "
                  "SAFETY NET only — applies to non-STR applicants whose gross income is ABOVE income_ceiling, "
                  "rescuing large households. RM5,860 B40 ceiling / 3.7 avg household = RM1,584 (DOSM 2024).",
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
    # Check 2 STEP 2/3: days a student has to answer the AI clarify queries after submit
    # before the application proceeds to a reviewer regardless (the SLA clock, design §5).
    query_response_sla_days = models.PositiveSmallIntegerField(
        default=5,
        help_text="Check-2 query SLA: days after submit to answer clarify queries before "
                  "the application is ready for assignment regardless (proceed-as-is, flagged).",
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
        # Phase C post-shortlist funnel (between shortlisted and recommended):
        ('profile_complete', 'Profile complete'),  # student confirmed a complete Step-4 profile
        ('interviewing', 'Interviewing'),           # interview in progress OR findings in, verdict not yet submitted
        ('interviewed', 'Interviewed — awaiting QC'),  # reviewer submitted the full verdict; awaiting quality control (QC)
        ('recommended', 'Recommended'),  # QC-accepted — provisional, masked from the student
        # Post-award lifecycle (roadmap docs/scholarship/post-award-lifecycle-plan.md):
        ('awarded', 'Awarded'),          # a funder committed; offer out + tri-partite agreement being signed
        ('active', 'Active'),            # agreement fully executed (Foundation signs last); awaiting first payout
        ('maintenance', 'Maintenance'),  # first tranche disbursed; recurring per-semester support loop
        ('closed', 'Closed'),            # terminal archive (manual close); see closure_reason
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
    # Reviewer-query S3: the normalised (sortable) date the student must report to their
    # institution, parsed from the offer letter's free-text reporting date by
    # pathway_engine.parse_reporting_date + stored by autofill_pathway_from_offer. Null when
    # the offer carries no readable date (then a reporting_date_unknown clarify is raised).
    reporting_date = models.DateField(null=True, blank=True)
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
    # DECLARED informal income (Phase 2A, P5b/P6): a working member with no payslip/EPF may
    # declare an average MONTHLY salary. {member: amount_rm_per_month:int}. Whether that figure
    # is ACCEPTED is computed, never stored: a valid-STR household → accepted; a non-STR family
    # → needs a supporting doc (income_support_doc) before it counts. Additive, 0-row-safe.
    income_declared = models.JSONField(
        default=dict, blank=True,
        help_text="Salary route: {member: declared avg monthly income (RM, int)} for a working "
                  "member with no payslip/EPF. Accepted if a valid STR is on file, else needs an "
                  "income_support_doc. Feeds earner_monthly_income → per-capita.")
    # UNEMPLOYMENT detail (Phase 2B, P7): for a household member whose occupation is 'unemployed',
    # WHY and SINCE WHEN — {member: {reason: str, since: 'YYYY-MM'}}. Reviewer texture for the
    # "why little/no income" story; an EPF statement (employer no. all-zeros) can corroborate.
    # Never a gate (P3: trust the student). Additive, 0-row-safe.
    income_nonearning = models.JSONField(
        default=dict, blank=True,
        help_text="{member: {reason, since:'YYYY-MM'}} for an 'unemployed' roster member — why and "
                  "since when. Reviewer texture; EPF (all-zeros employer) corroborates. Never a gate.")
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
    # B40 Phase E/F (F8a): stamped when the student completes post-award onboarding
    # (acknowledgement + questionnaire). The hard gate before the first disbursement.
    onboarded_at = models.DateTimeField(null=True, blank=True)
    # Post-award signing: stamped when the student passes the bursary-agreement
    # comprehension quiz ("Understand" step on /scholarship/award), recorded for
    # defensibility alongside the signed agreement.
    comprehension_passed_at = models.DateTimeField(null=True, blank=True)
    # Post-award signing — the parent/guardian SURETY's phone-PIN verification, captured
    # in-session just before the bursary signature. ``guarantor_phone`` is the locked
    # number (read from profile.guardians at apply) the PIN was sent to; the stamp marks a
    # successful check. ``bursary.sign_agreement`` requires a FRESH stamp (see
    # GUARANTOR_PHONE_VERIFY_TTL_SECONDS) so a signature can't ride a stale verification.
    guarantor_phone = models.CharField(max_length=32, blank=True, default='')
    guarantor_phone_verified_at = models.DateTimeField(null=True, blank=True)
    # R5 (Trust & Assurance): an INDEPENDENT party has confirmed this student's
    # enrolment with their institution — the institution-confirmation layer of the
    # layered assurance stack. DISTINCT from identity (``profile.nric_verified``):
    # that the person is real vs that the place is real. Surfaced to sponsors as a
    # BARE BOOLEAN badge only (never the verifier's evidence). Honest default False
    # until the enrolment-confirmation process exists.
    enrolment_verified = models.BooleanField(default=False)
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
    # Check 2 STEP 2: when the single 'answer your queries' reminder was sent (idempotent).
    query_reminder_at = models.DateTimeField(null=True, blank=True)
    # Check 2 STEP 2: when the student was first notified that clarify queries were raised
    # (sent once at submission, so they come back and answer). Idempotent.
    query_raised_notified_at = models.DateTimeField(null=True, blank=True)

    # Admin verify-&-accept (S11a): a PartnerAdmin confirms NRIC/name/results against
    # the uploaded MyKad, which sets profile.nric_verified (locks the NRIC) and
    # advances status → 'recommended'. These capture who/when/what was confirmed.
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

    # Closure bucket — WHY a funded application reached status='closed' (post-award lifecycle).
    # 'graduated'/'completed' are positive (programme finished vs contractual support period fulfilled);
    # 'withdrawn'/'lapsed'/'terminated' are negative. Set at the MANUAL close (Sprint 6). Blank otherwise.
    CLOSURE_REASONS = [
        ('graduated', 'Graduated — completed the programme'),
        ('completed', 'Completed the contractual support period'),
        ('withdrawn', 'Withdrawn by the student'),
        ('lapsed', 'Lapsed — support stopped (fell away)'),
        ('terminated', 'Terminated for cause'),
    ]
    closure_reason = models.CharField(
        max_length=20, choices=CLOSURE_REASONS, blank=True, default='',
        help_text="Why the application reached status='closed'; blank unless status='closed'",
    )
    # Post-award S6: the manual-close audit stamp (mirrors rejected_at/rejected_by). Set when
    # an admin closes a funded application; null/blank otherwise.
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.CharField(max_length=254, blank=True, default='')

    # Post-award S5: the operational sub-state WITHIN status='maintenance' (the funded
    # recurring loop). An admin lifecycle overlay, distinct from the sponsor-facing
    # ACADEMIC band (`pool.derive_progress_state`, derived from semester results):
    #   on_track       — funded, in good standing (default)
    #   probation      — at-risk (poor result / concern); support continues but flagged
    #   on_hold        — paused (a tranche release is BLOCKED until resumed)
    #   ready_to_close — support fulfilled / final result in; the S6 manual close reads this
    # Only meaningful while status='maintenance'; 'on_track' otherwise.
    MAINTENANCE_SUBSTATES = [
        ('on_track', 'On track'),
        ('probation', 'Probation (at-risk)'),
        ('on_hold', 'On hold (paused)'),
        ('ready_to_close', 'Ready to close'),
    ]
    maintenance_substate = models.CharField(
        max_length=20, choices=MAINTENANCE_SUBSTATES, blank=True, default='on_track',
        help_text="Operational sub-state within status='maintenance'; 'on_track' otherwise",
    )

    # 7-day DECLINE cool-off (#13): an admin decline is recorded SILENTLY here (bucket + due
    # date) instead of flipping status immediately. The release cron reveals it (status →
    # rejected + bucket decline email) once decline_due_at passes; an admin can Cancel before
    # then, so a reconsidered decline is never seen by the student. Blank/null = none pending.
    pending_rejection_category = models.CharField(
        max_length=20, choices=REJECTION_CATEGORIES, blank=True, default='',
        help_text="A scheduled-but-unrevealed decline bucket (cool-off); blank = none pending",
    )
    decline_due_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When a pending decline reveals + emails (cool-off end)",
    )
    pending_decline_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text="Email of the admin who scheduled the pending decline",
    )
    # Cancel-decline correctness (code-health S1): the decline email gets its OWN stamp —
    # ``decision_email_sent_at`` is stamped by the shortlist PASS email at release, so reusing
    # it made ``cancel_pending_decline`` believe every normally-processed student had already
    # been told (the restore branch never ran). And the restore target is SNAPSHOTTED, not
    # hardcoded 'interviewed' — 'interviewed' now means AWAITING QC, so a decline made from
    # shortlisted/interviewing must not land there on cancel (it would enter the QC queue
    # with no recorded verdict).
    decline_email_sent_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the bucket decline email was actually sent (distinct from the "
                  "shortlist decision email stamp)",
    )
    pre_decline_status = models.CharField(
        max_length=20, blank=True, default='',
        help_text="Status snapshot taken at admin_reject; cancel_pending_decline restores "
                  "to it (blank = legacy row, falls back to 'interviewed')",
    )

    # 2-day AWARD-confirmation cool-off (#14): on student/guardian accept we record the
    # acceptance + money hold immediately, but defer the 'sponsored' flip + the funding-confirmed
    # email + onboarding until award_due_at. The release cron finalises it; an admin Hold reverts
    # the acceptance before then. Null = no pending award confirmation.
    award_due_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When a pending award confirmation finalises (cool-off end)",
    )

    # Phase C: which reviewer this application is assigned to (for the interview
    # stage). Null = unassigned. SET_NULL so deactivating an admin doesn't delete
    # applications.
    assigned_to = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_applications',
        help_text="Phase C: the reviewer assigned to interview this applicant",
    )
    assigned_at = models.DateTimeField(
        null=True, blank=True,
        help_text="F7: when the current reviewer was assigned (null = unassigned)",
    )
    # ── Review-completion SLA nudges (TD-131) ──────────────────────────────────
    # Verdict-due = assigned_at + REVIEW_SLA_DAYS. The send_review_nudges cron fires each
    # of these at most once (idempotency stamps, like interview_reminded_*); they are reset
    # whenever the application is (re)assigned so the new reviewer's clock starts clean. A
    # recorded verdict (verdict_decided_at) cancels all of them.
    review_nudged_soon_at = models.DateTimeField(
        null=True, blank=True, help_text="When the 'verdict due soon' reviewer nudge was sent")
    review_nudged_overdue_at = models.DateTimeField(
        null=True, blank=True, help_text="When the 'verdict overdue' reviewer nudge was sent")
    review_escalated_at = models.DateTimeField(
        null=True, blank=True, help_text="When the overdue verdict was escalated to super-admins")

    # ── Interview scheduling (in-app booking + Google Meet) ────────────────────
    # The assigned reviewer proposes a few InterviewSlot options; the student books
    # one. The booking state lives here (one interview per application); the proposed
    # options are InterviewSlot rows. All additive/optional; the whole surface is dark
    # behind INTERVIEW_SCHEDULING_ENABLED. Times are tz-aware (stored UTC, shown MYT).
    INTERVIEW_STATUS_CHOICES = [
        ('', 'Not booked'), ('booked', 'Booked'), ('cancelled', 'Cancelled')]
    interview_slot = models.ForeignKey(
        'InterviewSlot', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', help_text="The proposed slot the student booked.")
    interview_start = models.DateTimeField(
        null=True, blank=True,
        help_text="Denormalised start of the booked interview (the chosen slot's time).")
    interview_status = models.CharField(
        max_length=10, blank=True, default='', choices=INTERVIEW_STATUS_CHOICES)
    interview_meeting_url = models.URLField(
        blank=True, default='',
        help_text="Google Meet (or manually-pasted) join link for the booked interview.")
    interview_meeting_provider = models.CharField(
        max_length=20, blank=True, default='',
        help_text="'google_meet' (auto-generated) or 'manual' (pasted by an admin).")
    interview_calendar_event_id = models.CharField(
        max_length=255, blank=True, default='',
        help_text="Google Calendar event id, so the booking can be updated/cancelled.")
    interview_booked_at = models.DateTimeField(null=True, blank=True)
    interview_cancelled_at = models.DateTimeField(null=True, blank=True)
    # Student asked for different times (none of the proposed slots work). Set when they
    # request alternatives in-app; cleared when the reviewer proposes a fresh menu.
    interview_alternatives_requested_at = models.DateTimeField(null=True, blank=True)
    interview_alternatives_note = models.TextField(blank=True, default='')
    # Why the student cancelled their booked interview (optional free text). Set on cancel,
    # passed to the reviewer's notice + shown on the cockpit; cleared when fresh times are proposed.
    interview_cancel_reason = models.TextField(blank=True, default='')
    # Idempotency stamps for the confirmation + the reminder cron (reset on reschedule).
    interview_confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    interview_reminded_1d_at = models.DateTimeField(null=True, blank=True)
    interview_reminded_1h_at = models.DateTimeField(null=True, blank=True)

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
    # TextField (not CharField) on purpose: students write a sentence or two here
    # ("My mother is a Grab driver and sole breadwinner…"), which overflowed the
    # old varchar(255) and silently rolled back the whole Story save. Anti-spam
    # length is enforced at the serializer/UI (STORY_TEXT_MAX), not the column.
    parents_occupation = models.TextField(
        blank=True, default='',
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
    # ── Structured family roster (redesign 2026-06) — the new INPUTS. Father/Mother
    #    (name as in IC + coded profession) + an optional pool of brother/sister/
    #    guardian. The legacy columns above (first_in_family, parents_occupation) are
    #    now DERIVED from this on save (services.save_application_details via
    #    family.derive_first_in_family / parents_occupation_summary), so every
    #    downstream reader keeps working unchanged. All additive/optional.
    father_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Father's name as in IC (structured roster).")
    father_occupation = models.CharField(
        max_length=40, blank=True, default='', choices=PROFESSION_CHOICES,
        help_text="Father's profession (coded; see family.PROFESSION_CHOICES).")
    father_occupation_other = models.CharField(
        max_length=120, blank=True, default='',
        help_text="Father's profession free text when occupation == 'other'.")
    mother_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Mother's name as in IC (structured roster).")
    mother_occupation = models.CharField(
        max_length=40, blank=True, default='', choices=PROFESSION_CHOICES,
        help_text="Mother's profession (coded).")
    mother_occupation_other = models.CharField(
        max_length=120, blank=True, default='',
        help_text="Mother's profession free text when occupation == 'other'.")
    other_family_members = models.JSONField(
        default=list, blank=True,
        help_text="Optional pool: [{role: brother|sister|guardian, occupation: <code>, "
                  "occupation_other: <str>}] — extra family members + their professions.")
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
    # Set when a superadmin REOPENS a recorded decision (to correct a reviewer error).
    # While non-null the decision panel is editable again, the reviewer dropdown unlocks,
    # and the sponsor profile is held from the pool (unpublished). Cleared on re-save or
    # cancel. The audit trail + the per-reviewer corrections count live in DecisionReopen.
    decision_reopened_at = models.DateTimeField(null=True, blank=True)

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
        # Phase 2A (P5b/D1): supporting proof for a DECLARED informal income when the family
        # has no valid STR — flexible, any ONE of an employer/wage letter, bank statements
        # showing income, or a community/penghulu letter. Tagged to the household member.
        ('income_support_doc', 'Income Support Document'),
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
        # Post-award: the student's bank statement / passbook proving the account the
        # bursary will be paid into. Gemini-extracts bank name + account number +
        # account holder; the holder MUST be the student (hard rule).
        ('bank_statement', 'Bank Statement'),
        # Catch-all for a reviewer-requested document not in the fixed list (e.g. the
        # current-semester results for a student already studying). Lands under "Other".
        ('other', 'Other Document'),
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
    # The officer ResolutionItem code (e.g. 'officer_3') this document satisfies — set
    # ONLY for a reviewer-requested upload via the Action Centre. It makes each request
    # its own single-instance slot: the slot key becomes (doc_type, household_member,
    # request_code). So multiple 'other' docs (4 separate "upload X" requests) coexist
    # instead of overwriting each other, and a reviewer-requested cross-person income
    # doc (e.g. father's IC on a mother-STR route) gets its own slot instead of
    # clobbering the student's route doc. '' = the student's own apply-form/route doc
    # (shared slot — unchanged behaviour).
    request_code = models.CharField(max_length=20, blank=True, default='')
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


class OnboardingResponse(models.Model):
    """B40 Phase E/F (F8a): the student's post-award onboarding — the questionnaire
    answers + the acknowledgement consent. One row per application (re-submitting
    updates it). Kept as a dedicated row rather than a JSON blob on the application
    for a clean audit trail of what was answered and when. The matching
    ``student_onboarding_ack`` Consent is the legal record; this holds the content."""
    application = models.OneToOneField(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='onboarding_response',
    )
    # Free-form questionnaire payload (the F8b frontend defines the shape); JSON so
    # the questions can evolve without a migration. Never holds identity documents.
    answers = models.JSONField(default=dict, blank=True)
    consent = models.ForeignKey(
        Consent, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'onboarding_responses'

    def __str__(self):
        return f'OnboardingResponse for application #{self.application_id}'


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
    # profile_engine.PROMPT_VERSION that produced the current draft/final. Lets us detect a
    # stale draft by version (not by date) and target regeneration. '' = pre-versioning.
    prompt_version = models.CharField(max_length=30, blank=True, default='')
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
    # A ≤20-word, CARD-STRICT one-liner for the sponsor-pool browse card (distinct from
    # anon_markdown, which is the fuller PII-redacted profile that MAY name school/town).
    # This must never carry name/school/town/state — generated by a strict prompt then
    # backstopped by scan_anon_for_identifiers. '' = none yet (the card shows course only).
    anon_blurb = models.CharField(max_length=200, blank=True, default='')
    # F3: stamped once this published student has been included in a real-time
    # sponsor alert batch, so the hourly job never re-sends them. Reset to null on
    # (re)publish so a freshly-published student is alerted exactly once.
    realtime_notified_at = models.DateTimeField(null=True, blank=True)
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


class InterviewSlot(models.Model):
    """A single interview time the assigned reviewer PROPOSES to a student.

    Model: the reviewer offers 2-3 slots per applicant; the student picks one
    (which sets the booking state on ScholarshipApplication). Withdrawing an
    unbooked option flips is_active to False rather than deleting (keeps a record).
    Times are tz-aware (stored UTC, rendered in Asia/Kuala_Lumpur). The whole
    surface is dark behind INTERVIEW_SCHEDULING_ENABLED.
    """
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='interview_slots',
    )
    reviewer = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.CASCADE, related_name='proposed_interview_slots',
        help_text="The reviewer who proposed this slot (= the assigned reviewer).",
    )
    start = models.DateTimeField(help_text="Proposed interview start (tz-aware).")
    duration_min = models.PositiveSmallIntegerField(default=45)
    # False once withdrawn by the reviewer or superseded by a fresh proposal round.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'interview_slots'
        ordering = ['start']

    def __str__(self):
        return f'InterviewSlot #{self.application_id} @ {self.start:%Y-%m-%d %H:%M}'


class InterviewMessage(models.Model):
    """A short free-text note from the STUDENT to their assigned reviewer.

    The always-open pressure valve around the scheduling flow: reschedule/cancel close
    inside the 12h cutoff, but "I'm running late" / "I'm sick" must still reach the
    reviewer — even one hour before the call. Stored for the cockpit thread + audit;
    delivery is a best-effort email to the assigned reviewer (the student never sees
    the reviewer's address). Rate-limited in scheduling.send_student_message.
    """
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='interview_messages',
    )
    text = models.TextField(help_text="The student's message (capped at 1000 chars on write).")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'interview_messages'
        ordering = ['created_at']

    def __str__(self):
        return f'InterviewMessage #{self.application_id} @ {self.created_at:%Y-%m-%d %H:%M}'


class DecisionReopen(models.Model):
    """Audit row for each time a superadmin REOPENS a recorded decision.

    Reopening a finalised decision asserts the assigned REVIEWER made an error;
    while a row is OPEN (``closed_at`` is null) the application's decision panel is
    editable again and the sponsor profile is held from the pool. On close:
      - ``resulted_in_change=True``  → the reopen led to a re-saved decision (a real
        correction); this is what COUNTS against the reviewer.
      - ``resulted_in_change=False`` → it was cancelled/restored with no change.

    The per-reviewer "corrections" count = COUNT(resulted_in_change=True) over this
    log (counting model B, the owner's call 2026-06-18) — derived from the audit
    trail, never a bare counter that could drift.
    """
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='decision_reopens',
    )
    # Attributed to the ASSIGNED reviewer at the moment of reopen (they own the
    # interview + recommendation). SET_NULL so deactivating an admin never destroys
    # the audit trail.
    reviewer = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='decision_reopens_attributed',
        help_text="The reviewer the correction is attributed to (assigned reviewer at reopen).",
    )
    reopened_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text="Email of the superadmin who reopened the decision.",
    )
    reason = models.TextField(help_text="Why the decision was reopened (the asserted reviewer error).")
    # Pool-publish state captured at reopen, so a cancel restores it exactly.
    was_published = models.BooleanField(default=False)
    # True once the reopen led to a re-saved decision (a real correction → counts).
    resulted_in_change = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'decision_reopens'
        ordering = ['-created_at']

    def __str__(self):
        state = 'open' if self.closed_at is None else 'closed'
        return f'DecisionReopen #{self.application_id} ({state})'


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
    # Boundary decision (2026-06-07): a TRUSTED sponsor (known/vetted — the launch
    # default) may see institution-level detail on the anonymised card; a future
    # PUBLIC/untrusted sponsor does not. Default True so every existing + launch
    # sponsor is trusted; flip to False per-sponsor when public onboarding opens.
    is_trusted = models.BooleanField(default=True)
    # F3 (Phase E/F): how often this sponsor wants to hear about newly-published
    # anonymised students. 'realtime' = an hourly-batched alert, 'weekly' = a
    # weekly digest, 'off' = no emails. Default 'weekly' (a gentle cadence).
    NOTIFY_FREQUENCIES = [('realtime', 'Real-time'), ('weekly', 'Weekly digest'), ('off', 'Off')]
    notify_frequency = models.CharField(max_length=10, choices=NOTIFY_FREQUENCIES, default='weekly')
    # When the last weekly digest was sent to THIS sponsor; the next digest only
    # includes students published after it (so a sponsor never gets a duplicate).
    last_digest_sent_at = models.DateTimeField(null=True, blank=True)
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
    # When the award good-news email was sent (or the award was handled without one, e.g.
    # a pre-existing/embargoed award backfilled so the cool-off cron never re-emails it).
    # NULL = still pending; the release cron emails once offered_at + the cool-off elapses.
    offer_emailed_at = models.DateTimeField(null=True, blank=True)
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


class Disbursement(models.Model):
    """Post-award lifecycle S4: the money-OUT ledger — a single tranche of a funded
    award, paid (eventually) to the student.

    This is a LEDGER, not custody: real disbursement via toyyibPay is deferred
    (TD-075), so ``release_tranche`` records a 'released' row with a mock reference
    rather than moving real money. A tranche is scheduled against a funded
    application; an admin marks it disbursed. **The first ``released`` tranche flips
    the application ``active`` → ``maintenance``** (it enters the recurring funded
    loop — see ``disbursement.release_tranche``).

    ``sponsorship`` is the allocation that funds the tranche (nullable + SET_NULL so a
    future Foundation-direct award with no Sponsorship row still works, and deleting a
    Sponsorship never erases the disbursement history). Anonymity is unaffected: this
    row never crosses to a sponsor surface, and the student's award view never names a
    sponsor."""
    STATUS = [
        ('scheduled', 'Scheduled'),  # planned tranche, not yet payable
        ('due', 'Due'),              # payable now (admin/cron) — awaiting release
        ('released', 'Released'),    # marked disbursed (mock until TD-075)
        ('withheld', 'Withheld'),    # admin held it back (probation / failed results — S5)
        ('returned', 'Returned'),    # money returned (withdrawal / termination)
    ]
    # Tranches that represent money actually paid out (for "has any release happened").
    PAID = ('released',)

    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='disbursements',
    )
    # The allocation funding this tranche. Nullable for a future Foundation-direct
    # award; SET_NULL so disbursement history survives a Sponsorship delete.
    sponsorship = models.ForeignKey(
        Sponsorship, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='disbursements',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS, default='scheduled')
    # 1-based tranche number within the award (Semester 1, 2, …) — drives ordering and
    # the "first release" flip.
    sequence = models.PositiveSmallIntegerField(default=1)
    label = models.CharField(max_length=100, blank=True, default='')
    scheduled_for = models.DateField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    # Admin email who released/withheld/returned it — audit (mirrors verified_by etc.).
    actioned_by = models.CharField(max_length=254, blank=True, default='')
    # toyyibPay billCode/ref once real; 'mock' for the dark ledger.
    reference = models.CharField(max_length=100, blank=True, default='mock')
    note = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'disbursements'
        ordering = ['sequence', 'id']

    def __str__(self):
        return f'Disbursement #{self.id} app={self.application_id} seq={self.sequence} {self.amount} ({self.status})'


class BankAccount(models.Model):
    """The student's bank account for the bursary payout — captured post-award via the
    Action Centre (upload a bank statement → Gemini pre-fills → the student confirms).

    The three CONFIRMED fields are authoritative (the student reviews/corrects the
    Gemini read before saving, because a misread account digit would misdirect money).
    The HOLDER MUST BE THE STUDENT — a hard rule (no parent/joint accounts); the save
    endpoint re-checks ``account_holder`` against the application name and refuses a
    mismatch. ``source_doc`` links the bank statement the data came from (SET_NULL so
    a re-upload of the proof never erases the confirmed account).

    Financial PII → its own table + RLS (service-role only), not stuffed in
    ``OnboardingResponse.answers``. Stored only; not shown on any surface yet — an
    officer payout view is a later step (real disbursement = TD-075)."""
    HOLDER_VERDICTS = [('ok', 'Holder matches the student')]

    application = models.OneToOneField(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='bank_account',
    )
    bank_name = models.CharField(max_length=120)
    account_number = models.CharField(max_length=40)
    account_holder = models.CharField(max_length=200)
    # The bank statement the fields were read from. Nullable + SET_NULL so the account
    # survives a re-upload/removal of the proof document.
    source_doc = models.ForeignKey(
        ApplicantDocument, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bank_accounts',
    )
    # Recorded at confirm time — only 'ok' ever persists (the holder==student gate is
    # hard), kept for an audit trail + future tolerance changes.
    holder_verdict = models.CharField(max_length=20, choices=HOLDER_VERDICTS, default='ok')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bank_accounts'

    def __str__(self):
        return f'BankAccount app={self.application_id} {self.bank_name} ****{self.account_number[-4:]}'


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
        # Check 2 STEP 2:
        ('clarify', 'Answer a question'),          # AI student query (one-line, non-sensitive)
        ('human', 'For the reviewer'),             # AI-triaged to the human; never shown to the student
    ]
    STATUS = [
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('waived', 'Waived'),     # officer decided it isn't needed
    ]
    # 'check2' = an AI clarify/human query raised by the Check-2 submission review;
    # kept OUT of the verdict-driven sync (which only reconciles source='system').
    SOURCE = [('system', 'System'), ('officer', 'Officer'), ('check2', 'Check 2')]

    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='resolution_items',
    )
    # The verdict fact this item belongs to (identity/academic/income/pathway),
    # or 'other' for an officer-raised item that isn't tied to a fact.
    fact = models.CharField(max_length=20, default='other')
    # The verdict item code (e.g. 'income_proof_missing') or, for officer items,
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
            # Same idempotence for Check-2 AI queries: one per (application, code), ever.
            models.UniqueConstraint(
                fields=['application', 'code'], condition=models.Q(source='check2'),
                name='uniq_check2_resolution_per_code'),
        ]

    def __str__(self):
        return f'ResolutionItem #{self.id} app={self.application_id} {self.code} ({self.status})'


class ReviewerProfile(models.Model):
    """A reviewer's own credentials + contact details (F6, Phase E/F Sprint 5).

    OneToOne to courses.PartnerAdmin (a cross-app FK, like the rest of this app's
    references to the courses domain). Lives here, not on PartnerAdmin, so the
    sensitive staff PII (phone/address) sits in its own table with its own RLS and
    is edited only via the self-scoped /admin/reviewer-profile/ endpoint — it can
    never reach the student/sponsor allowlist serializers. NO password field
    (authentication is Supabase's; passwords are never modelled).
    """
    partner_admin = models.OneToOneField(
        'courses.PartnerAdmin', on_delete=models.CASCADE,
        related_name='reviewer_profile',
    )
    highest_qualification = models.CharField(max_length=120, blank=True, default='')
    university = models.CharField(max_length=200, blank=True, default='')
    graduation_year = models.PositiveSmallIntegerField(null=True, blank=True)
    field_of_study = models.CharField(max_length=200, blank=True, default='')
    # Language fluency — used to match a reviewer to a student's preferred call language
    # (StudentProfile.preferred_call_language). 'conversational' or 'fluent' = can review in it.
    LANG_FLUENCY = [('', 'None'), ('conversational', 'Conversational'), ('fluent', 'Fluent')]
    english_fluency = models.CharField(max_length=20, blank=True, default='', choices=LANG_FLUENCY)
    bm_fluency = models.CharField(max_length=20, blank=True, default='', choices=LANG_FLUENCY)
    tamil_fluency = models.CharField(max_length=20, blank=True, default='', choices=LANG_FLUENCY)
    # Whether the reviewer's phone may be shared with students assigned to them (in the advance
    # "your interviewer will contact you" email). Opt-in by DEFAULT (True); a reviewer can opt out.
    share_phone_with_students = models.BooleanField(default=True)
    # Sensitive staff PII — reviewer + super only, never exposed to students/sponsors.
    phone = models.CharField(max_length=30, blank=True, default='')
    address = models.TextField(blank=True, default='')   # legacy single-line; kept for back-compat
    # Structured address (2026-06 redesign), mirroring the student address split.
    street_address = models.CharField(max_length=255, blank=True, default='')
    postcode = models.CharField(max_length=10, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=50, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reviewer_profiles'

    def __str__(self):
        return f'ReviewerProfile for {self.partner_admin_id}'


class AssignmentEvent(models.Model):
    """An audit row for each (re)assignment of an application to a reviewer (F7).

    `from_admin`/`to_admin` are nullable FKs (admins are soft-deactivated, never
    hard-deleted, so the identity survives); `by_email` snapshots who performed it.
    A `to_admin` of None records an unassignment.
    """
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE,
        related_name='assignment_events',
    )
    from_admin = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    to_admin = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    by_email = models.CharField(
        max_length=254, blank=True, default='',
        help_text="Email of the super-admin who performed the (re)assignment.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assignment_events'
        ordering = ['-created_at']

    def __str__(self):
        return f'AssignmentEvent app={self.application_id} -> {self.to_admin_id} ({self.created_at})'


class SemesterResult(models.Model):
    """B40 Phase E/F (F9a): an in-programme student's latest-semester academic
    result. This is the IN-PROGRAMME progress signal — distinct from the pre-award
    ``results_slip`` (the SPM slip captured at application). The uploaded slip is
    **myNADI-only** (never crosses to a sponsor); only the DERIVED, non-identifying
    ``cgpa``/``graduated`` band feeds ``pool.derive_progress_state`` (the coarse
    ``progress_state`` a sponsor sees). The latest row (by ``created_at``) wins."""
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE,
        related_name='semester_results',
    )
    # Free label for the semester, e.g. "2026 Sem 1" / "Year 1 Sem 2". Display-only;
    # ordering uses created_at, not this string.
    semester = models.CharField(max_length=50, blank=True, default='')
    # 0.00–4.00 (Malaysian CGPA). Nullable — a student may record completion before
    # the official CGPA is published.
    cgpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    graduated = models.BooleanField(
        default=False,
        help_text="True when this result marks the student's graduation.",
    )
    # The myNADI-only proof slip. SET_NULL + related_name='+' — the slip is internal
    # evidence; deleting the doc must never cascade-delete the progress record.
    results_slip = models.ForeignKey(
        ApplicantDocument, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    note = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'semester_results'
        ordering = ['-created_at']

    def __str__(self):
        return f'SemesterResult app={self.application_id} {self.semester} cgpa={self.cgpa}'


class GraduationMessage(models.Model):
    """B40 Phase E/F (F9a): a student's anonymity-preserving graduation thank-you.

    Pipeline (owner decision 2026-06-09): the student submits ``raw_text`` →
    ``pool.scan_anon_for_identifiers`` runs as a STRUCTURAL gate (any leak of the
    student's own name/school/city/NRIC/phone/email → ``status='blocked'`` with the
    leaked ``scan_result`` fields, the student must edit) → a clean message is
    ``pending`` → myNADI staff approve (``approved``) or reject. An approved message
    is surfaced to the funding sponsor as *"a message from a student you supported"*
    linked ONLY to the anonymous ``pool.pool_ref`` — never a direct channel, never
    the student's identity. ``scrubbed_text`` is what the sponsor sees (defaults to
    ``raw_text`` on approval; staff may lightly redact)."""
    STATUS_CHOICES = [
        ('pending', 'Pending review'),     # clean scan, awaiting staff approval
        ('blocked', 'Blocked — identifiers'),  # scan found the student's own tokens
        ('approved', 'Approved'),          # staff-approved, sponsor-visible
        ('rejected', 'Rejected'),          # staff declined
    ]
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE,
        related_name='graduation_messages',
    )
    raw_text = models.TextField()
    scrubbed_text = models.TextField(blank=True, default='')
    # List of identifying field names the scan flagged (e.g. ['name', 'city']);
    # empty when the message is clean.
    scan_result = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    # Email of the staff member who approved/rejected (admins are soft-deactivated,
    # so a snapshot string is kept rather than an FK).
    approved_by = models.CharField(max_length=254, blank=True, default='')
    review_note = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'graduation_messages'
        ordering = ['-created_at']

    def __str__(self):
        return f'GraduationMessage app={self.application_id} [{self.status}]'


class SponsorReferral(models.Model):
    """B40 Phase E/F (F4): one sponsor inviting a prospective sponsor to the F1
    landing. The full guest-book model (owner decision 2026-06-09): each invite is a
    row, so the inviter sees their invitations + conversion. The invitee's email/name
    is PII for someone who has NOT consented — a 60-day purge (``purge_expired_referrals``)
    scrubs ``invitee_email``/``invitee_name`` and flips a still-``invited`` row to
    ``expired`` (the row stays for the inviter's count, minus the personal data)."""
    STATUS_CHOICES = [
        ('invited', 'Invited'),    # email sent, not yet joined
        ('joined', 'Joined'),      # the invitee registered as a sponsor (attributed)
        ('expired', 'Expired'),    # 60 days passed without joining; PII purged
    ]
    inviter = models.ForeignKey(
        Sponsor, on_delete=models.CASCADE, related_name='referrals_sent',
    )
    invitee_email = models.EmailField(blank=True, default='')   # cleared on purge
    invitee_name = models.CharField(max_length=200, blank=True, default='')
    note = models.CharField(max_length=500, blank=True, default='')   # the inviter's personal message
    # Opaque, non-guessable invite code carried by the /sponsor?ref=<code> link.
    code = models.CharField(max_length=32, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='invited')
    # The account the invitee became, once they register (attribution). SET_NULL so
    # deleting a sponsor never cascades away the referral history.
    registered_sponsor = models.ForeignKey(
        Sponsor, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sponsor_referrals'
        ordering = ['-created_at']

    def __str__(self):
        return f'SponsorReferral {self.code} by sponsor={self.inviter_id} [{self.status}]'


class TrustContent(models.Model):
    """R5 (Trust & Transparency hub): the EDITABLE content behind the four-layer
    trust story — Who we are · Governance · Sources & uses of funds · Independent
    assurance. A single active row holds the fillable DATA (legal entity, trustees,
    annual figures, the auditor) as JSON so the organisation can fill it in over
    time as it formalises **without a code deploy** (edit the row directly / via
    admin). The UI CHROME (headings, "to be published" placeholders, explanatory
    copy) lives in trilingual i18n on the frontend — only the language-neutral,
    owner-authored data lives here, so i18n parity is never broken by DB content.

    Seeded with HONEST placeholders: the org is not yet formalised, figures are
    illustrative (``figures_are_illustrative``), trustees/auditor are empty. NEVER
    any student/sponsor PII — programme-level content only."""
    # Who we are — language-neutral facts; empty until the org registers.
    legal_entity = models.CharField(max_length=300, blank=True, default='')
    contact_email = models.EmailField(blank=True, default='help@halatuju.xyz')
    # Governance — list of {name, role, bio}; empty until trustees are appointed.
    trustees = models.JSONField(default=list, blank=True)
    # Sources & uses of funds — each a list of {label, amount} (RM). Illustrative
    # placeholders now; real figures (published annually) drop in as accounts mature.
    sources = models.JSONField(default=list, blank=True)
    uses = models.JSONField(default=list, blank=True)
    # Independent assurance — {fy, students_verified, disbursed, auditor, report_url}.
    assurance = models.JSONField(default=dict, blank=True)
    # True while the figures above are illustrative placeholders (the FE shows an
    # "illustrative" pill); flip to False once real audited figures are published.
    figures_are_illustrative = models.BooleanField(default=True)
    # Only the active row is served; lets a draft be staged without publishing.
    is_active = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trust_content'
        ordering = ['-updated_at']

    def __str__(self):
        return f'TrustContent active={self.is_active} updated={self.updated_at:%Y-%m-%d}'


class StandingGift(models.Model):
    """R6 (AutoSponsor): a sponsor's standing instruction to auto-direct their
    balance to the next matching pool student — an AutoInvest-style 'set it and
    forget it'. Each allocation still produces an OFFERED ``Sponsorship`` the
    student must accept (no real money moves) — the SAME safety model as a manual
    fund; it only automates the 'offer' click. One per sponsor (OneToOne).

    Matching (all optional): ``field_pref``/``state_pref`` empty = any; ``max_amount``
    empty = no cap. The sponsor's balance is the real throttle — each allocation
    holds the award, so the standing gift naturally stops when the balance runs low
    (skip silently, by owner decision) and resumes when it's topped up."""
    sponsor = models.OneToOneField(
        Sponsor, on_delete=models.CASCADE, related_name='standing_gift',
    )
    # Empty string = match any field/state (the student's `field_of_study` /
    # `profile.preferred_state`). Non-empty = only that exact value.
    field_pref = models.CharField(max_length=120, blank=True, default='')
    state_pref = models.CharField(max_length=60, blank=True, default='')
    # The most this sponsor will commit to a single student (caps which award
    # amounts qualify). Null = no per-student cap (balance is the only limit).
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    active = models.BooleanField(default=True)
    # When this gift last produced an allocation — used to spread allocations
    # fairly across standing gifts (least-recently-allocated goes next).
    last_allocated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'standing_gifts'

    def __str__(self):
        return f'StandingGift sponsor={self.sponsor_id} active={self.active}'


class WhatsAppMessage(models.Model):
    """Audit log of every outbound WhatsApp send attempt (Twilio).

    Comms are best-effort, so one row is written per attempt: delivery stays
    auditable and failures are visible. ``status`` mirrors Twilio's message status
    where known (queued→sent→delivered, or failed/undelivered)."""
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('undelivered', 'Undelivered'),
    ]
    # SET_NULL (not CASCADE): the message log outlives a deleted application.
    application = models.ForeignKey(
        'ScholarshipApplication', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='whatsapp_messages',
    )
    kind = models.CharField(max_length=50, blank=True, default='')  # e.g. 'interview_reminder_1day'
    to_number = models.CharField(max_length=32, blank=True, default='')  # E.164, or the raw value on a bad number
    body = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    provider_sid = models.CharField(max_length=64, blank=True, default='')  # Twilio message SID
    error = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'whatsapp_messages'
        ordering = ['-created_at']

    def __str__(self):
        return f'WA {self.kind} → {self.to_number} [{self.status}]'


class BursaryAgreement(models.Model):
    """The binding Conditional Bursary Award Agreement a student signs (with a
    parent/guardian as surety/guarantor) when they accept a sponsor's award.

    Parties: the STUDENT (primary), the PARENT/GUARDIAN (surety/guarantor), the
    FOUNDATION (counterparty — signatory from settings) and the PARTNER ORGANISATION
    (non-blocking witness). The DONOR is NEVER a party and is never named — anonymity
    is sacred, so there is no sponsor-name field here. The signed artefact is an
    immutable rendered HTML snapshot (+ its sha256) and a generated PDF in the private
    document bucket. v1: the parent co-signs in-session on the same device; the witness
    attestation is non-blocking. Behind BURSARY_AGREEMENT_ENABLED (default OFF)."""
    application = models.OneToOneField(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='bursary_agreement',
    )
    # The funded allocation this agreement binds (kept even if the sponsorship row is
    # later cleared — SET_NULL, never names the donor).
    sponsorship = models.ForeignKey(
        Sponsorship, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )
    version = models.CharField(max_length=20)
    locale = models.CharField(max_length=5, default='en')

    # ── Particulars (the filled-in terms, frozen at signing) ──────────────────
    award_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_schedule = models.TextField(blank=True, default='')
    institution_name = models.CharField(max_length=255, blank=True, default='')
    course_name = models.CharField(max_length=255, blank=True, default='')
    commencement_date = models.DateField(null=True, blank=True)
    progress_standard = models.TextField(blank=True, default='')
    foundation_signatory_name = models.CharField(max_length=200, blank=True, default='')
    foundation_signatory_title = models.CharField(max_length=255, blank=True, default='')
    foundation_signatory_nric = models.CharField(max_length=20, blank=True, default='')

    # ── Student signature ─────────────────────────────────────────────────────
    student_signed_name = models.CharField(max_length=200, blank=True, default='')
    student_signed_nric = models.CharField(max_length=20, blank=True, default='')
    student_signed_at = models.DateTimeField(null=True, blank=True)
    student_ip = models.GenericIPAddressField(null=True, blank=True)

    # ── Guarantor (parent/guardian surety) signature ──────────────────────────
    guarantor_name = models.CharField(max_length=200, blank=True, default='')
    guarantor_nric = models.CharField(max_length=20, blank=True, default='')
    guarantor_relationship = models.CharField(max_length=50, blank=True, default='')
    guarantor_method = models.CharField(max_length=20, default='in_session')
    guarantor_signed_at = models.DateTimeField(null=True, blank=True)
    guarantor_ip = models.GenericIPAddressField(null=True, blank=True)

    # ── Foundation countersignature ───────────────────────────────────────────
    foundation_signed_by = models.CharField(max_length=200, blank=True, default='')
    foundation_signed_at = models.DateTimeField(null=True, blank=True)

    # ── Witness (partner/referring organisation; non-blocking) ────────────────
    witness_org = models.ForeignKey(
        'courses.PartnerOrganisation', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    witness_signed_by = models.CharField(max_length=200, blank=True, default='')
    witness_name = models.CharField(max_length=200, blank=True, default='')
    witness_signed_at = models.DateTimeField(null=True, blank=True)

    # ── Signing-chain reminder stamps (S6) — when the last nudge for a still-pending
    # signature went out, so the cron doesn't re-send daily (it waits the interval).
    witness_reminded_at = models.DateTimeField(null=True, blank=True)
    countersign_reminded_at = models.DateTimeField(null=True, blank=True)

    # ── Artefact (immutable snapshot) ─────────────────────────────────────────
    rendered_html = models.TextField(blank=True, default='')
    agreement_sha256 = models.CharField(max_length=64, blank=True, default='')
    pdf_storage_path = models.CharField(max_length=500, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bursary_agreements'
        ordering = ['-created_at']

    def __str__(self):
        return f'BursaryAgreement #{self.id} app={self.application_id} ({self.status})'

    @property
    def binds(self):
        """True once BOTH the student and the guarantor have signed — the point the
        contract is binding on the student side (the Foundation/witness follow)."""
        return bool(self.student_signed_at and self.guarantor_signed_at)

    @property
    def is_executed(self):
        """Fully executed: the student+guarantor bind it AND the Foundation has
        countersigned AND the witness has attested."""
        return bool(self.binds and self.foundation_signed_at and self.witness_signed_at)

    @property
    def status(self):
        """Derived lifecycle: draft → student_signed → binds → countersigned → executed."""
        if self.is_executed:
            return 'executed'
        if self.binds and self.foundation_signed_at:
            return 'countersigned'
        if self.binds:
            return 'binds'
        if self.student_signed_at:
            return 'student_signed'
        return 'draft'
