"""The student profile and the email verification record."""

from django.db import models
from django.db.models import Value
from ..exam_questions import EXAM_CHOICES, INSTITUTION_TYPE_CHOICES
from ..stpm_pngk import stpm_cgpa_of
from ..utils import tidy_parentage_marker


class StudentProfile(models.Model):
    """
    User profile linked to Supabase Auth.

    Note: Authentication is handled by Supabase Auth.
    This model stores the student's academic profile and preferences.

    Table name: 'api_student_profiles'. The 'api_' prefix originally avoided a
    collision with the legacy Streamlit 'student_profiles' table; that dead table
    was dropped 2026-06-01 (TD-025). The prefix is retained as the canonical name
    (a rename isn't worth the RLS/raw-SQL/migration churn).
    """
    # Supabase Auth user ID (from JWT 'sub' claim)
    supabase_user_id = models.CharField(max_length=100, primary_key=True)

    # SPM Grades (stored as JSON for flexibility)
    grades = models.JSONField(
        default=dict,
        help_text="SPM grades: {'bm': 'A+', 'math': 'B', ...}"
    )

    # Identity (for follow-up tracking)
    name = models.CharField(max_length=255, blank=True, default='',
                            help_text="Student's full name")
    school = models.CharField(max_length=255, blank=True, default='',
                              help_text="SPM school name")

    # Contact & location
    address = models.TextField(blank=True, default='',
                               help_text="Street address")
    postal_code = models.CharField(max_length=5, blank=True, default='',
                                   help_text="5-digit Malaysian postcode")
    city = models.CharField(max_length=100, blank=True, default='',
                            help_text="City/town (auto-filled from postcode)")
    # TD-061: legacy `phone` dropped — contact_phone (below) is the canonical
    # phone, synced with /apply. (Column removed in courses/0050.)

    # Contact details (separate from login credentials)
    contact_email = models.EmailField(blank=True, default='',
                                       help_text="Verified contact email")
    contact_email_verified = models.BooleanField(default=False)
    contact_phone = models.CharField(max_length=20, blank=True, default='',
                                      help_text="Verified contact phone")
    contact_phone_verified = models.BooleanField(default=False)
    # WhatsApp comms consent. Default True = implied consent: a phone number given
    # for contact is consent to be contacted on it, like email (owner decision,
    # 2026-06-20). Surfaced as an opt-OUT toggle in the profile; gates every
    # outbound WhatsApp send (a value of False = the user opted out).
    whatsapp_opt_in = models.BooleanField(default=True)

    # Identity (Lentera longitudinal tracking)
    nric = models.CharField(max_length=14, blank=True, default='',
                            help_text="NRIC: XXXXXX-XX-XXXX")
    # ⚠ The help_text below is now UNDERSTATED and is left alone only because changing it costs
    # a migration for prose. Since 2026-07-29 there are TWO routes to this lock: an admin at
    # verify-&-accept (as described), AND the document check — `vision._lock_nric_if_confirmed`
    # sets it with no human in the loop when a GENUINE MyKad's name and number both match what
    # the student typed. The rule has one home: `apps.scholarship.identity`.
    #
    # ⚠ THIS FLAG IS A PROPERTY OF THE PROFILE; THE ONLY WAY TO UNSET IT IS ADDRESSED BY
    # APPLICATION (`AdminReleaseNricLockView`, super-only). That works because both routes above
    # require an application, so a locked profile always has one — 0 exceptions on production
    # against 643 profiles that have no application at all. **A new route that locks a profile
    # without an application would make that student's lock permanent and unreachable.** The
    # likely candidate is confirming a course-selector identity for Lentera's longitudinal
    # tracking, which is what this column was originally added for. Read that endpoint's
    # docstring before adding one.
    nric_verified = models.BooleanField(
        default=False,
        help_text="True once an admin verifies the NRIC against the uploaded MyKad "
                  "(then it locks). Until then the NRIC stays editable and is NOT "
                  "uniqueness-enforced. See docs/decisions.md (supersedes 'IC immutable').")
    angka_giliran = models.CharField(max_length=9, blank=True, default='',
                                     help_text="University application ref: AB123C456")

    # Family background
    # TD-061: legacy `family_income` (coarse free-text range) + `siblings` count
    # dropped — superseded by household_income/household_size below, which /apply
    # and /profile both write. (Columns removed in courses/0050.)
    # Financial detail (canonical source for the B40 Assistance Programme; collected
    # once here and reused across application rounds — see apps/scholarship)
    household_income = models.IntegerField(
        null=True, blank=True, help_text="Combined monthly household income in RM")
    household_size = models.IntegerField(
        null=True, blank=True, help_text="Number of people in the household")
    receives_str = models.BooleanField(
        default=False, help_text="Active Sumbangan Tunai Rahmah recipient (B40 anchor)")
    receives_jkm = models.BooleanField(
        default=False, help_text="Receives JKM assistance")
    guardians = models.JSONField(
        default=list, blank=True,
        help_text="Guardian details: [{name, relationship, occupation, income}]")

    # ── Structured family roster (the durable, profile-level home) ────────────
    # Mirrors apps.scholarship.ScholarshipApplication's roster columns (same field
    # names so the two copy field-for-field). This is the SOURCE: /profile edits it
    # for everyone (even with no B40 application). When an application is OPEN it is
    # kept in two-way sync with the application's copy; once the application is
    # decided, the application copy FREEZES and /profile edits stop touching it.
    # Profession codes are the coded values from apps.scholarship.family
    # (validated by the shared FE editor) — kept as plain CharFields here to avoid a
    # courses→scholarship import dependency.
    father_name = models.CharField(max_length=200, blank=True, default='')
    father_occupation = models.CharField(max_length=40, blank=True, default='')
    father_occupation_other = models.CharField(max_length=120, blank=True, default='')
    mother_name = models.CharField(max_length=200, blank=True, default='')
    mother_occupation = models.CharField(max_length=40, blank=True, default='')
    mother_occupation_other = models.CharField(max_length=120, blank=True, default='')
    other_family_members = models.JSONField(
        default=list, blank=True,
        help_text="Brother/sister/guardian pool: [{role, occupation, occupation_other?}]")
    siblings_in_school = models.PositiveSmallIntegerField(null=True, blank=True)
    siblings_in_tertiary = models.PositiveSmallIntegerField(null=True, blank=True)

    # ── Pathway / "Your Plans" (profile-level home; mirrors ScholarshipApplication) ──
    # Same field names + types as the application's pathway columns so they copy
    # field-for-field. /profile owns the picker (so a shortlisted student, locked out
    # of /apply, can still change pathway); two-way synced with an open application,
    # frozen on the app at the decision.
    pathway_certainty = models.CharField(max_length=10, blank=True, default='')
    chosen_pathway = models.CharField(max_length=20, blank=True, default='')
    pre_u_track = models.CharField(max_length=30, blank=True, default='')
    pre_u_institution = models.CharField(max_length=255, blank=True, default='')
    chosen_programme = models.JSONField(default=dict, blank=True)
    pathways_considered = models.JSONField(default=list, blank=True)
    uncertainty_reasons = models.JSONField(default=list, blank=True)
    uncertainty_note = models.TextField(blank=True, default='')

    # Demographics (for eligibility checking)
    gender = models.CharField(max_length=20, blank=True)
    nationality = models.CharField(max_length=50, default='Warganegara')
    bumiputera = models.BooleanField(null=True, blank=True, default=None)  # ⚠ course guide ONLY: bumiputera.py
    colorblind = models.BooleanField(default=False)
    disability = models.BooleanField(default=False)

    # Quiz results (student signals for ranking)
    student_signals = models.JSONField(
        default=dict,
        help_text="Quiz results for fit scoring"
    )

    # Preferences
    preferred_state = models.CharField(max_length=50, blank=True)
    preferred_call_language = models.CharField(
        max_length=10, blank=True, default='',
        help_text="Preferred language for phone calls: en/ms/ta/mixed (B40 outreach).")
    financial_pressure = models.CharField(max_length=20, blank=True)
    travel_willingness = models.CharField(max_length=50, blank=True)

    # STPM / exam type fields. Choices: `exam_questions.EXAM_CHOICES` (+ Matric/Asasi/Diploma, S2a)
    exam_type = models.CharField(max_length=10, choices=EXAM_CHOICES, default='spm')
    # ⚠ WHICH EXAM'S RESULTS WERE LAST *COMPLETED* — not which exam was last SELECTED.
    #
    # `exam_type` above answers two different questions and cannot answer both: "which exam am I
    # heading for?" (the course guide's, and the only one a Form Six student can answer 'STPM' to
    # honestly) and "which results do I hold?" (the bursary's). Selecting an exam sets it; entering
    # results is not required. So a Form Six student who taps STPM to explore programmes ends up
    # declared STPM with no STPM results, and every surface reading it for the SECOND question is
    # then wrong — the apply form tells her we have no results while ten SPM grades sit on file.
    #
    # This field only ever moves when a results form is COMPLETED (both editors refuse to continue
    # until they are), so it cannot be set by a selection alone. Blank means "never recorded" —
    # every row predates this column — and readers fall back to `exam_type`, which is what they
    # used before. It is NEVER a claim that the student sat the exam: the course guide lets anyone
    # type STPM grades to explore, and nothing on the record distinguishes that from a result.
    results_exam_type = models.CharField(
        max_length=10, blank=True, default='',
        choices=EXAM_CHOICES,
        help_text="Which exam's results were last COMPLETED. Blank = never recorded.",
    )
    # ⚠ THIRD RESULTS ROUTE (S2a, 2026-10-25): Matriculation / Asasi / Diploma. Their own columns,
    # on purpose: NOT `stpm_cgpa` (`has_stpm_results` reads it, so a Matriculation CGPA there would
    # make `results_held` say STPM) and NOT `coq_score` (the SPM merit input). The OVERALL CGPA is
    # computed, never stored (`exam_questions.overall_cgpa`).
    higher_cgpa = models.FloatField(
        null=True, blank=True,
        help_text="Matriculation / Asasi / Diploma CGPA (0-4) AS ENTERED. NULL = none.")
    higher_koko = models.FloatField(
        null=True, blank=True,
        help_text="Matriculation / Asasi co-curriculum score (0-10). NULL for Diploma.")
    higher_institution_type = models.CharField(
        max_length=10, blank=True, default='', db_default='', choices=INSTITUTION_TYPE_CHOICES,
        help_text="Diploma only: 'public' or 'private'. Only a PUBLIC diploma counts (D5).")
    # What "highest" ranks over (`exam_questions.results_held`): each results form adds its value
    # ON COMPLETION, and the sync drops an entry with no results behind it — so presence of data
    # never promotes (#15). [] on every row before S2a = the old rule, unchanged (D1).
    completed_qualifications = models.JSONField(
        default=list, blank=True, db_default=Value([], output_field=models.JSONField()),
        help_text="Qualifications whose results form was COMPLETED, e.g. ['spm', 'matric'].")
    stpm_grades = models.JSONField(default=dict, blank=True, help_text="STPM grades: {'PA': 'A', 'MATH_T': 'B+', ...}")
    stpm_cgpa = models.FloatField(null=True, blank=True)
    # THE STPM CGPA every reader uses (CGPA sprint C2): from the grades, else `stpm_cgpa` as stored.
    stpm_pngk = property(stpm_cgpa_of)
    stpm_koko = models.FloatField(null=True, blank=True, help_text="STPM co-curriculum score (0-10): merit only, never the CGPA (stpm_pngk.stpm_merit_overall).")
    # C4: TRUE = the backfill could not work this koko back cleanly -> Check 2 asks (`stpm_asks`).
    stpm_koko_unconfirmed = models.BooleanField(null=True, blank=True, help_text="TRUE: the stored STPM co-curriculum score was derived, not cleanly; the student is asked to confirm it. Cleared when they save one through onboarding.")
    muet_band = models.IntegerField(null=True, blank=True)
    coq_score = models.FloatField(
        null=True, blank=True,
        help_text="Co-curricular score out of 10 (entered at onboarding, feeds merit); "
                  "persisted so it pre-fills the scholarship Results section.")
    spm_prereq_grades = models.JSONField(
        default=dict, blank=True,
        help_text="SPM prerequisite grades for STPM students: {'bm': 'A', 'eng': 'B+', ...}"
    )
    stream_subjects = models.JSONField(
        default=list, blank=True,
        help_text="The SPM subjects the student studied as their stream/aliran "
                  "(e.g. ['phy','chem','bio','addmath']). When present, the merit "
                  "engine uses these as the Sec2 (30% stream) candidates instead of "
                  "guessing the stream from the pools (TD-063). Empty = fall back to "
                  "the count-heuristic (existing/historical profiles).")
    elective_subjects = models.JSONField(
        default=list, blank=True,
        help_text="The SPM subjects the student picked as electives/tambahan "
                  "(e.g. ['ekonomi','poa']). The durable record of *which* subjects "
                  "are electives — without it, the onboarding grades form can't "
                  "reconstruct the elective selection after logout/login and drops "
                  "those grades. Up to 7 (a student may sit many subjects). The merit "
                  "engine still uses only the best 2 (Sec3, 10%); the rest persist for "
                  "course-specific eligibility.")
    # TD-069 (2026-10-02): the STPM path's SPM prerequisites rebuild after logout/login, as v2.21
    # made the main flow's do. Its aliran picks need no column: spm_prereq_grades minus the four
    # compulsory subjects minus these electives. Read by nothing but the onboarding form.
    spm_elective_subjects = models.JSONField(
        default=list, blank=True,
        help_text="STPM path: which spm_prereq_grades keys are SPM electives (up to 7).")
    spm_stream = models.CharField(
        max_length=20, blank=True, default='',
        help_text="STPM path: the SPM stream picked for the prerequisites (science/arts/technical).")
    # The COURSE-SELECTOR's chip (sources Sprint D, 2026-10-19): the first `?ref=` code that brought
    # her (`referral_links.apply_ref_code`, first touch) — read by the partner dashboard's Source
    # column, filter and CSV. The bursary no longer writes it (each application keeps its own answer,
    # `ScholarshipApplication.referral_code`); values written by the bursary before then remain.
    referral_source = models.CharField(
        max_length=50, blank=True, null=True,
        help_text='Raw referral code or chip value (e.g. cumig, whatsapp, google)',
    )
    # `referred_by_org` is the REFERRAL PARTNER (a `?ref=` link, first touch; `referral_links`). The
    # profile's bursary `source` column left the model in sources Sprint D (courses 0083 drops it
    # after the deploy): no reader since Sprint C — the application carries its own source.
    referred_by_org = models.ForeignKey(
        'PartnerOrganisation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referred_students',
    )
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Normalise the full name to UPPER CASE at the write boundary (owner 2026-07-16),
        # so every reader — the payments CSV to Vircle, emails, the student app, and any
        # future surface — shows it consistently without each having to remember to
        # upper-case it. Idempotent, and catches every ORM write path (apply-form sync,
        # profile PUT/sync, the declaration-signature promote). The per-application
        # declaration signature (`ScholarshipApplication.declaration_name`) stays verbatim
        # as a legal record; `profile.name` is the canonical name everything displays.
        if self.name:
            self.name = tidy_parentage_marker(self.name.upper())
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'api_student_profiles'
        constraints = [
            # Soft-NRIC (Option A): an NRIC must be unique only once VERIFIED. While
            # unverified it stays editable and duplicates are tolerated (a typo of
            # someone else's number won't block submit); the clash surfaces at admin
            # verification, where only one NRIC can be verified. Supersedes the old
            # 'unique_nric_when_set' (unique whenever non-empty).
            models.UniqueConstraint(
                fields=['nric'],
                name='unique_verified_nric',
                condition=models.Q(nric_verified=True) & ~models.Q(nric=''),
            ),
        ]

    def __str__(self):
        return f"Profile {self.supabase_user_id}"


class EmailVerification(models.Model):
    """Token-based email verification for contact email."""
    profile = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name='email_verifications'
    )
    email = models.EmailField()
    token = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        db_table = 'email_verifications'

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Verify {self.email} for {self.profile_id}"
