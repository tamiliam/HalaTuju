"""
BrightPath Bursary Programme — data models.

Phase 1 (intake & profile engine). Sponsor and money models arrive in
Phases 2-3. See docs/scholarship/b40-assistance-prd.md and
docs/scholarship/b40-phase1-roadmap.md.
"""
from django.db import models
from django.utils import timezone

from .family import PROFESSION_CHOICES


class Programme(models.Model):
    """A gift programme — THE DURABLE LEVEL of the platform hierarchy (2026-07-26).

    Hierarchy: HalaTuju (platform) -> Organisation -> **Programme** -> Year (intake)
    -> the student's individual award.

    A Programme **IS** the gift ("the BrightPath Bursary", "the Sabah Bursary") — not a
    container for one. **One gift per programme** (owner ruling; see decisions.md
    "One gift per Programme", 2026-07-26). It is the level that NEVER LAPSES: students
    join annually into the same programme, and each annual intake is a
    ``ScholarshipCohort`` hanging beneath it.

    What lives where:
      * **Organisation** — branding, sender identity, staff, and THE SECURITY FENCE.
      * **Programme**    — the gift itself: its rules and (from a later sprint) its fund.
                           Rule DEFAULTS land here; today the tunables still live on the
                           cohort, which is why this model carries none yet.
      * **Year (cohort)** — the annual intake: open/closed, deadlines, per-intake overrides.

    This is NOT a second security boundary. The organisation fence
    (``_AdminBase._org_scoped`` / ``_org_allows``) is unchanged — programme is a
    narrowing INSIDE that wall, never a replacement for it.

    What the award is CALLED ("bursary" / "scholarship" / "assistance") is
    per-ORGANISATION wording resolved through ``branding.py`` — never a property of this
    model and never a behavioural switch. Every award is a GIFT, never a loan
    (platform invariant, decisions.md 2026-07-26).
    """
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT,
        related_name='programmes',
        help_text='The tenant organisation that runs this gift programme.',
    )
    code = models.CharField(
        max_length=50, unique=True,
        help_text="URL-safe slug, e.g. 'brightpath-flagship', 'brightpath-sabah'",
    )
    # Trilingual display name, mirroring the organisation's branding columns. A blank
    # ms/ta falls back to _en at render time (the branding.py fallback convention).
    name_en = models.CharField(max_length=200)
    name_ms = models.CharField(max_length=200, blank=True, default='')
    name_ta = models.CharField(max_length=200, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scholarship_programmes'
        ordering = ['organisation_id', 'code']

    def __str__(self):
        return f'{self.name_en} ({self.code})'


class ScholarshipCohort(models.Model):
    """
    A single application round — the YEAR (intake) level of the hierarchy: one annual
    round of students entering a ``Programme``. Holds the configurable shortlisting
    thresholds and funding parameters so they can be tuned without code changes (the
    shortlisting rules engine in Sprint 3 reads these).

    NOTE (2026-07-26): this model historically did TWO jobs — the programme (rules,
    funding envelope, eligibility) AND the intake year (``b40-2026``, ``year=2026``).
    ``Programme`` above now owns the durable half. Moving the tunables up to become
    programme-level DEFAULTS with per-intake overrides is deliberately a LATER sprint —
    those columns feed the verification engine, so that change is behaviour-sensitive
    and is kept out of the structural one.
    """
    # ── Tenant ownership (platform Sprint 1) ──────────────────────────────────
    # SOURCE OF TRUTH for "which organisation owns this programme". The
    # application-level denormalised copy (platform Sprint 2) must always equal
    # this — never store a second independently-mutable copy. Named
    # owning_organisation deliberately: `PartnerAdmin.org` / `referred_by_org`
    # mean the REFERRING org (attribution), never ownership/access control.
    # Nullable only for additive-migration safety; seeded to BrightPath (org #1)
    # by migration 0098 — NULL carries no meaning and nothing reads it yet.
    owning_organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT,
        null=True, blank=True, related_name='owned_cohorts',
        help_text='The tenant organisation that OWNS this programme (platform Sprint 1). '
                  'SOURCE OF TRUTH for tenancy. ScholarshipApplication.owning_organisation is '
                  'a denormalised copy of this, set in the application save(). A future '
                  '"move a cohort between organisations" flow MUST cascade the new value to '
                  'every one of that cohort.applications.owning_organisation (there is no DB '
                  'trigger — the drift guard test asserts they agree).',
    )
    # Platform programme layer (2026-07-26): the durable gift this intake belongs to.
    # ``organisation`` above stays the SOURCE OF TRUTH for tenancy/security; this is the
    # funding + rules level beneath it. Nullable for additive-migration safety and for
    # bare test fixtures; prod is backfilled. programme.organisation must agree with
    # owning_organisation — the drift guard test asserts it.
    programme = models.ForeignKey(
        'Programme', on_delete=models.PROTECT,
        null=True, blank=True, related_name='cohorts',
        help_text='The gift programme this annual intake belongs to (platform '
                  'programme layer). The programme never lapses; intakes cycle.',
    )

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
        ('profile_complete', 'Awaiting review'),  # student confirmed a complete Step-4 profile; case now with us, not yet reviewed
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
    # Platform tenancy (Sprint 2): the organisation that OWNS this application —
    # a DENORMALISED copy of cohort.owning_organisation (D-8). The cohort is the
    # source of truth; this copy is set automatically in save() so admin queries
    # can be org-fenced (Sprint 3a) without a join. NULL only for bare test
    # fixtures whose cohort has no owning_organisation; prod has none (backfill +
    # the seeded BrightPath cohort). Nothing reads this for authorisation yet.
    owning_organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT,
        null=True, blank=True, related_name='owned_applications',
        help_text="Tenant organisation that owns this application (denormalised "
                  "from cohort.owning_organisation; set in save()).",
    )
    # Platform programme layer (2026-07-26): the gift programme this application is
    # for — a DENORMALISED copy of cohort.programme, derived in save() exactly like
    # owning_organisation above. The cohort remains the source of truth. Set-once, so a
    # later cohort move never silently re-homes an existing application's money.
    # NULL only for bare test fixtures whose cohort has no programme; prod is backfilled.
    programme = models.ForeignKey(
        'Programme', on_delete=models.PROTECT,
        null=True, blank=True, related_name='applications',
        help_text="Gift programme this application belongs to (denormalised from "
                  "cohort.programme; set in save()).",
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
    # How many SEMESTERS this bursary funds — drives the sponsor "Semester completed" badge
    # (results uploaded >= this = the supported period is fulfilled). Owner-set per student over
    # time (varies by pathway + offer: STPM 3 / continuing 1, Matric/Asasi 2, UA/Poly 5-6, PISMP 10).
    # NULL → fall back to the heuristic award_amount/1000 (RM1,000 ≈ one semester); see
    # pool.supported_semesters. Nullable, no backfill.
    supported_semesters = models.PositiveSmallIntegerField(null=True, blank=True)
    # Payments module (D9): the student's Vircle eWallet account ID — 13 digits, prefix
    # VIRCLE_ID_PREFIX ('8000400175'). Arrives via the CSV import, the Action-Centre
    # confirmation, or an admin correction. Blank until captured; the payable fact for a run.
    vircle_id = models.CharField(
        max_length=30, blank=True, default='',
        help_text="Vircle eWallet account ID (13 digits, prefix 8000400175).")
    # Payments module: when Vircle actually ACTIVATED (switched on) this eWallet. Vircle reports
    # nothing back to us, so the ONLY activation signal is the owner's MANUAL 'Activated On' column
    # in the relay sheet; `vircle.sync_activation_status` mirrors that column into this field (the
    # sheet stays the source of truth). ADVISORY only — the payment run surfaces a "not yet
    # activated" flag off this, but it does NOT gate eligibility (owner: don't block payouts on the
    # manual step; a payment to a non-activated wallet bounces, it isn't lost). NULL = not (yet)
    # recorded as activated. See docs/decisions.md.
    vircle_activated_at = models.DateTimeField(null=True, blank=True)
    # Payments module (D6): a per-application "paid ahead of schedule" balance that the NEXT
    # payment run absorbs (rate − credit), then decrements at completion. How the July
    # regularisation is encoded once and consumed automatically. Default 0.
    payment_credit = models.DecimalField(max_digits=10, decimal_places=2, default=0)

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
    # institution. Normally parsed from the offer letter by pathway_engine.parse_reporting_date +
    # stored by services.sync_reporting_date_from_offer; when the letter carries no readable date
    # a reporting_date_unknown clarify is raised AND an officer may record it by hand.
    #
    # NOT display-only: `award` sizes the bursary off the course-start year derived from it, and
    # `payments` gates eligibility on it — a wrong or absent value moves money.
    # NO provenance columns by design (owner 2026-07-23: an officer-entered date is a rare
    # one-off, not worth three columns). The cockpit already distinguishes the two cases for
    # free: its verified tick reads DOCUMENT corroboration (lib/fieldVerification), so a
    # hand-typed date simply renders without a tick. Who typed it lives in the AUDIT log line in
    # services.set_reporting_date_by_officer.
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
    # Contract module: the ContractTemplate version whose comprehension quiz this student
    # passed. Pins the runtime quiz↔contract lockstep — ``bursary.sign_agreement`` refuses
    # (``comprehension_stale``) if the active template no longer matches what they were
    # quizzed on. SET_NULL so retiring a template never deletes the application.
    comprehension_template = models.ForeignKey(
        'ContractTemplate', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    # Witness-organisation OVERRIDE (go-live transition, 2026-07-19). The bursary witness
    # resolution reads override -> profile.referred_by_org -> none. This lets an org_admin
    # assign a witness for a SOURCELESS student (a private arrangement made outside the
    # portal) without inventing a referral. NULL = derive from referred_by_org as before.
    # SET_NULL so retiring an organisation never deletes the application.
    witness_org = models.ForeignKey(
        'courses.PartnerOrganisation', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
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
    # "You haven't submitted yet" nudge for a shortlisted student who gave consent but never
    # pressed the final Review & submit. Stamped with the time of the MOST RECENT nudge (the
    # one-time auto sweep, then any manual org-admin re-nudges); NULL = never nudged, so the
    # auto sweep fires exactly once. Drives the cockpit button's availability + cooldown.
    nudge_sent_at = models.DateTimeField(null=True, blank=True)
    # Check 2 STEP 2: when the single 'answer your queries' reminder was sent (idempotent).
    query_reminder_at = models.DateTimeField(null=True, blank=True)
    # Check 2 STEP 2: when the student was first notified that clarify queries were raised
    # (sent once at submission, so they come back and answer). Idempotent.
    query_raised_notified_at = models.DateTimeField(null=True, blank=True)
    # Partner comms (2026-07-26): when the referring organisation was told this student had
    # completed / had been awarded. Stamped by the hourly `send_partner_milestones` sweep, so
    # each milestone reaches a partner exactly once. NULL = not yet told. Same shape as
    # SponsorProfile.realtime_notified_at. The sweep re-checks the status before sending, which
    # is what stops a reverted transition (revert_if_profile_incomplete / awarded → recommended)
    # from ever producing an email.
    partner_awaiting_notified_at = models.DateTimeField(null=True, blank=True)
    partner_awarded_notified_at = models.DateTimeField(null=True, blank=True)

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
    # post-shortlist ones (interview/contractual/incomplete) are set by an admin action. Drives
    # which decline email is sent and whether the Review & actions panel stays visible (only the
    # pre-shortlist buckets hide it — those applicants were never reviewed; 'incomplete' KEEPS the
    # panel so the recorded reason/who/when of an irreversible reject stays auditable on the case).
    # Anything NOT in emails._DECLINE_TEMPLATES (ineligible, contractual, incomplete) gets the
    # generic warm decline (FAIL_*) — deliberate for 'incomplete': the 'interview' copy opens
    # "thank you for COMPLETING your application", which is false for a student who never did.
    REJECTION_CATEGORIES = [
        ('merit', 'Did not meet the academic/merit floor'),       # engine: academic floor
        ('need', 'Did not meet the financial-need criteria'),     # engine: income test
        ('ineligible', 'Out of scope / ineligible'),              # engine: consent/intent/IPTS gate
        ('interview', 'Reviewed but not selected'),               # admin: post-shortlist decline
        ('contractual', 'Failed post-award contractual steps'),   # admin: post-accept decline
        ('incomplete', 'Did not complete the application'),       # org_admin: drop a stuck shortlisted applicant
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
    # The org_admin's WHY, in their own words (bucket 'incomplete' — see services.org_admin_reject).
    # INTERNAL ONLY: never rendered into the student's decline email (a free-typed, single-language
    # note must not reach a trilingual student mail); it is the audit record of an irreversible act.
    # The QC decline keeps hanging its reason on the DecisionReopen trail instead (decisions.md
    # 2026-07-19) — that trail does not exist at 'shortlisted', which is why this field exists.
    rejection_comments = models.TextField(
        blank=True, default='',
        help_text="The rejecting admin's reason, recorded verbatim (bucket 'incomplete'); internal, never emailed",
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

    # Lifecycle transition stamps — the DATE an application FIRST reached each post-shortlist
    # milestone (set-if-null via `stamp_first`, so a reopen/re-award never overwrites the
    # original). They drive the officer-cockpit header timeline (Submitted·Recommended·Awarded
    # then Awarded·Active·Maintenance). Distinct from the audit stamps above: these mark the
    # STATE transition, not who acted. Null until the app reaches that state.
    recommended_at = models.DateTimeField(null=True, blank=True)  # QC-accept → 'recommended'
    # Email of the QC (super/qc) who QC-Accepted the case → 'recommended'. Distinct from the
    # reviewer's verdict_decided_by/verified_by: this is the separate second pair of eyes. Null
    # for cases recommended before this was captured (2026-07-08) — the UI falls back to the
    # reviewer's accept stamp for those.
    recommended_by = models.CharField(max_length=254, blank=True, default='')
    awarded_at = models.DateTimeField(null=True, blank=True)      # funder commits → 'awarded'
    active_at = models.DateTimeField(null=True, blank=True)       # agreement executed → 'active'
    maintenance_at = models.DateTimeField(null=True, blank=True)  # first payout → 'maintenance'

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
    # The award_amount snapshot, taken in the same breath as pre_decline_status and for the
    # same reason. A decline CLEARS award_amount (a rejected student holds no money), but
    # DECLINE_COOLOFF_DAYS is 7 in production, so every admin_reject is reversible for a week —
    # and a cancelled CONTRACTUAL decline restores a FUNDED student whose sponsorship is
    # reinstated. Without this snapshot that student would come back with no award amount, and
    # `payments.amount_due` would clamp their pay to zero (cap = award − paid) silently. So the
    # clear is only safe BECAUSE it is recoverable. NULL = nothing to restore.
    pre_decline_award_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="award_amount snapshot taken when a decline cleared it; "
                  "cancel_pending_decline restores it (NULL = nothing to restore)",
    )

    # ── QC gap-floor override (verification-model V5 #5, owner decision 1) ─────
    # QC-Accept refuses while any verdict fact is red/'gap' (400 verdict_gap_floor); only a
    # `super` may override, and ONLY with a recorded reason. Mirrors the DecisionReopen
    # attribution pattern (email string + stamp) so the audit survives admin-account churn.
    qc_override_reason = models.TextField(
        blank=True, default='',
        help_text="The super-admin's recorded reason for accepting past the verdict gap floor.")
    qc_override_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text="Email of the super-admin who overrode the QC gap floor.")
    qc_override_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the QC gap floor was overridden.")

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

    def save(self, *args, **kwargs):
        # Derive the denormalised owning organisation from the cohort (D-8): the
        # cohort is the source of truth, this copy exists so admin reads can be
        # org-fenced cheaply (Sprint 3a). Set-once — only when unset and a cohort
        # is present. Prefer the already-loaded cohort relation to avoid a query
        # on hot paths; else a single lightweight indexed lookup by cohort_id.
        # Stays None for a bare-cohort test fixture (cohort with no org) — a safe
        # degenerate bucket the fence still partitions correctly (=None → IS NULL).
        # Same derivation for the programme layer (2026-07-26): the gift this
        # application belongs to. Both copies are read from the cohort in ONE query
        # when the relation isn't already cached, so this adds no query on hot paths.
        needs_org = self.owning_organisation_id is None
        needs_programme = self.programme_id is None
        if (needs_org or needs_programme) and self.cohort_id:
            cached_cohort = self._state.fields_cache.get('cohort')
            if cached_cohort is not None:
                if needs_org:
                    self.owning_organisation_id = cached_cohort.owning_organisation_id
                if needs_programme:
                    self.programme_id = cached_cohort.programme_id
            else:
                derived = (
                    ScholarshipCohort.objects
                    .filter(pk=self.cohort_id)
                    .values_list('owning_organisation_id', 'programme_id')
                    .first()
                )
                if derived is not None:
                    if needs_org:
                        self.owning_organisation_id = derived[0]
                    if needs_programme:
                        self.programme_id = derived[1]
        super().save(*args, **kwargs)

    def stamp_first(self, field):
        """Set a lifecycle timestamp the FIRST time this app reaches that state
        (set-if-null). Returns the field name if it stamped — fold that into the
        caller's ``save(update_fields=[...])`` — else None. Does NOT save, so it
        composes with the transition's own save. A reopen/re-award that revisits the
        state leaves the original date intact."""
        if getattr(self, field) is None:
            setattr(self, field, timezone.now())
            return field
        return None

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
        # V4 — Check-2 academic-completeness docs promoted out of the 'other' catch-all (officers
        # were hand-requesting both). A school-leaving certificate (surat berhenti sekolah /
        # testimonial) for a post-SPM applicant; a current-semester result slip (latest CGPA) for
        # a student ALREADY studying (continuing STPM / college) — the model had no pre-award
        # current-performance box (SemesterResult is post-award only). Gemini-extracted; soft.
        ('school_leaving_cert', 'School Leaving Certificate'),
        ('semester_result', 'Semester Result Slip'),
        # Catch-all for a reviewer-requested document not in the fixed list. Lands under "Other".
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
    # ── Version history (Documents-box reorg Phase 2) ──────────────────────
    # A re-upload no longer HARD-deletes the old copy — it stamps the old row
    # `superseded_at` and points `superseded_by` at the replacement, keeping an
    # audit trail of what was replaced (shown under the officer "Old / Replaced"
    # sub-list). `superseded_at IS NULL` = the live row.
    # CRITICAL: every verdict / gate / completeness / student-facing read MUST
    # exclude superseded rows — funnel through `ApplicantDocument.live(qs)`
    # below. The default manager is DELIBERATELY unfiltered so the admin
    # serializer still returns superseded rows to show the history (a filtering
    # default manager would hide them from `application.documents`).
    superseded_at = models.DateTimeField(null=True, blank=True)
    superseded_by = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='supersedes',
    )

    class Meta:
        db_table = 'applicant_documents'
        ordering = ['-uploaded_at']

    @staticmethod
    def live(qs):
        """Filter a documents queryset (e.g. `application.documents`) to the
        live rows only. The single helper every verdict/gate read funnels
        through — `superseded_at IS NULL`."""
        return qs.filter(superseded_at__isnull=True)

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
    # Last time this sponsor was seen using their own portal — stamped by SponsorMeView,
    # the one call every sponsor page makes. Nothing recorded this before (no `last_login`
    # anywhere in the codebase), so an approved sponsor who never came back was
    # indistinguishable from an active one. NULL = not seen since this shipped.
    # Deliberately coarse: throttled to one write a day (`SPONSOR_SEEN_THROTTLE_HOURS`),
    # because "are they still with us" is a question about days, not minutes, and a write
    # on every portal request would put a needless UPDATE on a read path.
    last_seen_at = models.DateTimeField(null=True, blank=True)
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


class SponsorProgrammeMembership(models.Model):
    """A sponsor's acceptance into ONE gift programme (platform programme layer, 2026-07-26).

    The owner's rule: a sponsor sees a programme's students only if they *"specifically
    onboarded into both and accepted into both — and that is not a given"*. So the sponsor
    ACCOUNT stays platform-level (one login, one identity, one vetting of "is this a real,
    legitimate person") while **acceptance is per programme**, and it survives the year
    rollover because it attaches to the durable Programme, not to an intake.

    Two gates, both of which must pass before a sponsor sees a student:
      1. ``Sponsor.status == 'approved'`` — the ACCOUNT is vetted at all (unchanged);
      2. an ``approved`` membership row here — accepted into THIS programme.

    This narrows WHICH cards a funder sees. It must never touch the allowlist governing
    WHAT a card shows — anonymity is absolute and is enforced elsewhere (``pool.py`` +
    the allowlist serializers). See decisions.md, "Benefactor anonymity is absolute".
    """
    STATUS = [
        ('pending', 'Pending review'),   # onboarded into the programme, awaiting vetting
        ('approved', 'Approved'),         # accepted — may browse THIS programme's pool
        ('rejected', 'Rejected'),         # not accepted into this programme
        ('suspended', 'Suspended'),       # access to this programme revoked after approval
    ]
    sponsor = models.ForeignKey(
        Sponsor, on_delete=models.CASCADE, related_name='programme_memberships',
    )
    programme = models.ForeignKey(
        'Programme', on_delete=models.PROTECT, related_name='sponsor_memberships',
    )
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    # Who vetted this membership + when (the org admin acting for that programme).
    vetted_by = models.CharField(max_length=200, blank=True, default='')
    vetted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sponsor_programme_memberships'
        # One membership per (sponsor, programme) — acceptance is a state, not a log.
        constraints = [
            models.UniqueConstraint(fields=['sponsor', 'programme'],
                                    name='uniq_sponsor_programme_membership'),
        ]
        ordering = ['sponsor_id', 'programme_id']

    def __str__(self):
        return f'sponsor={self.sponsor_id} programme={self.programme_id} {self.status}'

    @property
    def is_approved(self):
        return self.status == 'approved'


class Donation(models.Model):
    """Phase E3: money a sponsor donates into myNADI (via toyyibPay; mocked until
    the gateway is wired). A donation is FINAL — it is myNADI's money. It credits
    the sponsor's internal **directed-giving balance** (donations − active
    allocations); the sponsor can only redirect that balance within the platform,
    never withdraw it to a bank. Outbound disbursement is a later, gated phase."""
    sponsor = models.ForeignKey(
        Sponsor, on_delete=models.CASCADE, related_name='donations',
    )
    # Platform programme layer (2026-07-26): the gift programme this money was given TO.
    # Funds given to one programme are never visible or spendable in another — a donor
    # gives to "Sabah", not to the platform at large (decisions.md, "Restricted funds and
    # sponsor acceptance attach to the Programme"). The wallet is therefore per
    # (sponsor, programme), never one pool. NULL only for bare test fixtures; prod is
    # backfilled to the flagship. Balance reads go through sponsorship.sponsor_balance().
    programme = models.ForeignKey(
        'Programme', on_delete=models.PROTECT,
        null=True, blank=True, related_name='donations',
        help_text='The gift programme this donation is restricted to.',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # toyyibPay billCode/ref once real; 'mock' for dev/dummy donations.
    reference = models.CharField(max_length=100, blank=True, default='mock')
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Provenance + sign-off (P4, 2026-07-26) ────────────────────────────────────
    # ONE record, different provenance — an admin-recorded credit today and a gateway
    # donation post-CLBG are the same row with a different `source`, never two parallel
    # money systems (decisions.md, "Money is OFF-platform until the CLBG exists").
    SOURCE_LEGACY = 'legacy'                # pre-P4 rows; provenance not recorded
    SOURCE_ADMIN = 'admin_recorded'         # off-platform gift, keyed in by an org admin
    SOURCE_GATEWAY = 'gateway'              # paid through the platform (post-CLBG)
    SOURCE_MOCK = 'mock'                    # dev/self-service stub — never real money
    SOURCES = [
        (SOURCE_LEGACY, 'Legacy'), (SOURCE_ADMIN, 'Admin-recorded'),
        (SOURCE_GATEWAY, 'Gateway'), (SOURCE_MOCK, 'Mock'),
    ]
    source = models.CharField(max_length=20, choices=SOURCES, default=SOURCE_LEGACY)
    # The bank-transfer reference. MANDATORY for an admin-recorded credit — it is the only
    # thread back to real money while the cash sits in an account the platform cannot see,
    # and what lets each credit reconcile 1:1 with a line on the bank statement (owner:
    # "one row per bank transfer").
    external_reference = models.CharField(max_length=120, blank=True, default='')

    # Sign-off chain — DELIBERATELY the same shape as PaymentRun's
    # (`draft → admin_signed → [finance_checked] → confirmed`), and the finance step is
    # likewise CONDITIONAL and never stored: payments.finance_check_required(organisation)
    # is evaluated live, so appointing a finance admin arms the check even for a credit
    # already mid-chain. ⚠ A change to the payment-run chain must update this one in the
    # same commit — they are one design (decisions.md).
    STATUS_DRAFT = 'draft'
    STATUS_ADMIN_SIGNED = 'admin_signed'
    STATUS_FINANCE_CHECKED = 'finance_checked'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUSES = [
        (STATUS_DRAFT, 'Draft'), (STATUS_ADMIN_SIGNED, 'Admin signed'),
        (STATUS_FINANCE_CHECKED, 'Finance checked'), (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    # Default 'confirmed': money that arrived by gateway/legacy IS confirmed by arrival.
    # ONLY the admin-recorded path opens at 'draft' — see sponsorship.record_admin_credit,
    # which is the sole creator of a SOURCE_ADMIN row (asserted by a source guard test).
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_CONFIRMED)
    # Each signature is a (name, email) PAIR, exactly as PaymentRun stores it. The EMAIL is
    # the identity key — pairwise distinctness is computed on it, never on the name. This is
    # not theoretical tidiness: prod carries TWO active admins both named "Ve. Elanjelian"
    # (a super and an org_admin, different accounts), so a name-keyed rule would BOTH let one
    # person fill two slots under two names AND wrongly refuse two genuinely different people
    # who share one. The name is stored for display and for the typed-name match only.
    recorded_by = models.CharField(max_length=200, blank=True, default='')
    recorded_by_email = models.CharField(max_length=254, blank=True, default='')
    recorded_at = models.DateTimeField(null=True, blank=True)
    finance_checked_by = models.CharField(max_length=200, blank=True, default='')
    finance_checked_by_email = models.CharField(max_length=254, blank=True, default='')
    finance_checked_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.CharField(max_length=200, blank=True, default='')
    confirmed_by_email = models.CharField(max_length=254, blank=True, default='')
    confirmed_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_spendable(self):
        """Only a CONFIRMED credit raises spendable balance. A recorded-but-unconfirmed
        credit is visible to admins and invisible to the sponsor, so it can never be
        allocated to a student before the second signature."""
        return self.status == self.STATUS_CONFIRMED

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


class PaymentRun(models.Model):
    """A monthly Vircle payment run for one organisation (Payments module, D1/D2).

    Holds the WORKING state — draft amounts, per-student include/exclude, the two typed
    signatures — on TOP of the immutable Disbursement ledger. Released Disbursement rows are
    created ONLY at countersignature (``payments.complete``), so "paid to date" is always
    ``SUM(released disbursements)`` — one source of truth for history, the backfill, and
    future runs alike (D1).

    Sign-off is a maker→checker chain (D2): ``draft → admin_signed → [finance_checked] →
    completed`` (+ ``cancelled``). The status field + a per-step signature TRIPLE
    (name/email/at) — not a boolean pair — is what let the finance 'checker' step land
    additively (Sprint 14, 2026-07-23) exactly where this docstring parked it.

    **The finance step is CONDITIONAL and its requirement is never stored here.**
    ``payments.finance_check_required(organisation)`` is evaluated LIVE at each sign attempt
    (the org has ≥1 active ``finance`` PartnerAdmin). With none, the chain runs as the
    original two steps, byte-identical. Deliberately not a column: storing it would freeze a
    run's shape at creation, and the owner's rule is that activating finance DOES arm the
    check for a run already sitting at ``admin_signed``. A historical ``completed`` run
    simply carries an empty finance triple — read it as "no finance admin existed", not as
    "the step was skipped".

    Backfill runs (D8) are first-class ``completed`` runs with no signatures (the signature
    fields are nullable/blank)."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('admin_signed', 'Admin signed'),
        ('finance_checked', 'Finance checked'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT, related_name='payment_runs',
    )
    # The GIFT this run pays from (P2b). A run pays students of ONE programme, so a benefactor's
    # money can never leave the gift it was given to and each programme reconciles on its own.
    # NULLABLE for history: every run created before P2b is backfilled to its items' programme,
    # and the column stays nullable so a legacy row is never rewritten into a claim it cannot
    # support. New runs REQUIRE it — enforced in `payments.create_run`, not by the column, so
    # the rule lives with the behaviour rather than in a schema constraint that would also
    # refuse the backfill.
    programme = models.ForeignKey(
        'Programme', on_delete=models.PROTECT, related_name='payment_runs',
        null=True, blank=True,
    )
    payment_date = models.DateField(help_text="The Vircle payment date; validated >= today at creation.")
    # The MONTH this run pays for (1st of that month). A run dated 30 Jun can pay for July, so the
    # covered month is explicit, not derived from payment_date. A student already paid for a month
    # (via a completed run with the same period_month) is excluded — no double-paying a month.
    period_month = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    reference = models.CharField(
        max_length=50, unique=True,
        help_text="e.g. 'PR-2026-08-001'; 'backfill-YYYY-MM-DD' for imports.")
    created_by = models.CharField(max_length=254, blank=True, default='')
    # Maker (first signature, role admin), then approver (countersignature, role org_admin) — D2.
    admin_signed_name = models.CharField(max_length=200, blank=True, default='')
    admin_signed_email = models.CharField(max_length=254, blank=True, default='')
    admin_signed_at = models.DateTimeField(null=True, blank=True)
    # Finance checker (middle signature, role finance) — Sprint 14. Empty on every run made
    # before the role existed, and on every run in an org with no active finance admin.
    finance_signed_name = models.CharField(max_length=200, blank=True, default='')
    finance_signed_email = models.CharField(max_length=254, blank=True, default='')
    finance_signed_at = models.DateTimeField(null=True, blank=True)
    org_admin_signed_name = models.CharField(max_length=200, blank=True, default='')
    org_admin_signed_email = models.CharField(max_length=254, blank=True, default='')
    org_admin_signed_at = models.DateTimeField(null=True, blank=True)
    # The CSV handed to Vircle (best-effort Drive write, D7); blank if the upload failed.
    drive_file_url = models.URLField(blank=True, default='')
    note = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_runs'
        ordering = ['-payment_date', '-id']

    def __str__(self):
        return f'PaymentRun {self.reference} {self.payment_date} ({self.status})'


class PaymentRunItem(models.Model):
    """One student's line in a PaymentRun. Amounts + the award/paid/vircle SNAPSHOTS freeze
    at creation so the signed record can't drift after signatures are collected; the
    ``disbursement`` is linked when the run completes."""
    run = models.ForeignKey(PaymentRun, on_delete=models.CASCADE, related_name='items')
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.PROTECT, related_name='payment_run_items',
    )
    included = models.BooleanField(default=True)
    exclude_reason = models.CharField(max_length=200, blank=True, default='')  # required when excluded
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)   # editable in draft; capped at remaining
    credit_applied = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="How much payment_credit this item consumed (audit; decremented at completion).")
    # Snapshots at creation (so the signed record can't drift):
    award_amount_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_to_date_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vircle_id_snapshot = models.CharField(max_length=30, blank=True, default='')
    # Set at completion — the released Disbursement this item produced. SET_NULL so deleting a
    # Disbursement never erases the run history.
    disbursement = models.ForeignKey(
        Disbursement, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_run_items',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_run_items'
        unique_together = ('run', 'application')
        ordering = ['id']

    def __str__(self):
        return f'PaymentRunItem run={self.run_id} app={self.application_id} {self.amount}'


# ── Requests component tree (Sprint 15.1) — the SINGLE source of truth ─────────────────
# A request's COMPONENT is the admin surface it is about. Parents are the org_admin-reachable
# surfaces (super-only Students + Course Data were REMOVED in 15.1); the only parent with
# sub-components is ``applications`` (the B40 pipeline stages). A sub-component's stored value is
# ``f'{parent}_{suffix}'`` (UNDERSCORE separator — a dot breaks the nested i18n lookup); every value
# is ≤30 chars (the column is varchar(30) with NO DB CHECK, so the app-level clamp
# ``org_requests.VALID_COMPONENTS`` — derived from this tree — MUST carry every value).
# ``org_requests.VALID_COMPONENTS`` and the model ``COMPONENT_CHOICES`` both derive from this map;
# the FE mirror + the i18n keys are pinned to it by ``test_org_requests`` so the three can never
# drift (never hand-enumerate — lessons.md).
REQUEST_COMPONENT_TREE = {
    'applications': (
        'student_details', 'documents', 'ai_prediction', 'queries', 'interview',
        'decision', 'agreement', 'student_profile',
    ),
    'sponsors': (),
    'payments': (),
    'contracts': (),
    'sources': (),
    'administration': (),
    'access': (),
    'other': (),
}

# English labels (human text — the VALUES derive from the tree, the labels are looked up here).
_REQUEST_COMPONENT_LABELS = {
    'applications': 'B40 Applications',
    'applications_student_details': 'Student details',
    'applications_documents': 'Documents',
    'applications_ai_prediction': 'AI Prediction & verdicts',
    'applications_queries': 'Queries & blockers',
    'applications_interview': 'Interview',
    'applications_decision': 'Recommendation & QC',
    'applications_agreement': 'Bursary agreement',
    'applications_student_profile': 'Student profile (sponsor-facing)',
    'sponsors': 'Sponsors',
    'payments': 'Payments',
    'contracts': 'Contracts',
    'sources': 'Sources',
    'administration': 'Administration',
    'access': 'Sign-in & access',
    'other': 'Other',
}


def flatten_component_tree(tree):
    """Ordered (value, ...) for the tree: each parent, followed by its ``parent_sub`` children."""
    out = []
    for parent, subs in tree.items():
        out.append(parent)
        out.extend(f'{parent}_{sub}' for sub in subs)
    return tuple(out)


class OrgRequest(models.Model):
    """An organisation's bug report / feature request, managed through the Requests space
    (Sprint 15). Named ``OrgRequest`` (not ``Request``) to stay grep-unambiguous against the
    HTTP request; the service module is ``org_requests.py`` (not ``requests.py``, which collides
    with the live HTTP library import).

    Flow: an org_admin submits → the AI reviewer (``org_requests.run_ai_review``, via the
    ``contracts._gemini_generate`` seam) classifies bug/feature, estimates work in HOURS, and may
    ask the requestee clarifying questions (which flow to the submitter DIRECTLY — no owner gate);
    the owner triages (authoritative, may reclassify per the adjudication rule) and sends an
    owner-gated quote in hours. The requestee accepts / rejects / defers / modifies.

    The AI DRAFT (``ai_draft_*`` + ``triage_note``) is NEVER in the org-facing serializer — only
    the owner sees it. The org sees the QUOTE the owner sends, not the AI's estimate.

    Adjudication rule (published verbatim, owner 2026-07-24): behaviour contradicting the role
    matrix / manual = bug (free); working-as-documented-but-wanted-different = feature (priced).
    Quotes are hours-only in v1 (no money — no hourly rate exists yet).
    """
    KIND_CHOICES = [('bug', 'Bug report'), ('feature', 'Feature request')]
    LANE_CHOICES = [('small_change', 'Small change'), ('sprint', 'Sprint')]
    # Bugzilla-style optional scoping fields (Sprint 15 increment, owner 2026-07-24). COMPONENT is
    # the admin surface the request is about — the user-facing MODULE names the admin nav uses
    # (halatuju-web/src/app/admin/layout.tsx + the Administration hub). URGENCY is the ORG's own
    # signal (the owner still adjudicates). All three are OPTIONAL ('' allowed).
    # Derived from REQUEST_COMPONENT_TREE (single source of truth, Sprint 15.1). Students +
    # Course Data removed (super-only surfaces); the 8 ``applications_*`` sub-components added.
    COMPONENT_CHOICES = [
        (value, _REQUEST_COMPONENT_LABELS.get(value, value))
        for value in flatten_component_tree(REQUEST_COMPONENT_TREE)
    ]
    URGENCY_CHOICES = [
        ('blocking', 'Blocking'),
        ('important', 'Important'),
        ('nice_to_have', 'Nice to have'),
    ]
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('triaged', 'Triaged'),
        ('quoted', 'Quoted'),
        ('approved', 'Approved'),
        ('deferred', 'Deferred'),
        ('scheduled', 'Scheduled'),
        ('done', 'Done'),
        ('declined', 'Declined'),
    ]

    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT, related_name='org_requests',
    )
    submitted_by = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.PROTECT, related_name='submitted_org_requests',
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')

    # Optional scoping (Sprint 15 increment) — org-submitted, org-visible.
    component = models.CharField(max_length=30, choices=COMPONENT_CHOICES, blank=True, default='')
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, blank=True, default='')
    steps_to_reproduce = models.TextField(blank=True, default='')

    # Clarification thread (AI ↔ requestee — flows FREE, no owner gate; owner CC'd by email).
    # Each entry: {question, asked_at, answer|null, answered_at|null}. modify() appends an old
    # description here as history too.
    clarifications = models.JSONField(default=list, blank=True)
    ai_run_count = models.PositiveSmallIntegerField(default=0)   # auto-run cap = 3

    # AI draft — NEVER in the org-facing payload (owner-only). The hours estimate stays here
    # until the owner sends a quote.
    ai_draft_kind = models.CharField(max_length=10, blank=True, default='')
    ai_draft_lane = models.CharField(max_length=20, blank=True, default='')
    ai_draft_hours = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    ai_draft_note = models.TextField(blank=True, default='')
    ai_draft_model = models.CharField(max_length=50, blank=True, default='')
    ai_draft_at = models.DateTimeField(null=True, blank=True)

    # Owner triage (authoritative — may reclassify kind per the adjudication rule).
    triaged_kind = models.CharField(max_length=10, blank=True, default='')
    lane = models.CharField(max_length=20, blank=True, default='')
    triage_note = models.TextField(blank=True, default='')
    triaged_at = models.DateTimeField(null=True, blank=True)

    # Owner quote (hours only, v1).
    quote_hours = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    quote_margin_pct = models.PositiveSmallIntegerField(null=True, blank=True)
    quote_note = models.TextField(blank=True, default='')
    quoted_at = models.DateTimeField(null=True, blank=True)

    approved_at = models.DateTimeField(null=True, blank=True)
    scheduled_for = models.DateField(null=True, blank=True)
    decline_reason = models.TextField(blank=True, default='')
    # Who ended it at 'declined': 'super' (decline) or 'org_admin' (withdraw) — audit.
    declined_by_role = models.CharField(max_length=20, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'org_requests'
        ordering = ('-created_at',)

    def __str__(self):
        return f'OrgRequest #{self.pk} [{self.status}] {self.title[:40]}'


class OrgRequestAttachment(models.Model):
    """A screenshot attached to an OrgRequest (Sprint 15.1, closes TD-172). Images ONLY, ≤5 per
    request. Mirrors ``ApplicantDocument``'s metadata shape — only the storage path + metadata live
    here; the file bytes go browser→Supabase via a signed URL and never pass through Django.

    Org-fenced by construction: the storage key is ``requests/<org_id>/<request_id>/<uuid>`` (via
    ``storage.build_request_attachment_key``); the signed download URL is refused when the key's org
    disagrees with the request's org (``storage.resolve_org_for_path``), and every endpoint reaches
    an attachment only through the org-fenced request lookup (a cross-org request id is 404).
    """
    org_request = models.ForeignKey(
        OrgRequest, on_delete=models.CASCADE, related_name='attachments',
    )
    storage_path = models.CharField(max_length=500)
    original_filename = models.CharField(max_length=255, blank=True, default='')
    content_type = models.CharField(max_length=100, blank=True, default='')
    size = models.IntegerField(default=0)
    uploaded_by = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.PROTECT, related_name='org_request_attachments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'org_request_attachments'
        ordering = ['id']

    def __str__(self):
        return f'OrgRequestAttachment #{self.pk} for OrgRequest #{self.org_request_id}'


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
    # Contract module: the versioned ContractTemplate this agreement was rendered from.
    # PROTECT — a deployed template that has governed a signed agreement can never be
    # deleted. Null for legacy agreements rendered from the hard-coded bursary.py
    # constants (pre-module); ``version`` above is filled from the template when present.
    template = models.ForeignKey(
        'ContractTemplate', null=True, blank=True,
        on_delete=models.PROTECT, related_name='agreements',
    )
    # Execution distribution (Sprint 5): the signed PDF is emailed to student + witness +
    # org admin and filed in Google Drive. Stamps guard idempotent best-effort delivery.
    executed_pdf_emailed_at = models.DateTimeField(null=True, blank=True)
    drive_file_url = models.URLField(blank=True, default='')

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


# ─────────────────────────────────────────────────────────────────────────────
# Contract module (org-owned, versioned bursary agreement).
#
# Replaces the hard-coded bursary.py constants + the static FE quiz with an
# org-authored, versioned, deployable artifact. Lifecycle is DEPLOYMENT, not
# approval: draft → pending_deployment → active → archived. A non-draft template
# is IMMUTABLE (the contracts.py authoring calls refuse status != 'draft'), which
# is what lets a signed BursaryAgreement PROTECT-reference the exact version it
# was rendered from, forever. Module is INERT in Sprint 1 — nothing reads it yet.
# ─────────────────────────────────────────────────────────────────────────────
class ContractTemplate(models.Model):
    """A versioned bursary-agreement template owned by one organisation.

    English is authoritative (the lawyer vets English only); ms/ta are courtesy
    translations offered only when fully translated. Exactly one ACTIVE template
    per org at a time — deploying a new version atomically archives the previous
    active one (see ``contracts.deploy``)."""
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('pending_deployment', 'Pending deployment'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    )
    PARENT_ROLE_CHOICES = (
        ('co_signer_all', 'Co-signer (all students)'),
        ('minor_only', 'Co-signer (minors only)'),
    )
    WITNESS_POLICY_CHOICES = (
        ('none', 'No witness'),
        ('optional', 'Witness optional'),
        ('required', 'Witness required'),
    )

    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT,
        related_name='contract_templates',
    )
    version = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Localised document chrome (en required; ms/ta blank until translated).
    title_en = models.CharField(max_length=255, blank=True, default='')
    title_ms = models.CharField(max_length=255, blank=True, default='')
    title_ta = models.CharField(max_length=255, blank=True, default='')
    preamble_en = models.TextField(blank=True, default='')
    preamble_ms = models.TextField(blank=True, default='')
    preamble_ta = models.TextField(blank=True, default='')
    progress_standard_en = models.TextField(blank=True, default='')
    progress_standard_ms = models.TextField(blank=True, default='')
    progress_standard_ta = models.TextField(blank=True, default='')

    # ── Flow config (party + signing rules) ───────────────────────────────────
    # NRIC is NEVER seeded/committed — the org admin fills it in the UI before deploy.
    counterparty_name = models.CharField(max_length=200, blank=True, default='')
    counterparty_title = models.CharField(max_length=255, blank=True, default='')
    counterparty_nric = models.CharField(max_length=20, blank=True, default='')
    # Free-text (multi-line) address — TextField so a long address can't overflow (cf. the
    # heading varchar(255) lesson). Pre-filled from the imported parties recital.
    counterparty_address = models.TextField(blank=True, default='')
    counterparty_notify_emails = models.JSONField(default=list, blank=True)
    parent_role = models.CharField(
        max_length=20, choices=PARENT_ROLE_CHOICES, default='co_signer_all',
    )
    parent_pin_required = models.BooleanField(default=True)
    witness_policy = models.CharField(
        max_length=10, choices=WITNESS_POLICY_CHOICES, default='optional',
    )

    # ── Attestation (the lawyer-vetting gate — T2) ────────────────────────────
    vetted_by_name = models.CharField(max_length=200, blank=True, default='')
    vetted_on = models.DateField(null=True, blank=True)
    vetting_attested_by_email = models.CharField(max_length=254, blank=True, default='')
    vetting_attested_at = models.DateTimeField(null=True, blank=True)

    # ── Lifecycle stamps ──────────────────────────────────────────────────────
    created_by_email = models.CharField(max_length=254, blank=True, default='')
    submitted_by_email = models.CharField(max_length=254, blank=True, default='')
    submitted_by_at = models.DateTimeField(null=True, blank=True)
    deployed_by_email = models.CharField(max_length=254, blank=True, default='')
    deployed_by_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contract_templates'
        ordering = ['organisation_id', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['organisation', 'version'],
                name='uniq_contract_template_org_version',
            ),
        ]

    def __str__(self):
        return f'{self.organisation_id}/{self.version} ({self.status})'

    @property
    def languages_available(self):
        """en, plus each language whose title/preamble/progress AND every clause
        (heading+body) are fully translated. English is always available."""
        langs = ['en']
        for lang in ('ms', 'ta'):
            if not (getattr(self, f'title_{lang}') and getattr(self, f'preamble_{lang}')
                    and getattr(self, f'progress_standard_{lang}')):
                continue
            clauses = list(self.clauses.all())
            if clauses and all(
                getattr(c, f'heading_{lang}') and getattr(c, f'body_{lang}')
                for c in clauses
            ):
                langs.append(lang)
        return langs


class ContractClause(models.Model):
    """One numbered clause of a ContractTemplate. English is authoritative; bodies
    are PLAIN TEXT (a blank line is a paragraph break) — no rich text in v1, for
    xhtml2pdf safety. A clause may be flagged as a comprehension-quiz candidate,
    in which case it carries a per-language quiz payload."""
    template = models.ForeignKey(
        ContractTemplate, on_delete=models.CASCADE, related_name='clauses',
    )
    order = models.PositiveIntegerField()
    # Hierarchy depth (2026-07-19): 0 = clause (1., 2.), 1 = sub-clause (1.1), 2 = sub-sub-clause
    # (i), ii)). The flat `order` sequence + `level` encodes the tree; numbers are COMPUTED from the
    # (order, level) run (contracts.clause_numbers), never stored. A clause may only be one level
    # deeper than the one before it (no skipping). A comprehension quiz may sit on a clause (0) or
    # sub-clause (1) — never a sub-sub-clause (2) — and a clause + its own descendants are mutually
    # exclusive (contracts.MAX_QUIZ_LEVEL / _resolve_quiz_flags).
    level = models.PositiveSmallIntegerField(default=0)
    heading_en = models.CharField(max_length=255, blank=True, default='')
    heading_ms = models.CharField(max_length=255, blank=True, default='')
    heading_ta = models.CharField(max_length=255, blank=True, default='')
    body_en = models.TextField(blank=True, default='')
    body_ms = models.TextField(blank=True, default='')
    body_ta = models.TextField(blank=True, default='')

    is_quiz_candidate = models.BooleanField(default=False)
    # Each quiz payload: {tag, plain, question, options:[3 strings], correct:0-2, why}
    # (matches the FE QuizCheckpoint). Empty dict = no quiz for that language.
    quiz_en = models.JSONField(default=dict, blank=True)
    quiz_ms = models.JSONField(default=dict, blank=True)
    quiz_ta = models.JSONField(default=dict, blank=True)
    # Audit: which Gemini model drafted the quiz. Blank = hand-written/seeded.
    quiz_generated_model = models.CharField(max_length=80, blank=True, default='')

    class Meta:
        db_table = 'contract_clauses'
        ordering = ['template_id', 'order']
        constraints = [
            models.UniqueConstraint(
                fields=['template', 'order'],
                name='uniq_contract_clause_template_order',
            ),
        ]

    def __str__(self):
        return f'{self.template_id}#{self.order} {self.heading_en}'


class PaymentScheduleRow(models.Model):
    """One row of a template's versioned payment schedule. A student is governed by
    the schedule of the version they signed, forever. The total is DERIVED —
    ``len(paid_offsets) * monthly_amount`` — never stored, so it can never drift
    from the offsets. ``paid_offsets`` are sorted 0-based month offsets from
    ``start_month`` and encode start, count, and gap/exam months in one field."""
    template = models.ForeignKey(
        ContractTemplate, on_delete=models.CASCADE, related_name='schedule_rows',
    )
    pathway = models.CharField(max_length=40)
    # '' = the plain pathway row; 'continuing' = the continuing-student variant.
    variant = models.CharField(max_length=20, blank=True, default='')
    label_en = models.CharField(max_length=120, blank=True, default='')
    label_ms = models.CharField(max_length=120, blank=True, default='')
    label_ta = models.CharField(max_length=120, blank=True, default='')
    monthly_amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_month = models.PositiveSmallIntegerField()  # 1-12
    paid_offsets = models.JSONField(default=list, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'contract_payment_schedule_rows'
        ordering = ['template_id', 'sort_order', 'pathway', 'variant']
        constraints = [
            models.UniqueConstraint(
                fields=['template', 'pathway', 'variant'],
                name='uniq_contract_schedule_template_pathway_variant',
            ),
        ]

    def __str__(self):
        return f'{self.template_id} {self.pathway}/{self.variant or "-"}'

    @property
    def total(self):
        from decimal import Decimal
        return (self.monthly_amount or Decimal('0')) * len(self.paid_offsets or [])


class UsageEvent(models.Model):
    """Per-tenant usage meter (Billing & usage v1 — Sprint 13a).

    ONE row per billable provider call at a sanctioned seam (Gemini / Cloud Vision /
    OpenAI / Brevo email / Twilio WhatsApp). Written UNCONDITIONALLY from deploy, ABSOLUTELY
    best-effort (see ``apps.scholarship.usage.record_usage`` — a metering failure can never
    break the user-facing call). Read only by the super/org_admin usage screen. Units and
    token counts ONLY — v1 carries NO prices (there is no price table yet).

    ``organisation`` is NULL for platform-base work (course-selector reports, ops mail) — the
    tenancy attribution kept for reconciliation, per the billing-sources investigation.
    """
    SERVICE_CHOICES = [
        ('gemini', 'Gemini'),
        ('vision_ocr', 'Cloud Vision OCR'),
        ('openai', 'OpenAI'),
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    ]

    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT, null=True, blank=True,
        related_name='usage_events',
        help_text='The tenant this billable call is attributed to. NULL = platform-base '
                  'work (course-selector reports, ops mail), kept for reconciliation.')
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='usage_events',
        help_text='The application in hand when known (SET_NULL so purging a case never '
                  'deletes its billing history).')
    service = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    model = models.CharField(max_length=80, blank=True, default='',
                             help_text='The provider model name (AI only), e.g. gemini-2.5-flash.')
    source = models.CharField(max_length=40, blank=True, default='',
                              help_text='The call-path tag, e.g. doc_extract, ic_fallback, '
                                        'profile_draft, report, or an email/whatsapp function tag.')
    quantity = models.IntegerField(default=1)
    input_tokens = models.IntegerField(null=True, blank=True,
                                       help_text='Prompt token count (AI only), from the '
                                                 "provider response's usage metadata.")
    output_tokens = models.IntegerField(null=True, blank=True,
                                        help_text='Completion token count (AI only).')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'usage_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organisation', 'created_at'], name='usage_org_created_idx'),
        ]

    def __str__(self):
        who = self.organisation_id or 'platform'
        return f'{self.service}:{self.source or "-"} org={who} @ {self.created_at:%Y-%m-%d}'


class PlatformCost(models.Model):
    """What the PLATFORM actually cost, per month, per SKU — the cost side of billing.

    Deliberately a SEPARATE ledger from ``UsageEvent``, because the two answer different
    questions and are true at different grains:

      * ``UsageEvent``  — "what did this ORGANISATION consume?"  per event, per tenant.
      * ``PlatformCost`` — "what did the PLATFORM cost?"          per month, per SKU.

    Measured 2026-07-26 against the June invoice: the meter accounts for ~RM20 of an RM88
    bill. The rest is infrastructure whose driver is our own cron schedule and deploy pace,
    not tenant activity. Metering it per-org would invent precision that does not exist, so
    this ledger records the INVOICE and marks each line attributable or not, rather than
    smearing untraceable cost across tenants.

    **Every row is an invoice fact, never an estimate.** ``provenance`` is what enforces that:
    a hand-typed Supabase figure must never be indistinguishable from a measured GCP one.
    (Lesson: "before importing a spreadsheet as payment history, confirm the money moved".)

    **Scope is the HalaTuju GCP project only.** The billing export covers the whole billing
    account; other products live under it (Lentera cost RM0.30 in June). The owner's ruling
    (2026-07-26) is that HalaTuju carries ~99.7% of GCP and 100% of Supabase — verified against
    the June bill — but the sync still FILTERS by project, because the filter is what keeps
    that ruling true if a sibling product ever grows.
    """
    SOURCE_CHOICES = [
        ('gcp', 'Google Cloud Platform'),
        ('supabase', 'Supabase'),
        ('brevo', 'Brevo'),
        ('twilio', 'Twilio'),
        ('other', 'Other'),
    ]
    # How this row came to exist. The distinction is load-bearing: only MEASURED rows can be
    # re-derived and re-checked; an ENTERED row is somebody's reading of a PDF and carries
    # human error. A reconciliation that mixes them without saying so is not an audit.
    PROVENANCE_CHOICES = [
        ('measured', 'Measured — pulled from the provider\'s own billing data'),
        ('entered', 'Entered by hand from an invoice'),
    ]

    period_month = models.CharField(
        max_length=7,
        help_text="Billing month as 'YYYY-MM'. The grain of an invoice, not of an event.")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    service = models.CharField(
        max_length=120, blank=True, default='',
        help_text="Provider service, e.g. 'Cloud Run', 'Artifact Registry'.")
    sku = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Provider SKU — the grain that actually explains a bill. Reading June by "
                  "SKU is what revealed Cloud Run JOBS (RM33) outranked Artifact Registry.")
    # ── The money, in three parts ────────────────────────────────────────────
    # A first cut carried only `amount_myr`, which quietly assumed every provider invoices in
    # ringgit. GCP does; **Supabase invoices in USD** ($25.00/month). Converting needs a rate,
    # and a rate typed from memory is exactly the "estimate dressed as a fact" this ledger
    # exists to prevent — so the invoice is recorded in ITS OWN currency, and the conversion is
    # a separate, visible, auditable step.
    currency = models.CharField(
        max_length=3, default='MYR',
        help_text='ISO code the invoice is denominated in. GCP = MYR, Supabase = USD.')
    amount_original = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='The figure printed on the invoice, in `currency`. Null for MYR invoices '
                  'where amount_myr IS the invoiced figure.')
    fx_rate = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text='Rate used to derive amount_myr from amount_original. Prefer the rate your '
                  'card was actually charged at — that is the real cost — over a spot rate.')
    amount_myr = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Cost in MYR — the common denominator every total is summed in. Decimal, '
                  'never float: this is money. **Nullable on purpose.** "We hold the invoice '
                  'but do not yet know what it cost us in ringgit" is a real and honest state; '
                  'a placeholder number in a money column gets quoted as if it were true. '
                  'Rows left null are counted and reported as incomplete, never silently '
                  'dropped from a total.')
    period_note = models.CharField(
        max_length=120, blank=True, default='',
        help_text='Set when the provider\'s billing period does not match the calendar month '
                  "— e.g. Supabase invoices on the 8th, so a period straddles two months. "
                  'Without this, a cross-provider reconciliation compares unlike periods.')
    attributable = models.BooleanField(
        default=False,
        help_text='True when this line moves with TENANT activity (per-document OCR, AI, '
                  'egress). False for platform-driven cost (cron compute, CI storage) — that '
                  'belongs in a platform fee, not a metered charge.')
    provenance = models.CharField(max_length=10, choices=PROVENANCE_CHOICES)
    invoice_ref = models.CharField(
        max_length=60, blank=True, default='',
        help_text="The provider's own invoice number (e.g. 'TPTHYS-00007'). Its own column, "
                  'not buried in a note: it is how a figure is traced back to the document it '
                  'came from, which is the whole point of an auditable ledger.')
    note = models.TextField(
        blank=True, default='',
        help_text='Anything a future reader needs in order to trust the figure — what was '
                  'excluded, an attribution caveat, why a rate was chosen.')
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'platform_costs'
        ordering = ['-period_month', 'source', '-amount_myr']
        constraints = [
            # One row per (month, source, service, sku) — makes the sync an idempotent UPSERT
            # rather than an append, so re-running a month corrects it instead of doubling it.
            models.UniqueConstraint(
                fields=['period_month', 'source', 'service', 'sku'],
                name='platform_cost_unique_line'),
        ]
        indexes = [
            models.Index(fields=['period_month', 'source'], name='platform_cost_month_idx'),
        ]

    def __str__(self):
        return f'{self.period_month} {self.source}/{self.sku or self.service}: RM{self.amount_myr}'


class BillingRate(models.Model):
    """PLATFORM-side, super-only: the editable numbers that turn cost + effort into a charge.

    Owner design (2026-07-27): hours are recorded on the ORG side; the conversion rate and the
    per-category margins live here, on the platform side, as editable values. One home, so a
    rate cannot drift between the screen that shows it and the code that bills on it.

    **Effective-dated, deliberately.** A rate is not a setting, it is a term — and a term has a
    date. Storing a single mutable number would mean editing the hourly rate in September
    silently re-prices August's invoice, which is the kind of quiet retroactive change that
    destroys trust in a bill. `rate_in_force()` therefore always asks "what was true on THAT
    day?", never "what is true now?".

    **There is no default and no fallback.** If no rate is in force, the charge calculation
    REFUSES rather than returning zero or a guess. An unbilled month is a visible problem
    somebody fixes; a month billed at an invented rate is an invoice you have to withdraw.
    """
    CATEGORY_INFRASTRUCTURE = 'infrastructure'   # what we pay Google/Supabase to keep it running
    CATEGORY_METERED = 'metered'                 # per-event usage the tenant actually drives
    CATEGORY_DEVELOPMENT = 'development'         # building the tenant's modules
    CATEGORY_CHOICES = [
        (CATEGORY_INFRASTRUCTURE, 'Infrastructure (platform fee)'),
        (CATEGORY_METERED, 'Metered usage'),
        (CATEGORY_DEVELOPMENT, 'Development hours'),
    ]

    KIND_MARGIN_PCT = 'margin_pct'
    KIND_HOURLY_RATE = 'hourly_rate'
    KIND_CHOICES = [
        (KIND_MARGIN_PCT, 'Margin (%) added to the category'),
        (KIND_HOURLY_RATE, 'Hourly rate (RM per hour)'),
    ]

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Percent for margin_pct (15 = +15%), RM/hour for hourly_rate. Decimal, '
                  'never float — this ends up on an invoice.')
    effective_from = models.DateField(
        help_text='The day this value takes effect. A month is billed on the value in force '
                  'during that month, so changing a rate never re-prices a closed month.')
    updated_by_email = models.EmailField(
        blank=True, default='',
        help_text='Who set it. A rate change is a commercial act and should have a name on it.')
    note = models.TextField(
        blank=True, default='',
        help_text='Why this value. A future reader asking "why 15%?" deserves an answer here '
                  'rather than in somebody\'s memory.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_rates'
        ordering = ['category', 'kind', '-effective_from']
        constraints = [
            # One value per (category, kind) per start date — a new value is a NEW ROW with a
            # later date, never an edit of the old one. The history is the audit trail.
            models.UniqueConstraint(
                fields=['category', 'kind', 'effective_from'],
                name='billing_rate_unique_effective'),
        ]

    def __str__(self):
        unit = '%' if self.kind == self.KIND_MARGIN_PCT else ' RM/h'
        return f'{self.category}.{self.kind} = {self.value}{unit} from {self.effective_from}'


class OrgBuildHours(models.Model):
    """ORG-side: hours spent building THIS organisation's modules, in a given month.

    Owner requirement (2026-07-27): the billing must include the hours spent building the
    tenant's modules. This is the record of those hours — deliberately separate from
    `PlatformCost`, which holds money we PAY OUT. Hours are money we CHARGE. Summing the two
    in one table would make every total meaningless.

    **`basis` is required and is the point of the model.** No time-tracking system has ever
    existed here, so every hours figure is somebody's reconstruction — from working days, from
    a sprint count, from memory. That is legitimate input, but only if the reconstruction
    travels with the number. "70 working days at 4h" is auditable; "280" is not.
    """
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT,
        related_name='build_hours',
        help_text='The tenant whose modules were built. PROTECT: billing history must outlive '
                  'any tidy-up of the organisation record.')
    period_month = models.CharField(max_length=7, help_text="'YYYY-MM' the work is billed in.")
    module = models.CharField(
        max_length=200,
        help_text="What was built, in the owner's words — e.g. 'Payments module', "
                  "'Programme layer P1a-P4b'. This is what the tenant reads on the invoice.")
    hours = models.DecimalField(
        max_digits=8, decimal_places=1,
        help_text='Hours spent. One decimal place: nobody can honestly reconstruct minutes.')
    basis = models.TextField(
        help_text='REQUIRED. How this figure was arrived at — the working-day count, the '
                  'sprint span, whatever it was. There is no time tracker, so the number is a '
                  'reconstruction and is only trustworthy if it says so.')
    recorded_by_email = models.EmailField(blank=True, default='')
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'org_build_hours'
        ordering = ['-period_month', 'organisation']
        indexes = [
            models.Index(fields=['organisation', 'period_month'], name='build_hours_org_idx'),
        ]

    def __str__(self):
        return f'{self.period_month} {self.organisation_id}: {self.hours}h {self.module}'


# ── Partner-organisation comms (2026-07-26) ───────────────────────────────────
# Weekly + milestone emails to the referral organisations that run this bursary
# alongside us. See docs/plans/2026-07-26-partner-comms-roadmap.md.

class PartnerEmailTemplate(models.Model):
    """One of the five partner emails: its wording AND its on/off switch.

    Enablement is a property of the TEMPLATE, not of an (organisation, kind) pair —
    owner ruling 2026-07-26: *"if the email template is active, it goes out to all
    qualifying partners. It is either, or."* So there is exactly one row per kind and
    no per-organisation selection anywhere in this feature.

    `body` is plain text with `{placeholder}` tokens (the allowlist per kind lives in
    `partner_comms.KINDS`); blank lines are paragraph breaks. Rendering wraps it in the
    shared HTML email shell — HTML is the primary part, with a plain-text alternative
    carrying the same information.
    """
    KIND_CHOICES = [
        ('weekly_summary', 'Weekly summary'),
        ('shortlisted_followup', 'Chase list'),
        ('awaiting_review', 'Awaiting review'),
        ('awarded', 'Awarded'),
        ('assigned', 'A student joins their list'),
    ]
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, unique=True)
    enabled = models.BooleanField(default=False)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    updated_by_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'partner_email_templates'
        ordering = ['kind']

    def __str__(self):
        return f'{self.kind} ({"on" if self.enabled else "off"})'


class PartnerEmailLog(models.Model):
    """Every partner email we attempted — the audit trail, the "last sent" the admin
    screen shows, AND the fingerprint the weekly skip compares against.

    Deliberately the only home for send state: the most recent row for an
    (organisation, kind) pair answers both "when did we last write to them?" and "did
    anything change since?", so there is no second copy of that state to drift.

    A row is written even when the send FAILS (`ok=False`) and when it is skipped for
    having no recipient — silence must be visible, not indistinguishable from success.
    """
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.CASCADE,
        related_name='partner_email_log',
    )
    kind = models.CharField(max_length=32, choices=PartnerEmailTemplate.KIND_CHOICES)
    # The addresses actually written to, as stored (already lower-cased + de-duplicated).
    recipients = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=255, blank=True, default='')
    # Set for the per-student kinds; NULL for the two weekly digests.
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='partner_emails',
    )
    # Short hash of the payload (the stage counts) — the weekly-summary skip test.
    fingerprint = models.CharField(max_length=64, blank=True, default='')
    students = models.IntegerField(default=0, help_text='How many students the email covered.')
    ok = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True, default='',
                            help_text="Why nothing was sent, e.g. 'no_recipient', 'unchanged'.")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'partner_email_log'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['organisation', 'kind', '-sent_at'],
                         name='partner_email_org_kind_idx'),
        ]

    def __str__(self):
        return f'{self.kind} → org={self.organisation_id} @ {self.sent_at:%Y-%m-%d %H:%M}'


class SponsorEmailTemplate(models.Model):
    """One of the nine sponsor emails: its wording AND its on/off switch.

    The sibling of `PartnerEmailTemplate`, and deliberately the same shape — one row per kind,
    enablement on the TEMPLATE rather than on a (sponsor, kind) pair. A per-sponsor switch was
    never considered: a sponsor is not a tenant, and "which of my donors hear about a new
    student" is not a decision anyone should be making one donor at a time.

    `body` is plain text with `{placeholder}` tokens (the allowlist per kind lives in
    `sponsor_comms.PLACEHOLDERS`); blank lines are paragraph breaks and a block that is exactly
    `{student_cards}` becomes the rich per-student cards. Rendering goes through
    `email_templates.render`, shared with the partner family.

    Nine kinds, not eleven: `low_balance` and `annual_statement` were deferred by the owner on
    2026-07-28 because they edge from transactional account mail into marketing, and what a
    sponsor consented to at registration is not currently reviewable (TD-186).
    """
    KIND_CHOICES = [
        ('welcome', 'Welcome — registered, awaiting vetting'),
        ('approved', 'Approved'),
        ('rejected', 'Not approved'),
        ('suspended', 'Suspended'),
        ('reinstated', 'Reinstated'),
        ('credit_confirmed', 'Credit confirmed'),
        ('new_students', 'New students to consider'),
        ('weekly_digest', 'Weekly digest'),
        ('referral_invite', 'Invitation to a prospective sponsor'),
    ]
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, unique=True)
    enabled = models.BooleanField(default=False)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    updated_by_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sponsor_email_templates'
        ordering = ['kind']

    def __str__(self):
        return f'{self.kind} ({"on" if self.enabled else "off"})'


class SponsorEmailLog(models.Model):
    """Every sponsor email we attempted — the audit trail and the "last sent" the panel shows.

    A row is written even when the send FAILS and when it is SKIPPED for having no recipient or
    a switched-off template: silence must be visible, not indistinguishable from success. That
    rule is inherited from partner comms, where it exists because an unreachable organisation
    looked exactly like a quiet one.

    `sponsor` is nullable for one reason: `referral_invite` goes to a prospective sponsor who has
    no account yet, so the row records the INVITER and the recipient address separately.
    """
    sponsor = models.ForeignKey(
        'Sponsor', on_delete=models.SET_NULL, null=True, blank=True, related_name='email_log',
    )
    kind = models.CharField(max_length=32, choices=SponsorEmailTemplate.KIND_CHOICES)
    # The addresses actually written to, as stored (already lower-cased + de-duplicated).
    recipients = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=255, blank=True, default='')
    ok = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True, default='',
                            help_text="Why nothing was sent, e.g. 'no_recipient', 'disabled'.")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sponsor_email_log'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['sponsor', 'kind', '-sent_at'],
                         name='sponsor_email_kind_idx'),
        ]

    def __str__(self):
        return f'{self.kind} → sponsor={self.sponsor_id} @ {self.sent_at:%Y-%m-%d %H:%M}'


class SponsorTermsVersion(models.Model):
    """One version of the terms a sponsor accepts when they join.

    The sibling of `ContractTemplate` in intent and deliberately a fraction of its size. What is
    kept from there: draft immutability, a publish that archives the previous active row inside one
    transaction, and a version string that a past acceptance can point at forever. What is dropped:
    the payment schedule, the counterparty/signing apparatus, the lawyer-vetting attestation, .docx
    import, PDF rendering, and the three-level clause hierarchy — sections here are a FLAT numbered
    list, because a thirteen-section document does not need an outline tree.

    PLATFORM-LEVEL, with no `organisation` FK, matching `Sponsor` and `SponsorEmailTemplate` (both
    classified `cross-org-by-design` in test_org_fence.py). A sponsor account is not a tenant's
    property, so neither are the terms it accepts. A second tenant wanting its own terms is a
    documented later decision, not a field guessed at now.

    ⚠ These are NOT the bursary agreement. That is a 94-clause instrument between BrightPath and a
    STUDENT, and a sponsor is not a party to it (see TD-191). Do not merge the two.
    """
    STATUS_DRAFT = 'draft'
    STATUS_ACTIVE = 'active'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ARCHIVED, 'Archived'),
    )

    version = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    # English is authoritative; ms/ta are courtesy translations and may lag (warning W1).
    title_en = models.CharField(max_length=255, blank=True, default='')
    title_ms = models.CharField(max_length=255, blank=True, default='')
    title_ta = models.CharField(max_length=255, blank=True, default='')
    intro_en = models.TextField(blank=True, default='')
    intro_ms = models.TextField(blank=True, default='')
    intro_ta = models.TextField(blank=True, default='')

    created_by_email = models.CharField(max_length=254, blank=True, default='')
    published_by_email = models.CharField(max_length=254, blank=True, default='')
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sponsor_terms_versions'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.version} ({self.status})'

    @property
    def languages_available(self):
        """Locales a sponsor may be served WHOLE. English is always available.

        A locale only counts when the title, the intro AND every section heading and body carry
        it — a half-translated document would otherwise silently fall back mid-page, which reads
        as a bug to the person it happens to.
        """
        out = ['en']
        sections = list(self.sections.all())
        for loc in ('ms', 'ta'):
            if not (getattr(self, f'title_{loc}').strip() and getattr(self, f'intro_{loc}').strip()):
                continue
            if all(getattr(sec, f'heading_{loc}').strip() and getattr(sec, f'body_{loc}').strip()
                   for sec in sections) and sections:
                out.append(loc)
        return out


class SponsorTermsSection(models.Model):
    """One numbered section of a `SponsorTermsVersion`, and optionally its quiz checkpoint.

    FLAT — there is no `level`. Sections are numbered 1..N by `order`, contiguously, and the number
    shown is the order itself rather than a computed outline label. That single choice removes the
    whole hierarchy apparatus the contract module needs (`normalise_levels`, `clause_numbers`,
    `MAX_QUIZ_LEVEL`, ancestor/descendant resolution, indent/outdent and their guards).

    Headings are TextField rather than CharField(255) on purpose: the contract module needed a
    `_fit_heading` guard on every write path because an over-long heading could overflow the
    varchar and 500 a save. A TextField cannot.

    `quiz_{en,ms,ta}` reuses the payload shape the student bursary quiz already uses —
    ``{tag, plain, question, options: [3 strings], correct: 0-2, why}`` — so the authoring editor
    and the sponsor-facing quiz component both port from working code. An empty dict means no quiz
    in that language; `en` is mandatory whenever `is_quiz_candidate` is set.
    """
    terms = models.ForeignKey(
        SponsorTermsVersion, on_delete=models.CASCADE, related_name='sections',
    )
    order = models.PositiveIntegerField()

    heading_en = models.TextField(blank=True, default='')
    heading_ms = models.TextField(blank=True, default='')
    heading_ta = models.TextField(blank=True, default='')
    body_en = models.TextField(blank=True, default='')
    body_ms = models.TextField(blank=True, default='')
    body_ta = models.TextField(blank=True, default='')

    is_quiz_candidate = models.BooleanField(default=False)
    quiz_en = models.JSONField(default=dict, blank=True)
    quiz_ms = models.JSONField(default=dict, blank=True)
    quiz_ta = models.JSONField(default=dict, blank=True)
    # Blank = hand-written. Otherwise the model that drafted it, kept as provenance.
    quiz_generated_model = models.CharField(max_length=80, blank=True, default='')

    class Meta:
        db_table = 'sponsor_terms_sections'
        ordering = ['terms_id', 'order']
        constraints = [
            models.UniqueConstraint(fields=['terms', 'order'],
                                    name='uniq_sponsor_terms_section_order'),
        ]

    def __str__(self):
        return f'{self.terms_id}.{self.order} {self.heading_en[:40]}'


class SponsorTermsAcceptance(models.Model):
    """That a given sponsor accepted a given VERSION — or was deliberately not asked.

    One row per (sponsor, version), and a HISTORY table rather than a latest-value field on
    `Sponsor`: publishing a new version can then re-ask without destroying the record of what was
    agreed before. `terms` is PROTECT so a version that has governed an acceptance can never be
    deleted out from under it.

    ⚠ `basis` is load-bearing and must never be collapsed to a boolean. `grandfathered` means WE DID
    NOT ASK THIS PERSON, which is the opposite of "they agreed" — every surface that reads it must
    say so. Same principle as `SponsorEmailLog` writing a row for a skip: silence has to be visible,
    not indistinguishable from success.

    ⚠ This is NOT `Sponsor.consent_at` / `consent_version`. Those hold the PDPA privacy consent — a
    permission the sponsor GRANTS US, imposing no duty on them. Merging the two is the error TD-191
    exists to prevent.
    """
    BASIS_ACCEPTED = 'accepted'
    BASIS_GRANDFATHERED = 'grandfathered'
    BASIS_CHOICES = (
        (BASIS_ACCEPTED, 'Accepted by the sponsor'),
        (BASIS_GRANDFATHERED, 'Grandfathered — never asked'),
    )

    sponsor = models.ForeignKey(
        'Sponsor', on_delete=models.CASCADE, related_name='terms_acceptances',
    )
    terms = models.ForeignKey(
        SponsorTermsVersion, on_delete=models.PROTECT, related_name='acceptances',
    )
    basis = models.CharField(max_length=20, choices=BASIS_CHOICES, default=BASIS_ACCEPTED)

    # Typing a name IS the signature here, matching `BursaryAgreement.student_signed_name` and the
    # credit chain's `admin_signed_name` / `finance_signed_name` / `org_admin_signed_name`.
    # `registered_name_at_acceptance` freezes the account name at that moment so a divergence stays
    # visible to an admin forever — we never REFUSE a variant spelling, because there is no IC to
    # match against and rejecting someone their own name is a worse failure than storing a
    # difference.
    signed_name = models.CharField(max_length=200, blank=True, default='')
    registered_name_at_acceptance = models.CharField(max_length=200, blank=True, default='')

    accepted_at = models.DateTimeField(null=True, blank=True)
    quiz_passed_at = models.DateTimeField(null=True, blank=True)
    locale = models.CharField(max_length=5, blank=True, default='en')
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # Grandfathering only: who granted the exemption and why.
    granted_by_email = models.CharField(max_length=254, blank=True, default='')
    reason = models.CharField(max_length=300, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sponsor_terms_acceptances'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['sponsor', 'terms'],
                                    name='uniq_sponsor_terms_acceptance'),
        ]

    def __str__(self):
        return f'sponsor={self.sponsor_id} {self.terms_id} ({self.basis})'


# ─────────────────────────────────────────────────────────────────────────────
# What a programme ASKS FOR — the Layer 0 catalogue (config roadmap, sprint 2)
# ─────────────────────────────────────────────────────────────────────────────

# Shared by the catalogue's DEFAULT and a programme's CHOICE, so the two can never drift into
# meaning different things. 'optional' is a real state, not a shade of off: four documents are
# offered today without ever blocking a submission.
ITEM_STATE_CHOICES = [
    ('off', 'Not asked for'),
    ('optional', 'Offered, never blocks'),
    ('required', 'Must be provided'),
]


class ApplicationItem(models.Model):
    """One thing an application can ask a student for — a document or a question.

    **THIS IS A CATALOGUE, NOT A FORM BUILDER, and the distinction is the whole design.**
    Every row here is OUR content: we write it, we translate it into en/ms/ta, we know what
    the engine does with it. An organisation chooses WHICH of these apply to its programme
    (``ProgrammeApplicationItem`` below). It never authors a new one.

    Why it cannot be otherwise:

    * **Documents are read, not merely stored.** Each ``doc_type`` has recognition logic, a
      versioned signature model and verification behaviour behind it. An organisation can
      switch on a document the engine already understands; it cannot invent "water bill" and
      have anything comprehend the result. Hence the hard rule below that ``code`` must name
      an EXISTING ``ApplicantDocument.DOC_TYPES`` value.
    * **Questions must exist in three languages.** ``scripts/check-i18n.js`` fails the build on
      a missing key, and the owner is the Tamil authority. An org-authored question would
      quietly become his homework or ship English to a Tamil-speaking student.
    * **New personal data lands on erasure.** A free-text field an organisation invented is a
      new category of applicant data that Sprint E must know how to delete.

    This is the shipped form of the recorded platform rule: *"tenants configure WHICH checks
    and documents apply to their programme; they never get bespoke logic."*
    """
    KIND_CHOICES = [('document', 'Document'), ('question', 'Question')]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES)

    # ⚠ For kind='document' this MUST be a value in ApplicantDocument.DOC_TYPES. The catalogue
    # NAMES an existing type; it never invents one. Enforced by test, not by a DB constraint,
    # because DOC_TYPES is a Python list and a migration cannot follow it.
    code = models.CharField(max_length=50)

    # Full i18n key, resolved by the web app. Never a literal label — a label stored here would
    # be a fourth place translations live and would escape check-i18n.js entirely.
    label_key = models.CharField(max_length=200)

    # An organisation may NOT switch this off. The floor is a POLICY decision, not an
    # engineering one — owner 2026-07-28: identity card, results slip, offer letter, consent,
    # and the family/income block.
    is_core = models.BooleanField(default=False)

    # What a NEWLY created programme starts with, before anybody ticks anything.
    #
    # ⚠ Three states, not a boolean. The first cut of this column was `default_on: bool`, which
    # cannot express "offered by default but never blocking" — and four items are exactly that
    # today (water bill, electricity bill, statement of intent, photo). A flag that cannot
    # represent a state the system already has is a schema asserting something false; caught
    # while writing the seed, fixed before any row existed.
    default_state = models.CharField(max_length=20, choices=ITEM_STATE_CHOICES, default='off')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'application_items'
        ordering = ['kind', 'code']
        constraints = [
            models.UniqueConstraint(fields=['kind', 'code'], name='uniq_application_item'),
        ]

    def __str__(self):
        return f'{self.kind}:{self.code}'


class ProgrammeApplicationItem(models.Model):
    """One programme's answer to one catalogue item: off, optional, or required.

    **On PROGRAMME, not on ScholarshipCohort** — owner-approved 2026-07-28, and a deliberate
    departure from the "new tunables go on the cohort" convention. That convention exists to
    stop tunables becoming module CONSTANTS; both models are data, so it is not violated in
    spirit. What a programme asks for is the gift's IDENTITY, not the year's: a cohort-level
    home would make every annual intake re-tick the same list, which is exactly the rot this
    work exists to prevent. ``ScholarshipApplication.programme`` is already denormalised and
    set once in ``save()``, so resolution is one hop with no join through the cohort.

    ⚠ **NOT A SECURITY BOUNDARY.** Which items a programme asks for is configuration, never
    access control. The organisation fence (``_AdminBase._org_scoped`` / ``_org_allows``,
    cross-org ⇒ 404) is untouched by anything here. Confusing a configuration surface with a
    fence is the 2026-07-15 surface-partition incident, and it is worth restating in every
    model that a tenant can edit.
    """
    programme = models.ForeignKey(
        Programme, on_delete=models.CASCADE, related_name='application_items',
    )
    item = models.ForeignKey(
        ApplicationItem, on_delete=models.PROTECT, related_name='programme_selections',
    )
    state = models.CharField(max_length=20, choices=ITEM_STATE_CHOICES)

    updated_at = models.DateTimeField(auto_now=True)
    updated_by_email = models.CharField(max_length=254, blank=True, default='')

    class Meta:
        db_table = 'programme_application_items'
        ordering = ['programme_id', 'item_id']
        constraints = [
            models.UniqueConstraint(fields=['programme', 'item'],
                                    name='uniq_programme_application_item'),
        ]

    def __str__(self):
        return f'programme={self.programme_id} {self.item_id}={self.state}'
