"""Course characteristics for fit scoring: `CourseTag`.

Moved verbatim out of `models.py` (Bumi coverage Sprint D1, 2026-10-29), a moves-only split:
`models.py` is a ledgered oversize file (see `halatuju_api/CLAUDE.md`, `## Code standards`) and sat
at its 1105-line allowance, and Sprint D1 adds `CourseRequirement.req_bumiputera` there. `models.py`
re-exports the name at its foot, so every `from apps.courses.models import CourseTag` and every
migration's `courses.CourseTag` is unchanged. The only edit is that `course` names `'Course'` as a
string — the same model, resolved by Django's registry — because a module imported from the foot of
`models.py` must not import `models.py` back (the `models_stpm.py` precedent).
"""
from django.db import models


class CourseTag(models.Model):
    """
    Course characteristics for fit scoring / ranking.

    Source: Supabase `course_tags` table
    """
    course = models.OneToOneField(
        'Course',
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

