"""
Database models for HalaTuju courses and eligibility.

All data lives in Supabase PostgreSQL. Models:
- FieldTaxonomy (canonical field classification)
- Course, CourseRequirement, CourseTag
- StpmCourse, StpmRequirement
- Institution, CourseInstitution
- MascoOccupation (M2M via Course.career_occupations)
- StudentProfile, SavedCourse
"""
from django.db import models
from django.db.models import Q

from .utils import tidy_parentage_marker


class FieldTaxonomy(models.Model):
    """
    Canonical field/discipline classification for all courses.

    37 entries covering all SPM and STPM course fields.
    Language-neutral keys with trilingual display names.
    Image slugs map directly to Supabase Storage filenames.
    """
    key = models.CharField(max_length=50, primary_key=True)
    name_en = models.CharField(max_length=100)
    name_ms = models.CharField(max_length=100)
    name_ta = models.CharField(max_length=100)
    image_slug = models.CharField(max_length=100, help_text="Supabase Storage filename (without .png)")
    parent_key = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='children',
        help_text="Parent group for dropdown grouping (~9 top-level groups)"
    )
    sort_order = models.IntegerField(default=0)
    riasec_primary = models.CharField(
        max_length=1, blank=True, default='',
        choices=[
            ('R', 'Realistic'), ('I', 'Investigative'), ('A', 'Artistic'),
            ('S', 'Social'), ('E', 'Enterprising'), ('C', 'Conventional'),
        ],
        help_text="Primary Holland RIASEC type for this field"
    )

    class Meta:
        db_table = 'field_taxonomy'
        ordering = ['sort_order', 'key']

    def __str__(self):
        return f"{self.key}: {self.name_ms}"


class Course(models.Model):
    """
    Master course information.

    Source: Supabase `courses` table
    """
    course_id = models.CharField(max_length=50, primary_key=True)
    course = models.CharField(max_length=255, help_text="Course name in Malay")
    wbl = models.BooleanField(default=False, help_text="Work-Based Learning flag")
    level = models.CharField(max_length=50, help_text="Diploma, Sijil, Asasi, etc.")
    department = models.CharField(max_length=100)
    field = models.CharField(max_length=100)
    semesters = models.IntegerField(null=True, blank=True)
    field_key = models.ForeignKey(
        FieldTaxonomy, on_delete=models.PROTECT,
        related_name='courses',
        help_text="Canonical field classification"
    )
    headline = models.TextField(blank=True, default='', help_text="Catchy student-friendly headline")
    headline_en = models.TextField(blank=True, default='', help_text="English headline")
    description = models.TextField(blank=True)
    description_en = models.TextField(blank=True, default='', help_text="English description/synopsis")
    is_active = models.BooleanField(
        default=True,
        help_text="False = MOHE no longer lists this programme (soft-delete, never hard-deleted; "
                  "see docs/decisions.md). Set by sync_spm_mohe. NOTE: read paths are intentionally "
                  "NOT yet filtered by this — detail/search still show inactive courses until a "
                  "later sprint wires the filter (mirrors StpmCourse), so the golden master is unaffected.",
    )

    # Career pathway: links to MASCO occupation codes
    career_occupations = models.ManyToManyField(
        'MascoOccupation',
        related_name='courses',
        blank=True,
        help_text="MASCO occupation codes this course leads to"
    )

    class Meta:
        db_table = 'courses'
        ordering = ['course_id']

    def __str__(self):
        return f"{self.course_id}: {self.course}"


class MascoOccupation(models.Model):
    """
    MASCO (Malaysia Standard Classification of Occupations) job codes.

    Source: Supabase `masco_occupations` table
    Links to official eMASCO portal: emasco.mohr.gov.my
    """
    masco_code = models.CharField(max_length=20, primary_key=True)
    job_title = models.CharField(max_length=255, help_text="Official Malay job title")
    emasco_url = models.URLField(max_length=500, blank=True, help_text="Link to eMASCO portal page")

    class Meta:
        db_table = 'masco_occupations'
        ordering = ['masco_code']

    def __str__(self):
        return f"{self.masco_code}: {self.job_title}"


