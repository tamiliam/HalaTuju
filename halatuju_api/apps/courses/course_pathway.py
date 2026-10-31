"""Which apply-form PATHWAY a catalogue course belongs to — one rule for the boot map and one course.

`CoursesConfig._load_data` builds `course_pathway_map` ({course_id: pathway}) for the whole SPM
catalogue at start-up; the scholarship pickers group courses by it (`views_offerings`). The offer
realignment (2026-10-31) needs the same answer for ONE course, from a management command or a test
where the boot map may be empty. Both now read `pathway_for_requirement`, so the two can never
disagree about a non-TVET course. An STPM degree is `university`: the STPM / third-route holder's
picker stores the pathway step's own key, and a degree is reached through University.
"""
from .tvet_families import TVET_CATEGORY_PATHWAY


def pathway_for_requirement(source_type, level):
    """The pathway of a NON-TVET SPM course, from its requirement's `source_type` and its `level`:
    `ua` is `asasi` at the Asasi level and `university` otherwise; every other source type is its
    own pathway (`poly`, `kkom`, `pismp`, `matric`, `stpm`)."""
    if source_type == 'ua':
        return 'asasi' if (level or '').lower() == 'asasi' else 'university'
    return source_type


def course_pathway_type(course_id):
    """The pathway of ONE catalogue course, or '' when it is not in either catalogue or a TVET
    course's campuses span more than one TVET family. Read-only."""
    from .models import CourseInstitution, CourseRequirement, StpmCourse
    cid = (course_id or '').strip()
    if not cid:
        return ''
    if StpmCourse.objects.filter(course_id=cid).exists():
        return 'university'
    req = (CourseRequirement.objects.filter(course_id=cid)
           .values_list('source_type', 'course__level').first())
    if req is None:
        return ''
    source_type, level = req
    if source_type != 'tvet':
        return pathway_for_requirement(source_type, level)
    families = {TVET_CATEGORY_PATHWAY[c] for c in CourseInstitution.objects.filter(course_id=cid)
                .values_list('institution__category', flat=True) if c in TVET_CATEGORY_PATHWAY}
    if len(families) > 1:
        return ''
    return next(iter(families)) if families else 'tvet'
