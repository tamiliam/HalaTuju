"""A NEW intake's criteria tree (criteria Sprint 3b, TD-772 / TD-774).

Kept out of `criteria` (the gate) so that file stays under the size line. Pure: no DB, no save.
"""
from .criteria import from_legacy, validate_tree


#: The bars `ScholarshipCohort` used to give every new intake SILENTLY (model defaults until
#: criteria Sprint 3b, TD-772). The model has none now - a blank is no rule. Named here for the
#: harnesses that must keep their meaning (the test factory, the eval fixtures, `bursary_e2e`),
#: never as a fallback for a real intake.
FORMER_MODEL_DEFAULTS = {'min_spm_a_count': 4, 'min_spm_bplus_count': 5, 'min_stpm_pngk': 2.9,
                         'per_capita_ceiling': 1584}


def stamp_new(cohort):
    """A NEW intake's tree, set at create time (criteria Sprint 3b, TD-774; decisions.md
    2026-11-26 "A new intake year stores its tree when it is created"): ``cohort.criteria =
    from_legacy(cohort)`` from the values the creator gave - a blank value is NO rule (the model
    has no silent bars since 3b). Returns `validate_tree`'s problems; on any, nothing is set and
    the caller refuses the create. Never saves.

    Plain `from_legacy`, as `build_criteria_trees --apply` stores it: a new year has no decisions
    to keep, so it starts on the stored meaning (a PNGK floor with no SPM bar has no SPM group),
    never on `tree_of`'s NULL fallback - and a year created after --apply is never left NULL."""
    from .criteria_write import empty_problems
    tree = from_legacy(cohort)
    # Review R1 (Sprint 3), should-fix 2: a year whose boxes are all blank would store a tree that
    # checks nothing (every student passes) - refused like the criteria API refuses it.
    problems = validate_tree(tree) or empty_problems(tree)
    if not problems:
        cohort.criteria = tree
    return problems
