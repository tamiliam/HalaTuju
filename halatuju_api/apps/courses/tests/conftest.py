"""
Shared test fixtures for courses app.

Provides a helper to load CourseRequirement data from the test DB into the
app config's DataFrame — replicating what apps.py does at production startup.
"""
import pandas as pd
from django.apps import apps


def load_requirements_df():
    """
    Load CourseRequirement rows from test DB into a DataFrame and inject
    it into the app config, matching the hybrid engine startup flow.

    Call this in setUpClass/setUp AFTER Django fixtures have loaded the data.
    Returns the DataFrame for direct use if needed.
    """
    from apps.courses.models import CourseRequirement

    qs = CourseRequirement.objects.all().values()
    if not qs.exists():
        raise RuntimeError("No CourseRequirement rows in test DB — check fixtures")

    df = pd.DataFrame(list(qs))

    # Inject into app config (same as apps.py)
    courses_config = apps.get_app_config('courses')
    courses_config.requirements_df = df

    # Build course_pathway_map for pre-U courses
    pathway_map = getattr(courses_config, 'course_pathway_map', {})
    for _, row in df.iterrows():
        cid = row['course_id']
        st = row['source_type']
        if st in ('matric', 'stpm'):
            pathway_map[cid] = st
        elif cid not in pathway_map:
            pathway_map[cid] = st
    courses_config.course_pathway_map = pathway_map

    return df
