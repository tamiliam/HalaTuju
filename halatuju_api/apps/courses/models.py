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


class PartnerOrganisation(models.Model):
    """Partner organisation that refers students via roadshows or campaigns."""
    code = models.CharField(max_length=50, unique=True, help_text='URL slug: cumig, partner2')
    name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'partner_organisations'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class StudentProfile(models.Model):
    """
    User profile linked to Supabase Auth.

    Note: Authentication is handled by Supabase Auth.
    This model stores the student's academic profile and preferences.

    Table name: 'api_student_profiles' to avoid conflict with existing
    Streamlit 'student_profiles' table which has 29 users.
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
                               help_text="Home address")
    phone = models.CharField(max_length=20, blank=True, default='',
                             help_text="Phone number")

    # Identity (Lentera longitudinal tracking)
    nric = models.CharField(max_length=14, blank=True, default='',
                            help_text="NRIC: XXXXXX-XX-XXXX")

    # Family background
    family_income = models.CharField(max_length=30, blank=True, default='',
                                     help_text="Family monthly income range")
    siblings = models.IntegerField(null=True, blank=True,
                                   help_text="Number of siblings")

    # Demographics (for eligibility checking)
    gender = models.CharField(max_length=20, blank=True)
    nationality = models.CharField(max_length=50, default='Warganegara')
    colorblind = models.CharField(max_length=10, default='Tidak')
    disability = models.CharField(max_length=10, default='Tidak')

    # Quiz results (student signals for ranking)
    student_signals = models.JSONField(
        default=dict,
        help_text="Quiz results for fit scoring"
    )

    # Preferences
    preferred_state = models.CharField(max_length=50, blank=True)
    financial_pressure = models.CharField(max_length=20, blank=True)
    travel_willingness = models.CharField(max_length=50, blank=True)

    # STPM / exam type fields
    exam_type = models.CharField(
        max_length=10,
        choices=[('spm', 'SPM'), ('stpm', 'STPM')],
        default='spm',
    )
    stpm_grades = models.JSONField(
        default=dict, blank=True,
        help_text="STPM grades: {'PA': 'A', 'MATH_T': 'B+', ...}"
    )
    stpm_cgpa = models.FloatField(null=True, blank=True)
    muet_band = models.IntegerField(null=True, blank=True)
    spm_prereq_grades = models.JSONField(
        default=dict, blank=True,
        help_text="SPM prerequisite grades for STPM students: {'bm': 'A', 'eng': 'B+', ...}"
    )
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

    class Meta:
        db_table = 'api_student_profiles'

    def __str__(self):
        return f"Profile {self.supabase_user_id}"


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
    min_muet_band = models.IntegerField(default=1)

    # Demographic / fitness requirements
    req_interview = models.BooleanField(default=False)
    no_colorblind = models.BooleanField(default=False)
    req_medical_fitness = models.BooleanField(default=False)
    req_malaysian = models.BooleanField(default=False)
    req_bumiputera = models.BooleanField(default=False)

    class Meta:
        db_table = 'stpm_requirements'
        indexes = [
            models.Index(fields=['min_cgpa'], name='idx_stpm_req_min_cgpa'),
        ]

    def __str__(self):
        return f"STPM Requirements for {self.course_id}"
