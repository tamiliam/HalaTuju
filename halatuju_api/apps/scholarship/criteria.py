"""The intake's criteria as ONE AND/OR tree (criteria editor, Sprint 1, 2026-11-25).

Pure: no DB writes, no network. Sprint 1 ships the engine, the converter from today's cohort
columns and a read-only replay (`replay_criteria`); nothing live reads this module yet. Sprint 2
stores the tree on the intake and switches `shortlisting.evaluate` onto it. The spec, with worked
examples, is the 2026-11-25 entry in docs/decisions.md ("Criteria tree semantics").

The stored shape (the owner-approved v9 design; internal keys only, never admin wording)::

    {'all': [
        {'section': 'results', 'any' | 'all': [
            {'route': 'post_spm', 'all': [{'test': 'min_pngk', 'value': 3.0},
                                         {'test': 'min_merit', 'value': 80}]},
            {'route': 'spm', 'all': [{'test': 'grade_count', 'at_least': 3, 'grade_or_better': 'C'},
                                    {'test': 'min_upu_merit', 'value': 70}]}]},
        {'section': 'income', 'any' | 'all': [{'test': 'household_income_max', 'rm': 5860},
                                              {'test': 'income_per_person_under', 'rm': 1584}]},
        {'section': 'born_in', 'any': ['sabah', 'labuan']}],
     'flag': [{'test': 'course_start_year', 'allowed': [2025, 2026]}]}

A section that is absent is not checked; a group that is absent is switched off. Everything
outside the tree (consent, intent, IPTS, the D5 public-diploma gate) is unchanged and keeps its
order: consent, intent, IPTS, born in, D5, results, income - exactly `shortlisting.evaluate`'s.

⚠ Reasons and categories are byte-identical to `shortlisting.evaluate` for every legacy shape
(`from_legacy`), because a reviewer and the decline email read them. The formatting therefore
keeps today's quirks on purpose ("3 at A- (need 4)" has no "or better"; "RMNone" when only the
per-person ceiling is set). Sprint 2 removes the duplication by making `shortlisting` call this.
"""
from apps.courses import public as courses_public

from . import start_year as _start_year
from .birth_state import STATE_KEYS
from .birth_state import check as check_birth_state
from .shortlisting import ShortlistResult, _count, spm_merit

#: SPM grades, best first. "N at G or better" counts every grade up to and including G. SPM has
#: no C- (`shortlisting.CREDIT_GRADES`); D, E, G and anything unknown never count.
GRADES = ('A+', 'A', 'A-', 'B+', 'B', 'C+', 'C')
MODES = ('any', 'all')
SECTIONS = ('results', 'income', 'born_in')
GROUPS = ('post_spm', 'spm')
GROUP_TESTS = {'post_spm': ('min_pngk', 'min_merit'), 'spm': ('grade_count', 'min_upu_merit')}
INCOME_TESTS = ('household_income_max', 'income_per_person_under')
FLAG_TESTS = ('course_start_year',)

#: Owner ruling 2026-11-25: the degree intake migrates with the SPM group OFF (closes the #921
#: gap: an SPM-only student there met no bar). Kept OUT of `from_legacy` on purpose, so the
#: converter stays a plain reading of the columns and the exception is named where it is used.
SPM_OFF_AT_MIGRATION = frozenset({'bpb-deg-dip-2026'})


def at_or_better(grades, grade):
    """How many SPM subjects in ``grades`` are at ``grade`` or better (A+ best, C worst)."""
    return _count(grades, set(GRADES[:GRADES.index(grade) + 1]))


def _mode(node):
    """``(mode, items)`` of a node holding exactly one of 'any' / 'all'."""
    for m in MODES:
        if m in node:
            return m, node[m]
    return None, None


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ── Validation ──────────────────────────────────────────────────────────────────────────────

