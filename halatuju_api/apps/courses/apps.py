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
        from .models import CourseRequirement, CourseTag

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

        # Load course tags into DataFrame
        tags_qs = CourseTag.objects.all().values()
        if tags_qs.exists():
            self.course_tags_df = pd.DataFrame(list(tags_qs))
            logger.info(f"Loaded {len(self.course_tags_df)} course tags")

        logger.info("Course data loading complete")