class CourseRequirement(models.Model):
    """
    Eligibility requirements for courses.

    Source: Supabase `course_requirements` table

    CRITICAL: These fields map directly to the engine.py logic.
    Do not rename without updating the engine.
    """
    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name='requirement',
        primary_key=True
    )

    # Source file tracking
    source_type = models.CharField(
        max_length=20,
        choices=[
            ('poly', 'Polytechnic'),
            ('kkom', 'Community College'),
            ('tvet', 'TVET/ILKBS/ILJTM'),
            ('ua', 'University/Asasi'),
            ('pismp', 'PISMP/Teacher Training'),
            ('matric', 'Matriculation'),
            ('stpm', 'STPM/Form 6'),
        ],
        default='poly'
    )

    # Minimum counts
    min_credits = models.IntegerField(default=0)
    min_pass = models.IntegerField(default=0)
    max_aggregate_units = models.IntegerField(default=100)
    merit_cutoff = models.FloatField(null=True, blank=True)
    merit_type = models.CharField(
        max_length=20,
        choices=[
            ('standard', 'Standard SPM merit'),
            ('matric', 'Matriculation grade points'),
            ('stpm_mata_gred', 'STPM mata gred'),
        ],
        default='standard',
        help_text="Merit calculation formula to use"
    )

    # ===== DEMOGRAPHIC REQUIREMENTS =====
    req_malaysian = models.BooleanField(default=False, help_text="Must be Malaysian citizen")
    req_male = models.BooleanField(default=False, help_text="Males only")
    req_female = models.BooleanField(default=False, help_text="Females only")
    no_colorblind = models.BooleanField(default=False, help_text="Must NOT be colourblind")
    no_disability = models.BooleanField(default=False, help_text="Must NOT have disability")
    req_disability = models.BooleanField(
        default=False,
        help_text="Student MUST have a declared disability — special-needs (MBPK) intake. "
                  "Gated on the onboarding 'Physical disability' signal."
    )

    # ===== CORE PASS REQUIREMENTS =====
    pass_bm = models.BooleanField(default=False, help_text="Pass Bahasa Malaysia")
    pass_history = models.BooleanField(default=False, help_text="Pass History")
    pass_eng = models.BooleanField(default=False, help_text="Pass English")
    pass_math = models.BooleanField(default=False, help_text="Pass Mathematics")

    # ===== CREDIT REQUIREMENTS =====
    credit_bm = models.BooleanField(default=False, help_text="Credit in BM")
    credit_english = models.BooleanField(default=False, help_text="Credit in English")
    credit_math = models.BooleanField(default=False, help_text="Credit in Math")
    credit_addmath = models.BooleanField(default=False, help_text="Credit in Add Math")

    # ===== COMPOSITE OR-GROUP REQUIREMENTS =====
    pass_stv = models.BooleanField(default=False, help_text="Pass Science/Tech/Vocational")
    credit_stv = models.BooleanField(default=False, help_text="Credit in Science/Tech/Vocational")
    credit_sf = models.BooleanField(default=False, help_text="Credit in Science or Physics")
    credit_sfmt = models.BooleanField(default=False, help_text="Credit in Sci/Phy/AddMath")
    credit_bmbi = models.BooleanField(default=False, help_text="Credit in BM or English")

    # ===== TVET-SPECIFIC REQUIREMENTS =====
    pass_math_addmath = models.BooleanField(default=False, help_text="Pass Math OR Add Math")
    pass_science_tech = models.BooleanField(default=False, help_text="Pass Science OR Tech subject")
    pass_math_science = models.BooleanField(default=False, help_text="Pass Math OR Science")
    credit_math_sci = models.BooleanField(default=False, help_text="Credit in Math OR Science")
    credit_math_sci_tech = models.BooleanField(default=False, help_text="Credit Math/Sci/Tech")
    three_m_only = models.BooleanField(default=False, help_text="3M only: read/write/count")
    single = models.BooleanField(default=False, help_text="Must be unmarried")

    # ===== UNIVERSITY/ASASI (Grade B Requirements) =====
    credit_bm_b = models.BooleanField(default=False, help_text="Grade B+ or better in BM")
    credit_eng_b = models.BooleanField(default=False, help_text="Grade B+ or better in English")
    credit_math_b = models.BooleanField(default=False, help_text="Grade B+ or better in Math")
    credit_addmath_b = models.BooleanField(default=False, help_text="Grade B+ or better in Add Math")

    # ===== UNIVERSITY/ASASI (Distinction Requirements) =====
    distinction_bm = models.BooleanField(default=False, help_text="Distinction (A-) in BM")
    distinction_eng = models.BooleanField(default=False, help_text="Distinction in English")
    distinction_math = models.BooleanField(default=False, help_text="Distinction in Math")
    distinction_addmath = models.BooleanField(default=False, help_text="Distinction in Add Math")
    distinction_phy = models.BooleanField(default=False, help_text="Distinction in Physics")
    distinction_chem = models.BooleanField(default=False, help_text="Distinction in Chemistry")
    distinction_bio = models.BooleanField(default=False, help_text="Distinction in Biology")
    distinction_sci = models.BooleanField(default=False, help_text="Distinction in Science")

    # ===== UA SCIENCE/MATH COMPOSITE REQUIREMENTS =====
    pass_sci = models.BooleanField(default=False, help_text="Pass Science")
    credit_sci = models.BooleanField(default=False, help_text="Credit in Science")
    credit_science_group = models.BooleanField(default=False, help_text="Credit in Science group")
    credit_math_or_addmath = models.BooleanField(default=False, help_text="Credit in Math or Add Math")

    # ===== RELIGIOUS SUBJECT REQUIREMENTS (PI/PM) =====
    pass_islam = models.BooleanField(default=False, help_text="Pass Pendidikan Islam")
    credit_islam = models.BooleanField(default=False, help_text="Credit in Pendidikan Islam")
    pass_moral = models.BooleanField(default=False, help_text="Pass Pendidikan Moral")
    credit_moral = models.BooleanField(default=False, help_text="Credit in Pendidikan Moral")

    # ===== COMPLEX REQUIREMENTS (JSON) =====
    subject_group_req = models.JSONField(
        null=True, blank=True,
        help_text="JSON: Aggregate/diversity checks"
    )
    complex_requirements = models.JSONField(
        null=True, blank=True,
        help_text="JSON: OR-group requirements with counts"
    )

    # ===== ADVISORY FLAGS =====
    req_interview = models.BooleanField(default=False, help_text="Interview required (advisory only)")
    remarks = models.TextField(blank=True, help_text="Additional notes")

    class Meta:
        db_table = 'course_requirements'
        indexes = [
            models.Index(fields=['min_credits']),
            models.Index(fields=['source_type']),
        ]

    def __str__(self):
        return f"Requirements for {self.course_id}"


