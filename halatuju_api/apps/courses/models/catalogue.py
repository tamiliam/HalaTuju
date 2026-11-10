"""The course catalogue: fields, courses, requirements, institutions and the offerings that join them."""

from django.db import models


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
    # Bumi coverage Sprint D1: a Bumiputera-only programme (UiTM, MARA). Shown only to a Malaysian
    # who said yes (`bumiputera.py`); `db_default` so the image still serving inserts (0088).
    req_bumiputera = models.BooleanField(default=False, db_default=False)

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
