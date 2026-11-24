"""READ-ONLY: today's gate (`shortlisting.evaluate`) against the criteria tree, per intake.

Criteria editor Sprint 1 (2026-11-25). For every application with an intake, both engines judge
the same live profile; the tree is `criteria.from_legacy(cohort)` - what Sprint 2 will store.
`--plain` keeps an SPM group with no bar beside a PNGK floor (the CGPA trap left ON), to show
that shape's comparison without the owner's ruling. Prints, per intake, how many agree and the
differences grouped into classes, each split into PENDING (submitted, decision not released:
what `rescore_pending_decisions` can still change) and DECIDED, with a count per status. The
owner's rulings allow exactly these:

  a1_post_spm_below_floor_passes_spm   a post-SPM holder whose CGPA is BELOW the floor and who
                                       meets the SPM group, which holds a rule that can fail,
                                       on today's own SPM test (merit included) - old reject, new pass
  a2_post_spm_cgpa_missing_passes_spm  the same, but the CGPA is missing / unreadable / a
                                       matric or asasi with no co-curriculum score
  b_spm_only_spm_group_off             an SPM-only student on an intake whose SPM group is OFF
                                       (a floor with no SPM bar: the degree intake) - old pass, new reject
  b2_spm_only_still_refused_new_reason the same intake shape, but today ALREADY refuses the student
                                       on the SPM bars (a bar stored as 0 with no SPM grades or no
                                       merit); still refused for merit, the reason now names the
                                       missing post-SPM result. No live intake has this shape.

Anything else is `unexpected` (or `reason_only` when only the wording moved) and is a bug in
the engine until shown otherwise. A pass through an SPM group with no rule able to fail is NEVER
expected (owner, review round 2): it lands in `unexpected`. The course-start flag is compared too
(`start_year.reading` against the tree's flag); a differing flag needs a look. Every intake's
`from_legacy` tree is also put through `criteria.validate` (`criteria.refused_trees`); a refused
tree (a wrong-case birth state, junk-only start years) is listed by id and code and needs a look.

⚠ PRIVACY: prints intake ids / codes, statuses, counts and application ids ONLY - never a name,
NRIC, phone, email, grade or income figure.

⚠ WRITES NOTHING: the whole run sits in one transaction that is marked READ ONLY on PostgreSQL
(transaction-scoped, never session-level - safe through the pooler) and is rolled back at the end.

    python manage.py replay_criteria                 # every application
    python manage.py replay_criteria --cohort CODE   # one intake (repeatable; unknown code = error)
    python manage.py replay_criteria --plain         # SPM group kept for the CGPA-trap shape
"""
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.courses import public as courses_public
from apps.scholarship import criteria, shortlisting, start_year
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

CLASS_A1 = 'a1_post_spm_below_floor_passes_spm'
CLASS_A2 = 'a2_post_spm_cgpa_missing_passes_spm'
CLASS_B = 'b_spm_only_spm_group_off'
CLASS_B2 = 'b2_spm_only_still_refused_new_reason'
REASON_ONLY = 'reason_only'
UNEXPECTED = 'unexpected'
EXPECTED = {'same', CLASS_A1, CLASS_A2, CLASS_B, CLASS_B2}
FLAG_DIFFERS = 'start_year_flag_differs'


def _groups(tree):
    sec = criteria.section(tree, 'results')
    if not sec:
        return {}
    _, groups = criteria._mode(sec)
    return {g['route']: g['all'] for g in groups}


def classify(application, cohort, old, new, tree):
    """'same', or the difference class of one application (see the module docstring). Class (a)
    needs (1) a new SPM group holding at least one rule that can fail (`criteria.spm_can_fail`) -
    an automatic pass is never expected - and (2) a pass on the OLD gate's own SPM test,
    `shortlisting._spm_bars` with the merit ON (``spm_held=True``), because beside a floor the new
    engine applies the UPU merit to a post-SPM holder too. Confirmed on the old gate, never on the
    new engine, so the two engines do not vouch for each other."""
    if (old.verdict, old.bucket, old.reason, old.category) == (new.verdict, new.bucket, new.reason, new.category):
        return 'same'
    profile = getattr(application, 'profile', None)
    tertiary = courses_public.is_tertiary(criteria._held(profile))
    groups = _groups(tree)
    floor_set = getattr(cohort, 'min_stpm_pngk', None) is not None
    if (tertiary and floor_set and old.category == 'merit' and new.category != 'merit'
            and 'post_spm' in groups and 'spm' in groups and criteria.spm_can_fail(groups['spm'])
            and shortlisting._spm_bars(profile, cohort, courses_public.spm_grades_for(profile), spm_held=True)[0]):
        return CLASS_A1 if ' below ' in old.reason else CLASS_A2
    if (not tertiary and floor_set and 'spm' not in groups and 'post_spm' in groups
            and new.category == 'merit' and new.reason.startswith('academic floor: no post-SPM results')):
        if old.category != 'merit':
            return CLASS_B
        if old.verdict == 'rejected' and old.reason.startswith('academic floor: '):
            return CLASS_B2
    if (old.verdict, old.category) == (new.verdict, new.category):
        return REASON_ONLY
    return UNEXPECTED