class CourseTag(models.Model):
    """
    Course characteristics for fit scoring / ranking.

    Source: Supabase `course_tags` table
    """
    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name='tags',
        primary_key=True
    )

    # Fit scoring dimensions
    work_modality = models.CharField(
        max_length=50,
        help_text="hands_on, mixed, theoretical"
    )
    people_interaction = models.CharField(
        max_length=50,
        help_text="high_people, moderate_people, low_people"
    )
    cognitive_type = models.CharField(
        max_length=50,
        help_text="procedural, abstract, problem_solving"
    )
    learning_style = models.JSONField(
        default=list,
        help_text="Array: project_based, continuous_assessment, etc."
    )
    load = models.CharField(
        max_length=50,
        help_text="physically_demanding, mentally_demanding, balanced_load"
    )
    outcome = models.CharField(
        max_length=50,
        help_text="employment_first, pathway_friendly, etc."
    )
    environment = models.CharField(
        max_length=50,
        help_text="field, lab, office, workshop"
    )

    # v1.2 taxonomy additions
    credential_status = models.CharField(max_length=50, default='unregulated')
    creative_output = models.CharField(max_length=50, default='none')
    service_orientation = models.CharField(max_length=50, default='neutral')
    interaction_type = models.CharField(max_length=50, default='mixed')
    career_structure = models.CharField(max_length=50, default='volatile')

    class Meta:
        db_table = 'course_tags'

    def __str__(self):
        return f"Tags for {self.course_id}"


