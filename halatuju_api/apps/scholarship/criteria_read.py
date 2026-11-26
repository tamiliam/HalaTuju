"""Read the intake's rules for every reader OTHER than the gate (criteria Sprint 2, TD-772).

The gate reads the tree itself (`criteria.evaluate` through `shortlisting.evaluate`). The document
rules (`results_route.gift_asks_higher`), the means test (`income_engine.amounts`), the verdict
fingerprint (`verdict_context.intake_values`) and the born-in surfaces (`birth_state.cohort_rule`)
read it through here, so none of them can drift from the shortlist. Pure: no DB, no network.
"""
from .criteria import _mode, _num, _year_flag, birth_states, section, start_years, tree_of


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


def income_ceilings(cohort):
    """``(household_income_max, income_per_person_under, mode)`` of the income section; ``(None,
    None, None)`` when it is absent (the means test is not applied). Today's columns:
    ``(income_ceiling, per_capita_ceiling, 'any')``.

    ⚠ `income_engine.amounts.income_headroom` grades the margin on the 'any' meaning (B40 while
    gross <= the more generous of the two lines). Every tree `from_legacy` builds is 'any'; an
    'all' income section is not storable until the editor (criteria Sprint 3) and the headroom
    reader learn it together (TD-772)."""
    if cohort is None:
        return None, None, None
    income = section(tree_of(cohort), 'income')
    if not income:
        return None, None, None
    mode, tests = _mode(income)
    by = {t.get('test'): t.get('rm') for t in tests or []}
    return by.get('household_income_max'), by.get('income_per_person_under'), mode


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
