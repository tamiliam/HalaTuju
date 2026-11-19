"""The public face of the courses app, for every OTHER app (audit A3.12, TD-414).

Other apps (today only `scholarship`) reach into courses for a handful of things. Before this
module they imported each one from whichever courses file happened to hold it, so any courses file
could be moved or renamed only by chasing imports across the app boundary. This facade is the one
door: a name listed here is a promise to the other apps, and a courses file behind it may move
without them noticing.

Part 2 (A3.13) adds the two models `reports` reads, `StudentProfile` and `FieldTaxonomy`.

Package F2-1 adds the catalogue and merit helpers scholarship used to import from their home files.

F2b stage 1 adds the loose staff, gift, offerings and contrast helpers scholarship used to import
from their home files: `PartnerAdminMixin`, `is_google_email`, `fetch_auth_data`, `invitation_dict`,
`MARA_DIVISION`, `SPM_PATHWAYS`, the staff fence trio, the delete rules, the archive questions, the
gift resolvers and the `contrast` module. The underscore names are re-exported under public names.

Part 1 re-exports the `exam_questions` names scholarship uses (the held-qualification, SPM-grade,
CGPA and merit readers). Later parts add the models, the staff helpers and the rest.

Rules:
- Re-export only. Nothing here computes, so the facade adds no behaviour. A re-exported name is the
  SAME object as the one in its home module (`public.results_held is exam_questions.results_held`).
- Because a from-import binds the object early, a test that wants to replace one of these names
  patches it where the CALLER looks it up (`apps.scholarship.pool.results_held`, or
  `public.merit_100` for a caller that reads it through the module), never on `exam_questions`.
- Courses itself keeps importing its own files directly; this module is for other apps.
"""
from . import contrast
from . import exam_questions as _exam_questions
from .exam_questions import (
    QUALIFICATION_LABELS,
    THIRD_ROUTE,
    ResultsHeldField,
    completed_qualifications,
    diploma_is_public,
    has_stpm_results,
    heading_for,
    held_summary,
    is_tertiary,
    merit_100,
    overall_cgpa,
    overall_from,
    results_held,
    spm_grades_for,
    spm_grades_none_label,
    spm_slip_comparable,
    third_route_overall,
)
from .course_pathway import course_pathway_type
from .csv_safe import csv_cell
from .engine import calculate_merit_score, prepare_merit_inputs
from .models import FieldTaxonomy, StudentProfile
from .pismp_taxonomy import aliran_of
from .search import _digits_expr as digits_expr
from .search import apply_people_search, people_search_term
from .stpm_engine import STPM_CGPA_POINTS, calculate_stpm_cgpa
from .stpm_pngk import pngk_from_grades, stpm_cgpa_of
from .staff_archive import archive_asked, in_a_group_refusal
from .staff_delete_rules import delete_fields, lock_org_admins_of, powers_holder_ids, sole_org_admin_ids
from .staff_fence import _deletable_now as deletable_now
from .staff_fence import _staff_target_manageable as staff_target_manageable
from .staff_fence import staff_target_readable
from .staff_gift import _as_id as gift_as_id
from .staff_gift import _gift_refusal as gift_refusal
from .staff_gift import _not_found as gift_not_found
from .staff_gift import resolve_gifts
from . import (
    org_config, password_change_flag, staff_activity_hook, staff_archive, staff_gift,
    staff_permissions, staff_reinvite, staff_tables, supabase_admin, theme_tokens, theme_versions,
)
from .tvet_families import family_of
from .tvet_institutions import HELD
from .utils import tidy_parentage_marker
from .views_admin import PartnerAdminMixin, is_google_email
from .views_admin import _fetch_auth_data as fetch_auth_data
from .views_admin import _invitation_dict as invitation_dict
from .views_offerings import MARA_DIVISION, SPM_PATHWAYS

__all__ = [
    'QUALIFICATION_LABELS', 'THIRD_ROUTE', 'ResultsHeldField', 'completed_qualifications',
    'diploma_is_public', 'has_stpm_results', 'heading_for', 'held_summary', 'is_tertiary',
    'merit_100', 'overall_cgpa', 'overall_from', 'results_held', 'spm_grades_for',
    'spm_grades_none_label', 'spm_slip_comparable', 'third_route_overall',
    'FieldTaxonomy', 'StudentProfile',
    'course_pathway_type', 'csv_cell', 'calculate_merit_score', 'prepare_merit_inputs',
    'aliran_of', 'digits_expr', 'apply_people_search', 'people_search_term',
    'STPM_CGPA_POINTS', 'calculate_stpm_cgpa', 'pngk_from_grades', 'stpm_cgpa_of',
    'family_of', 'HELD', 'tidy_parentage_marker',
    'register_stpm_document_witness',
    'PartnerAdminMixin', 'is_google_email', 'fetch_auth_data', 'invitation_dict',
    'MARA_DIVISION', 'SPM_PATHWAYS',
    'deletable_now', 'staff_target_manageable', 'staff_target_readable',
    'delete_fields', 'lock_org_admins_of', 'powers_holder_ids', 'sole_org_admin_ids', 'archive_asked', 'in_a_group_refusal',
    'gift_as_id', 'gift_refusal', 'gift_not_found', 'resolve_gifts',
    'contrast',
    # Module doors (F2b stage 2): the object IS the home module, so patches on it keep working.
    'password_change_flag', 'staff_activity_hook', 'staff_archive', 'staff_gift',
    'staff_permissions', 'staff_reinvite', 'staff_tables', 'supabase_admin',
    'theme_tokens', 'theme_versions',
    # H3b: the organisation tunables door, for new scholarship callers (older ones still import it
    # directly, listed in test_cross_app_private_imports).
    'org_config',
]


def register_stpm_document_witness(witness):
    """Tell `results_held` how to ask scholarship whether a live document is STPM results.

    Registered, not imported: courses imports nothing from scholarship at module level. The witness
    is read from `exam_questions` at call time, so it has to be SET there; this writes it through.
    """
    _exam_questions.STPM_DOCUMENT_WITNESS = witness