def validate(tree):
    """Every problem with ``tree`` as a list of short strings; ``[]`` means it is valid.

    Refuses rather than repairs (request #30's lesson): an unknown key, a repeated section or
    test, an empty group list, a negative or non-numeric value are each an error."""
    errs = []
    if not isinstance(tree, dict) or set(tree) - {'all', 'flag'} or not isinstance(tree.get('all', []), list):
        return ['tree must be {all: [...], flag: [...]}']
    seen = set()
    for sec in tree.get('all', []):
        name = sec.get('section') if isinstance(sec, dict) else None
        if name not in SECTIONS:
            errs.append(f'unknown section {name!r}')
            continue
        if name in seen:
            errs.append(f'section {name} repeated')
        seen.add(name)
        mode, items = _mode(sec)
        if set(sec) != {'section', mode} or not isinstance(items, list) or not items:
            errs.append(f'section {name} needs one non-empty any/all list')
            continue
        if name == 'born_in':
            if mode != 'any' or any(s not in STATE_KEYS for s in items) or len(set(items)) != len(items):
                errs.append('born_in must be any: [distinct state keys]')
        elif name == 'results':
            errs += _validate_groups(items)
        else:
            errs += _validate_tests(items, INCOME_TESTS, 'income')
    flags = tree.get('flag', [])
    if not isinstance(flags, list) or len(flags) > 1:
        errs.append('flag must be a list of at most one test')
    else:
        for f in flags:
            years = f.get('allowed') if isinstance(f, dict) else None
            if (not isinstance(f, dict) or f.get('test') not in FLAG_TESTS or set(f) != {'test', 'allowed'}
                    or not isinstance(years, list) or not years
                    or _start_year.normalise_years(years)[1] is False):
                errs.append('course_start_year needs allowed: [years]')
    return errs


def _validate_groups(groups):
    errs, seen = [], set()
    for g in groups:
        route = g.get('route') if isinstance(g, dict) else None
        if route not in GROUPS or set(g) != {'route', 'all'} or not isinstance(g['all'], list):
            errs.append(f'bad results group {route!r}')
            continue
        if route in seen:
            errs.append(f'group {route} repeated')
        seen.add(route)
        errs += _validate_tests(g['all'], GROUP_TESTS[route], route, allow_empty=True)
    return errs


def _validate_tests(tests, allowed, where, allow_empty=False):
    errs, seen = [], set()
    if not tests and not allow_empty:
        return [f'{where} has no tests']
    for t in tests:
        kind = t.get('test') if isinstance(t, dict) else None
        if kind not in allowed:
            errs.append(f'{where}: unknown test {kind!r}')
            continue
        key = (kind, t.get('grade_or_better'))
        if key in seen:
            errs.append(f'{where}: {kind} repeated')
        seen.add(key)
        if kind == 'grade_count':
            n = t.get('at_least')
            if (set(t) != {'test', 'at_least', 'grade_or_better'} or t.get('grade_or_better') not in GRADES
                    or not isinstance(n, int) or isinstance(n, bool) or n < 1):
                errs.append(f'{where}: grade_count needs at_least >= 1 and a grade A+ to C')
        else:
            field = 'rm' if kind in INCOME_TESTS else 'value'
            v = t.get(field)
            if set(t) != {'test', field} or not _num(v) or v < 0:
                errs.append(f'{where}: {kind} needs a number {field} >= 0')
    return errs


# ── Results ─────────────────────────────────────────────────────────────────────────────────

def _held(profile):
    """The results the student HOLDS, as `_academic_ok` reads them ('spm' when nothing)."""
    return (courses_public.results_held(profile) or 'spm') if profile else 'spm'


def _post_spm_group(profile, held, tests, cgpa_of):
    """A FINAL post-SPM result (STPM, Matriculation, Asasi or Diploma - `results_held`, so a
    student still studying reads 'spm' and fails) meeting every test. No tests = any such result."""
    floor = next((t['value'] for t in tests if t['test'] == 'min_pngk'), None)
    if not courses_public.is_tertiary(held):
        return False, 'no post-SPM results' + (f' (PNGK floor {floor:g})' if floor is not None else '')
    failures = []
    for t in tests:
        if t['test'] == 'min_pngk':
            ok, why = _cgpa_test(profile, held, t['value'], cgpa_of)
        else:
            m = courses_public.merit_100(profile)
            ok = m is not None and m >= t['value']
            why = (f'post-SPM merit not available (need {t["value"]})' if m is None
                   else f'post-SPM merit {m} below {t["value"]}')
        if not ok:
            failures.append(why)
    return (not failures), '; '.join(failures)