class Institution(models.Model):
    """
    Educational institutions offering courses.

    Source: Supabase `institutions` table
    """
    institution_id = models.CharField(max_length=50, primary_key=True)
    institution_name = models.CharField(max_length=255)
    acronym = models.CharField(max_length=20, blank=True)
    type = models.CharField(max_length=50, help_text="IPTA, Politeknik, etc.")
    category = models.CharField(max_length=100, blank=True)
    subcategory = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    url = models.URLField(blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Demographics (for institution modifiers in ranking)
    dun = models.CharField(max_length=100, blank=True, help_text="State assembly constituency")
    parliament = models.CharField(max_length=100, blank=True, help_text="Federal constituency")
    indian_population = models.FloatField(null=True, blank=True)
    indian_percentage = models.FloatField(null=True, blank=True)
    average_income = models.FloatField(null=True, blank=True)

    # Ranking modifiers (from institutions.json)
    modifiers = models.JSONField(
        default=dict, blank=True,
        help_text="Ranking modifiers: urban, cultural_safety_net, etc."
    )

    class Meta:
        db_table = 'institutions'
        ordering = ['state', 'institution_name']
        indexes = [
            models.Index(fields=['state']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f"{self.acronym or self.institution_id}: {self.institution_name}"


class CourseInstitution(models.Model):
    """
    Many-to-many: Which courses are offered at which institutions.

    Source: Supabase `course_institutions` table
    """
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='offerings'
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='courses_offered'
    )

    # Per-offering details (from details.csv)
    hyperlink = models.URLField(blank=True, help_text="Course application URL")
    tuition_fee_semester = models.CharField(max_length=100, blank=True)
    hostel_fee_semester = models.CharField(max_length=100, blank=True)
    registration_fee = models.CharField(max_length=100, blank=True)
    monthly_allowance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    practical_allowance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    free_hostel = models.BooleanField(default=False)
    free_meals = models.BooleanField(default=False)

    class Meta:
        db_table = 'course_institutions'
        unique_together = ['course', 'institution']
        indexes = [
            models.Index(fields=['institution']),
        ]

    def __str__(self):
        return f"{self.course_id} @ {self.institution_id}"


class PartnerOrganisationQuerySet(models.QuerySet):
    """Makes the SAFE read the obvious one — see `tenants()`."""

    def tenants(self):
        """Only TENANT organisations: those that own an active programme, or have an active
        `org_admin`.

        ⚠ THIS EXISTS BECAUSE THE PLAIN QUERYSET IS A TRAP. This table is dual-role (see the
        model docstring): it holds tenant organisations AND referral organisations — schools and
        NGOs that send us students — with **no flag distinguishing them**. Production has ten
        rows and exactly one tenant. So `PartnerOrganisation.objects.filter(is_active=True)`
        reads like "the organisations" and returns nine things that are not.

        That is not hypothetical: the console's organisation switcher shipped on 2026-07-28
        offering Sri Murugan Centre and Tara Foundation as tenants to switch into, written by
        someone who had verified this exact trap against production the same morning and written
        it down. A note in a knowledge base does not reach the moment the queryset is typed; a
        manager method does.

        Both conditions, not either alone: ownership alone loses a tenant created moments before
        its programme (the admin form makes organisation + programme + administrator together),
        and `org_admin` alone loses a live tenant whose administrator was revoked.

        `role='org_admin'` specifically, NOT "has a PartnerAdmin" — a referral organisation's
        logins are `partner`-role course-selector accounts, and counting those would readmit
        precisely the rows this excludes.
        """
        from django.db.models import Exists, OuterRef, Q
        from apps.scholarship.models import Programme

        owns_programme = Programme.objects.filter(
            organisation_id=OuterRef('pk'), is_active=True)
        has_org_admin = PartnerAdmin.objects.filter(
            owning_organisation_id=OuterRef('pk'), role='org_admin', is_active=True)
        return self.filter(Q(Exists(owns_programme)) | Q(Exists(has_org_admin)))


class PartnerOrganisation(models.Model):
    """Referral partner AND the platform's tenant Organisation record (dual role).

    - Referral registry (original role): `StudentProfile.referred_by_org` /
      `PartnerAdmin.org` point here to mean "the organisation that REFERRED a
      student/admin" — an attribution marker, NEVER an access-control boundary.
    - Platform organisation (platform Sprint 1, 2026-07): the tenant that OWNS a
      scholarship programme. Ownership hangs off `ScholarshipCohort.owning_organisation`
      (the source of truth for programme ownership); the branding/sender/module columns
      below are that tenant's configuration surface (PRD §2–§3). These columns are
      seeded but NOT yet read anywhere — the read seams land in later platform sprints
      (branding Sprint 5/6, module enforcement Sprint 10).
    `is_active` doubles as the tenant active/suspended switch (D-5: suspend, never delete).
    """
    code = models.CharField(max_length=50, unique=True, help_text='URL slug: cumig, partner2')
    name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True)
    contact_person = models.CharField(max_length=200, blank=True, default='')
    # The contact person's phone (paired with contact_person/contact_email above; the
    # Sources module + AdminProfileView both edit this SAME field — deliberately not a
    # second `contact_phone` column, which would drift against the existing editor).
    phone = models.CharField(max_length=30, blank=True, default='')
    is_active = models.BooleanField(default=True)
    # Active-source flag (go-live transition, 2026-07-19): when a future apply form reopens
    # it will draw its "who referred you" list from the organisations flagged here (plus
    # social-media/other chips for unaffiliated students). Default False; the 6 live referral
    # orgs are seeded True by migration. Referral attribution still uses `referred_by_org`
    # regardless of this flag — this only governs apply-form visibility.
    show_in_apply = models.BooleanField(default=False)
    # ⚠ NULL MEANS EVERY GIFT — the same ruling and the same shape as `PartnerAdmin.programme`.
    # This narrows `show_in_apply`: it says WHICH gifts' apply forms list this school, and it is
    # only consulted when the flag is on. All seven live referral organisations are NULL, so every
    # one of them still appears on every form and there is nothing to backfill.
    #
    # ⚠ NOT ACCESS CONTROL, and doubly so here. A referral organisation is an ATTRIBUTION
    # relationship, never a scope (`PartnerAdmin.org` / `referred_by_org` carry that warning too,
    # and the scopes endpoint refuses to offer a referral org as a tenant for the same reason).
    # This is a dropdown's contents.
    programme = models.ForeignKey(
        'scholarship.Programme', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_sources',
        help_text="Gift programme whose apply form lists this source. NULL = every gift, which "
                  "is the default and what every existing source has.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Tenant identity & branding (platform Sprint 1; '' = use platform default) ──
    programme_name_en = models.CharField(max_length=200, blank=True, default='')
    programme_name_ms = models.CharField(max_length=200, blank=True, default='')
    programme_name_ta = models.CharField(max_length=200, blank=True, default='')
    logo_url = models.CharField(max_length=500, blank=True, default='')
    brand_colour = models.CharField(
        max_length=20, blank=True, default='',
        help_text="Hex colour, e.g. '#137fec'; '' = platform default",
    )
    persona_name_en = models.CharField(max_length=100, blank=True, default='')
    persona_name_ms = models.CharField(max_length=100, blank=True, default='')
    persona_name_ta = models.CharField(max_length=100, blank=True, default='')
    team_signoff_en = models.CharField(max_length=200, blank=True, default='')
    team_signoff_ms = models.CharField(max_length=200, blank=True, default='')
    team_signoff_ta = models.CharField(max_length=200, blank=True, default='')

    # ── Tenant sender identity (platform Sprint 1) ──
    email_from = models.EmailField(blank=True, default='')
    email_reply_to = models.EmailField(blank=True, default='')
    email_support = models.EmailField(blank=True, default='')
    frontend_url = models.CharField(max_length=200, blank=True, default='')

    # ── Module flags (platform Sprint 1; WRITTEN but NOT enforced until Sprint 10) ──
    module_scholarship = models.BooleanField(default=False)
    module_sponsor_pool = models.BooleanField(default=False)
    module_comms_whatsapp = models.BooleanField(default=False)
    module_payout = models.BooleanField(default=False)

    # Use `PartnerOrganisation.objects.tenants()` for anything that means "the
    # organisations we run" — the plain queryset also returns REFERRAL organisations.
    objects = PartnerOrganisationQuerySet.as_manager()

    class Meta:
        db_table = 'partner_organisations'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class OrganisationTheme(models.Model):
    """An organisation's colours, STORED as the resolved token set (Layer 1 A1).

    Why a row rather than a wider `brand_colour` column: what is stored is the set of shades a
    tenant APPROVED, not an input we re-derive per request. See `theme_tokens` for the full
    argument — briefly, deriving on the way out means improving the derivation silently restyles
    every tenant, and it makes A4's full palette a migration instead of a second editor.

    ── Shape ──
    `tokens` is `{"light": {"brand-50": "247 250 254", ...}, "dark": {...}}`; values are the
    space-separated RGB triplets the CSS custom properties take, so painting is a straight write
    with no conversion. Every write passes `theme_tokens.validate_tokens` via `save()` — the fence
    is on the model, not on an endpoint, so a shell caller cannot go around it.

    ── Several rows per organisation, ONE of them live (Layer 1 A3) ──
    A1 shipped this as a `OneToOne` and said A3 would relax it. It has. An organisation now has a
    HISTORY of colour versions and at most one `active` — which is what makes changing a colour
    something other than a live experiment on applicants:

        draft     — being worked on. NEVER served. At most one per organisation.
        active    — what visitors see. At most one per organisation.
        archived  — what they used to see. Kept, because that is what makes Revert a real undo
                    rather than "try to remember the old hex".

    ⚠ **THE SERVE PATH READS `active` AND NOTHING ELSE**, at one seam — `active_for()` below, which
    `scholarship.branding` calls. If a draft could reach a visitor, the whole sprint is undone, so
    that is the single filter to protect. The lifecycle (publish, revert) lives in
    `courses.theme_versions`, not here: a model that both stores and transitions ends up with the
    transaction spread across its callers.

    ⚠ THE UNIQUENESS IS PER STATE, NOT PER ORGANISATION. Two partial constraints (`draft` and
    `active`) rather than one blanket rule — an organisation may hold many `archived` rows and must,
    or Revert has nothing to go back to.

    ── BrightPath deliberately has NO row ──
    The platform's light ramp in `globals.css` is the seeded brand hexes, not `brand_ramp()`'s
    output, so giving BrightPath a derived row would shift its own colours by a channel or two.
    No row → the web app keeps today's behaviour exactly.
    """
    STATUS_DRAFT = 'draft'
    STATUS_ACTIVE = 'active'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ARCHIVED, 'Archived'),
    )

    organisation = models.ForeignKey(
        PartnerOrganisation, on_delete=models.CASCADE, related_name='themes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    # The colour the set was derived FROM. Provenance, not the source of truth — a hand-written or
    # (later) per-token set may have no single colour behind it, hence blank-able.
    source_colour = models.CharField(
        max_length=20, blank=True, default='',
        help_text="The hex these tokens were derived from, e.g. '#a21caf'; '' = set by hand",
    )
    tokens = models.JSONField(default=dict)
    published_by_email = models.CharField(max_length=254, blank=True, default='')
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organisation_themes'
        ordering = ['-created_at']
        constraints = [
            # PARTIAL, per state. An organisation may hold many `archived` rows and must — that
            # history IS the undo. Only "being worked on" and "what visitors see" are singular.
            models.UniqueConstraint(
                fields=['organisation'], condition=models.Q(status='draft'),
                name='one_draft_theme_per_organisation'),
            models.UniqueConstraint(
                fields=['organisation'], condition=models.Q(status='active'),
                name='one_active_theme_per_organisation'),
        ]

    @classmethod
    def active_for(cls, organisation):
        """⚠ THE SERVE SEAM. The one live theme for an organisation, or None.

        `scholarship.branding.Branding.theme` calls this and nothing else. Everything a visitor
        sees goes through here, so this filter is the whole of "a draft never reaches a student":
        `test_a_draft_never_reaches_a_visitor` breaks loudly if it is widened.
        """
        return cls.objects.filter(organisation=organisation, status=cls.STATUS_ACTIVE).first()

    def __str__(self):
        return f'Theme for {self.organisation.code}'

    def save(self, *args, **kwargs):
        # The seam every writer passes. `validate_tokens` raises ThemeTokenError (a ValueError) on
        # anything a tenant may not store — a tone, an unknown family, a malformed triplet, or a
        # `brand-500` that differs between the modes.
        from . import theme_tokens
        theme_tokens.validate_tokens(self.tokens)
        return super().save(*args, **kwargs)


class PartnerAdmin(models.Model):
    """Admin user for a partner organisation. Separate from StudentProfile."""
    # Role categories. Kept ALONGSIDE is_super_admin (expand-contract): is_super_admin
    # is backfilled into role and still read by legacy code; a later TD drops it once
    # role is the sole source of truth.
    #   super    — PLATFORM superadmin (the owner). Everything, cross-org; the only role
    #              that sees the platform surfaces (Dashboard / Students directory / Course
    #              Data) — those are super-only from the surface-partition sprint (2026-07-15).
    #   admin    — a B40 staff role, org-scoped: sees its OWN organisation's B40 applications
    #              (read; write only where assigned). NO LONGER sees the platform Students/
    #              Dashboard/Course-Data surfaces (that admin-branch became super-only in the
    #              surface partition). "View-only admin" in the UI.
    #   org_admin — ORGANISATION superadmin (e.g. BrightPath's programme lead): org-wide B40
    #              READ + the QC gate + STAFF MANAGEMENT (invite/list/resend/revoke reviewers,
    #              admins, qc) for its OWN organisation only. Never cross-org, never the
    #              platform surfaces, never super. Includes QC powers (small-team compromise,
    #              owner decision 2026-07-15). UI label: "Organisation admin".
    #   partner  — a REFERRAL organisation rep: Dashboard + Students + Profile, scoped to their
    #              OWN referral org's students only (referral semantics, not the B40 tenant fence).
    #   reviewer — an individual volunteer: B40 Applications + Profile, scoped to the
    #              applicants ASSIGNED to them only; records the verdict → 'interviewed' (awaiting QC).
    #   qc       — quality control: reads its org's B40 applications but its only WRITE is the
    #              QC gate on an 'interviewed' case — Accept (→ recommended) or Reopen (→ back to
    #              the reviewer with comments). Cannot record verdicts / verify / interview.
    #   finance  — org FINANCE admin: the payment-run CHECKER (the middle signature between the
    #              maker and the approver), plus Payments read and the funding summary. NO B40
    #              scope at all (`_b40_scope` → 'none'): no applicant list, no cockpit, no
    #              documents, no income, no verdicts — its only student data is the
    #              award/paid/remaining/eWallet allowlist inside the Payments module. Sponsors
    #              view-only; Administration view-only. Never reviews, QCs or takes an
    #              assignment. **The chain's finance step is DORMANT until the organisation has
    #              ≥1 active finance admin** — evaluated live, never stored on the run.
    # ('viewer' retired 2026-06-09 → folded into 'admin'; 0 viewers existed on prod.)
    ROLE_CHOICES = [
        ('super', 'Super admin'),
        ('admin', 'Admin'),
        ('org_admin', 'Organisation admin'),
        ('partner', 'Partner'),
        ('reviewer', 'Reviewer'),
        ('qc', 'Quality control'),
        ('finance', 'Finance admin'),
    ]
    supabase_user_id = models.CharField(
        max_length=100, unique=True, null=True, blank=True,
        help_text='Set on first login via UID or email match',
    )
    org = models.ForeignKey(
        PartnerOrganisation, on_delete=models.CASCADE,
        null=True, blank=True, related_name='admins',
        help_text='NULL for super admin',
    )
    # Platform tenancy (Sprint 3a): the organisation whose programme this staff
    # member works within — the ACCESS-CONTROL boundary for B40 applications.
    # DISTINCT from `org` above: `org` is the *referring* organisation (referral
    # attribution, used for the partner-students list + bursary witness), never for
    # access control. NULL = platform-level: `super` (global, sees every org) and
    # `partner` (no B40 access — `_b40_scope` returns 'none'). A non-super B40 staff
    # role (admin/reviewer/qc) is bound to exactly one owning organisation.
    owning_organisation = models.ForeignKey(
        PartnerOrganisation, on_delete=models.PROTECT,
        null=True, blank=True, related_name='staff',
        help_text='Tenant org this staff member is scoped to for B40 access '
                  '(NULL = platform-level: super/partner). Never the referral org.',
    )
    # ⚠ NULL MEANS EVERY GIFT, AND THAT IS THE OWNER'S RULING (2026-09-04). Which gift a reviewer
    # covers is a NARROWING, not a fence: `owning_organisation` above is the boundary, and this
    # only says "offer this person the Sabah cases, not the flagship's". So NULL is the permissive
    # default, every one of the 17 org-scoped staff on production keeps working untouched, and
    # THERE IS NO BACKFILL — which is the point. Migration 0123 once populated a column for
    # everybody alive that day and nothing kept doing it for the next person; a default that means
    # "as before" cannot go stale that way (lessons.md, 2026-07-29).
    #
    # ⚠ ONE gift, not a list. With two gifts "NULL = both" covers every case; a person who should
    # cover two of three cannot be expressed and would need a join table. That limit is accepted
    # deliberately (owner, 2026-09-04) and is unreachable until a third gift exists.
    #
    # ⚠ IT IS NOT A FENCE, AND MUST NEVER BECOME ONE. The org fence is `_org_scoped`/`_org_allows`;
    # a reviewer bound to a gift who is somehow handed another gift's case still passes the fence,
    # because the fence is about the ORGANISATION. This decides who is OFFERED work.
    programme = models.ForeignKey(
        'scholarship.Programme', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='staff',
        help_text='Gift programme this person is scoped to. NULL = every gift the organisation '
                  'runs, which is the default and what every existing staff member has.',
    )
    is_super_admin = models.BooleanField(default=False)
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default='reviewer',
        help_text='super / admin / partner / reviewer. Backfilled from is_super_admin.',
    )
    is_active = models.BooleanField(default=True)
    # ⚠ READ THIS BEFORE REACHING FOR `is_active` TO MEAN "step back for a while".
    #
    # `is_active=False` is REVOKED — the account is gone. `get_admin` (courses/views_admin.py)
    # filters on it, so an inactive admin cannot even sign in; it also drops them from
    # notification sets, disarms the finance check and feeds the last-org-admin guard.
    #
    # `paused_at` is PAUSED — a volunteer taking a breather, and the whole point is that they
    # keep their account: they sign in, finish the interviews already theirs, and un-pause
    # themselves. It blocks ONE thing, NEW assignment (`services._can_review`), and deliberately
    # not `scheduling._can_review`, because a paused reviewer must still be able to propose times
    # for a case they are already holding.
    #
    # Two flags that nearly mean the same thing WILL be confused (lessons.md, IC lock 2026-07-29),
    # so the difference is named here rather than left to be inferred, and
    # `test_reviewer_pause.py` asserts pause ≠ revoke on each behaviour that separates them.
    # NULL = participating. Request #10, 2026-08-02.
    paused_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When this reviewer stepped back. NULL = participating. Blocks NEW assignment '
                  'only — never sign-in, and never work already theirs. NOT a revoke: that is '
                  'is_active.',
    )
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ⚠ UNTIL 2026-08-03 THIS SYSTEM COULD NOT SAY WHETHER AN INVITED PERSON EVER TURNED UP.
    # There was no last_login, no accepted_at, nothing — so somebody invited five minutes ago and a
    # colleague of a year both read "Active" on the staff table. These two fields answer the two
    # different questions that were being asked of one missing fact.
    #
    # ⚠ `supabase_user_id` IS NOT THE SIGNAL, and it looks like one. It is written at INVITE time
    # for a non-Google address (the account is provisioned then), and stays NULL for a Google or
    # already-registered invitee until `get_admin` backfills it. So it records how somebody was
    # provisioned, not whether they came. Do not reach for it again.
    #
    # NULL is "NOT RECORDED", never "never signed in" — both columns start empty for everybody who
    # was already here, and the backfill from Supabase is best-effort. Any screen must say so.
    first_seen_at = models.DateTimeField(
        null=True, blank=True,
        help_text='First time this person opened the console. Set once, never updated — it is what '
                  'closes their invitation. NULL means not recorded, not "never came".',
    )
    last_seen_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Most recent console session, throttled to about once a day. Answers "are they '
                  'still with us?". NULL means not recorded.',
    )

    class Meta:
        db_table = 'partner_admins'

    @property
    def is_super(self):
        """True for a super admin via either the new role or the legacy flag."""
        return self.role == 'super' or self.is_super_admin

    @property
    def is_paused(self):
        """True when this person has stepped back from NEW work. Never means revoked."""
        return self.paused_at is not None

    def __str__(self):
        org_name = self.org.name if self.org else 'Super Admin'
        return f'{self.name} ({org_name})'


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

    # STPM / exam type fields
    exam_type = models.CharField(
        max_length=10,
        choices=[('spm', 'SPM'), ('stpm', 'STPM')],
        default='spm',
    )
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
        choices=[('spm', 'SPM'), ('stpm', 'STPM')],
        help_text="Which exam's results were last COMPLETED. Blank = never recorded.",
    )
    stpm_grades = models.JSONField(
        default=dict, blank=True,
        help_text="STPM grades: {'PA': 'A', 'MATH_T': 'B+', ...}"
    )
    stpm_cgpa = models.FloatField(null=True, blank=True)
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
    referral_source = models.CharField(
        max_length=50, blank=True, null=True,
        help_text='Raw referral code or chip value (e.g. cumig, whatsapp, google)',
    )
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


