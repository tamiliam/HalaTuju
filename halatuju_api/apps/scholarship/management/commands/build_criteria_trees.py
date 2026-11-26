"""Store each intake's criteria tree (criteria editor Sprint 2, migration 0219's fill step).

For every intake whose `criteria` is NULL, stores `criteria.from_legacy(cohort)`, which then becomes
the stored source of truth. ⚠ THIS IS THE STEP THAT CHANGES OUTCOMES on the CGPA-trap shape (a PNGK
floor and no SPM bar - intake 5, bpb-deg-dip-2026): while NULL the gate reads today's meaning
(`criteria.tree_of`, the trap left on); the stored tree switches the SPM group OFF (owner ruling
2026-11-25), so an SPM-only student there moves from pass to refused. Every other live intake keeps
its outcomes. Run `replay_criteria` first: it judges NULL rows with the tree this command would store.
Already-scored decisions are HELD by `rescore_pending_decisions` (owner ruling 6). An intake that
already has a tree is never touched. If any tree fails `criteria.validate_tree`, nothing is written
and the intakes are named (id and code only).

DRY RUN BY DEFAULT: lists what it would store. ``--apply`` writes, in one transaction with every
intake row locked (``select_for_update``, TD-774), only with the owner's yes (production data). Prints intake ids and codes only.

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
                rows = ScholarshipCohort.objects.order_by('id')
                if opts['apply']:
                    # TD-774: lock every intake row for the whole read-build-write, so an admin
                    # requirement save cannot commit new columns between our read and our write
                    # (it waits for this transaction). Still open: a save that READ the row before
                    # the lock and writes after it (the admin form takes no lock) - see TD-774.
                    rows = rows.select_for_update()
                done = criteria.build_trees(list(rows), save)
        except ValueError as e:
            raise CommandError(str(e)) from e
        verb = 'stored' if opts['apply'] else 'would store'
        for cid, code in done:
            self.stdout.write(f'{verb}: {cid} {code}')
        self.stdout.write(f'{verb} {len(done)} tree(s)' + ('' if opts['apply'] else ' (dry run; --apply to write)'))
