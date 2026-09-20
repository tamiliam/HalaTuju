"""
`ScholarshipApplication` — the wide central row — and the funding need on it.

This is the one module the 600-line standard cannot hold: `ScholarshipApplication`
is 847 lines of FIELDS on a single class (159 of them), so no move can divide it.
Its `oversize_files` entry was RELABELLED onto this path by a declared `_moved`
record in `code-standards.json` and ratcheted down; nothing was bought by it.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models
from django.utils import timezone

from ..family import PROFESSION_CHOICES
from .programmes import ScholarshipCohort

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
    # Payments module: when Vircle actually ACTIVATED (switched on) this eWallet. ⚠ THIS FIELD IS
    # NOW THE SOURCE OF TRUTH, and the relay sheet's 'Activated On' column is its mirror — the
    # reverse of the arrangement until 2026-09-11, when the owner's hand-kept column was retired
    # because Vircle's inbound webhook reports activation itself (a row whose Status reads "Done";
    # `vircle_airtable.apply_update` stamps it, set-once). ADVISORY only — the payment run surfaces a "not yet
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
    # Layer 0 (2026-08-30): what the PROGRAMME asked for, frozen at the Step-4 Submit
    # (`confirm_profile`). `{'captured_at', 'documents': {code: state}, 'questions': {code: state}}`.
    # `requirements.resolve` reads this FIRST, so a configuration change made after a student
    # submitted can never re-gate them (an organisation switching a question ON would otherwise
    # make a submitted form "incomplete" and `revert_if_profile_incomplete` would un-submit it).
    # NULL = never frozen: a not-yet-submitted application follows the live configuration, and a
    # revert to `shortlisted` clears it so the student re-submits against the current form.
    # Distinct from `intake_snapshot`, which is taken at the APPLY submit, an earlier moment.
    requirements_snapshot = models.JSONField(
        null=True, blank=True,
        help_text="What the programme asked for, frozen at the Step-4 Submit. NULL until then.",
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
    # ⚠ WHICH PREDICTOR PRODUCED THE SNAPSHOT ABOVE. Without it the AI Reliability card averages
    # every generation of `verdict_engine` as if it were one model — 88 pairs were banked between
    # 2026-06-17 and 2026-09-01 with no way to tell, and the engine changed on 2026-09-10.
    # `verdict_engine.VERDICT_ENGINE_VERSION` at capture; `PRE_VERSIONING` for rows that predate it.
    # A SIBLING COLUMN rather than a key inside `ai_verdict_snapshot`: every reader of that field
    # (audit._snapshot_status_map, compute_overrides, the serializer, the cockpit) iterates it as a
    # LIST of facts, so a wrapper would be a data migration plus four call sites for no gain.
    ai_verdict_engine_version = models.CharField(
        max_length=32, blank=True, default='',
        help_text="The verdict_engine version that produced ai_verdict_snapshot. "
                  "'pre-versioning' = decided before this was recorded. Empty = never decided.",
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