def _cgpa_test(profile, held, floor, cgpa_of):
    """`shortlisting._academic_ok`'s STPM and third-route branches, verbatim in effect."""
    if held == 'stpm':
        p = cgpa_of(profile)
        if p is None:
            return False, 'STPM PNGK not provided'
        if p >= floor:
            return True, ''
        return False, f'PNGK {p} below {floor}'
    label = courses_public.QUALIFICATION_LABELS[held]
    raw = getattr(profile, 'higher_cgpa', None)
    if raw is None:
        return False, f'{label} CGPA not provided'
    overall = courses_public.third_route_overall(held, raw, getattr(profile, 'higher_koko', None))
    if overall is None:
        if held != 'diploma' and getattr(profile, 'higher_koko', None) is None:
            return False, f'{label} co-curriculum score not provided'
        return False, f'{label} CGPA not readable ({raw})'
    if overall >= floor:
        return True, ''
    return False, f'{label} CGPA {overall:.2f} below {floor:.2f}'


def _spm_group(profile, held, tests):
    """The SPM group on `spm_grades_for` (a post-SPM holder's SPM block only). A post-SPM holder
    may pass here too (owner, 2026-11-25: 'any' is a real any) on the GRADE tests only - the UPU
    merit stays SPM holders only (D3). No tests = passes."""
    grades = courses_public.spm_grades_for(profile)
    spm_held = not courses_public.is_tertiary(held)
    grade_tests = [t for t in tests if t['test'] == 'grade_count']
    if not spm_held and not grades and grade_tests:
        return False, 'SPM grades not provided'
    a_rule = next((t['at_least'] for t in grade_tests if t['grade_or_better'] == 'A-'), None)
    failures = []
    for t in tests:
        if t['test'] == 'grade_count':
            g, n = t['grade_or_better'], t['at_least']
            have = at_or_better(grades, g)
            if have < n:
                failures.append(_grade_reason(have, g, n, a_rule))
        elif spm_held:
            m, v = spm_merit(profile), t['value']
            if m is None:
                failures.append(f'merit point not available (need {v})')
            elif m < v:
                failures.append(f'merit point {m} below {v}')
    return (not failures), '; '.join(failures)


def _grade_reason(have, grade, n, a_rule):
    """Today's wording for A-, B+ and C (`shortlisting._spm_bars`); the same pattern otherwise."""
    if grade == 'A-':
        return f'{have} at A- (need {n})'
    if grade == 'B+':
        # The B+ count is a TOTAL; stated the way it is set when an A- rule sits beside it.
        extra = n - (a_rule or 0)
        need = f'{a_rule} at A- plus {extra} more at B+' if a_rule is not None and extra > 0 else f'{n} at B+ or better'
        return f'{have} at B+ or better (need {need})'
    return f'{have} at {grade} or better (need {n})'


def results_ok(profile, section, cgpa_of=courses_public.stpm_cgpa_of):
    """``(ok, reason)`` for the results section. ``section`` None = not checked (passes).

    'any' fails with the reason of the student's OWN group (post-SPM for a post-SPM holder, else
    SPM) when it is present, else of the group that is; 'all' joins every failing group's reason.
    A post-SPM holder failing the SPM group with no post-SPM group present reads
    'SPM-only intake: ...' (D16c's wording)."""
    if not section:
        return True, ''
    mode, groups = _mode(section)
    held = _held(profile)
    out = {}
    for g in groups:
        if g['route'] == 'post_spm':
            out['post_spm'] = _post_spm_group(profile, held, g['all'], cgpa_of)
        else:
            ok, why = _spm_group(profile, held, g['all'])
            if not ok and courses_public.is_tertiary(held) and not any(x['route'] == 'post_spm' for x in groups):
                why = 'SPM-only intake: ' + why
            out['spm'] = (ok, why)
    if not out:
        return True, ''
    if mode == 'all':
        bad = [why for ok, why in out.values() if not ok]
        return (not bad), '; '.join(bad)
    if any(ok for ok, _ in out.values()):
        return True, ''
    own = 'post_spm' if courses_public.is_tertiary(held) else 'spm'
    return False, out[own][1] if own in out else next(iter(out.values()))[1]


# ── Income ──────────────────────────────────────────────────────────────────────────────────

