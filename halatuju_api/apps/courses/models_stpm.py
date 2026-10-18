"""The STPM degree catalogue: `StpmCourse` and its `StpmRequirement`.

Moved verbatim out of `models.py` (sources-and-referrals Sprint B, 2026-10-18), a moves-only split:
`models.py` is a ledgered oversize file (see `halatuju_api/CLAUDE.md`, `## Code standards`) and was
at its allowance. `models.py` re-exports both names at its foot, so every `from apps.courses.models
import StpmCourse` and every migration's `courses.StpmCourse` is unchanged. The only edit is that
`field_key` names `'FieldTaxonomy'` as a string — the same model, resolved by Django's registry —
because a module imported from the foot of `models.py` must not import `models.py` back.
"""
from django.db import models


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
        'FieldTaxonomy', on_delete=models.PROTECT,
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
