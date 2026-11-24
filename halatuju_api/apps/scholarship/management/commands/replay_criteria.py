"""READ-ONLY: today's gate (`shortlisting.evaluate`) against the criteria tree, per intake.

Criteria editor Sprint 1 (2026-11-25). For every application with an intake, both engines judge
the same live profile; the tree is `criteria.tree_for_migration(cohort)` - what Sprint 2 will store
(`--plain`: `from_legacy` alone, no degree-intake exception). Prints, per intake, how many agree
and the differences grouped into classes. The owner's rulings allow exactly two:

  a_post_spm_below_floor_passes_spm  a post-SPM holder below the PNGK / CGPA floor who meets the
                                     SPM group ('any' is a real any)  - old reject, new pass
  b_spm_only_spm_group_off           an SPM-only student on an intake whose SPM group is OFF
                                     (the degree intake)               - old pass, new reject

Anything else is printed as `unexpected` (or `reason_only` when only the wording moved) and is a
bug in the engine until shown otherwise.

⚠ PRIVACY: prints intake ids / codes, counts and application ids ONLY - never a name, NRIC,
phone, email, grade or income figure.

⚠ WRITES NOTHING: the whole run sits in one transaction that is marked READ ONLY on PostgreSQL
(transaction-scoped, never session-level - safe through the pooler) and is rolled back at the end.

    python manage.py replay_criteria                 # every application, migration trees
    python manage.py replay_criteria --cohort CODE   # one intake (repeatable)
    python manage.py replay_criteria --plain         # from_legacy only
"""
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from apps.courses import public as courses_public
from apps.scholarship import criteria, shortlisting
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

CLASS_A = 'a_post_spm_below_floor_passes_spm'
CLASS_B = 'b_spm_only_spm_group_off'
REASON_ONLY = 'reason_only'
UNEXPECTED = 'unexpected'


def _groups(tree):
    sec = criteria.section(tree, 'results')
    if not sec:
        return {}
    _, groups = criteria._mode(sec)
    return {g['route']: g['all'] for g in groups}


def classify(application, old, new, tree):
    """'same', or the difference class of one application (see the module docstring)."""
    if (old.verdict, old.bucket, old.reason, old.category) == (new.verdict, new.bucket, new.reason, new.category):
        return 'same'
    profile = getattr(application, 'profile', None)
    held = criteria._held(profile)
    groups = _groups(tree)
    tertiary = courses_public.is_tertiary(held)
    if (tertiary and old.category == 'merit' and new.category != 'merit'
            and 'post_spm' in groups and 'spm' in groups
            and criteria._spm_group(profile, held, groups['spm'])[0]):
        return CLASS_A
    if (not tertiary and 'spm' not in groups and 'post_spm' in groups and old.category != 'merit'
            and new.category == 'merit' and new.reason.startswith('academic floor: no post-SPM results')):
        return CLASS_B
    if (old.verdict, old.category) == (new.verdict, new.category):
        return REASON_ONLY
    return UNEXPECTED


def replay(cohort_codes=None, plain=False):
    """``{cohort_id: {'code', 'total', 'classes': Counter, 'ids': {class: [ids]}}}``. Pure reads."""
    cohorts = ScholarshipCohort.objects.all().order_by('id')
    if cohort_codes:
        cohorts = cohorts.filter(code__in=cohort_codes)
    out = {}
    for cohort in cohorts:
        tree = criteria.from_legacy(cohort) if plain else criteria.tree_for_migration(cohort)
        row = {'code': cohort.code, 'total': 0, 'classes': Counter(), 'ids': defaultdict(list)}
        apps = (ScholarshipApplication.objects.filter(cohort=cohort)
                .select_related('profile').order_by('id'))
        for app in apps:
            old = shortlisting.evaluate(app, cohort)
            new = criteria.evaluate(app, tree)
            cls = classify(app, old, new, tree)
            row['total'] += 1
            row['classes'][cls] += 1
            if cls != 'same':
                row['ids'][cls].append(app.id)
        out[cohort.id] = row
    return out


class Command(BaseCommand):
    help = 'Compare the shortlisting gate with the criteria tree, per intake (read-only).'

    def add_arguments(self, parser):
        parser.add_argument('--cohort', action='append', default=[], help='Intake code (repeatable).')
        parser.add_argument('--plain', action='store_true',
                            help='Use from_legacy alone (no degree-intake exception).')

    def handle(self, *args, **opts):
        with transaction.atomic():
            if connection.vendor == 'postgresql':
                with connection.cursor() as cur:
                    cur.execute('SET TRANSACTION READ ONLY')
            result = replay(opts['cohort'] or None, plain=opts['plain'])
            transaction.set_rollback(True)
        totals = Counter()
        for cid, row in result.items():
            totals.update(row['classes'])
            parts = ', '.join(f'{k}={v}' for k, v in sorted(row['classes'].items())) or 'no applications'
            self.stdout.write(f'cohort {cid} ({row["code"]}): total={row["total"]}; {parts}')
            for cls, ids in sorted(row['ids'].items()):
                self.stdout.write(f'  {cls}: {", ".join(str(i) for i in ids)}')
        summary = ', '.join(f'{k}={v}' for k, v in sorted(totals.items())) or 'nothing to compare'
        self.stdout.write(f'TOTAL: {summary}')
        bad = totals[UNEXPECTED] + totals[REASON_ONLY]
        self.stdout.write('RESULT: ' + ('only expected classes' if not bad else f'{bad} need a look'))