def income_ok(profile, section):
    """``(ok, bucket, reason)`` for the income section; `shortlisting._income_ok` for every legacy
    shape (mode 'any'). STR declared passes first, bucket 'A', in either mode. ``section`` None =
    not checked, bucket ''."""
    if not section:
        return True, '', 'no financial requirement set for this programme'
    mode, tests = _mode(section)
    by = {t['test']: t['rm'] for t in tests}
    ceiling, pc_ceiling = by.get('household_income_max'), by.get('income_per_person_under')
    if profile and getattr(profile, 'receives_str', False):
        return True, 'A', 'STR recipient'
    inc = getattr(profile, 'household_income', None) if profile else None
    if not inc:
        return False, '', 'no STR and household income not provided'
    size = getattr(profile, 'household_size', None) if profile else None
    if mode == 'all' and ceiling is not None and pc_ceiling is not None:
        if inc > ceiling:
            return False, '', f'income RM{inc:.0f} > RM{ceiling}'
        if not size or size <= 0:
            return False, '', f'income RM{inc:.0f} <= RM{ceiling} but household size not provided'
        per_capita = inc / size
        if per_capita >= pc_ceiling:
            return False, '', f'income RM{inc:.0f} <= RM{ceiling} but per-capita RM{per_capita:.0f} >= RM{pc_ceiling}'
        return True, 'B', (f'household income RM{inc:.0f} <= RM{ceiling} and per-capita '
                           f'RM{per_capita:.0f} < RM{pc_ceiling}')
    # 'any' (and a single test, where 'any' and 'all' agree): today's rule, wording and all.
    if ceiling is not None and inc <= ceiling:
        return True, 'B', f'household income RM{inc:.0f} <= RM{ceiling} (B40)'
    if pc_ceiling is None:
        return False, '', f'income RM{inc:.0f} > RM{ceiling}'
    if not size or size <= 0:
        return False, '', f'income RM{inc:.0f} > RM{ceiling} and household size not provided'
    per_capita = inc / size
    if per_capita < pc_ceiling:
        return True, 'B', (f'income RM{inc:.0f} above B40 ceiling but per-capita '
                           f'RM{per_capita:.0f} < RM{pc_ceiling}')
    return False, '', f'income RM{inc:.0f} > RM{ceiling} and per-capita RM{per_capita:.0f} >= RM{pc_ceiling}'


# ── The whole tree ──────────────────────────────────────────────────────────────────────────

def section(tree, name):
    """The section node called ``name``, or None (absent = not checked)."""
    return next((s for s in (tree or {}).get('all', []) if s.get('section') == name), None)


def birth_states(tree):
    """The born-in state keys ([] = not checked, `birth_state.check`'s 'off')."""
    s = section(tree, 'born_in')
    return list(s['any']) if s else []


def start_years(tree):
    """The course-start years of the flag ([] = no flag)."""
    f = next((f for f in (tree or {}).get('flag', []) if f.get('test') == 'course_start_year'), None)
    return _start_year.stored_years(f['allowed']) if f else []


def start_year_flag(application, tree):
    """`start_year.reading` on the tree: None when no years are set, else
    ``{state, start_year, years}``. A flag for a person, never a decline."""
    years = start_years(tree)
    if not years:
        return None
    year = _start_year.possible_start_years(application).year
    state = _start_year.decide(year, years)
    return {'state': state, 'start_year': str(year) if state != 'unknown' else None, 'years': years}


def evaluate(application, tree, cgpa_of=courses_public.stpm_cgpa_of):
    """`shortlisting.evaluate` with the intake's rules read from ``tree``: same gates, same order,
    same verdicts, buckets, reasons and categories for every legacy tree."""
    profile = getattr(application, 'profile', None)
    if not application.consent_to_contact:
        return ShortlistResult('rejected', '', 'no consent to contact', 'ineligible')
    if not application.intends_tertiary_2026:
        return ShortlistResult('rejected', '', 'not intending tertiary study this year', 'ineligible')
    if application.upu_status == 'ipts':
        return ShortlistResult('rejected', '', 'IPTS-only — outside programme scope', 'ineligible')
    ok, why = check_birth_state(getattr(profile, 'nric', '') if profile else '', birth_states(tree))
    if not ok:
        return ShortlistResult('rejected', '', why, 'ineligible')
    if profile is not None and courses_public.results_held(profile) == 'diploma' and not courses_public.diploma_is_public(profile):
        stated = (getattr(profile, 'higher_institution_type', '') or '').strip().lower()
        why = ('Diploma from a private college: only diplomas from public institutions count '
               'for this programme') if stated == 'private' else (
              'Diploma institution not stated: only diplomas from public institutions count '
              'for this programme')
        return ShortlistResult('rejected', '', why, 'ineligible')
    ok, why = results_ok(profile, section(tree, 'results'), cgpa_of)
    if not ok:
        return ShortlistResult('rejected', '', f'academic floor: {why}', 'merit')
    ok, bucket, why = income_ok(profile, section(tree, 'income'))
    if not ok:
        return ShortlistResult('rejected', '', f'income: {why}', 'need')
    return ShortlistResult('shortlisted', bucket, why)