class SavedCourse(models.Model):
    """
    Courses saved/bookmarked by students.

    Supports both SPM (Course) and STPM (StpmCourse) via two nullable FKs.
    Exactly one FK must be set per row (enforced by DB check constraint).
    """
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='saved_courses'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    stpm_course = models.ForeignKey(
        'StpmCourse',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    saved_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    interest_status = models.CharField(
        max_length=20,
        choices=[
            ('interested', 'Interested'),
            ('planning', 'Planning to apply'),
            ('applied', 'Applied'),
            ('got_offer', 'Got offer'),
        ],
        default='interested',
        help_text="Student's self-reported interest level"
    )

    class Meta:
        db_table = 'saved_courses'
        ordering = ['-saved_at']
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(course__isnull=False, stpm_course__isnull=True) |
                    Q(course__isnull=True, stpm_course__isnull=False)
                ),
                name='exactly_one_course_type',
            ),
        ]

    @property
    def course_id_value(self):
        """Return whichever course ID is set."""
        return self.course_id if self.course_id else self.stpm_course_id

    @property
    def course_type(self):
        """Return 'stpm' or 'spm' based on which FK is set."""
        return 'stpm' if self.stpm_course_id else 'spm'

    def __str__(self):
        return f"{self.student_id} saved {self.course_id_value}"


