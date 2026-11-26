"""Saving an intake's criteria tree from the admin API (criteria Sprint 3, `views_admin.criteria_tree`).

Pure: no DB, no save. Kept out of `criteria` (the gate, in the verdict engine's model register):
nothing here changes how a stored tree is READ - these are the extra checks a WRITE must pass on
top of `criteria.validate_tree`, and the old requirement columns a saved tree is mirrored into.

WHY STRICTER THAN `validate_tree`. `validate_tree` runs on every READ (`tree_of`), so tightening it
could refuse a tree already stored. These checks run only when an admin saves, so a typo is
refused before it decides anybody's money: a PNGK floor of 30 instead of 3.0, a merit of 800, an
income line of RM58600000, a non-finite number (a JSON 1e999 parses as infinity, and an infinite
floor fails everybody), a tree that checks nothing at all.
"""
import math
from types import SimpleNamespace

from . import start_year as _start_year
from .criteria import _mode, from_legacy, validate_tree
from .criteria_read import column_values

#: The top of each scale. A PNGK / CGPA is out of 4.00 (STPM, Matriculation, Asasi, Diploma read
#: on the same 4-point scale, `courses.public.third_route_overall`); both merits are out of 100
#: (`shortlisting.spm_merit`, `courses.public.merit_100`).
PNGK_MAX = 4.0
MERIT_MAX = 100
#: Typo guards, not rules: no SPM certificate carries 20 subjects, no gift's household line is
#: RM100,000 a month.
COUNT_MAX = 20
RM_MAX = 100_000

EMPTY_TREE = 'the tree checks nothing, so every student would pass: add at least one section'


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _test_problems(t, where):
    kind = t['test']
    if kind == 'grade_count':
        if t['at_least'] > COUNT_MAX:
            return [f'{where}: grade_count at_least must be {COUNT_MAX} or fewer']
        return []
    if kind in ('household_income_max', 'income_per_person_under'):
        rm = t['rm']
        # The columns hold whole ringgit (`ScholarshipCohort.income_ceiling` is an integer); a
        # fraction would be cut off in the column and the two would disagree.
        if not isinstance(rm, int) or rm > RM_MAX:
            return [f'{where}: {kind} needs a whole number rm from 0 to {RM_MAX}']
        return []
    top = PNGK_MAX if kind == 'min_pngk' else MERIT_MAX
    if not _finite(t['value']) or t['value'] > top:
        return [f'{where}: {kind} needs a number value from 0 to {top:g}']
    return []


def write_problems(tree):
    """Every reason ``tree`` must not be SAVED, as short strings; ``[]`` means it may be.

    `criteria.validate_tree` first (its problems are returned alone when there are any, because
    the walk below trusts the shape it proves), then: a tree with no section is refused
    (`EMPTY_TREE`); each number must be finite and inside its scale; income in whole ringgit; the
    course-start years once each, in order, as whole numbers (the form `start_year.normalise_years`
    stores), so the tree and its column say the same years the same way. Refuses, never repairs."""
    problems = validate_tree(tree)
    if problems:
        return problems
    if not tree.get('all'):
        return [EMPTY_TREE]
    out = []
    for sec in tree['all']:
        name = sec['section']
        if name == 'born_in':
            continue
        items = _mode(sec)[1]
        if name == 'results':
            for g in items:
                out += [p for t in g['all'] for p in _test_problems(t, g['route'])]
        else:
            out += [p for t in items for p in _test_problems(t, name)]
    for f in tree.get('flag', []):
        years = f['allowed']
        if (any(isinstance(y, bool) or not isinstance(y, int) for y in years)
                or years != _start_year.normalise_years(years)[0]):
            out.append('course_start_year needs allowed: [whole years, once each, in order]')
    return out


def columns_for(tree):
    """The old requirement columns that say ``tree`` as nearly as they can:
    ``{column: value}`` for the seven numbers, ``allowed_birth_states`` and ``allowed_start_years``
    (``[]`` = no rule). Read with `criteria_read.column_values`, the reader the admin rows use, so
    the columns a save writes are exactly the values the Rules tab shows."""
    return column_values(SimpleNamespace(criteria=tree))


def says_more_than_columns(tree):
    """True when the columns cannot say ``tree`` (`from_legacy` of `columns_for` is a different
    tree): an 'all' income join, a post-SPM merit, a grade count at A, B or C+, an SPM group that
    is empty where `from_legacy` would leave it out, a post-SPM group with no floor. Such a tree is
    saved whole; the OLD form then refuses to rebuild it (409 ``rules_beyond_columns``, TD-774)."""
    return from_legacy(SimpleNamespace(**columns_for(tree))) != tree
