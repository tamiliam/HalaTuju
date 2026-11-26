"""READ-ONLY: the old columns gate (`shortlisting.evaluate_columns`) against the criteria tree, per
intake: the STORED tree, or - while it is NULL - the tree `build_criteria_trees --apply` WOULD store
(`criteria.from_legacy`). A NULL row's live gate (`criteria.tree_of`) is today's gate exactly, so the
run shows what --apply would change, not what the gate does today.

Criteria editor Sprint 1 (2026-11-25), extended in Sprint 2 (2026-11-26). For every application with
an intake, both engines judge the same live profile. Each intake line says where its tree came from
(`tree=stored` / `tree=columns`); a stored tree that is not exactly `from_legacy(cohort)` is listed
as STORED TREE DIFFERS FROM COLUMNS and needs a look (until the editor exists, only the migration
and the old form write trees, and both write `from_legacy`). `--plain` compares against the columns'
tree with an SPM group kept beside a PNGK floor (the CGPA trap left ON). Prints, per intake, how
many agree and the differences grouped into classes, each split into PENDING (submitted, decision
not released: what `rescore_pending_decisions` would re-score, but HOLDS - owner ruling 6) and
DECIDED, with a count per status. The owner's rulings allow exactly these (Sprint 2: results are
judged 'own', so a post-SPM holder is never passed by the SPM group - owner ruling B for intakes 3
and 4 - and Sprint 1's classes a1 / a2 no longer exist; any such pass is `unexpected`):

  b_spm_only_spm_group_off             an SPM-only student on an intake whose SPM group is OFF
                                       (a floor with no SPM bar: the degree intake) - old pass, new reject
  b2_spm_only_still_refused_new_reason the same intake shape, but today ALREADY refuses the student
                                       on the SPM bars (a merit stored as 0 and no merit point
                                       available); still refused for merit, the reason now names
                                       the missing post-SPM result. No live intake has this shape.

Anything else is `unexpected` (or `reason_only` when only the wording moved) and is a bug in
the engine until shown otherwise. The course-start flag is compared too (`start_year.reading`
against the tree's flag); a differing flag needs a look. Every intake's tree (stored, or the one
--apply would store) is also put through `criteria.validate_tree`; a refused tree (a wrong-case birth state, junk-only start years)
is listed by id and code and needs a look.

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

CLASS_B = 'b_spm_only_spm_group_off'
CLASS_B2 = 'b2_spm_only_still_refused_new_reason'
REASON_ONLY = 'reason_only'
UNEXPECTED = 'unexpected'
EXPECTED = {'same', CLASS_B, CLASS_B2}
FLAG_DIFFERS = 'start_year_flag_differs'
STORED_DIFFERS = 'STORED TREE DIFFERS FROM COLUMNS'


def _groups(tree):
    sec = criteria.section(tree, 'results')
    if not sec:
        return {}
    _, groups = criteria._mode(sec)
    return {g['route']: g['all'] for g in groups}


def classify_replay(application, cohort, old, new, tree):
    """'same', or the difference class of one application (see the module docstring). ``old`` is
    the columns gate's result, ``new`` the tree's. Class (b) is read from the tree's shape and the
    student's results, never from the new engine's say-so alone."""
    if (old.verdict, old.bucket, old.reason, old.category) == (new.verdict, new.bucket, new.reason, new.category):
        return 'same'
    profile = getattr(application, 'profile', None)
    tertiary = courses_public.is_tertiary(criteria._held(profile))
    groups = _groups(tree)
    floor_set = getattr(cohort, 'min_stpm_pngk', None) is not None
    if (not tertiary and floor_set and 'spm' not in groups and 'post_spm' in groups
            and new.category == 'merit' and new.reason.startswith('academic floor: no post-SPM results')):
        if old.category != 'merit':
            return CLASS_B
        if (old.verdict == 'rejected' and old.reason.startswith('academic floor: ')
                and 'merit point not available' in old.reason):
            return CLASS_B2
    if (old.verdict, old.category) == (new.verdict, new.category):
        return REASON_ONLY
    return UNEXPECTED


def _pending(app):
    return app.status == 'submitted' and app.decision_released_at is None


def replay(cohort_codes=None, plain=False):
    """``{cohort_id: {'code', 'total', 'source', 'stored_differs', 'classes': Counter, 'flags': Counter,
    'refused': [problems], 'ids': {class: {'pending'|'decided': [ids]}}, 'statuses': {class: Counter}}}``.
    Pure reads. ``source`` is 'stored' or 'columns' (`criteria.tree_of`); ``stored_differs`` is True when
    a stored tree is not `from_legacy(cohort)`. ``refused`` is `validate_tree` of the stored tree, or of
    `from_legacy(cohort)` while NULL (what --apply would store), whatever ``plain`` says. An unknown
    intake code raises CommandError."""
    cohorts = ScholarshipCohort.objects.all().order_by('id')
    if cohort_codes:
        cohorts = cohorts.filter(code__in=cohort_codes)
        missing = sorted(set(cohort_codes) - set(cohorts.values_list('code', flat=True)))
        if missing:
            raise CommandError(f'unknown intake code(s): {", ".join(missing)}')
    out = {}
    for cohort in cohorts:
        stored = getattr(cohort, 'criteria', None)
        # The tree to judge: the STORED one, or - while NULL - the one `build_criteria_trees --apply`
        # WOULD store (`from_legacy`), so the run shows what --apply changes. NOT `tree_of`'s NULL
        # fallback: that is today's gate exactly (keep_empty_spm) and `validate_tree` refuses it.
        target = stored if isinstance(stored, dict) else criteria.from_legacy(cohort)
        tree = criteria.from_legacy(cohort, keep_empty_spm=True) if plain else target
        row = {'code': cohort.code, 'total': 0, 'classes': Counter(), 'flags': Counter(),
               'source': 'stored' if stored is not None else 'columns',
               'stored_differs': stored is not None and stored != criteria.from_legacy(cohort),
               'refused': criteria.validate_tree(target),
               'ids': defaultdict(lambda: {'pending': [], 'decided': []}), 'statuses': defaultdict(Counter)}
        apps = (ScholarshipApplication.objects.filter(cohort=cohort)
                .select_related('profile', 'cohort').order_by('id'))
        for app in apps:
            cls = classify_replay(app, cohort, shortlisting.evaluate_columns(app, cohort), criteria.evaluate(app, tree), tree)
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
        totals, flags, refused, differs = Counter(), Counter(), 0, 0
        for cid, row in result.items():
            totals.update(row['classes'])
            flags.update(row['flags'])
            parts = ', '.join(f'{k}={v}' for k, v in sorted(row['classes'].items())) or 'no applications'
            self.stdout.write(f'cohort {cid} ({row["code"]}): tree={row["source"]}; total={row["total"]}; {parts}')
            if row['stored_differs']:
                differs += 1
                self.stdout.write(f'  {STORED_DIFFERS}')
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
        self.stdout.write(f'TOTAL: {summary}; {FLAG_DIFFERS}={flags[FLAG_DIFFERS]}; trees_refused={refused}; '
                          f'stored_trees_differ={differs}')
        bad = sum(n for k, n in totals.items() if k not in EXPECTED) + flags[FLAG_DIFFERS] + refused + differs
        self.stdout.write('RESULT: ' + ('only expected classes' if not bad else f'{bad} need a look'))
