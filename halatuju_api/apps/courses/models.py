"""
Database models for HalaTuju courses and eligibility.

These models mirror the CSV data structure from the Streamlit version:
- courses.csv → Course
- requirements.csv + tvet_requirements.csv + university_requirements.csv → CourseRequirement
- course_tags.json → CourseTag
- institutions.csv → Institution
- links.csv → CourseInstitution
- masco_details.csv → MascoOccupation
- course_masco_link.csv → Course.career_occupations (M2M)
"""
from django.db import models


class Course(models.Model):
    """
    Master course information.

    Source: courses.csv (431 rows)
    """
    course_id = models.CharField(max_length=50, primary_key=True)
    course = models.CharField(max_length=255, help_text="Course name in Malay")
    wbl = models.BooleanField(default=False, help_text="Work-Based Learning flag")
    level = models.CharField(max_length=50, help_text="Diploma, Sijil, Asasi, etc.")
    department = models.CharField(max_length=100)
    field = models.CharField(max_length=100)
    frontend_label = models.CharField(max_length=100, help_text="UI category label")
    semesters = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)

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

    Source: masco_details.csv (274 entries)
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

    Source: requirements.csv + tvet_requirements.csv + university_requirements.csv

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
        ],
        default='poly'
    )

    # Minimum counts
    min_credits = models.IntegerField(default=0)
    min_pass = models.IntegerField(default=0)
    max_aggregate_units = models.IntegerField(default=100)
    merit_cutoff = models.FloatField(null=True, blank=True)

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

    Source: course_tags.json (431 entries)
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

    Source: institutions.csv (212 rows)
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

    Source: links.csv (633 rows) + details.csv
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
    """
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='saved_courses'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE
    )
    saved_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'saved_courses'
        unique_together = ['student', 'course']
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.student_id} saved {self.course_id}"
