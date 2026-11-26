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
        {'section': 'born_in', 'any': ['sabah', 'wp_labuan']}],
     'flag': [{'test': 'course_start_year', 'allowed': [2025, 2026]}]}

A section that is absent is not checked; a group that is absent is switched off. Everything
outside the tree (consent, intent, IPTS, the D5 public-diploma gate) is unchanged and keeps its
order: consent, intent, IPTS, born in, D5, results, income - exactly `shortlisting.evaluate`'s.

⚠ Reasons and categories are byte-identical to `shortlisting.evaluate` for every legacy shape
(`from_legacy`), outside the two owner-ruled differences (decisions.md 2026-11-25), because a reviewer and the decline email read them. The formatting therefore
keeps today's quirks on purpose ("3 at A- (need 4)" has no "or better"; "RMNone" when only the
per-person ceiling is set). Sprint 2 removes the duplication by making `shortlisting` call this.
"""
from apps.courses import public as courses_public

from . import start_year as _start_year
from .birth_state import STATE_KEYS, stored_keys
from .birth_state import check as check_birth_state
from .shortlisting import ShortlistResult, _count, spm_merit

#: SPM grades, best first. "N at G or better" counts every grade up to and including G. SPM has
#: no C- (`shortlisting.CREDIT_GRADES`); D, E, G and anything unknown never count.
GRADES = ('A+', 'A', 'A-', 'B+', 'B', 'C+', 'C')
MODES = ('any', 'all')
#: The results section also takes 'own' (owner ruling B, 2026-11-26): each student is judged on the
#: group for the results they HOLD - a post-SPM holder on the post-SPM group (the SPM group is no
#: alternative door for them), an SPM holder on the SPM group. Today's gate, exactly; every migrated
#: tree uses it. A post-SPM holder with no post-SPM group falls to the SPM group's grade rules
#: (D16c, 'SPM-only intake: ...'); an SPM holder with no SPM group fails on the post-SPM group.
RESULTS_MODES = ('own',) + MODES
SECTIONS = ('results', 'merit', 'income', 'born_in')
GROUPS = ('post_spm', 'spm')
GROUP_TESTS = {'post_spm': ('min_pngk',), 'spm': ('grade_count',)}
#: Merit is its OWN section, ANDed with results and applied to every student (owner ruling 4,
#: 2026-11-26: "merit is not a subset of SPM"): ``min_upu_merit`` binds SPM holders (the UPU merit,
#: `shortlisting.spm_merit`), ``min_merit`` binds post-SPM holders (the merit from the PNGK / CGPA,
#: `merit_100`). A test that is absent is not checked for that kind of student, which is how today's
#: ``min_merit_score`` (SPM applicants only, D3) migrates without changing anyone's answer.
MERIT_TESTS = ('min_upu_merit', 'min_merit')
INCOME_TESTS = ('household_income_max', 'income_per_person_under')
FLAG_TESTS = ('course_start_year',)



def at_or_better(grades, grade):
    """How many SPM subjects in ``grades`` are at ``grade`` or better (A+ best, C worst)."""
    return _count(grades, set(GRADES[:GRADES.index(grade) + 1]))


def _mode(node):
    """``(mode, items)`` of a node holding exactly one of 'own' / 'any' / 'all'."""
    for m in RESULTS_MODES:
        if m in node:
            return m, node[m]
    return None, None


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ── Validation ──────────────────────────────────────────────────────────────────────────────

def validate_tree(tree):
    """Every problem with ``tree`` as a list of short strings; ``[]`` means it is valid.

    Refuses rather than repairs (request #30's lesson): an unknown key, a repeated section or
    test, an empty group list, a negative or non-numeric value are each an error."""
    errs = []
    if not isinstance(tree, dict) or set(tree) - {'all', 'flag'} or not isinstance(tree.get('all', []), list):
        return ['tree must be {all: [...], flag: [...]}']
    seen = set()
    merit = section(tree, 'merit')
    merit_tests = merit.get('all') if isinstance(merit, dict) and isinstance(merit.get('all'), list) else []
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
        if mode == 'own' and name != 'results':
            errs.append(f'section {name}: "own" is for results only')
            continue
        if name == 'born_in':
            if mode != 'any' or any(s not in STATE_KEYS for s in items) or len(set(items)) != len(items):
                errs.append('born_in must be any: [distinct state keys]')
        elif name == 'results':
            errs += _validate_groups(items, mode, merit_tests)
        elif name == 'merit':
            if mode != 'all':
                errs.append('merit must be all: [tests]')
            else:
                errs += _validate_tests(items, MERIT_TESTS, 'merit')
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


def spm_can_fail(tests, merit_tests=()):
    """True when an SPM group holds a grade count above 0, or ``merit_tests`` (the merit section's
    tests - pass them only where that section binds the same students) a UPU merit above 0.
    A 0 count or a 0 merit only asks that SPM grades be given."""
    return any((t.get('test') == 'grade_count' and _num(t.get('at_least')) and t['at_least'] > 0)
               or (t.get('test') == 'min_upu_merit' and _num(t.get('value')) and t['value'] > 0)
               for t in list(tests) + list(merit_tests) if isinstance(t, dict))


#: Owner ruling 2026-11-25 (review round 2, c): a void SPM door beside a PNGK floor is refused.
VOID_SPM_DOOR = ('results: an SPM group with no rule that can fail, beside a post-SPM group under "any", '
                 'would let every SPM holder through - add a rule to the SPM group or switch it off')


#: The same trap under 'own' (#921, the CGPA trap left on): an SPM group that cannot fail beside a
#: post-SPM group, with no UPU merit above 0 either, passes every SPM holder.
VOID_SPM_GROUP = ('results: an SPM group with no rule that can fail, beside a post-SPM group, lets every '
                  'SPM holder through - add a rule to the SPM group or switch it off')


def _validate_groups(groups, mode='any', merit_tests=()):
    errs, seen = [], set()
    by_route = {g.get('route'): g for g in groups if isinstance(g, dict)}
    spm_tests = by_route.get('spm', {}).get('all')
    if 'post_spm' in by_route and isinstance(spm_tests, list):
        # Under 'any' the SPM group is a door for post-SPM holders too, and the merit section's UPU
        # merit does not bind them there, so only a grade count guards it.
        if mode == 'any' and not spm_can_fail(spm_tests):
            errs.append(VOID_SPM_DOOR)
        elif mode == 'own' and not spm_can_fail(spm_tests, merit_tests):
            errs.append(VOID_SPM_GROUP)
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
                    or not isinstance(n, int) or isinstance(n, bool) or n < 0):
                # 0 is allowed: today's "0 set" bar, which only asks that SPM grades be given
                errs.append(f'{where}: grade_count needs at_least >= 0 and a grade A+ to C')
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
        ok, why = _cgpa_test(profile, held, t['value'], cgpa_of)
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
    """The SPM group's grade rules on `spm_grades_for` (a post-SPM holder's SPM block only). No
    tests = passes. The UPU merit is not here: it is the merit section's (Sprint 2, owner ruling 4)
    and binds SPM holders only, so a post-SPM holder tested here (D16c's SPM-only intake, or the
    'any' door) faces the grade rules alone - today's D3 meaning, unchanged."""
    grades = courses_public.spm_grades_for(profile)
    if courses_public.is_tertiary(held) and not grades and tests:
        return False, 'SPM grades not provided'
    a_rule = next((t['at_least'] for t in tests if t['grade_or_better'] == 'A-'), None)
    failures = []
    for t in tests:
        g, n = t['grade_or_better'], t['at_least']
        have = at_or_better(grades, g)
        if have < n:
            failures.append(_grade_reason(have, g, n, a_rule))
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

    'own' judges the student on their OWN group only (`RESULTS_MODES`). 'any' fails with the reason
    of the student's own group when it is present, else of the group that is; 'all' joins every
    failing group's reason. A post-SPM holder failing the SPM group with no post-SPM group present
    reads 'SPM-only intake: ...' (D16c's wording)."""
    if not section:
        return True, ''
    mode, groups = _mode(section)
    held = _held(profile)
    tertiary = courses_public.is_tertiary(held)
    by_route = {g['route']: g['all'] for g in groups}
    has_floor = 'post_spm' in by_route
    if mode == 'own':
        own = 'post_spm' if (tertiary and has_floor) or 'spm' not in by_route else 'spm'
        by_route = {own: by_route[own]}
    out = {}
    for route, tests in by_route.items():
        if route == 'post_spm':
            out['post_spm'] = _post_spm_group(profile, held, tests, cgpa_of)
        else:
            ok, why = _spm_group(profile, held, tests)
            if not ok and tertiary and not has_floor:
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


def merit_ok(profile, section):
    """``(ok, reason)`` for the merit section (`MERIT_TESTS`): each test binds its own kind of
    student only. ``section`` None = not checked (passes). Today's wording for the UPU merit."""
    if not section:
        return True, ''
    tertiary = courses_public.is_tertiary(_held(profile))
    failures = []
    for t in section['all']:
        v = t['value']
        if t['test'] == 'min_upu_merit' and not tertiary:
            m = spm_merit(profile)
            if m is None:
                failures.append(f'merit point not available (need {v})')
            elif m < v:
                failures.append(f'merit point {m} below {v}')
        elif t['test'] == 'min_merit' and tertiary:
            m = courses_public.merit_100(profile)
            if m is None:
                failures.append(f'post-SPM merit not available (need {v})')
            elif m < v:
                failures.append(f'post-SPM merit {m} below {v}')
    return (not failures), '; '.join(failures)


def academic_ok(profile, tree, cgpa_of=courses_public.stpm_cgpa_of):
    """``(ok, reason)``: the results section AND the merit section - today's one 'academic floor'
    step, the reasons joined in today's order (grade rules first, then the merit)."""
    ok, why = results_ok(profile, section(tree, 'results'), cgpa_of)
    mok, mwhy = merit_ok(profile, section(tree, 'merit'))
    if ok and mok:
        return True, ''
    return False, '; '.join(w for w in ((why if not ok else ''), (mwhy if not mok else '')) if w)


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
    return next((s for s in (tree or {}).get('all', []) if isinstance(s, dict) and s.get('section') == name), None)


def birth_states(tree):
    """The born-in state keys ([] = not checked, `birth_state.check`'s 'off')."""
    s = section(tree, 'born_in')
    return list(s['any']) if s else []


def _year_flag(tree):
    return next((f for f in (tree or {}).get('flag', []) if f.get('test') == 'course_start_year'), None)


def start_years(tree):
    """The course-start years of the flag ([] = no flag)."""
    f = _year_flag(tree)
    return _start_year.stored_years(f['allowed']) if f else []


def start_year_flag(application, tree):
    """`start_year.reading` on the tree: None when there is no flag, else
    ``{state, start_year, years}``. A flag for a person, never a decline. A flag whose stored
    years are all junk stays ON with no years (`start_year.rule_on`), read exactly as `reading` reads it."""
    if _year_flag(tree) is None:
        return None
    years = start_years(tree)
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
    ok, why = academic_ok(profile, tree, cgpa_of)
    if not ok:
        return ShortlistResult('rejected', '', f'academic floor: {why}', 'merit')
    ok, bucket, why = income_ok(profile, section(tree, 'income'))
    if not ok:
        return ShortlistResult('rejected', '', f'income: {why}', 'need')
    return ShortlistResult('shortlisted', bucket, why)


# ── From today's columns ────────────────────────────────────────────────────────────────────

def has_spm_bar(cohort):
    """True when the intake sets an SPM bar that can fail a student who gave SPM grades: a grade
    count or the UPU merit above 0 (owner ruling 2026-11-25, b). A bar stored as 0 only asks that
    SPM grades be given, so it does not count. The same test as `spm_can_fail` on the tree."""
    return any((getattr(cohort, name, None) or 0) > 0 for name in (
        'min_spm_a_count', 'min_spm_bplus_count', 'min_spm_credit_count', 'min_merit_score'))


def from_legacy(cohort, keep_empty_spm=False):
    """The tree that today's cohort columns mean. Results are joined by 'own' (owner ruling B,
    2026-11-26, superseding 25 Nov's 'any'): a post-SPM holder is judged on the PNGK / CGPA floor
    only, never through the SPM group. ``min_merit_score`` becomes the merit section's
    ``min_upu_merit`` (SPM holders only, D3; owner ruling 4: merit is its own section).

    * ``min_stpm_pngk`` set (0 included) -> a post-SPM group with min_pngk; NULL -> no post-SPM
      group (D16c: the intake is SPM-only and a post-SPM holder is tested on the SPM GRADE bars).
    * A-, B+ (a TOTAL), credit (C) counts -> the SPM group's grade_count rules; ``min_merit_score``
      -> the merit section's min_upu_merit (SPM holders only, D3). NULL = no rule. A 0 is KEPT as
      a rule, exactly as today: it never fails a count, but a post-SPM holder on a blank-floor
      intake with no SPM grades fails "SPM grades not provided", an SPM holder with no merit fails
      a merit 0, and the B+ wording reads "0 at A- plus N more at B+".
    * THE CGPA TRAP, BY SHAPE (owner ruling 2026-11-25: the trap = SPM group OFF): a PNGK floor
      with no SPM bar (`has_spm_bar` false) has NO SPM group, so SPM-only students do not qualify.
      Today such an intake passes them (#921); intake 5 (bpb-deg-dip-2026) is the one live case.
      So `validate_tree(from_legacy(c))` never meets `VOID_SPM_DOOR`. ``keep_empty_spm=True`` keeps the
      group (the replay's ``--plain`` view) for COMPARISON ONLY: that tree is the trap left on, and
      `validate_tree` refuses it.
    * Otherwise the SPM group is present whenever the results section is. No academic value at
      all -> no section.
    * income_ceiling / per_capita_ceiling -> income, 'any' (today's rescue rule); neither -> none.
    * allowed_birth_states (`birth_state.stored_keys`) -> born_in; allowed_start_years
      (`start_year.rule_on` / `stored_years`) -> the flag. Empty -> none.

    ⚠ THE STORED TREE IS THE SOURCE OF TRUTH from Sprint 2. Only three callers build from the
    columns: migration 0219 (`build_trees`), the NULL fallback (`tree_of`), and the OLD admin
    form's save (`views_admin.intake_years`), which is still the only editor and can only express
    what the columns express. Once the criteria editor can store a tree the columns cannot say
    (an 'any' / 'all' choice, a merit for post-SPM holders), that form must stop rebuilding it -
    otherwise a save would undo the choice."""
    def g(name):
        return getattr(cohort, name, None)

    spm = [{'test': 'grade_count', 'at_least': int(v), 'grade_or_better': grade}
           for v, grade in ((g('min_spm_a_count'), 'A-'), (g('min_spm_bplus_count'), 'B+'),
                            (g('min_spm_credit_count'), 'C')) if v is not None]
    merit = g('min_merit_score')
    pngk = g('min_stpm_pngk')
    sections = []
    if pngk is not None or spm or merit is not None:
        groups = [{'route': 'post_spm', 'all': [{'test': 'min_pngk', 'value': pngk}]}] if pngk is not None else []
        if pngk is None or has_spm_bar(cohort) or keep_empty_spm:
            groups.append({'route': 'spm', 'all': spm})
        sections.append({'section': 'results', 'own': groups})
    if merit is not None:
        sections.append({'section': 'merit', 'all': [{'test': 'min_upu_merit', 'value': merit}]})
    income = [{'test': t, 'rm': g(col)} for t, col in (('household_income_max', 'income_ceiling'),
                                                       ('income_per_person_under', 'per_capita_ceiling'))
              if g(col) is not None]
    if income:
        sections.append({'section': 'income', 'any': income})
    states = stored_keys(g('allowed_birth_states'))
    if states:
        sections.append({'section': 'born_in', 'any': states})
    tree = {'all': sections}
    if _start_year.rule_on(g('allowed_start_years')):
        tree['flag'] = [{'test': 'course_start_year', 'allowed': _start_year.stored_years(g('allowed_start_years'))}]
    return tree


#: Sprint 2's data migration stores exactly `from_legacy` (the CGPA trap is decided by shape).
tree_for_migration = from_legacy


def tree_of(cohort):
    """The intake's rules as the gate reads them (Sprint 2): the STORED tree, else - ``criteria``
    still NULL (a row the image before Sprint 2 created between migrate and deploy, or one not yet
    built) - `from_legacy` of its columns, the same tree a build would store. ``{'all': []}`` is a
    stored "nothing checked" and is never replaced."""
    stored = getattr(cohort, 'criteria', None)
    # A dict only: a stub or a test double (a Mock answers every attribute) is read from its columns.
    return stored if isinstance(stored, dict) else from_legacy(cohort)


def build_trees(cohorts, save):
    """Sprint 2's fill: ``from_legacy`` for every intake whose ``criteria`` is NULL, refused whole
    (ValueError naming ids and codes, nothing written) when any tree fails `validate_tree`.
    ``save(cohort, tree)`` writes one row. Returns ``[(id, code)]`` filled. Used by migration
    0219 and by the ``build_criteria_trees`` command (the old admin form rebuilds its own row with
    `from_legacy` on every save - `views_admin.intake_years`)."""
    todo = [c for c in cohorts if getattr(c, 'criteria', None) is None]
    bad = refused_trees(todo)
    if bad:
        raise ValueError('criteria trees refused: ' + '; '.join(f'{i} {code}: {errs}' for i, code, errs in bad))
    for c in todo:
        save(c, from_legacy(c))
    return [(c.id, c.code) for c in todo]


def refused_trees(cohorts):
    """``[(id, code, [problems])]`` for every intake whose `from_legacy` tree `validate_tree` refuses -
    a stored birth state that is not a known key (a wrong case such as 'Sabah'), a start-year
    list of junk only. Sprint 2's migration must stop on these rather than store them. Ids, codes
    and the generic problem texts only."""
    out = []
    for c in cohorts:
        errs = validate_tree(from_legacy(c))
        if errs:
            out.append((getattr(c, 'id', None), getattr(c, 'code', ''), errs))
    return out