# ── From today's columns ────────────────────────────────────────────────────────────────────

def _rule(v):
    """A count / merit column: NULL or 0 = no rule."""
    return None if v is None or v == 0 else v


def from_legacy(cohort):
    """The tree that today's cohort columns mean. Results are joined by 'any' (owner ruling
    2026-11-25), so a post-SPM holder below the PNGK floor who meets the SPM group now passes.

    * ``min_stpm_pngk`` set (0 included) -> a post-SPM group with min_pngk; NULL -> no post-SPM
      group (D16c: the intake is SPM-only and a post-SPM holder is tested on the SPM GRADE bars).
    * A-, B+ (a TOTAL), credit (C) counts -> grade_count rules; ``min_merit_score`` ->
      min_upu_merit (SPM holders only, D3). NULL or 0 = no rule.
    * The SPM group is present whenever the results section is - with no tests it passes any
      student, which is what a blank SPM bar does today. No academic value at all -> no section.
    * income_ceiling / per_capita_ceiling -> income, 'any' (today's rescue rule); neither -> none.
    * allowed_birth_states -> born_in; allowed_start_years -> the flag. Empty -> none.
    The degree-intake exception lives in `tree_for_migration`, not here."""
    def g(name):
        return getattr(cohort, name, None)

    spm =[{'test': 'grade_count', 'at_least': int(v), 'grade_or_better': grade}
           for v, grade in ((_rule(g('min_spm_a_count')), 'A-'), (_rule(g('min_spm_bplus_count')), 'B+'),
                            (_rule(g('min_spm_credit_count')), 'C')) if v is not None]
    if _rule(g('min_merit_score')) is not None:
        spm.append({'test': 'min_upu_merit', 'value': g('min_merit_score')})
    pngk = g('min_stpm_pngk')
    sections = []
    if pngk is not None or spm:
        groups = [{'route': 'post_spm', 'all': [{'test': 'min_pngk', 'value': pngk}]}] if pngk is not None else []
        groups.append({'route': 'spm', 'all': spm})
        sections.append({'section': 'results', 'any': groups})
    income = [{'test': t, 'rm': g(col)} for t, col in (('household_income_max', 'income_ceiling'),
                                                       ('income_per_person_under', 'per_capita_ceiling'))
              if g(col) is not None]
    if income:
        sections.append({'section': 'income', 'any': income})
    states = list(g('allowed_birth_states') or [])
    if states:
        sections.append({'section': 'born_in', 'any': states})
    tree = {'all': sections}
    years = _start_year.stored_years(g('allowed_start_years'))
    if years:
        tree['flag'] = [{'test': 'course_start_year', 'allowed': years}]
    return tree


def without_spm_group(tree):
    """A copy of ``tree`` with the SPM results group switched OFF (the "CGPA trap": SPM-only
    students are not eligible). Refuses to leave a results section with no group."""
    out = {'all': [dict(s) for s in tree.get('all', [])], **({'flag': tree['flag']} if 'flag' in tree else {})}
    for s in out['all']:
        if s['section'] == 'results':
            mode, groups = _mode(s)
            kept = [x for x in groups if x['route'] != 'spm']
            if not kept:
                raise ValueError('switching the SPM group off would leave no results group')
            s[mode] = kept
    return out


def tree_for_migration(cohort):
    """What Sprint 2's data migration will store: `from_legacy`, plus the owner's one named
    exception - the degree intake (``SPM_OFF_AT_MIGRATION``) loses its SPM group."""
    tree = from_legacy(cohort)
    if getattr(cohort, 'code', None) in SPM_OFF_AT_MIGRATION:
        tree = without_spm_group(tree)
    return tree
