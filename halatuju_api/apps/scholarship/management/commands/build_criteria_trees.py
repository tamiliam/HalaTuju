"""Store each intake's criteria tree (criteria editor Sprint 2, migration 0219's fill step).

For every intake whose `criteria` is NULL, stores `criteria.from_legacy(cohort)` - the tree the gate
already reads for it at run time (`criteria.tree_of`), so NO OUTCOME CHANGES: the tree only becomes
the stored source of truth. An intake that already has a tree is never touched. If any tree fails
`criteria.validate_tree`, nothing is written and the intakes are named (id and code only).

DRY RUN BY DEFAULT: lists what it would store. ``--apply`` writes, in one transaction, only with the
owner's yes (production data). Prints intake ids and codes only.

    python manage.py build_criteria_trees            # dry run
    python manage.py build_criteria_trees --apply
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.scholarship import criteria
from apps.scholarship.models import ScholarshipCohort


class Command(BaseCommand):
    help = "Store each intake's criteria tree built from its requirement columns (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the trees (one transaction).')

    def handle(self, *args, **opts):
        def save(c, tree):
            if opts['apply']:
                ScholarshipCohort.objects.filter(pk=c.pk, criteria__isnull=True).update(criteria=tree)

        try:
            with transaction.atomic():
                done = criteria.build_trees(list(ScholarshipCohort.objects.order_by('id')), save)
        except ValueError as e:
            raise CommandError(str(e)) from e
        verb = 'stored' if opts['apply'] else 'would store'
        for cid, code in done:
            self.stdout.write(f'{verb}: {cid} {code}')
        self.stdout.write(f'{verb} {len(done)} tree(s)' + ('' if opts['apply'] else ' (dry run; --apply to write)'))
