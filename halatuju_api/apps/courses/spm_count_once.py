"""COUNT-ONCE SUBJECT BLOCKS — the `count_once` extension of `complex_requirements` (Bumi Sprint D1).

MOHE's SPM requirements say things the legacy `or_groups` cannot: "Gred C dalam mana-mana DUA (2)
mata pelajaran yang belum diambil kira" (two MORE subjects, not already counted), sometimes with
"tidak termasuk ..." (an exclude list), and bullet lists where each bullet is ONE slot ("DUA (2)
mata pelajaran berikut: • Matematik / Matematik Tambahan • Biologi / Fizik"). Legacy `or_groups`
count each group on its own, so one subject may satisfy two groups; that stays exactly as it is
(the golden master holds it). A `count_once` BLOCK is new, opt-in, and self-contained:

    "complex_requirements": {
      "or_groups": [...],                       # legacy, unchanged, evaluated first
      "count_once": [                           # each block must pass on its own
        {"counted": ["eng"],                    # subjects a requirement flag already counted
         "groups": [
           {"count": 1, "grade": "C", "subjects": ["math", "addmath"]},
           {"count": 2, "grade": "D", "slots": [["geo", "poa"], ["bio"], ["phy"]]}],
         "remaining": [{"count": 2, "grade": "C", "exclude": ["bm"]}]}
      ]}

A block passes when ONE assignment gives every unit its own student subject:
  * a group without `slots` is `count` units, each met by any listed subject at `grade` or better;
  * a group with `slots` is `count` units from `count` DIFFERENT slots (a bullet counts once);
  * a `remaining` entry is `count` units, each met by ANY other subject at `grade` or better that is
    not in `exclude`;
  * no unit may use a subject in `counted`, and no student subject is used twice.
"Each subject at most once" over a many-to-many map is a bipartite MATCHING (augmenting paths), not
a first-fit loop — a greedy pick could spend Fizik on the remaining slot and starve the science
group (the lesson behind `stpm_engine._distinct_matches`).

Keys are the grade form's engine keys (`map_subject_code` folds codes the same way as `or_groups`).
"""
from itertools import combinations, product

from .engine import AGGREGATE_GRADE_POINTS, map_subject_code


def _meets(grade, min_grade):
    """The legacy `or_groups` grade test, so a count-once unit reads a grade the same way."""
    return bool(grade) and AGGREGATE_GRADE_POINTS.get(grade, 10) <= AGGREGATE_GRADE_POINTS.get(min_grade, 8)


def _keys(subjects):
    return {map_subject_code(s) for s in subjects or []}


def _max_matching(units, grades):
    """How many units get a distinct student subject. A unit is (allowed_keys or None, min_grade,
    excluded_keys); None means any subject."""
    owner = {}  # student key -> index of the unit using it

    def assign(i, seen):
        allowed, grade, excluded = units[i]
        for key, student_grade in grades.items():
            if key in seen or key in excluded or (allowed is not None and key not in allowed):
                continue
            if not _meets(student_grade, grade):
                continue
            seen.add(key)
            if key not in owner or assign(owner[key], seen):
                owner[key] = i
                return True
        return False

    return sum(1 for i in range(len(units)) if assign(i, set()))


def _slot_choices(group):
    """Every way to pick `count` distinct slots of a slotted group (each pick: a list of units)."""
    grade = group.get('grade', 'E')
    slots = [_keys(s) for s in group['slots']]
    count = group.get('count', 1)  # more than there are slots: no pick, so the block fails
    return [[(slots[i], grade) for i in pick] for pick in combinations(range(len(slots)), count)]


def block_passes(grades, block):
    """True when one count-once assignment fills every unit of the block (see the module doc)."""
    counted = _keys(block.get('counted'))
    grades = {k: g for k, g in (grades or {}).items() if k not in counted}
    fixed, choices = [], []
    for group in block.get('groups', []):
        if group.get('slots'):
            choices.append(_slot_choices(group))
        else:
            allowed = _keys(group.get('subjects'))
            fixed += [(allowed, group.get('grade', 'E'), frozenset())] * group.get('count', 1)
    for entry in block.get('remaining', []):
        fixed += [(None, entry.get('grade', 'E'), frozenset(_keys(entry.get('exclude'))))] * entry.get('count', 1)
    for picks in product(*choices):
        units = fixed + [(allowed, grade, frozenset()) for pick in picks for allowed, grade in pick]
        if _max_matching(units, grades) == len(units):
            return True
    return False


def count_once_failure(grades, blocks):
    """The engine's door: None when every block passes, else the fail reason for the audit trail."""
    for n, block in enumerate(blocks or [], 1):
        if not block_passes(grades, block):
            return f"Count-once block {n} not met (each subject counts once)"
    return None