class AdmissionOutcome(models.Model):
    """
    Tracks a student's application outcome for a specific course/institution.
    Enables HalaTuju to measure real-world impact: did we help them get in?
    """
    STATUS_CHOICES = [
        ('applied', 'Applied'),
        ('offered', 'Offered'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='outcomes'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='outcomes'
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outcomes'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='applied')
    intake_year = models.IntegerField(null=True, blank=True)
    intake_session = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    applied_at = models.DateField(null=True, blank=True)
    outcome_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admission_outcomes'
        unique_together = ['student', 'course', 'institution']
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.student_id} → {self.course_id} ({self.status})"


class StpmCourse(models.Model):
    """STPM degree course offered by a public university."""

    STREAM_CHOICES = [
        ('science', 'Science'),
        ('arts', 'Arts'),
        ('both', 'Both'),
    ]

    course_id = models.CharField(max_length=50, primary_key=True)
    course_name = models.CharField(max_length=500)
    university = models.CharField(max_length=255)
    institution = models.ForeignKey(
        'Institution', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stpm_courses',
        help_text='Linked institution (resolved from university name)'
    )
    stream = models.CharField(
        max_length=20, choices=STREAM_CHOICES, default='both'
    )
    merit_score = models.FloatField(null=True, blank=True, help_text='UPU average merit percentage (0-100)')
    field = models.CharField(max_length=255, blank=True, default='', help_text='AI-assigned field category')
    field_key = models.ForeignKey(
        FieldTaxonomy, on_delete=models.PROTECT,
        related_name='stpm_courses',
        help_text="Canonical field classification"
    )
    description = models.TextField(blank=True, default='', help_text='AI-generated course description')
    headline = models.CharField(max_length=200, blank=True, default='', help_text='Quirky BM headline for student-facing subtitle')
    mohe_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text='Link to MOHE ePanduan programme page'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='False = removed from MOHE, hidden from search/eligibility'
    )

    # Quiz enrichment fields (Sprint 2 — RIASEC matching)
    riasec_type = models.CharField(
        max_length=1, blank=True, default='',
        choices=[
            ('R', 'Realistic'), ('I', 'Investigative'), ('A', 'Artistic'),
            ('S', 'Social'), ('E', 'Enterprising'), ('C', 'Conventional'),
        ],
        help_text="Primary Holland RIASEC type for this programme"
    )
    difficulty_level = models.CharField(
        max_length=10, blank=True, default='',
        choices=[
            ('low', 'Low'), ('moderate', 'Moderate'), ('high', 'High'),
        ],
        help_text="Programme difficulty for resilience matching"
    )
    efficacy_domain = models.CharField(
        max_length=15, blank=True, default='',
        choices=[
            ('quantitative', 'Quantitative'), ('scientific', 'Scientific'),
            ('verbal', 'Verbal'), ('practical', 'Practical'),
        ],
        help_text="Primary cognitive domain for efficacy matching"
    )

    # Career pathway: links to MASCO occupation codes
    career_occupations = models.ManyToManyField(
        'MascoOccupation',
        related_name='stpm_courses',
        blank=True,
        help_text="MASCO occupation codes this programme leads to"
    )

    class Meta:
        db_table = 'stpm_courses'
        ordering = ['university', 'course_name']

    def __str__(self):
        return f"{self.course_id}: {self.course_name}"