def _pending(app):
    return app.status == 'submitted' and app.decision_released_at is None


def replay(cohort_codes=None, plain=False):
    """``{cohort_id: {'code', 'total', 'classes': Counter, 'flags': Counter, 'refused': [problems],
    'ids': {class: {'pending'|'decided': [ids]}}, 'statuses': {class: Counter}}}``. Pure reads.
    ``refused`` is `validate(from_legacy(cohort))` - the tree Sprint 2 would store, whatever
    ``plain`` says. An unknown intake code raises CommandError."""
    cohorts = ScholarshipCohort.objects.all().order_by('id')
    if cohort_codes:
        cohorts = cohorts.filter(code__in=cohort_codes)
        missing = sorted(set(cohort_codes) - set(cohorts.values_list('code', flat=True)))
        if missing:
            raise CommandError(f'unknown intake code(s): {", ".join(missing)}')
    out = {}
    for cohort in cohorts:
        tree = criteria.from_legacy(cohort, keep_empty_spm=plain)
        row = {'code': cohort.code, 'total': 0, 'classes': Counter(), 'flags': Counter(),
               'refused': criteria.validate(criteria.from_legacy(cohort)),
               'ids': defaultdict(lambda: {'pending': [], 'decided': []}), 'statuses': defaultdict(Counter)}
        apps = (ScholarshipApplication.objects.filter(cohort=cohort)
                .select_related('profile', 'cohort').order_by('id'))
        for app in apps:
            cls = classify(app, cohort, shortlisting.evaluate(app, cohort), criteria.evaluate(app, tree), tree)
            row['total'] += 1
            row['classes'][cls] += 1
            marks = [cls] if cls != 'same' else []
            if start_year.reading(app) != criteria.start_year_flag(app, tree):
                row['flags'][FLAG_DIFFERS] += 1
                marks.append(FLAG_DIFFERS)
            for mark in marks:
                row['ids'][mark]['pending' if _pending(app) else 'decided'].append(app.id)
                row['statuses'][mark][app.status] += 1
        out[cohort.id] = row
    return out


class Command(BaseCommand):
    help = 'Compare the shortlisting gate with the criteria tree, per intake (read-only).'

    def add_arguments(self, parser):
        parser.add_argument('--cohort', action='append', default=[], help='Intake code (repeatable).')
        parser.add_argument('--plain', action='store_true',
                            help='Keep an SPM group with no bar beside a PNGK floor (CGPA trap left on).')

    def handle(self, *args, **opts):
        with transaction.atomic():
            if connection.vendor == 'postgresql':
                with connection.cursor() as cur:
                    cur.execute('SET TRANSACTION READ ONLY')
            result = replay(opts['cohort'] or None, plain=opts['plain'])
            transaction.set_rollback(True)
        totals, flags, refused = Counter(), Counter(), 0
        for cid, row in result.items():
            totals.update(row['classes'])
            flags.update(row['flags'])
            parts = ', '.join(f'{k}={v}' for k, v in sorted(row['classes'].items())) or 'no applications'
            self.stdout.write(f'cohort {cid} ({row["code"]}): total={row["total"]}; {parts}')
            if row['refused']:
                refused += 1
                self.stdout.write(f'  TREE REFUSED by validate: {"; ".join(row["refused"])}')
            for cls in sorted(row['ids']):
                ids = row['ids'][cls]
                st = ', '.join(f'{s}={n}' for s, n in sorted(row['statuses'][cls].items()))
                self.stdout.write(f'  {cls}: pending (submitted, undecided)={len(ids["pending"])}, '
                                  f'decided={len(ids["decided"])} [{st}]')
                for when in ('pending', 'decided'):
                    if ids[when]:
                        self.stdout.write(f'    {when}: {", ".join(str(i) for i in ids[when])}')
        summary = ', '.join(f'{k}={v}' for k, v in sorted(totals.items())) or 'nothing to compare'
        self.stdout.write(f'TOTAL: {summary}; {FLAG_DIFFERS}={flags[FLAG_DIFFERS]}; trees_refused={refused}')
        bad = sum(n for k, n in totals.items() if k not in EXPECTED) + flags[FLAG_DIFFERS] + refused
        self.stdout.write('RESULT: ' + ('only expected classes' if not bad else f'{bad} need a look'))
