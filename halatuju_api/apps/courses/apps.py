"""
Courses app configuration.

Loads course data from database into Pandas DataFrames at startup
for the hybrid engine approach.
"""
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoursesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.courses'
    verbose_name = 'Courses & Eligibility'

    # DataFrames loaded at startup (hybrid engine approach)
    requirements_df = None
    tvet_requirements_df = None
    university_requirements_df = None
    course_tags_df = None

    # Ranking engine data (loaded at startup)
    course_tags_map = {}       # {course_id: tags_dict}
    inst_modifiers_map = {}    # {inst_id: modifiers_dict}
    inst_subcategories = {}    # {inst_id: subcategory_string}
    course_pathway_map = {}    # {course_id: pathway_type}

    def ready(self):
        """
        Called when Django starts. Load data from DB into Pandas DataFrames.

        This is the hybrid approach:
        - Data lives in PostgreSQL (managed via Django ORM)
        - At startup, load into Pandas DataFrames for the engine
        - Engine logic remains unchanged (golden master preserved)
        """
        # Only load data if we're in the main process (not migrations/shell)
        import sys
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return

        try:
            self._load_data()
        except Exception as e:
            # Don't crash startup if DB is empty or unavailable
            logger.warning(f"Could not load course data at startup: {e}")
            logger.warning("Data will need to be loaded manually or after migration")

    def _load_data(self):
        """Load all requirement data from database into DataFrames."""
        import pandas as pd
        from .models import CourseRequirement, CourseTag, Institution

        logger.info("Loading course data from database...")

        # Load requirements into DataFrame
        qs = CourseRequirement.objects.all().values()
        if qs.exists():
            self.requirements_df = pd.DataFrame(list(qs))

            logger.info(f"Loaded {len(self.requirements_df)} course requirements")
        else:
            logger.warning("No course requirements found in database")

        # Load course tags into DataFrame + dict for ranking engine
        tags_qs = CourseTag.objects.all().values()
        if tags_qs.exists():
            self.course_tags_df = pd.DataFrame(list(tags_qs))
            # Build {course_id: tags_dict} for ranking engine
            self.course_tags_map = {
                row['course_id']: {
                    k: v for k, v in row.items() if k != 'course_id'
                }
                for row in tags_qs
            }
            logger.info(f"Loaded {len(self.course_tags_df)} course tags")

        # Enrich course_tags_map with field_key for field interest matching
        from .models import Course
        for course in Course.objects.only('course_id', 'field_key'):
            cid = course.course_id
            if cid in self.course_tags_map:
                self.course_tags_map[cid]['field_key'] = course.field_key_id
            else:
                self.course_tags_map[cid] = {'field_key': course.field_key_id}

        # Load institution subcategories for ranking tie-breaking
        inst_qs = Institution.objects.all().values('institution_id', 'subcategory')
        self.inst_subcategories = {
            row['institution_id']: row['subcategory']
            for row in inst_qs
            if row['subcategory']
        }
        logger.info(f"Loaded {len(self.inst_subcategories)} institution subcategories")

        # Load institution modifiers from DB (migrated from JSON file)
        inst_mod_qs = Institution.objects.exclude(modifiers={}).values(
            'institution_id', 'modifiers'
        )
        self.inst_modifiers_map = {
            row['institution_id']: row['modifiers']
            for row in inst_mod_qs
        }
        logger.info(f"Loaded {len(self.inst_modifiers_map)} institution modifiers")

        # Build course → pathway_type map for frontend pathway summary
        from .models import Course, CourseInstitution
        course_pathway_map = {}

        # Map institution_id → category for TVET lookups
        inst_cat_qs = Institution.objects.filter(
            category__in=['ILJTM', 'ILKBS']
        ).values('institution_id', 'category')
        inst_categories = {
            row['institution_id']: row['category'].lower()
            for row in inst_cat_qs
        }

        # Build TVET course → pathway_type via CourseInstitution
        tvet_course_ids = set(
            CourseRequirement.objects.filter(
                source_type='tvet'
            ).values_list('course_id', flat=True)
        )
        for ci in CourseInstitution.objects.filter(
            course_id__in=tvet_course_ids
        ).values('course_id', 'institution_id'):
            cid = ci['course_id']
            iid = ci['institution_id']
            if iid in inst_categories and cid not in course_pathway_map:
                course_pathway_map[cid] = inst_categories[iid]

        # Default remaining TVET to 'tvet'
        for cid in tvet_course_ids:
            if cid not in course_pathway_map:
                course_pathway_map[cid] = 'tvet'

        # Non-TVET courses
        for req in CourseRequirement.objects.exclude(
            source_type='tvet'
        ).select_related('course').values(
            'course_id', 'source_type', 'course__level'
        ):
            cid = req['course_id']
            st = req['source_type']
            level = req['course__level'] or ''
            if st == 'ua':
                course_pathway_map[cid] = (
                    'asasi' if level.lower() == 'asasi' else 'university'
                )
            elif st in ('matric', 'stpm'):
                course_pathway_map[cid] = st
            else:
                course_pathway_map[cid] = st  # poly, kkom, pismp

        self.course_pathway_map = course_pathway_map
        logger.info(
            f"Loaded {len(course_pathway_map)} course pathway mappings"
        )

        logger.info("Course data loading complete")