class StpmRequirement(models.Model):
    """Admission requirements for an STPM degree course."""

    course = models.OneToOneField(
        StpmCourse,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='requirement',
    )

    # STPM academic requirements
    min_cgpa = models.FloatField(default=2.0)
    stpm_min_subjects = models.IntegerField(default=2)
    stpm_min_grade = models.CharField(max_length=5, default='C')

    # Individual STPM subject requirements
    stpm_req_pa = models.BooleanField(default=False)
    stpm_req_math_t = models.BooleanField(default=False)
    stpm_req_math_m = models.BooleanField(default=False)
    stpm_req_physics = models.BooleanField(default=False)
    stpm_req_chemistry = models.BooleanField(default=False)
    stpm_req_biology = models.BooleanField(default=False)
    stpm_req_economics = models.BooleanField(default=False)
    stpm_req_accounting = models.BooleanField(default=False)
    stpm_req_business = models.BooleanField(default=False)

    # Flexible subject group requirement (JSON)
    stpm_subject_group = models.JSONField(null=True, blank=True)

    # SPM prerequisite subjects
    spm_credit_bm = models.BooleanField(default=False)
    spm_pass_sejarah = models.BooleanField(default=False)
    spm_credit_bi = models.BooleanField(default=False)
    spm_pass_bi = models.BooleanField(default=False)
    spm_credit_math = models.BooleanField(default=False)
    spm_pass_math = models.BooleanField(default=False)
    spm_credit_addmath = models.BooleanField(default=False)
    spm_credit_science = models.BooleanField(default=False)

    # Flexible SPM subject group requirement (JSON)
    spm_subject_group = models.JSONField(null=True, blank=True)

    # MUET requirement
    min_muet_band = models.FloatField(default=1.0)

    # Demographic / fitness requirements
    req_interview = models.BooleanField(default=False)
    no_colorblind = models.BooleanField(default=False)
    req_medical_fitness = models.BooleanField(default=False)
    req_malaysian = models.BooleanField(default=False)
    req_bumiputera = models.BooleanField(default=False)
    req_male = models.BooleanField(default=False)
    req_female = models.BooleanField(default=False)
    single = models.BooleanField(default=False)
    no_disability = models.BooleanField(default=False)

    class Meta:
        db_table = 'stpm_requirements'
        indexes = [
            models.Index(fields=['min_cgpa'], name='idx_stpm_req_min_cgpa'),
        ]

    def __str__(self):
        return f"STPM Requirements for {self.course_id}"


