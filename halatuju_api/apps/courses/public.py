"""The public face of the courses app, for every OTHER app (audit A3.12, TD-414).

Other apps (today only `scholarship`) reach into courses for a handful of things. Before this
module they imported each one from whichever courses file happened to hold it, so any courses file
could be moved or renamed only by chasing imports across the app boundary. This facade is the one
door: a name listed here is a promise to the other apps, and a courses file behind it may move
without them noticing.

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
from . import exam_questions as _exam_questions
from .exam_questions import (  # noqa: F401  (the re-exports ARE the point)
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

__all__ = [
    'QUALIFICATION_LABELS', 'THIRD_ROUTE', 'ResultsHeldField', 'completed_qualifications',
    'diploma_is_public', 'has_stpm_results', 'heading_for', 'held_summary', 'is_tertiary',
    'merit_100', 'overall_cgpa', 'overall_from', 'results_held', 'spm_grades_for',
    'spm_grades_none_label', 'spm_slip_comparable', 'third_route_overall',
    'register_stpm_document_witness',
]


def register_stpm_document_witness(witness):
    """Tell `results_held` how to ask scholarship whether a live document is STPM results.

    Registered, not imported: courses imports nothing from scholarship at module level. The witness
    is read from `exam_questions` at call time, so it has to be SET there; this writes it through.
    """
    _exam_questions.STPM_DOCUMENT_WITNESS = witness
