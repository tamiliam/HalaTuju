"""Read the intake's rules for every reader OTHER than the gate (criteria Sprint 2, TD-772).

The gate reads the tree itself (`criteria.evaluate` through `shortlisting.evaluate`). The document
rules (`results_route.gift_asks_higher`), the means test (`income_engine.amounts`), the verdict
fingerprint (`verdict_context.intake_values`) and the born-in surfaces (`birth_state.cohort_rule`)
read it through here, so none of them can drift from the shortlist. Pure: no DB, no network.
"""
from .criteria import StoredTreeRefused, _mode, _num, _year_flag, birth_states, section, start_years, tree_of


def pngk_floor(cohort):
    """The post-SPM group's PNGK / CGPA floor, or None when the intake has no post-SPM group
    (today's ``min_stpm_pngk`` NULL: an SPM-only intake, D16c). Read as a float, as the column was."""
    if cohort is None:
        return None
    results = section(tree_of(cohort), 'results')
    groups = _mode(results)[1] if results else None
    for g in groups or []:
        if g.get('route') == 'post_spm':
            floor = next((t.get('value') for t in g.get('all', []) if t.get('test') == 'min_pngk'), None)
            return float(floor) if _num(floor) else floor
    return None


def asks_post_spm_results(cohort):
    """True when the intake has a post-SPM group with a floor: `results_route.gift_asks_higher`'s
    question ("does this gift ask for higher results?"). Today: ``min_stpm_pngk is not None``."""
    return pngk_floor(cohort) is not None


def results_routes(cohort):
    """Which results the intake's results section lets through, for the apply page's Step 3 notes
    (TD-773). DISPLAY ONLY: read from the tree the gate reads (`tree_of`), never from intake
    numbers, and it changes no verdict. As `criteria.results_ok` judges:

    * ``'spm'`` - no post-SPM group: everyone is judged on SPM grades (a post-SPM holder too, D16c).
    * ``'post_spm'`` - post-SPM results are NEEDED: an SPM-only holder cannot pass ('own' / 'any'
      with no SPM group, or 'all' with a post-SPM group, where both groups bind).
    * ``'both'`` - 'own' with both groups: a post-SPM holder on the PNGK / CGPA only, an SPM holder
      on the SPM grades only.
    * ``'either'`` - 'any' with both groups: either group lets a student through.
    * ``None`` - no results rule, no intake, or a stored tree `validate_tree` refuses (TD-774: it is
      logged by `tree_of`; a note must not guess at rules nobody can read)."""
    if cohort is None:
        return None
    try:
        results = section(tree_of(cohort), 'results')
    except StoredTreeRefused:
        return None
    if not results:
        return None
    mode, groups = _mode(results)
    routes = {g.get('route') for g in groups or []}
    if 'post_spm' not in routes:
        return 'spm' if 'spm' in routes else None
    if 'spm' not in routes or mode == 'all':
        return 'post_spm'
    return 'both' if mode == 'own' else 'either'


def income_ceilings(cohort):
    """``(household_income_max, income_per_person_under, mode)`` of the income section; ``(None,
    None, None)`` when it is absent (the means test is not applied). Today's columns:
    ``(income_ceiling, per_capita_ceiling, 'any')``.

    ``mode`` is the section's join: 'any' (either line passes; every tree `from_legacy` builds)
    or 'all' (both must pass). `income_engine.amounts.income_headroom` reads both (Sprint 3b)."""
    if cohort is None:
        return None, None, None
    income = section(tree_of(cohort), 'income')
    if not income:
        return None, None, None
    mode, tests = _mode(income)
    by = {t.get('test'): t.get('rm') for t in tests or []}
    return by.get('household_income_max'), by.get('income_per_person_under'), mode


#: The requirement columns, in the order the admin screens serve them (`views_admin.gifts`).
COLUMN_FIELDS = ('min_spm_a_count', 'min_spm_bplus_count', 'min_spm_credit_count', 'min_stpm_pngk',
                 'min_merit_score', 'income_ceiling', 'per_capita_ceiling')
#: The SPM grade_count rules the columns can say: "at least N at A- / B+ / C or better".
_GRADE_COLUMN = {'A-': 'min_spm_a_count', 'B+': 'min_spm_bplus_count', 'C': 'min_spm_credit_count'}


def column_values(cohort):
    """The intake's rules as the old requirement columns would say them, READ FROM THE TREE
    (criteria Sprint 3b, TD-772): ``{column: value}`` for `COLUMN_FIELDS` plus
    ``allowed_birth_states`` (keys) and ``allowed_start_years`` (years). None / [] = no rule.

    Every reader that used to read the columns (the admin intake rows, the seed's report, the
    courses claim) reads them here, so a stored tree wins over contradicting columns. With no
    stored tree it is the columns themselves (`tree_of`'s NULL fallback round-trips them), and a
    tree built by `from_legacy` round-trips too (the four live intakes, `test_criteria_readers`).

    ⚠ A tree can say what the columns cannot (an 'all' join, a post-SPM merit, a grade count at
    another grade). Those parts have no column and are left out here: read the tree itself
    (`criteria.tree_of`) where the whole rule matters."""
    out = dict.fromkeys(COLUMN_FIELDS)
    out['allowed_birth_states'], out['allowed_start_years'] = [], []
    if cohort is None:
        return out
    tree = tree_of(cohort)
    results = section(tree, 'results')
    for g in (_mode(results)[1] if results else None) or []:
        for t in g.get('all', []):
            if g.get('route') == 'post_spm' and t.get('test') == 'min_pngk':
                out['min_stpm_pngk'] = t.get('value')
            elif g.get('route') == 'spm' and t.get('test') == 'grade_count':
                col = _GRADE_COLUMN.get(t.get('grade_or_better'))
                if col:
                    out[col] = t.get('at_least')
    merit = section(tree, 'merit')
    for t in (_mode(merit)[1] if merit else None) or []:
        if t.get('test') == 'min_upu_merit':
            out['min_merit_score'] = t.get('value')
    income = section(tree, 'income')
    for t in (_mode(income)[1] if income else None) or []:
        col = {'household_income_max': 'income_ceiling', 'income_per_person_under': 'per_capita_ceiling'}.get(t.get('test'))
        if col:
            out[col] = t.get('rm')
    out['allowed_birth_states'] = birth_states(tree)
    out['allowed_start_years'] = start_years(tree)
    return out


def birth_state_keys(cohort):
    """The born-in state keys as `birth_state.stored_keys` reads them ([] = not checked). Pass it
    where a reader passed ``cohort.allowed_birth_states``: `stored_keys` of a list of strings is
    that list, so `check`, `meets_rule` and the IC-lock read the same answer."""
    return birth_states(tree_of(cohort)) if cohort is not None else []


def start_years_rule(cohort):
    """None when the intake has no course-start flag, else its years in order (`start_year.
    stored_years`; [] for a flag whose stored years are all junk, which stays ON). Today:
    ``stored_years(allowed_start_years) if rule_on(allowed_start_years) else None``."""
    if cohort is None:
        return None
    tree = tree_of(cohort)
    return start_years(tree) if _year_flag(tree) is not None else None
