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
import hashlib
import json
import math
from types import SimpleNamespace

from . import start_year as _start_year
from .criteria import _mode, from_legacy, section, validate_tree
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
#: Review R1 (Sprint 3), should-fix 2: a results section whose groups hold no rule passes everyone.
NO_RESULTS_RULE = ('results: no group holds a rule, so every student passes it - add a rule, '
                   'or a merit section')
#: Review R1 (Sprint 3), blocker 1: a post-SPM group with no floor passes every post-SPM holder,
#: even one with no CGPA, while `criteria_read.pngk_floor` reads None - so no higher-results
#: document is asked for (`results_route.gift_asks_higher` is False). The gate and the document
#: rules would split.
NO_PNGK_FLOOR = 'results: a post-SPM group needs a min_pngk floor'
#: The same split for the post-SPM merit: it binds post-SPM holders, whose results no document
#: is asked for unless a post-SPM group has a floor.
MERIT_NEEDS_FLOOR = 'merit: min_merit (the post-SPM merit) needs a post-SPM group with a min_pngk floor'
#: The problems `empty_problems` gives: the old form answers them as 400 ``bad_criteria``.
EMPTY_PROBLEMS = (EMPTY_TREE, NO_RESULTS_RULE)


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


def empty_problems(tree):
    """``[EMPTY_TREE]`` / ``[NO_RESULTS_RULE]`` / ``[]`` for a tree `validate_tree` passes: does it
    check anything at all? Run on EVERY save of a tree - the criteria API (`write_problems`), the
    old form's rebuild (`intake_years._rebuild_criteria`) and a new year's tree
    (`criteria_new.stamp_new`) - so no route stores a tree that lets everybody through.
    `from_legacy` never builds a results section without a rule unless it adds a merit section."""
    if not tree.get('all'):
        return [EMPTY_TREE]
    results = section(tree, 'results')
    if (results and not any(g['all'] for g in _mode(results)[1])
            and section(tree, 'merit') is None):
        return [NO_RESULTS_RULE]
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
    problems = empty_problems(tree)
    if problems:
        return problems
    out = []
    results, merit = section(tree, 'results'), section(tree, 'merit')
    groups = {g['route']: g['all'] for g in _mode(results)[1]} if results else {}
    # `GROUP_TESTS['post_spm']` is ('min_pngk',) and a test is never repeated, so a post-SPM group
    # has a floor exactly when it holds a test.
    if 'post_spm' in groups and not groups['post_spm']:
        out.append(NO_PNGK_FLOOR)
    if merit and any(t['test'] == 'min_merit' for t in merit['all']) and not groups.get('post_spm'):
        out.append(MERIT_NEEDS_FLOOR)
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
    is empty where `from_legacy` would leave it out. Order alone never counts (`same_tree`). Such
    a tree is saved whole; the OLD form then refuses to rebuild it (409 ``rules_beyond_columns``, TD-774)."""
    return not same_tree(from_legacy(SimpleNamespace(**columns_for(tree))), tree)


def _canonical(tree):
    """A valid ``tree`` with every order that means nothing sorted out (review R1, minor 6): the
    sections (read by name, `criteria.section`), the results groups (read by route), the tests in
    a list (each is checked; only a reason's wording follows their order) and the born-in states
    (a set). An empty ``flag`` list is the same as none. The course-start years are kept as stored
    (`write_problems` asks them in order)."""
    def tests(ts):
        return sorted(ts, key=lambda t: (t['test'], t.get('grade_or_better') or ''))
    secs = []
    for sec in tree.get('all', []):
        mode, items = _mode(sec)
        if sec['section'] == 'results':
            items = sorted(({'route': g['route'], 'all': tests(g['all'])} for g in items),
                           key=lambda g: g['route'])
        elif sec['section'] == 'born_in':
            items = sorted(items)
        else:
            items = tests(items)
        secs.append({'section': sec['section'], mode: items})
    out = {'all': sorted(secs, key=lambda s: s['section'])}
    if tree.get('flag'):
        out['flag'] = tree['flag']
    return out


def same_tree(a, b):
    """True when ``a`` and ``b`` say the same rules, whatever order their parts are in. A tree
    `validate_tree` refuses is compared exactly (its shape cannot be trusted to sort)."""
    if validate_tree(a) or validate_tree(b):
        return a == b
    return _canonical(a) == _canonical(b)


def digest(stored):
    """The stale-write fingerprint of an intake's STORED criteria value (review R1, should-fix 5):
    sha256 of its compact JSON with sorted keys. Served on GET and PATCH; a PATCH must send the
    one it read, so a save made from a screen that is out of date is refused (409
    ``criteria_changed``). Exact, not order-blind: any write to the column moves it."""
    text = json.dumps(stored, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
