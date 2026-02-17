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

            # Rename columns to match engine expectations (CSV column names)
            # Django model uses 'three_m_only' but engine expects '3m_only'
            col_renames = {'three_m_only': '3m_only'}
            self.requirements_df.rename(
                columns={k: v for k, v in col_renames.items()
                         if k in self.requirements_df.columns},
                inplace=True
            )

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

        # Load institution subcategories for ranking tie-breaking
        inst_qs = Institution.objects.all().values('institution_id', 'subcategory')
        self.inst_subcategories = {
            row['institution_id']: row['subcategory']
            for row in inst_qs
            if row['subcategory']
        }
        logger.info(f"Loaded {len(self.inst_subcategories)} institution subcategories")

        # Load institution modifiers from JSON (not yet in model)
        self._load_institution_modifiers()

        logger.info("Course data loading complete")

    def _load_institution_modifiers(self):
        """Load institution modifiers from data/institutions.json."""
        import json
        import os

        # JSON is in the Streamlit project root, two levels up from halatuju_api/
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        )))
        json_path = os.path.join(
            os.path.dirname(base_dir), 'data', 'institutions.json'
        )

        if not os.path.exists(json_path):
            logger.warning(f"Institution modifiers file not found: {json_path}")
            return

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.inst_modifiers_map = {
                    str(item.get('inst_id', '')).strip(): item.get('modifiers', {})
                    for item in data
                    if item.get('inst_id')
                }
            logger.info(f"Loaded {len(self.inst_modifiers_map)} institution modifiers")
        except Exception as e:
            logger.warning(f"Error loading institution modifiers: {e}")
