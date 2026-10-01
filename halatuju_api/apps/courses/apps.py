"""
Courses app configuration.

Loads course data from database into Pandas DataFrames at startup
for the hybrid engine approach.
"""
import logging
import threading
import time

from django.apps import AppConfig

logger = logging.getLogger(__name__)

#: TD-047: a request that finds the data EMPTY retries the load — at most once per this many
#: seconds per process, so a database that is really down is not hammered by every request.
DATA_RETRY_INTERVAL_SECONDS = 60


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

    # TD-047 lazy retry state (per process). Monotonic clock of the last retry; the lock stops two
    # concurrent requests from both reloading — the loser simply answers with what is there.
    _last_retry_at = None
    _retry_lock = threading.Lock()

    def data_loaded(self):
        """True when the eligibility frame holds rows. Pure read: no query, no retry."""
        df = self.requirements_df
        return df is not None and not df.empty

    def _retry_due(self):
        last = self._last_retry_at
        return last is None or time.monotonic() - last >= DATA_RETRY_INTERVAL_SECONDS

    def ensure_data(self):
        """`requirements_df`, after ONE more load attempt if it is empty (TD-047).

        A failed startup load used to leave every eligibility check answering 503 until the
        container restarted. Now the request that finds it empty tries again — rate-limited to
        once per `DATA_RETRY_INTERVAL_SECONDS`, inline, no thread. Never raises.

        ⚠ Only the ELIGIBILITY route calls this. The ranking route reads the maps as they are, so
        it stays empty until an eligibility check (which every student runs first) has retried.
        """
        if self.data_loaded() or not self._retry_due():
            return self.requirements_df
        if not self._retry_lock.acquire(blocking=False):
            return self.requirements_df
        try:
            # Re-checked UNDER the lock (review F5b): a thread that read the stale clock above may
            # have waited while another one ran the retry — that one's result stands.
            if self.data_loaded() or not self._retry_due():
                return self.requirements_df
            self._last_retry_at = time.monotonic()
            self._load_data()
        except Exception as e:
            logger.warning(f"Course data retry failed: {e}")
        finally:
            self._retry_lock.release()
        return self.requirements_df

    def ready(self):
        """
        Called when Django starts. Load data from DB into Pandas DataFrames.

        This is the hybrid approach:
        - Data lives in PostgreSQL (managed via Django ORM)
        - At startup, load into Pandas DataFrames for the engine
        - Engine logic remains unchanged (golden master preserved)
        """
        # Only load data if we're in the main process (not migrations/shell). The eligibility
        # DataFrame is only needed to SERVE eligibility; skip it for schema + read-only diagnostic
        # commands so they boot fast (esp. run locally against a remote DB).
        import sys
        _SKIP_DATA_CMDS = ('migrate', 'makemigrations', 'stuck_report', 'shell')
        if any(cmd in sys.argv for cmd in _SKIP_DATA_CMDS):
            return

        try:
            self._load_data()
        except Exception as e:
            # Don't crash startup if DB is empty or unavailable
            logger.warning(f"Could not load course data at startup: {e}")
            logger.warning("Data will need to be loaded manually or after migration")

    def _load_data(self):
        """Load all requirement data from database into DataFrames.

        ⚠ BUILT INTO LOCALS, PUBLISHED AT THE END, `requirements_df` LAST (review F5a). The lazy
        retry (`ensure_data`) runs this while requests are being served; assigning each frame as
        it was built let a request see an eligibility frame beside half-built ranking maps, and a
        load that failed half-way left them so. Now a failure publishes nothing, and a request that
        sees `requirements_df` set sees every map that goes with it."""
        import pandas as pd
        from .models import CourseRequirement, CourseTag, Institution

        logger.info("Loading course data from database...")

        # Load requirements into DataFrame
        requirements_df = None
        qs = CourseRequirement.objects.all().values()
        if qs.exists():
            requirements_df = pd.DataFrame(list(qs))

            logger.info(f"Loaded {len(requirements_df)} course requirements")
        else:
            logger.warning("No course requirements found in database")

        # Load course tags into DataFrame + dict for ranking engine
        course_tags_df, course_tags_map = self.course_tags_df, {}
        tags_qs = CourseTag.objects.all().values()
        if tags_qs.exists():
            course_tags_df = pd.DataFrame(list(tags_qs))
            # Build {course_id: tags_dict} for ranking engine
            course_tags_map = {
                row['course_id']: {
                    k: v for k, v in row.items() if k != 'course_id'
                }
                for row in tags_qs
            }
            logger.info(f"Loaded {len(course_tags_df)} course tags")

        # Enrich course_tags_map with field_key for field interest matching
        from .models import Course
        for course in Course.objects.only('course_id', 'field_key'):
            cid = course.course_id
            if cid in course_tags_map:
                course_tags_map[cid]['field_key'] = course.field_key_id
            else:
                course_tags_map[cid] = {'field_key': course.field_key_id}

        # Load institution subcategories for ranking tie-breaking
        inst_qs = Institution.objects.all().values('institution_id', 'subcategory')
        inst_subcategories = {
            row['institution_id']: row['subcategory']
            for row in inst_qs
            if row['subcategory']
        }
        logger.info(f"Loaded {len(inst_subcategories)} institution subcategories")

        # Load institution modifiers from DB (migrated from JSON file)
        inst_mod_qs = Institution.objects.exclude(modifiers={}).values(
            'institution_id', 'modifiers'
        )
        inst_modifiers_map = {
            row['institution_id']: row['modifiers']
            for row in inst_mod_qs
        }
        logger.info(f"Loaded {len(inst_modifiers_map)} institution modifiers")

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

        logger.info(
            f"Loaded {len(course_pathway_map)} course pathway mappings"
        )

        # Publish. Every map first; the eligibility frame — what `data_loaded` reads — LAST.
        self.course_tags_df = course_tags_df
        self.course_tags_map = course_tags_map
        self.inst_subcategories = inst_subcategories
        self.inst_modifiers_map = inst_modifiers_map
        self.course_pathway_map = course_pathway_map
        if requirements_df is not None:
            self.requirements_df = requirements_df
        logger.info("Course data loading complete")