class CourseDataStatus(models.Model):
    """Last-run status per course-data source/check, for the admin Course Data dashboard.

    The refresh/validate/audit tools upsert a row here when they run, so the dashboard can
    show freshness ("STPM refreshed 13 Jun", "SPM never refreshed") and last link-health /
    audit findings WITHOUT re-running anything. A missing row = 'never run' (rendered as a
    first-class state). Read-only on the dashboard; written only by the management commands.
    """
    KEY_CHOICES = [
        ('epanduan_stpm', 'e-Panduan — STPM refresh'),
        ('epanduan_spm', 'e-Panduan — SPM refresh'),
        ('uptvet', 'UP_TVET inventory'),
        ('emasco', 'eMASCO occupations'),
        ('link_health', 'Catalogue link health'),
        ('audit', 'Data audit'),
    ]
    key = models.CharField(max_length=40, primary_key=True, choices=KEY_CHOICES)
    last_run_at = models.DateTimeField(help_text='When the tool that writes this key last completed')
    summary = models.JSONField(default=dict, blank=True, help_text='Run summary (counts/findings) for display')
    detail = models.TextField(blank=True, default='', help_text='Optional human note / command used')

    class Meta:
        db_table = 'course_data_status'
        verbose_name_plural = 'Course data statuses'

    def __str__(self):
        return f"{self.key} @ {self.last_run_at:%Y-%m-%d %H:%M}"
